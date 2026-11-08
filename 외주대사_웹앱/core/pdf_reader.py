"""명세서 PDF → 페이지 이미지 → AI 판독(JSON) → 행 단위 표.

판독 결과 페이지 형식(AI 출력, 판독 파일 JSON 공통):
{page, supplier_name, period_text, doc_no, rows:[{row_no, date, po_no, part_no, part_name, qty,
 unit_price, amount, tax, is_return, is_corrected, correction_note, remark, y_center_pct}],
 printed_supply_total, printed_tax_total, notes}
"""
import base64
import io
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import pymupdf
from PIL import Image, ImageDraw

from .normalize import find_year, normalize_part, parse_date, part_key, to_number

# ---------------------------------------------------------------- PDF → 이미지

def page_count(pdf_bytes: bytes) -> int:
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        return doc.page_count


def render_page(pdf_bytes: bytes, page_no: int, long_edge: int = 1600) -> bytes:
    """page_no 는 1부터. 긴 변이 long_edge 픽셀이 되도록 PNG 로 렌더링."""
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        page = doc[page_no - 1]
        zoom = long_edge / max(page.rect.width, page.rect.height)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        return pix.tobytes("png")


def detect_row_bands(pdf_bytes: bytes, page_no: int, min_rows: int = 1) -> list[tuple[float, float]]:
    """표의 가로 괘선을 찾아 데이터 행 영역(위·아래, 페이지 높이 대비 0~1) 목록을 돌려준다.

    가장 길게 이어진 '행 높이 괘선 묶음'을 표로 보고, 첫 칸(머리글)은 제외한다.
    괘선이 흐려 min_rows 개보다 적게 찾으면 밝기 기준을 낮춰 다시 찾는다.
    """
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        page = doc[page_no - 1]
        zoom = 1000 / max(page.rect.width, page.rect.height)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY)
    h, w = pix.height, pix.width
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(h, pix.stride)[:, :w]
    best: list = []
    for offset in (18, 12, 8):
        found = _row_bands_from_lines(_horizontal_lines(arr, offset), h)
        if len(found) > len(best):
            best = found
        if len(best) >= min_rows:
            break
    return best


def _row_bands_from_lines(lines: list[float], h: int) -> list[tuple[float, float]]:
    if len(lines) < 3:
        return []
    bands = [(lines[i], lines[i + 1]) for i in range(len(lines) - 1)]
    ok = [0.012 * h < (b - a) < 0.08 * h for a, b in bands]
    best, cur = [], []
    for band, good in zip(bands, ok):
        if good:
            cur.append(band)
        else:
            best, cur = (cur if len(cur) > len(best) else best), []
    best = cur if len(cur) > len(best) else best
    if len(best) < 2:
        return []
    return [(a / h, b / h) for a, b in best[1:]]


def _longest_run(row: np.ndarray) -> int:
    if not row.any():
        return 0
    d = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
    return int((np.where(d == -1)[0] - np.where(d == 1)[0]).max())


def _horizontal_lines(arr: np.ndarray, offset: float = 18) -> list[float]:
    """그레이 이미지에서 가로 괘선의 세로 위치(픽셀) 목록."""
    h, w = arr.shape
    # 스캔본 괘선은 흐린 회색이라 고정 임계값 대신 종이 배경 밝기 기준으로 판단
    dark = (arr < (float(np.median(arr)) - offset)).astype(np.int32)
    # 가로로 L 픽셀 이상 이어진 어두운 구간만 '선 픽셀'로 본다 (글자 획은 짧다)
    L = max(8, int(0.03 * w))
    cs = np.concatenate([np.zeros((h, 1), np.int32), np.cumsum(dark, axis=1)], axis=1)
    full = (cs[:, L:] - cs[:, :-L]) == L                      # x..x+L-1 전부 어두움
    fs = np.concatenate([np.zeros((h, 1), np.int32), np.cumsum(full, axis=1)], axis=1)
    idx = np.arange(w)
    lo, hi = np.clip(idx - L + 1, 0, full.shape[1]), np.clip(idx + 1, 0, full.shape[1])
    line_px = (fs[:, hi] - fs[:, lo]) > 0                     # 그런 구간에 덮이는 픽셀
    # 기울어진 스캔 대비: 위아래 2픽셀 안에 선 픽셀이 있으면 그 열은 선이 지나간 것으로 본다
    band = line_px.copy()
    for s in (1, 2):
        band[s:] |= line_px[:-s]
        band[:-s] |= line_px[s:]
    # 나란히 놓인 두 상자의 밑선이 합쳐 보이지 않도록 '끊기지 않고 이어진 길이'로 판단
    frac = np.array([_longest_run(band[y]) for y in range(h)]) / w
    is_line = frac >= 0.5
    lines, y = [], 0
    while y < h:
        if is_line[y]:
            y0 = y
            while y < h and is_line[y]:
                y += 1
            if y - y0 > 0.012 * h:
                # 음영을 칠한 머리글처럼 두꺼운 덩어리는 위·아래 가장자리를 각각 선으로 본다
                lines += [float(y0), float(y - 1)]
            else:
                lines.append(y0 + float(np.argmax(frac[y0:y])))
            continue
        y += 1
    # 너무 가까운 선(이중선 등)은 하나로
    merged = []
    for v in lines:
        if merged and v - merged[-1] < 0.008 * h:
            merged[-1] = (merged[-1] + v) / 2
        else:
            merged.append(v)
    return merged


def highlight_page(png: bytes, bands: list[tuple[float, float]], label: str = "") -> bytes:
    """페이지 이미지에 강조 띠(반투명 빨강)를 그린다."""
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    W, H = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for top, bottom in bands:
        y0, y1 = int(top * H), int(bottom * H)
        draw.rectangle([int(0.02 * W), y0, int(0.98 * W), y1], fill=(255, 40, 40, 55),
                       outline=(220, 0, 0, 255), width=3)
    out = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- AI 판독

_ROW_SCHEMA = {
    "type": "object",
    "properties": {
        "row_no": {"type": "integer", "description": "표의 No/순번 열 값. 번호 열이 없으면 0"},
        "date": {"type": "string", "description": "납품일자를 인쇄된 그대로 (예 2026-09-01, 09/02, 2026.09.01). 월·일이 분리된 양식은 'M/D'"},
        "po_no": {"type": "string", "description": "발주번호. 없으면 빈 문자열"},
        "part_no": {"type": "string", "description": "품번/품목코드/도면번호"},
        "part_name": {"type": "string"},
        "qty": {"type": "number", "description": "수량. 반품(△)은 음수. 정정 표기가 있으면 정정 후 값"},
        "unit_price": {"type": "number"},
        "amount": {"type": "number", "description": "공급가액. 반품은 음수"},
        "tax": {"anyOf": [{"type": "number"}, {"type": "null"}], "description": "행 세액. 열이 없으면 null"},
        "is_return": {"type": "boolean", "description": "△ 등 반품(차감) 표시 여부"},
        "is_corrected": {"type": "boolean", "description": "손글씨 정정·취소선 등 고친 흔적 여부"},
        "correction_note": {"type": "string", "description": "정정 내용 (예 '수량 62→60'). 없으면 빈 문자열"},
        "remark": {"type": "string", "description": "비고 열 내용 및 품명 아래 작은 메모"},
        "y_center_pct": {"type": "number", "description": "이 행의 세로 중심 위치, 페이지 높이 대비 0~100"},
    },
    "required": ["row_no", "date", "po_no", "part_no", "part_name", "qty", "unit_price", "amount", "tax",
                 "is_return", "is_corrected", "correction_note", "remark", "y_center_pct"],
    "additionalProperties": False,
}

PAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "supplier_name": {"type": "string", "description": "공급자 상호"},
        "period_text": {"type": "string", "description": "거래기간/○월분/납품일자 등 기간 표기 그대로"},
        "doc_no": {"type": "string", "description": "명세서 번호. 없으면 빈 문자열"},
        "rows": {"type": "array", "items": _ROW_SCHEMA},
        "printed_supply_total": {"anyOf": [{"type": "number"}, {"type": "null"}],
                                 "description": "이 페이지에 인쇄된 공급가액 합계. 이 페이지에 합계가 없으면 null"},
        "printed_tax_total": {"anyOf": [{"type": "number"}, {"type": "null"}]},
        "notes": {"type": "string", "description": "판독이 불확실한 칸, 특이사항. 없으면 빈 문자열"},
    },
    "required": ["supplier_name", "period_text", "doc_no", "rows", "printed_supply_total",
                 "printed_tax_total", "notes"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """당신은 한국 제조업체 구매팀의 거래명세서 판독 담당입니다. 스캔된 거래명세서 페이지 이미지 1장을 받아, 표의 품목 행을 빠짐없이 정확히 옮겨 적습니다. 판독 결과는 ERP 입고 이력과 1원 단위로 대사되므로 숫자 한 자리도 추측하지 말고 이미지에 보이는 그대로 적으세요.

규칙
- 품목이 적힌 행만 rows 에 넣습니다. 빈 행, 머리글, 합계 행은 넣지 않습니다. 위에서 아래 순서를 지킵니다.
- 숫자의 천 단위 쉼표는 빼고 숫자로 적습니다.
- 수량 앞에 △(또는 ▲, -) 가 있으면 반품(차감)입니다: is_return=true, 수량·공급가액·세액을 음수로 적습니다.
- 손글씨로 숫자를 지우고 고쳐 쓴 흔적(취소선, 덧쓰기)이 있으면 고친 뒤 값을 적고 is_corrected=true, correction_note 에 '항목 이전값→새값'을 적습니다.
- printed_supply_total 은 이 페이지에 인쇄된 '공급가액 합계'입니다. 여러 장짜리 명세서의 앞장처럼 이 페이지에 합계가 없으면 null 입니다.
- y_center_pct 는 행의 세로 중심 위치를 페이지 전체 높이 대비 % 로 어림합니다.
- 흐리거나 확신이 없는 칸은 가장 그럴듯한 값을 적고 notes 에 행 번호와 칸 이름을 남깁니다."""


def make_client(api_key: str | None = None):
    import anthropic
    return anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()


def read_page_ai(client, png: bytes, *, model: str, effort: str, filename: str, page_no: int,
                 total_pages: int, vendor_hint: str = "") -> dict:
    """페이지 이미지 1장을 Claude 로 판독해 페이지 dict 를 돌려준다."""
    text = f"파일: {filename} ({page_no}/{total_pages} 페이지)"
    if vendor_hint:
        text += f"\n이 업체 양식의 특징: {vendor_hint}"
    text += "\n이 페이지의 거래명세서를 판독해 주세요."
    with client.beta.messages.stream(
        model=model,
        max_tokens=32000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        thinking={"type": "adaptive"},
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": PAGE_SCHEMA}},
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                             "data": base64.standard_b64encode(png).decode("ascii")}},
                {"type": "text", "text": text},
            ],
        }],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"{filename} {page_no}페이지: AI가 판독을 거절했습니다")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError(f"{filename} {page_no}페이지: 응답이 길이 제한에 걸려 잘렸습니다")
    body = next(b.text for b in msg.content if b.type == "text")
    data = json.loads(body)
    data["page"] = page_no
    return data


def read_pdf_ai(client, pdf_bytes: bytes, filename: str, *, model: str, effort: str,
                vendor_hint: str = "", workers: int = 4, on_page_done=None) -> list[dict]:
    """PDF 전 페이지를 병렬로 판독. 실패한 페이지는 error 키가 있는 빈 페이지로 남긴다."""
    n = page_count(pdf_bytes)
    pages: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(read_page_ai, client, render_page(pdf_bytes, p), model=model, effort=effort,
                      filename=filename, page_no=p, total_pages=n, vendor_hint=vendor_hint): p
            for p in range(1, n + 1)
        }
        for fut in as_completed(futs):
            p = futs[fut]
            try:
                pages[p] = fut.result()
            except Exception as e:  # 한 페이지 실패가 전체를 멈추지 않게
                pages[p] = {"page": p, "supplier_name": "", "period_text": "", "doc_no": "", "rows": [],
                            "printed_supply_total": None, "printed_tax_total": None, "notes": "",
                            "error": f"{type(e).__name__}: {e}"}
            if on_page_done:
                on_page_done(filename, p, n)
    return [pages[p] for p in sorted(pages)]


# ---------------------------------------------------------------- JSON → 표

ROW_COLUMNS = ["업체코드", "업체", "파일", "페이지", "행번호", "페이지내순서", "일자", "원본일자", "발주번호",
               "품번", "품명", "수량", "단가", "공급가액", "세액", "반품", "정정", "정정내용", "비고", "위치y"]
PAGE_COLUMNS = ["파일", "페이지", "업체코드", "공급자상호", "기간표기", "명세서번호", "인쇄공급가액합계",
                "인쇄세액합계", "판독메모", "오류"]


def pages_to_frames(filename: str, vendor_code: str, vendor_name: str, pages: list[dict],
                    default_year: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """페이지 dict 목록 → (행 표, 페이지 정보 표). 일자 정규화·반품 부호·행번호 보충을 한다."""
    year = None
    for p in pages:
        year = year or find_year(p.get("period_text"))
    year = year or default_year

    rows, infos, seq = [], [], 0
    for p in sorted(pages, key=lambda x: x.get("page", 0)):
        pno = int(p.get("page", 0))
        infos.append({
            "파일": filename, "페이지": pno, "업체코드": vendor_code,
            "공급자상호": p.get("supplier_name", ""), "기간표기": p.get("period_text", ""),
            "명세서번호": p.get("doc_no", ""),
            "인쇄공급가액합계": to_number(p.get("printed_supply_total")),
            "인쇄세액합계": to_number(p.get("printed_tax_total")),
            "판독메모": p.get("notes", ""), "오류": p.get("error", ""),
        })
        for i, r in enumerate(p.get("rows", [])):
            seq += 1
            qty, price = to_number(r.get("qty")), to_number(r.get("unit_price"))
            amt, tax = to_number(r.get("amount")), to_number(r.get("tax"))
            ret = bool(r.get("is_return")) or (qty is not None and qty < 0) or (amt is not None and amt < 0)
            if ret:
                qty = -abs(qty) if qty is not None else qty
                amt = -abs(amt) if amt is not None else amt
                tax = -abs(tax) if tax is not None else tax
            iso, _ = parse_date(r.get("date"), year)
            row_no = to_number(r.get("row_no")) or 0
            y = to_number(r.get("y_center_pct"))
            rows.append({
                "업체코드": vendor_code, "업체": vendor_name, "파일": filename, "페이지": pno,
                "행번호": int(row_no) if row_no and row_no > 0 else seq, "페이지내순서": i,
                "일자": iso, "원본일자": str(r.get("date", "")),
                "발주번호": str(r.get("po_no", "") or "").strip(),
                "품번": normalize_part(r.get("part_no")), "품명": str(r.get("part_name", "") or ""),
                "수량": qty, "단가": price, "공급가액": amt, "세액": tax, "반품": ret,
                "정정": bool(r.get("is_corrected")), "정정내용": str(r.get("correction_note", "") or ""),
                "비고": str(r.get("remark", "") or ""), "위치y": y / 100 if y is not None else None,
            })
    return pd.DataFrame(rows, columns=ROW_COLUMNS), pd.DataFrame(infos, columns=PAGE_COLUMNS)


def finalize_rows(rows: pd.DataFrame) -> pd.DataFrame:
    """편집 후에도 다시 부르는 공통 후처리: 품번 키, 행 ID."""
    rows = rows.copy().reset_index(drop=True)
    rows["품번"] = rows["품번"].map(normalize_part)
    rows["품번키"] = rows["품번"].map(part_key)
    rows["stmt_id"] = range(len(rows))
    return rows


def load_reading_json(data: bytes | str) -> dict[str, list[dict]]:
    """판독 파일(JSON) → {파일명: 페이지 목록}."""
    obj = json.loads(data)
    if obj.get("kind") != "pages" or "files" not in obj:
        raise ValueError("판독 파일 형식이 아닙니다 (kind='pages', files 항목 필요)")
    return obj["files"]


def dump_reading_json(files: dict[str, list[dict]]) -> bytes:
    return json.dumps({"version": 1, "kind": "pages", "files": files}, ensure_ascii=False,
                      indent=1).encode("utf-8")


def rows_to_pages(rows: pd.DataFrame, page_info: pd.DataFrame) -> dict[str, list[dict]]:
    """(수정된) 행 표를 판독 파일 형식으로 되돌린다 — 수정 결과를 내려받아 다음에 다시 쓰기 위함."""
    files: dict[str, list[dict]] = {}
    for _, pi in page_info.sort_values(["파일", "페이지"]).iterrows():
        sub = rows[(rows["파일"] == pi["파일"]) & (rows["페이지"] == pi["페이지"])].sort_values("페이지내순서")
        files.setdefault(pi["파일"], []).append({
            "page": int(pi["페이지"]), "supplier_name": pi["공급자상호"], "period_text": pi["기간표기"],
            "doc_no": pi["명세서번호"], "notes": pi["판독메모"],
            "printed_supply_total": _num(pi["인쇄공급가액합계"]), "printed_tax_total": _num(pi["인쇄세액합계"]),
            "rows": [{
                "row_no": int(r["행번호"]), "date": r["일자"] or r["원본일자"], "po_no": r["발주번호"],
                "part_no": r["품번"], "part_name": r["품명"], "qty": _num(r["수량"]),
                "unit_price": _num(r["단가"]), "amount": _num(r["공급가액"]), "tax": _num(r["세액"]),
                "is_return": bool(r["반품"]), "is_corrected": bool(r["정정"]),
                "correction_note": r["정정내용"], "remark": r["비고"],
                "y_center_pct": None if pd.isna(r["위치y"]) else float(r["위치y"]) * 100,
            } for _, r in sub.iterrows()],
        })
    return files


def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return to_number(v.item() if hasattr(v, "item") else v)
    except Exception:
        return to_number(str(v))

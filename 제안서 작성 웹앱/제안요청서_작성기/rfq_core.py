"""제안요청서 작성기 — 읽기·매칭·워드 생성 로직 (화면과 분리)."""
import copy
import re
import zipfile
from datetime import date, datetime, timedelta
from io import BytesIO

import pandas as pd
from docx import Document

TARGET_STATUS = "요청서 발송 전"
DELIVERY_PLACE = "천안공장 자재창고"
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

REQUEST_COLUMNS = ["요청번호", "품목군", "품목", "규격", "수량", "단위", "희망 납기", "상태"]
SUPPLIER_COLUMNS = ["협력사", "품목군", "담당자", "직급"]

# 표 0: 왼쪽 칸 제목 → 대상 행의 키 ("발신"은 채우지 않음)
HEADER_FIELDS = ["요청번호", "요청일", "수신", "수신 담당자", "견적 회신 기한"]
ITEM_FIELDS = ["품목", "규격", "수량", "단위", "희망 납기", "납품 장소"]


class TemplateError(ValueError):
    """양식의 표 구성이 예상과 다를 때."""


class ColumnError(ValueError):
    """엑셀에 필수 열이 없을 때."""

    def __init__(self, filename, missing):
        self.missing = missing
        super().__init__(f"{filename}에 필수 열이 없습니다: {', '.join(missing)}")


# ---------------------------------------------------------------- 값 변환

def _blank(v):
    if v is None:
        return True
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return isinstance(v, str) and not v.strip()


def _text(v):
    if _blank(v):
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def to_date(v):
    """날짜형·엑셀 일련번호·문자열을 date로. 읽을 수 없으면 None."""
    if _blank(v):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if 1 <= v < 2958466:  # 1900-01-01 ~ 9999-12-31
            return date(1899, 12, 30) + timedelta(days=int(v))
        return None
    s = str(v).strip()
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return to_date(float(s))
    m = re.match(r"^(\d{4})[-./년\s]+(\d{1,2})[-./월\s]+(\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def format_date(d):
    return d.strftime("%Y-%m-%d") if d else ""


def format_qty(v):
    """숫자면 천 단위 쉼표, 아니면 원래 글자 그대로."""
    if _blank(v):
        return ""
    num = v
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        try:
            num = float(s)
        except ValueError:
            return v.strip()
    if isinstance(num, bool) or not isinstance(num, (int, float)):
        return str(v).strip()
    if float(num).is_integer():
        return f"{int(num):,}"
    return f"{num:,.10g}" if abs(num) < 1000 else f"{num:,}"


def add_business_days(start, n=3):
    d = start
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:  # 월~금
            n -= 1
    return d


def format_deadline(d, time_text="17:00"):
    return f"{d:%Y-%m-%d}({WEEKDAYS[d.weekday()]}) {time_text}"


# ---------------------------------------------------------------- 엑셀 읽기

def _read_excel(file, filename, required):
    if hasattr(file, "seek"):
        file.seek(0)
    df = pd.read_excel(file, sheet_name=0, dtype=object)
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ColumnError(filename, missing)
    # 완전히 빈 행 제거
    return df.dropna(how="all").reset_index(drop=True)


def load_requests(file):
    """구매요청서 읽기. 필수 열 검사, 날짜 변환."""
    df = _read_excel(file, "구매요청서", REQUEST_COLUMNS)
    df = df[df["요청번호"].map(lambda v: not _blank(v))].reset_index(drop=True)
    df["희망 납기_원본"] = df["희망 납기"]
    df["희망 납기"] = df["희망 납기"].map(to_date)
    if "요청일" in df.columns:
        df["요청일"] = df["요청일"].map(to_date)
    for c in ["요청번호", "품목군", "상태"]:
        df[c] = df[c].map(_text)
    return df


def load_suppliers(file):
    """협력사목록 읽기. 필수 열 검사."""
    df = _read_excel(file, "협력사목록", SUPPLIER_COLUMNS)
    df = df[df["협력사"].map(lambda v: not _blank(v))].reset_index(drop=True)
    for c in df.columns:
        df[c] = df[c].map(_text)
    return df


# ---------------------------------------------------------------- 매칭

def rfq_number(pr_no, supplier):
    base = re.sub(r"^PR-", "", pr_no.strip(), flags=re.IGNORECASE)
    return f"RFQ-{base}-{supplier}"


def build_targets(req, sup):
    """상태 필터 + 품목군 매칭 → (대상 DataFrame, 경고 목록, 정보 목록)."""
    warnings, infos = [], []

    is_target = req["상태"] == TARGET_STATUS
    excluded = req[~is_target]
    if len(excluded):
        detail = ", ".join(f"{r['요청번호']}({r['상태'] or '상태 없음'})" for _, r in excluded.iterrows())
        infos.append(f"상태가 '{TARGET_STATUS}'이 아닌 {len(excluded)}건 제외됨: {detail}")
    targets = req[is_target]

    rows, seen = [], set()
    for _, r in targets.iterrows():
        if r["희망 납기"] is None and not _blank(r["희망 납기_원본"]):
            warnings.append(f"{r['요청번호']}: 희망 납기 '{r['희망 납기_원본']}'을(를) 날짜로 읽을 수 없어 빈칸으로 둡니다.")
        matched = sup[sup["품목군"] == r["품목군"]]
        if matched.empty:
            warnings.append(f"{r['요청번호']}: '{r['품목군']}' 품목군 협력사 없음")
            continue
        for _, s in matched.iterrows():
            key = (r["요청번호"], s["협력사"])
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "포함": True,
                "요청번호": r["요청번호"],
                "RFQ번호": rfq_number(r["요청번호"], s["협력사"]),
                "품목": _text(r["품목"]),
                "규격": _text(r["규격"]),
                "수량": format_qty(r["수량"]),
                "단위": _text(r["단위"]),
                "희망 납기": format_date(r["희망 납기"]),
                "협력사": s["협력사"],
                "담당자": f"{s['담당자']} {s['직급']}".strip(),
                "비고": s.get("비고", ""),
                "전화": s.get("전화", ""),
                "이메일": s.get("이메일", ""),
                "결제 조건": s.get("결제 조건", ""),
                "요청부서": _text(r.get("요청부서")),
                "요청자": _text(r.get("요청자")),
                "용도": _text(r.get("용도")),
            })
    columns = ["포함", "요청번호", "RFQ번호", "품목", "규격", "수량", "단위", "희망 납기",
               "협력사", "담당자", "비고", "전화", "이메일", "결제 조건", "요청부서", "요청자", "용도"]
    return pd.DataFrame(rows, columns=columns), warnings, infos


# ---------------------------------------------------------------- 워드

def _norm(s):
    return re.sub(r"\s+", "", s or "")


def _check_template(doc):
    if len(doc.tables) < 2:
        raise TemplateError("양식의 표 구성이 예상과 다릅니다 (표가 2개 이상 있어야 합니다).")
    t0, t1 = doc.tables[0], doc.tables[1]
    labels = {_norm(row.cells[0].text) for row in t0.rows if len(row.cells) >= 2}
    missing = [f for f in HEADER_FIELDS if _norm(f) not in labels]
    if missing:
        raise TemplateError(f"양식의 표 구성이 예상과 다릅니다 (첫 번째 표에 없는 칸: {', '.join(missing)}).")
    if len(t1.rows) < 2 or len(t1.rows[0].cells) < len(ITEM_FIELDS):
        raise TemplateError("양식의 표 구성이 예상과 다릅니다 (품목 표는 2행 6열이어야 합니다).")
    head = [_norm(c.text) for c in t1.rows[0].cells]
    missing = [f for f in ITEM_FIELDS if _norm(f) not in head]
    if missing:
        raise TemplateError(f"양식의 표 구성이 예상과 다릅니다 (품목 표에 없는 칸: {', '.join(missing)}).")


def validate_template(template_bytes):
    """양식이 쓸 수 있는지 검사. 문제가 있으면 TemplateError."""
    try:
        doc = Document(BytesIO(template_bytes))
    except Exception as e:
        raise TemplateError(f"양식 파일을 열 수 없습니다: {e}") from e
    _check_template(doc)


def _fill_cell(cell, value):
    """셀 첫 문단의 서식을 유지한 채 값을 넣는다.

    양식의 빈 칸에는 서식만 가진 빈 run이 있으므로 마지막 빈 run에 글자를 넣고,
    없으면 마지막 run의 서식을 복사한 새 run을 추가한다.
    """
    para = cell.paragraphs[0]
    runs = para.runs
    if runs and not runs[-1].text:
        runs[-1].text = value
        return
    new_run = para.add_run(value)
    if runs and runs[-1]._r.rPr is not None:
        new_run._r.insert(0, copy.deepcopy(runs[-1]._r.rPr))


def make_rfq_docx(template_bytes, row, req_date, deadline):
    """대상 1건 → .docx 바이트."""
    doc = Document(BytesIO(template_bytes))
    _check_template(doc)

    header_values = {
        "요청번호": row["RFQ번호"],
        "요청일": format_date(req_date),
        "수신": row["협력사"],
        "수신 담당자": row["담당자"],
        "견적 회신 기한": deadline,
    }
    header_map = {_norm(k): v for k, v in header_values.items()}
    for tr in doc.tables[0].rows:
        cells = tr.cells
        if len(cells) < 2:
            continue
        key = _norm(cells[0].text)
        if key in header_map:
            _fill_cell(cells[1], header_map[key])

    item_values = {
        "품목": row["품목"],
        "규격": row["규격"],
        "수량": row["수량"],
        "단위": row["단위"],
        "희망 납기": row["희망 납기"],
        "납품 장소": DELIVERY_PLACE,
    }
    t1 = doc.tables[1]
    head = [_norm(c.text) for c in t1.rows[0].cells]
    value_cells = t1.rows[1].cells
    for name, value in item_values.items():
        _fill_cell(value_cells[head.index(_norm(name))], value)

    out = BytesIO()
    doc.save(out)
    return out.getvalue()


# ---------------------------------------------------------------- 파일

_BAD_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]')


def _safe(s):
    return _BAD_CHARS.sub("", s).strip()


def make_filename(row):
    """RFQ-2610-001_서진금속_SUS304환봉.docx"""
    prefix = row["RFQ번호"]
    suffix = f"-{row['협력사']}"
    if prefix.endswith(suffix):
        prefix = prefix[: -len(suffix)]
    item = re.sub(r"\s+", "", row["품목"])
    return _safe(f"{prefix}_{row['협력사']}_{item}") + ".docx"


def make_zip(files):
    """[(파일명, 바이트)] → ZIP 바이트. 한글 파일명은 UTF-8 플래그로 저장된다."""
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        used = set()
        for name, data in files:
            base, n = name, 2
            while name in used:
                name = base.replace(".docx", f"({n}).docx")
                n += 1
            used.add(name)
            zf.writestr(name, data)
    return out.getvalue()


def zip_filename(req_date):
    return f"제안요청서_{req_date:%Y%m%d}.zip"


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.stdout.reconfigure(encoding="utf-8")
    here = Path(__file__).parent
    req_path = sys.argv[1] if len(sys.argv) > 1 else here.parent / "구매요청서.xlsx"
    req = load_requests(req_path)
    sup = load_suppliers(here / "data" / "협력사목록.xlsx")
    targets, warns, infos = build_targets(req, sup)
    for m in infos + warns:
        print("!", m)
    today = date.today()
    print(f"작성일 {today}, 회신 기한 {format_deadline(add_business_days(today, 3))}")
    for i, r in targets.iterrows():
        print(i + 1, r["RFQ번호"], r["담당자"], r["품목"], r["수량"], r["단위"], r["희망 납기"], r["비고"], make_filename(r), sep=" | ")

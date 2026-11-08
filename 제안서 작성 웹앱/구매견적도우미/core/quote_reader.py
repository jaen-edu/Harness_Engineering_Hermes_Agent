"""견적서 파일 → AI 입력용 변환 (3-1)."""
import base64
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

import openpyxl
import pdfplumber

SUPPORTED = {".xlsx", ".pdf", ".png", ".jpg", ".jpeg"}
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
MIN_PDF_TEXT = 30  # 글자가 이보다 적으면 스캔본으로 보고 원본을 보낸다


class UnsupportedFile(ValueError):
    pass


def _cell_text(v):
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d") if v.time() == datetime.min.time() else v.isoformat(sep=" ")
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def xlsx_to_text(data):
    """모든 시트의 빈 칸이 아닌 셀을 `셀주소: 값` 줄로."""
    wb = openpyxl.load_workbook(BytesIO(data), data_only=True)
    lines = []
    for ws in wb.worksheets:
        lines.append(f"[시트: {ws.title}]")
        for row in ws.iter_rows():
            for c in row:
                if c.value is None or (isinstance(c.value, str) and not c.value.strip()):
                    continue
                lines.append(f"{c.coordinate}: {_cell_text(c.value)}")
    return "\n".join(lines)


def pdf_to_text(data):
    with pdfplumber.open(BytesIO(data)) as pdf:
        pages = [(p.extract_text() or "").strip() for p in pdf.pages]
    return "\n\n".join(f"[{i + 1}쪽]\n{t}" for i, t in enumerate(pages) if t)


def to_ai_input(filename, data):
    """파일 1개 → {"filename", "kind", "blocks", "preview"}.

    kind: "text"(엑셀·글자 PDF) / "document"(스캔 PDF 원본) / "image"
    blocks: Claude 메시지 content에 그대로 넣을 블록 목록
    """
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED:
        raise UnsupportedFile(f"{filename}: 지원하지 않는 파일입니다. PDF로 저장 후 올려 주세요. (xlsx, pdf, png, jpg 가능)")

    if ext == ".xlsx":
        try:
            text = xlsx_to_text(data)
        except Exception as e:
            raise UnsupportedFile(f"{filename}: 엑셀 파일을 열 수 없습니다 ({e}). PDF로 저장 후 올려 주세요.") from e
        return {"filename": filename, "kind": "text", "preview": text,
                "blocks": [{"type": "text", "text": f"<견적서 파일명=\"{filename}\" 형식=\"엑셀 셀 목록\">\n{text}\n</견적서>"}]}

    if ext == ".pdf":
        try:
            text = pdf_to_text(data)
        except Exception as e:
            raise UnsupportedFile(f"{filename}: PDF를 열 수 없습니다 ({e}).") from e
        if len("".join(text.split())) >= MIN_PDF_TEXT:
            return {"filename": filename, "kind": "text", "preview": text,
                    "blocks": [{"type": "text", "text": f"<견적서 파일명=\"{filename}\" 형식=\"PDF 글자\">\n{text}\n</견적서>"}]}
        b64 = base64.standard_b64encode(data).decode("ascii")
        return {"filename": filename, "kind": "document", "preview": "(스캔본 PDF — 원본 그대로 AI에 전달)",
                "blocks": [
                    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}},
                    {"type": "text", "text": f"위 문서는 견적서 파일 \"{filename}\"(스캔본)입니다."},
                ]}

    b64 = base64.standard_b64encode(data).decode("ascii")
    return {"filename": filename, "kind": "image", "preview": "(이미지 — 원본 그대로 AI에 전달)",
            "blocks": [
                {"type": "image", "source": {"type": "base64", "media_type": IMAGE_TYPES[ext], "data": b64}},
                {"type": "text", "text": f"위 이미지는 견적서 파일 \"{filename}\"입니다."},
            ]}

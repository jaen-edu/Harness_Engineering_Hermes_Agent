"""공통 도구 — 값 정리, 날짜 변환, 엑셀 읽기, 협력사명 정리."""
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
DEFAULT_TEMPLATE = DATA_DIR / "제안요청서_양식.docx"
DEFAULT_SUPPLIERS = DATA_DIR / "협력사목록.xlsx"

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

REQUEST_COLUMNS = ["요청번호", "품목군", "품목", "규격", "수량", "단위", "희망 납기", "상태"]
SUPPLIER_COLUMNS = ["협력사", "품목군", "담당자", "직급"]


class ColumnError(ValueError):
    """엑셀에 필수 열이 없을 때."""

    def __init__(self, filename, missing):
        self.missing = missing
        super().__init__(f"{filename}에 필수 열이 없습니다: {', '.join(missing)}")


def is_blank(v):
    if v is None:
        return True
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return isinstance(v, str) and not v.strip()


def to_text(v):
    if is_blank(v):
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def to_date(v):
    """날짜형·엑셀 일련번호·문자열을 date로. 읽을 수 없으면 None."""
    if is_blank(v):
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


def to_number(v):
    """숫자로 바꿀 수 있으면 int/float, 아니면 None."""
    if is_blank(v) or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v) if float(v).is_integer() else float(v)
    s = re.sub(r"[,\s원]", "", str(v))
    try:
        f = float(s)
    except ValueError:
        return None
    return int(f) if f.is_integer() else f


def format_date(d):
    return d.strftime("%Y-%m-%d") if d else ""


def format_won(v):
    return "" if v is None else f"{round(v):,}"


def normalize_supplier(name):
    """㈜·(주)·주식회사·공백을 빼서 협력사 이름을 비교 가능하게 만든다."""
    s = to_text(name)
    s = re.sub(r"㈜|\(주\)|\(株\)|주식회사|\s+", "", s)
    return s


# ---------------------------------------------------------------- 엑셀 읽기

def _read_excel(file, filename, required):
    if hasattr(file, "seek"):
        file.seek(0)
    df = pd.read_excel(file, sheet_name=0, dtype=object)
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ColumnError(filename, missing)
    return df.dropna(how="all").reset_index(drop=True)


def load_requests(file):
    """구매요청서 읽기. 필수 열 검사, 날짜 변환."""
    df = _read_excel(file, "구매요청서", REQUEST_COLUMNS)
    df = df[df["요청번호"].map(lambda v: not is_blank(v))].reset_index(drop=True)
    df["희망 납기_원본"] = df["희망 납기"]
    df["희망 납기"] = df["희망 납기"].map(to_date)
    if "요청일" in df.columns:
        df["요청일"] = df["요청일"].map(to_date)
    for c in ["요청번호", "품목군", "상태"]:
        df[c] = df[c].map(to_text)
    return df


def load_suppliers(file):
    """협력사목록 읽기. 필수 열 검사."""
    df = _read_excel(file, "협력사목록", SUPPLIER_COLUMNS)
    df = df[df["협력사"].map(lambda v: not is_blank(v))].reset_index(drop=True)
    for c in df.columns:
        df[c] = df[c].map(to_text)
    return df


def request_info(req_df, pr_no):
    """구매요청서에서 한 건을 꺼내 분석용 dict로."""
    r = req_df[req_df["요청번호"] == pr_no].iloc[0]
    return {
        "요청번호": r["요청번호"],
        "품목군": r["품목군"],
        "품목": to_text(r["품목"]),
        "규격": to_text(r["규격"]),
        "수량": to_number(r["수량"]),
        "단위": to_text(r["단위"]),
        "희망 납기": r["희망 납기"],
        "용도": to_text(r.get("용도")),
        "요청부서": to_text(r.get("요청부서")),
        "요청자": to_text(r.get("요청자")),
        "상태": r["상태"],
    }

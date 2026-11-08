"""품번·일자·숫자 정규화 공통 함수."""
import math
import re
from datetime import date

_DASHES = "‐‑‒–—―−－"


def normalize_part(s) -> str:
    """표시용 품번: 대문자, 공백 제거, 하이픈 통일."""
    if s is None or (isinstance(s, float) and math.isnan(s)):
        return ""
    s = str(s).strip().upper()
    for d in _DASHES:
        s = s.replace(d, "-")
    s = re.sub(r"\s+", "", s)
    return re.sub(r"-{2,}", "-", s)


def part_key(s) -> str:
    """매칭용 품번 키: 영문·숫자·한글만 남긴다 (공백·하이픈 표기 차이 무시)."""
    return re.sub(r"[^0-9A-Z가-힣]", "", normalize_part(s))


def to_number(v):
    """'1,234' '△6' '(31,800)' 같은 표기를 숫자로. 읽을 수 없으면 None."""
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        if isinstance(v, float) and math.isnan(v):
            return None
        return int(v) if float(v).is_integer() else float(v)
    s = str(v).strip()
    if not s:
        return None
    neg = s.startswith(("△", "▲", "-", "(", "－"))
    s = re.sub(r"[^0-9.]", "", s)
    if not s or s == ".":
        return None
    n = float(s)
    n = int(n) if n.is_integer() else n
    return -n if neg else n


def find_year(text):
    m = re.search(r"(20\d{2})", str(text or ""))
    return int(m.group(1)) if m else None


def parse_date(raw, default_year=None):
    """여러 표기의 일자를 YYYY-MM-DD 로. 연도가 없으면 default_year 를 붙인다.

    반환: (iso 문자열 또는 None, 연도 보충 여부)
    """
    if raw is None:
        return None, False
    if hasattr(raw, "year") and hasattr(raw, "month"):
        return date(raw.year, raw.month, raw.day).isoformat(), False
    s = str(raw).strip()
    m = re.search(r"(20\d{2})\s*[-./년]\s*(\d{1,2})\s*[-./월]\s*(\d{1,2})", s)
    filled = False
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.search(r"(\d{1,2})\s*[-./월]\s*(\d{1,2})", s)
        if not m or default_year is None:
            return None, False
        y, mo, d = int(default_year), int(m.group(1)), int(m.group(2))
        filled = True
    try:
        return date(y, mo, d).isoformat(), filled
    except ValueError:
        return None, False


def fmt_won(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "-"
    v = round(v)
    return f"△{abs(v):,}원" if v < 0 else f"{v:,}원"


def fmt_qty(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "-"
    txt = f"{abs(v):,.0f}" if float(v).is_integer() else f"{abs(v):,}"
    return f"△{txt}개" if v < 0 else f"{txt}개"

"""ERP 외주입고이력 엑셀 읽기·정규화."""
import pandas as pd

from .normalize import normalize_part, parse_date, part_key, to_number

REQUIRED = ["입고일자", "입고번호", "업체코드", "업체명", "품번", "입고수량", "단가", "공급가액"]
OPTIONAL = ["발주번호", "품명", "단위", "부가세", "합계금액", "입고창고", "입고담당자"]


class ErpFormatError(ValueError):
    pass


def load_erp(file, sheet="입고이력") -> pd.DataFrame:
    xls = pd.ExcelFile(file)
    sheet_name = sheet if sheet in xls.sheet_names else xls.sheet_names[0]
    df = pd.read_excel(xls, sheet_name=sheet_name, dtype=object)
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ErpFormatError(f"ERP 엑셀에 필요한 열이 없습니다: {', '.join(missing)} (시트 '{sheet_name}')")
    for c in OPTIONAL:
        if c not in df.columns:
            df[c] = None

    df = df.dropna(how="all").copy()
    df = df[df["입고번호"].notna()].reset_index(drop=True)
    df["일자"] = [parse_date(v)[0] for v in df["입고일자"]]
    for c in ["입고수량", "단가", "공급가액", "부가세", "합계금액"]:
        df[c] = [to_number(v) for v in df[c]]
    for c in ["입고번호", "발주번호", "업체코드", "업체명", "품명", "단위", "입고창고", "입고담당자"]:
        df[c] = df[c].map(lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip())
    df["품번"] = df["품번"].map(normalize_part)
    df["품번키"] = df["품번"].map(part_key)
    df["erp_id"] = range(len(df))
    return df

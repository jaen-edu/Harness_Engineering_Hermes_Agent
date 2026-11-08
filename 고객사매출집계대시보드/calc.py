"""파일 읽기, 검증, 집계·판정 계산.

화면(app.py)과 분리해 두어 검산(verify_calc.py)으로 바로 돌려 볼 수 있다.
금액은 모두 원 단위 정수, 비율은 Fraction(정확한 분수)으로 계산하고
화면·엑셀에 보여줄 때만 소수점 1자리로 반올림한다.
"""
from __future__ import annotations

import io
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

import openpyxl
import pandas as pd

UNDER = "미달"
CAUTION = "주의"
NORMAL = "정상"
RATE_LIMIT = 90    # 달성률이 이 값(%) 미만이면 미달
MOM_LIMIT = -20    # 전월 대비가 이 값(%) 이하이면 주의
CRITERIA_TEXT = "달성률 90% 미만 = 미달(빨강) / 전월 대비 −20% 이하 = 주의(노랑)"
LAST_QUARTER_STOP_WORDS = ("합계", "분기 합계 상위 3")

SHIP_REQUIRED = ("출하일", "고객사", "금액")
TARGET_REQUIRED = ("고객사", "분기", "목표금액")


class StopError(Exception):
    """집계를 멈춰야 하는 문제. 메시지를 그대로 화면에 보여준다."""


# ---------------------------------------------------------------- 표시 형식

def to_won(value: int) -> int:
    """엑셀 숫자를 원 단위 정수로 바꾼다(반올림)."""
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def round1(value: Fraction) -> Decimal:
    """비율을 소수점 1자리로 반올림(사사오입)."""
    exact = Decimal(value.numerator) / Decimal(value.denominator)
    result = exact.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return result + 0  # -0.0 → 0.0


def fmt_won(value: int | None, unit: str = "원") -> str:
    if value is None:
        return "없음"
    return f"{value:,}{unit}".replace("-", "−")


def fmt_pct(value: Fraction | None, signed: bool = False, none_text: str = "") -> str:
    if value is None:
        return none_text
    r = round1(value)
    text = f"{abs(r)}%"
    if r < 0:
        return "−" + text
    if signed and r > 0:
        return "+" + text
    return text


def fmt_exact(value: Fraction) -> str:
    """툴팁용 반올림 전 값(소수점 4자리)."""
    return f"{float(value):.4f}%".replace("-", "−")


def month_label(month: int) -> str:
    return f"{month}월"


def quarter_label(year: int, quarter: int) -> str:
    return f"{year}년 {quarter}분기"


# ---------------------------------------------------------------- 파일 읽기

@dataclass
class ShipmentFile:
    name: str
    rows: pd.DataFrame                  # 정리된 출하 행
    months: list[tuple[int, int]]       # 출하일로 정한 (연, 월) 목록
    main_month: tuple[int, int] | None  # 행이 가장 많은 달
    warnings: list[str] = field(default_factory=list)


@dataclass
class TargetFile:
    name: str
    rows: pd.DataFrame                  # 고객사, 분기, 목표금액
    quarters: list[str]
    warnings: list[str] = field(default_factory=list)


@dataclass
class LastQuarterFile:
    name: str
    label: str | None                   # 예: 2026년 2분기
    totals: dict[str, int]              # 고객사 → 분기 합계
    warnings: list[str] = field(default_factory=list)


def _open_sheet(name: str, data: bytes, sheet: str) -> pd.DataFrame:
    try:
        xls = pd.ExcelFile(io.BytesIO(data), engine="openpyxl")
    except Exception as exc:  # 엑셀이 아니거나 깨진 파일
        raise StopError(f"'{name}' 파일을 엑셀로 열 수 없습니다. ({exc})") from exc
    use = sheet if sheet in xls.sheet_names else xls.sheet_names[0]
    df = xls.parse(use)
    df.columns = [str(c).strip() for c in df.columns]
    return df.dropna(how="all")


def _missing_columns(name: str, df: pd.DataFrame, required: tuple[str, ...]) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise StopError(
            f"'{name}' 파일에 필수 열 {', '.join(repr(c) for c in missing)}이(가) 없습니다. "
            f"(1행 열 이름: {', '.join(df.columns)})"
        )


def _clean_text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def read_shipments(name: str, data: bytes) -> ShipmentFile:
    df = _open_sheet(name, data, "출하실적")
    _missing_columns(name, df, SHIP_REQUIRED)
    warnings: list[str] = []

    records = []
    for idx, row in df.iterrows():
        excel_row = idx + 2  # 1행이 열 이름
        customer = _clean_text(row["고객사"])
        shipped = pd.to_datetime(row["출하일"], errors="coerce")
        amount = pd.to_numeric(row["금액"], errors="coerce")
        if not customer:
            warnings.append(f"{name} {excel_row}행: 고객사가 비어 있어 집계에서 뺐습니다.")
            continue
        if pd.isna(shipped):
            warnings.append(f"{name} {excel_row}행({customer}): 출하일을 읽을 수 없어 집계에서 뺐습니다.")
            continue
        if pd.isna(amount):
            warnings.append(f"{name} {excel_row}행({customer}): 금액이 비어 있거나 숫자가 아니어서 집계에서 뺐습니다.")
            continue
        records.append({
            "출하일": shipped.date(),
            "출하번호": _clean_text(row.get("출하번호")),
            "고객사": customer,
            "품번": _clean_text(row.get("품번")),
            "수량": pd.to_numeric(row.get("수량"), errors="coerce"),
            "단가": pd.to_numeric(row.get("단가"), errors="coerce"),
            "금액": to_won(amount),
            "비고": _clean_text(row.get("비고")),
            "파일": name,
            "행": excel_row,
        })

    rows = pd.DataFrame(records, columns=[
        "출하일", "출하번호", "고객사", "품번", "수량", "단가", "금액", "비고", "파일", "행"])
    counts = Counter((d.year, d.month) for d in rows["출하일"])
    months = sorted(counts)
    main_month = counts.most_common(1)[0][0] if counts else None

    if len(months) > 1:
        detail = ", ".join(f"{y}-{m:02d} {counts[(y, m)]}행" for y, m in months)
        warnings.append(f"{name}: 한 파일에 여러 달의 출하일이 섞여 있습니다({detail}). 행마다 출하일의 달로 집계합니다.")

    found = re.search(r"(\d{4})\D?(\d{1,2})(?!\d)", name)
    if found and months:
        name_month = (int(found.group(1)), int(found.group(2)))
        if name_month not in months or len(months) > 1:
            shown = ", ".join(f"{y}-{m:02d}" for y, m in months)
            warnings.append(
                f"{name}: 파일명은 {name_month[0]}-{name_month[1]:02d}이지만 출하일은 {shown}입니다. 출하일 기준으로 집계합니다.")

    return ShipmentFile(name, rows, months, main_month, warnings)


def read_targets(name: str, data: bytes) -> TargetFile:
    df = _open_sheet(name, data, "분기목표")
    _missing_columns(name, df, TARGET_REQUIRED)
    rows = pd.DataFrame({
        "고객사": df["고객사"].map(_clean_text),
        "분기": df["분기"].map(_clean_text),
        "목표금액": pd.to_numeric(df["목표금액"], errors="coerce"),
        "행": df.index + 2,
    })
    rows = rows[rows["고객사"] != ""]
    quarters = list(dict.fromkeys(q for q in rows["분기"] if q))
    return TargetFile(name, rows, quarters)


def read_last_quarter(name: str, data: bytes) -> LastQuarterFile:
    try:
        ws = openpyxl.load_workbook(io.BytesIO(data), data_only=True).worksheets[0]
    except Exception as exc:
        raise StopError(f"'{name}' 파일을 엑셀로 열 수 없습니다. ({exc})") from exc

    header_row = name_col = total_col = None
    label = None
    for row in ws.iter_rows():
        texts = [_clean_text(c.value) for c in row]
        if label is None:
            for t in texts:
                m = re.search(r"(\d{4})\s*년\s*(\d)\s*분기", t)
                if m:
                    label = quarter_label(int(m.group(1)), int(m.group(2)))
                    break
        if "고객사" in texts:
            header_row = row[0].row
            name_col = texts.index("고객사")
            if "분기 합계" not in texts:
                raise StopError(f"'{name}' 파일의 표 머리글({header_row}행)에 '분기 합계' 열이 없습니다.")
            total_col = texts.index("분기 합계")
            break
    if header_row is None:
        raise StopError(f"'{name}' 파일에서 '고객사'가 적힌 머리글 행을 찾지 못했습니다.")

    warnings: list[str] = []
    totals: dict[str, int] = {}
    for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
        customer = _clean_text(row[name_col]) if name_col < len(row) else ""
        if customer in LAST_QUARTER_STOP_WORDS:
            break  # 합계 행과 그 아래 설명 행은 건너뛴다
        if not customer:
            continue
        value = pd.to_numeric(row[total_col], errors="coerce")
        if pd.isna(value):
            warnings.append(f"{name}: {customer}의 분기 합계가 숫자가 아니어서 지난 분기 비교에서 뺐습니다.")
            continue
        totals[customer] = totals.get(customer, 0) + to_won(value)
    return LastQuarterFile(name, label, totals, warnings)


# ---------------------------------------------------------------- 집계

@dataclass
class CustomerResult:
    name: str
    months: list[int]                 # 분기 3개월 매출
    total: int
    target: int | None                # None = 목표 없음
    rate: Fraction | None             # 달성률(%) 반올림 전
    mom: Fraction | None              # 전월 대비(%), None = 비교불가
    prev_total: int | None            # 지난 분기 합계, None = 신규
    vs_prev: Fraction | None          # 지난 분기 대비(%)
    judgment: str                     # 미달/주의/정상, 목표 없으면 ""
    rank: int | None = None           # Top 3 순위

    @property
    def mom_text(self) -> str:
        return fmt_pct(self.mom, signed=True, none_text="비교불가")

    @property
    def vs_prev_text(self) -> str:
        if self.prev_total is None:
            return "신규"
        return fmt_pct(self.vs_prev, signed=True, none_text="비교불가")


@dataclass
class Summary:
    year: int
    quarter: int
    months: list[tuple[int, int]]
    customers: list[CustomerResult]   # 고객사명 가나다순
    total: CustomerResult             # 합계 행
    top3: list[CustomerResult]
    prev_label: str
    warnings: list[str]
    returns: list[dict]               # 반품 행(화면 표시용)

    @property
    def label(self) -> str:
        return quarter_label(self.year, self.quarter)

    @property
    def month_names(self) -> list[str]:
        return [month_label(m) for _, m in self.months]

    @property
    def cards(self) -> list[CustomerResult]:
        """Top 3를 맨 앞에, 나머지는 매출액 순."""
        rest = [c for c in sorted(self.customers, key=_rank_key) if c.rank is None]
        return self.top3 + rest


def _pct(numerator: int, denominator: int) -> Fraction:
    return Fraction(numerator * 100, denominator)


def judge(rate: Fraction | None, mom: Fraction | None) -> str:
    """판정은 반올림 전 값으로 한다. 정확히 90%는 정상."""
    if rate is None:
        return ""
    if rate < RATE_LIMIT:
        return UNDER
    if mom is not None and mom <= MOM_LIMIT:
        return CAUTION
    return NORMAL


def _rank_key(c: CustomerResult):
    # 분기 매출 내림차순, 같으면 달성률 높은 쪽(목표 없음은 뒤로), 그다음 이름
    return (-c.total, c.rate is None, -(c.rate or 0), c.name)


def _make_result(name, months, target, prev_total) -> CustomerResult:
    total = sum(months)
    rate = _pct(total, target) if target else None
    mom = _pct(months[2] - months[1], months[1]) if months[1] != 0 else None
    vs_prev = None
    if prev_total:
        vs_prev = _pct(total - prev_total, prev_total)
    return CustomerResult(name, months, total, target, rate, mom, prev_total, vs_prev, judge(rate, mom))


def _md(d: date) -> str:
    return f"{d.month}/{d.day}"


def check_quarter(files: list[ShipmentFile]) -> tuple[int, int, list[tuple[int, int]]]:
    """세 파일이 같은 분기의 연속 3개월인지 확인. 아니면 StopError."""
    by_month: dict[tuple[int, int], list[str]] = {}
    for f in files:
        if f.main_month:
            by_month.setdefault(f.main_month, []).append(f.name)
    dup = {m: names for m, names in by_month.items() if len(names) > 1}
    if dup:
        detail = "; ".join(f"{y}년 {m}월: {', '.join(n)}" for (y, m), n in dup.items())
        raise StopError(f"같은 달 출하실적이 두 번 올라왔습니다({detail}). 한 달에 한 파일만 올려 주세요.")

    all_months = sorted({m for f in files for m in f.months})
    if not all_months:
        raise StopError("출하실적 파일에 집계할 출하 행이 없습니다.")
    quarters = sorted({(y, (m - 1) // 3 + 1) for y, m in all_months})
    if len(quarters) > 1:
        shown = ", ".join(f"{y}년 {m}월" for y, m in all_months)
        raise StopError(
            f"출하실적의 출하일이 여러 분기에 걸쳐 있습니다({shown}). 같은 분기의 연속된 3개월 파일을 올려 주세요.")
    year, q = quarters[0]
    expected = [(year, 3 * q - 2), (year, 3 * q - 1), (year, 3 * q)]
    missing = [m for m in expected if m not in all_months]
    if missing:
        have = "·".join(month_label(m) for _, m in all_months)
        need = "·".join(month_label(m) for _, m in missing)
        files_hint = ", ".join(f"출하실적_{y}-{m:02d}.xlsx" for y, m in missing)
        raise StopError(
            f"{quarter_label(year, q)} 출하실적 중 {have}만 있습니다. {need} 출하실적({files_hint})을 올려 주세요.")
    return year, q, expected


def compute(ship_files: list[ShipmentFile], target_file: TargetFile, last_file: LastQuarterFile) -> Summary:
    year, q, months = check_quarter(ship_files)
    label = quarter_label(year, q)
    warnings: list[str] = []
    for f in ship_files:
        warnings += f.warnings
    warnings += target_file.warnings + last_file.warnings

    rows = pd.concat([f.rows for f in ship_files], ignore_index=True)
    rows["연월"] = [(d.year, d.month) for d in rows["출하일"]]

    # 분기목표: 출하일로 정한 분기와 '분기' 열이 같은 행만
    tq = target_file.rows
    tq = tq[tq["분기"].str.replace(r"\s+", "", regex=True) == label.replace(" ", "")]
    if tq.empty:
        shown = ", ".join(target_file.quarters) or "없음"
        warnings.append(f"분기목표 파일에 '{label}' 행이 없습니다(파일에 있는 분기: {shown}). 모든 고객사의 목표를 '없음'으로 둡니다.")
    targets: dict[str, int] = {}
    for _, t in tq.iterrows():
        if pd.isna(t["목표금액"]):
            warnings.append(f"분기목표 {t['행']}행({t['고객사']}): 목표금액이 숫자가 아니어서 목표 '없음'으로 둡니다.")
            continue
        if t["고객사"] in targets:
            warnings.append(f"분기목표에 {t['고객사']}의 {label} 목표가 두 번 있습니다. 먼저 나온 {targets[t['고객사']]:,}원을 씁니다.")
            continue
        targets[t["고객사"]] = to_won(t["목표금액"])

    # 반품: 기록된 달에 그대로 포함(차감)하고 건별 경고
    returns = []
    for _, r in rows[rows["금액"] < 0].iterrows():
        d = r["출하일"]
        returns.append({"출하일": d, "고객사": r["고객사"], "품번": r["품번"], "금액": r["금액"], "비고": r["비고"]})
        no = f", {r['출하번호']}" if r["출하번호"] else ""
        warnings.append(
            f"반품: {d:%Y-%m-%d} {r['고객사']} {r['품번']} {fmt_won(r['금액'])}{no} → {d.month}월 매출에서 차감했습니다.")
        warnings += _check_return_note(r, rows)

    # 금액 ≠ 수량 × 단가
    for _, r in rows.iterrows():
        if pd.notna(r["수량"]) and pd.notna(r["단가"]):
            calc = to_won(r["수량"] * r["단가"])
            if calc != r["금액"]:
                warnings.append(
                    f"금액 확인: {r['파일']} {r['행']}행 {r['고객사']} {r['품번']} — 금액 {r['금액']:,}원이 "
                    f"수량×단가 {calc:,}원과 다릅니다. 파일의 금액으로 집계했습니다.")

    # 출하번호 중복
    numbered = rows[rows["출하번호"] != ""]
    for no, grp in numbered.groupby("출하번호"):
        if len(grp) > 1:
            where = ", ".join(f"{r['파일']} {r['행']}행" for _, r in grp.iterrows())
            warnings.append(f"출하번호 중복: {no} ({where}) — 모든 행을 집계했습니다.")

    # 고객사별 월 매출
    names = sorted(set(rows["고객사"]) | set(targets))
    monthly = rows.groupby(["고객사", "연월"])["금액"].sum()
    counts = rows.groupby(["고객사", "연월"]).size()
    customers = []
    for name in names:
        values = [int(monthly.get((name, ym), 0)) for ym in months]
        no_ship = [ym for ym in months if counts.get((name, ym), 0) == 0]
        if len(no_ship) == 3:
            warnings.append(f"{name}: {label} 출하가 한 건도 없습니다. 분기 매출 0원으로 표시합니다.")
        else:
            for _, m in no_ship:
                warnings.append(f"{m}월 {name}: 출하가 없습니다. {m}월 매출 0원으로 집계했습니다.")
        if name not in targets:
            warnings.append(f"{name}: 분기목표 파일에 {label} 목표가 없습니다. 목표 '없음', 달성률·판정은 비워 둡니다.")
        customers.append(_make_result(name, values, targets.get(name), last_file.totals.get(name)))

    for c in customers:
        if c.mom is None and c.target is not None:
            warnings.append(
                f"{c.name}: 직전 달({month_label(months[1][1])}) 매출이 0원이라 전월 대비를 계산할 수 없습니다('비교불가'). 달성률로만 판정합니다.")

    top3 = sorted(customers, key=_rank_key)[:3]
    for i, c in enumerate(top3, start=1):
        c.rank = i

    total_target = sum(targets[n] for n in names if n in targets) if targets else None
    prev_sum = sum(last_file.totals.values()) or None
    total = _make_result("합계", [sum(c.months[i] for c in customers) for i in range(3)], total_target, prev_sum)
    total.judgment = ""

    q_prev, y_prev = (q - 1, year) if q > 1 else (4, year - 1)
    prev_label = last_file.label or quarter_label(y_prev, q_prev)

    return Summary(year, q, months, customers, total, top3, prev_label, warnings, returns)


def _check_return_note(r, rows: pd.DataFrame) -> list[str]:
    """반품 비고의 원출하일(예: '8/28 출하분')에 같은 고객사·품번 출하가 있는지 확인."""
    found = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})", r["비고"])
    if not found:
        return []
    d = r["출하일"]
    month, day = int(found.group(1)), int(found.group(2))
    year = d.year if (month, day) <= (d.month, d.day) else d.year - 1
    try:
        origin = date(year, month, day)
    except ValueError:
        return [f"반품 비고 확인: {r['고객사']} {r['품번']} 반품 비고 '{r['비고']}'의 날짜를 읽을 수 없습니다."]

    same = rows[(rows["고객사"] == r["고객사"]) & (rows["품번"] == r["품번"]) & (rows["금액"] > 0)]
    if (same["출하일"] == origin).any():
        return []
    uploaded = {(x.year, x.month) for x in rows["출하일"]}
    head = f"반품 비고 날짜 불일치: {_md(d)} {r['고객사']} {r['품번']} 반품 비고는 '{r['비고']}'이나"
    if (origin.year, origin.month) not in uploaded:
        return [f"{head} {origin.month}월 출하실적이 올라온 범위 밖이라 원출하를 확인할 수 없습니다."]
    same_month = sorted(x for x in same["출하일"] if (x.year, x.month) == (origin.year, origin.month))
    if same_month:
        detail = f"{origin.month}월 {r['고객사']} {r['품번']} 출하는 {', '.join(_md(x) for x in same_month)}뿐입니다."
    else:
        detail = f"{origin.month}월에 {r['고객사']} {r['품번']} 출하가 없습니다."
    return [f"{head} {_md(origin)}에 같은 품번 출하가 없습니다. {detail}"]

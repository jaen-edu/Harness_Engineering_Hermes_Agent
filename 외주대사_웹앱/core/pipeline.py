"""판독 결과 → 검산 → 대사 → 요약까지 한 번에 (화면과 테스트가 같이 쓴다)."""
from dataclasses import dataclass

import pandas as pd

from .matcher import collapse_bundles, reconcile
from .pdf_reader import PAGE_COLUMNS, ROW_COLUMNS, finalize_rows, pages_to_frames
from .report import build_summary
from .validator import check_rows, check_totals, vendor_check_ok
from .vendors import vendor_name


def build_statement(files: dict[str, list[dict]], vendor_of_file: dict[str, str], vendors: list[dict],
                    default_year: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, infos = [], []
    for fn, pages in files.items():
        code = vendor_of_file.get(fn) or ""
        r, i = pages_to_frames(fn, code, vendor_name(code, vendors), pages, default_year)
        rows.append(r)
        infos.append(i)
    rows_df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=ROW_COLUMNS)
    info_df = pd.concat(infos, ignore_index=True) if infos else pd.DataFrame(columns=PAGE_COLUMNS)
    return finalize_rows(rows_df), info_df


def validate(rows: pd.DataFrame, page_info: pd.DataFrame):
    rows = check_rows(finalize_rows(rows))
    totals = check_totals(rows, page_info)
    return rows, totals, vendor_check_ok(rows, totals)


@dataclass
class Result:
    rows: pd.DataFrame
    totals: pd.DataFrame
    issues: pd.DataFrame
    collapsed: pd.DataFrame
    summary: pd.DataFrame


def run_reconcile(rows: pd.DataFrame, page_info: pd.DataFrame, erp: pd.DataFrame, vendors: list[dict],
                  date_window: int = 7) -> Result:
    rows, totals, ok = validate(rows, page_info)
    names = {v["code"]: v["name"] for v in vendors}
    for _, r in erp[["업체코드", "업체명"]].drop_duplicates().iterrows():
        names.setdefault(r["업체코드"], r["업체명"])
    issues = reconcile(rows, erp, names, date_window)
    collapsed = collapse_bundles(issues)
    summary = build_summary(rows, erp, collapsed, ok, names)
    return Result(rows, totals, issues, collapsed, summary)

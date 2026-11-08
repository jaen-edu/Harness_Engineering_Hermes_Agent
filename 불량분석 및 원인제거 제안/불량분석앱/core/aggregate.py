"""KPI, 주차×라인 불량률, 유형별 추이. 모든 숫자는 여기서 계산한다."""
from __future__ import annotations

import pandas as pd

from core.loader import week_sort_key


def sorted_weeks(weeks) -> list[str]:
    return sorted({w for w in weeks if w}, key=week_sort_key)


def window(all_weeks, week: str, n: int) -> list[str]:
    """week를 마지막으로 하는 최근 n주 (데이터에 있는 주차 기준)."""
    ws = sorted_weeks(all_weeks)
    if week not in ws:
        return ws[-n:]
    i = ws.index(week)
    return ws[max(0, i - n + 1): i + 1]


def week_line(defects: pd.DataFrame, production: pd.DataFrame) -> pd.DataFrame:
    """주차 × 라인: 생산수량, 불량수량, 불량건수, 불량률(%), 근무일수."""
    g = (defects.groupby(["주차", "라인"])
         .agg(불량수량=("불량수량", "sum"), 불량건수=("불량수량", "size"))
         .reset_index())
    m = production[["주차", "라인", "생산수량", "근무일수"]].merge(g, on=["주차", "라인"], how="left")
    m[["불량수량", "불량건수"]] = m[["불량수량", "불량건수"]].fillna(0).astype(int)
    m["불량률"] = m["불량수량"] / m["생산수량"] * 100
    m["_k"] = m["주차"].map(week_sort_key)
    return m.sort_values(["_k", "라인"]).drop(columns="_k").reset_index(drop=True)


def week_total(wl: pd.DataFrame) -> pd.DataFrame:
    t = (wl.groupby("주차")
         .agg(생산수량=("생산수량", "sum"), 불량수량=("불량수량", "sum"),
              불량건수=("불량건수", "sum"), 근무일수=("근무일수", "max"))
         .reset_index())
    t["불량률"] = t["불량수량"] / t["생산수량"] * 100
    t["_k"] = t["주차"].map(week_sort_key)
    return t.sort_values("_k").drop(columns="_k").reset_index(drop=True)


def kpi(wl: pd.DataFrame, week: str) -> dict:
    t = week_total(wl).set_index("주차")
    cur = t.loc[week]
    ws = list(t.index)
    prev = t.loc[ws[ws.index(week) - 1]] if ws.index(week) > 0 else None
    out = {
        "주차": week,
        "생산수량": int(cur["생산수량"]),
        "불량수량": int(cur["불량수량"]),
        "불량건수": int(cur["불량건수"]),
        "불량률": float(cur["불량률"]),
        "근무일수": int(cur["근무일수"]),
        "전주": None,
    }
    if prev is not None:
        out["전주"] = ws[ws.index(week) - 1]
        out["전주_생산수량"] = int(prev["생산수량"])
        out["전주_불량수량"] = int(prev["불량수량"])
        out["전주_불량건수"] = int(prev["불량건수"])
        out["전주_불량률"] = float(prev["불량률"])
        out["불량률_증감pp"] = out["불량률"] - out["전주_불량률"]
    return out


def rate_pivot(wl: pd.DataFrame, weeks: list[str]) -> pd.DataFrame:
    p = wl[wl["주차"].isin(weeks)].pivot(index="라인", columns="주차", values="불량률")
    return p[[w for w in weeks if w in p.columns]]


def type_trend(defects: pd.DataFrame, weeks: list[str], value: str = "qty") -> pd.DataFrame:
    """불량유형 × 주차. value='qty' 수량 합계, 'count' 건수. 마지막 주 수량 내림차순."""
    d = defects[defects["주차"].isin(weeks)]
    aggfunc = "sum" if value == "qty" else "size"
    p = d.pivot_table(index="불량유형", columns="주차", values="불량수량", aggfunc=aggfunc, fill_value=0)
    p = p.reindex(columns=[w for w in weeks], fill_value=0).astype(int)
    if len(weeks) >= 2:
        p["전주 대비"] = p[weeks[-1]] - p[weeks[-2]]
    return p.sort_values(weeks[-1], ascending=False)


def top_types(defects: pd.DataFrame, week: str, n: int = 3) -> pd.DataFrame:
    """이번 주 불량유형 수량 순위 (건수 함께)."""
    d = defects[defects["주차"] == week]
    g = d.groupby("불량유형").agg(불량수량=("불량수량", "sum"), 불량건수=("불량수량", "size"))
    return g.sort_values("불량수량", ascending=False).head(n).reset_index()

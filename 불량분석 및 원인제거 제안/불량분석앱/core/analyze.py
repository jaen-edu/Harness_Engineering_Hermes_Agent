"""파레토, 교차 분석, 변화점 감지."""
from __future__ import annotations

import pandas as pd

import config
from core.aggregate import rate_pivot


def pareto(defects: pd.DataFrame, week: str, by: str) -> pd.DataFrame:
    d = defects[defects["주차"] == week]
    g = d.groupby(by)["불량수량"].sum().sort_values(ascending=False).reset_index()
    total = g["불량수량"].sum()
    g["점유율"] = g["불량수량"] / total * 100 if total else 0
    g["누적점유율"] = g["점유율"].cumsum()
    return g


def cross_top(defects: pd.DataFrame, week: str, n: int = 10) -> pd.DataFrame:
    d = defects[defects["주차"] == week]
    g = (d.groupby(["라인", "품번", "품명", "불량유형"])
         .agg(불량수량=("불량수량", "sum"), 불량건수=("불량수량", "size"))
         .sort_values("불량수량", ascending=False).head(n).reset_index())
    g["점유율"] = g["불량수량"] / d["불량수량"].sum() * 100
    return g


def distribution(defects: pd.DataFrame, week: str, by: str) -> pd.DataFrame:
    """불량유형 × by(출하처 / 발견 공정) 수량 표."""
    d = defects[defects["주차"] == week]
    p = d.pivot_table(index="불량유형", columns=by, values="불량수량", aggfunc="sum", fill_value=0).astype(int)
    p["합계"] = p.sum(axis=1)
    return p.sort_values("합계", ascending=False)


def outflow_share(defects: pd.DataFrame, week: str) -> pd.DataFrame:
    d = defects[defects["주차"] == week]
    g = d.groupby("불량유형").agg(
        전체=("불량수량", "sum"),
        출하검사=("불량수량", lambda s: s[d.loc[s.index, "발견 공정"] == config.OUTFLOW_PROCESS].sum()),
    )
    g["출하검사 비중"] = g["출하검사"] / g["전체"] * 100
    return g.sort_values("출하검사 비중", ascending=False).reset_index()


def detect_changes(defects: pd.DataFrame, wl: pd.DataFrame, week: str, weeks: list[str]) -> list[dict]:
    """4개 규칙으로 변화점을 찾는다. 각 항목의 filter는 원본 행을 찾는 조건."""
    out: list[dict] = []
    cur = defects[defects["주차"] == week]

    # 1) 유형 급증
    if len(weeks) >= 2 and weeks[-1] == week:
        prev_w = weeks[-2]
        q = defects[defects["주차"].isin([prev_w, week])].pivot_table(
            index="불량유형", columns="주차", values="불량수량", aggfunc="sum", fill_value=0)
        for t, r in q.iterrows():
            p, c = int(r.get(prev_w, 0)), int(r.get(week, 0))
            diff = c - p
            pct = (diff / p * 100) if p else float("inf")
            if diff >= config.SURGE_QTY and pct >= config.SURGE_PCT:
                pct_s = f"+{pct:.0f}%" if p else "신규"
                out.append({
                    "규칙": "유형 급증", "대상": t,
                    "내용": f"{t} {p} → {c}개 ({pct_s}, +{diff}개, {prev_w} 대비)",
                    "filter": {"불량유형": t, "주차": [prev_w, week]},
                })

    # 2) 연속 상승 (라인 불량률)
    rp = rate_pivot(wl, weeks)
    for line, r in rp.iterrows():
        vals = [v for v in r.tolist() if pd.notna(v)]
        steps = 0
        for a, b in zip(reversed(vals[:-1]), reversed(vals[1:])):
            if b > a:
                steps += 1
            else:
                break
        if steps >= config.CONSEC_RISE_STEPS:
            seg = vals[-(steps + 1):]
            out.append({
                "규칙": "연속 상승", "대상": line,
                "내용": f"{line} 불량률 {seg[0]:.2f}% → {seg[-1]:.2f}% ({steps + 1}주 연속 상승, {steps}회)",
                "filter": {"라인": line, "주차": [week]},
            })

    # 3) 하루 집중
    if not cur.empty:
        keys = ["라인", "품번", "불량유형"]
        daily = cur.groupby(keys + ["발생일"])["불량수량"].sum().reset_index()
        tot = daily.groupby(keys)["불량수량"].transform("sum")
        daily["비중"] = daily["불량수량"] / tot
        daily["주간"] = tot
        hit = daily[(daily["비중"] >= config.DAY_CONC_SHARE) & (daily["주간"] >= config.DAY_CONC_MIN_QTY)]
        for _, r in hit.iterrows():
            day = pd.Timestamp(r["발생일"])
            out.append({
                "규칙": "하루 집중", "대상": f"{r['라인']} {r['품번']} {r['불량유형']}",
                "내용": (f"{r['라인']} {r['품번']} {r['불량유형']} 주간 {int(r['주간'])}개 중 "
                       f"{int(r['불량수량'])}개({r['비중'] * 100:.0f}%)가 {day.month}/{day.day} 하루에 발생"),
                "filter": {"라인": r["라인"], "품번": r["품번"], "불량유형": r["불량유형"], "주차": [week]},
            })

    # 4) 유출 위험
    if not cur.empty:
        for _, r in outflow_share(defects, week).iterrows():
            if r["전체"] > 0 and r["출하검사"] / r["전체"] >= config.OUTFLOW_SHARE:
                out.append({
                    "규칙": "유출 위험", "대상": r["불량유형"],
                    "내용": (f"{r['불량유형']} 출하검사 발견 {int(r['출하검사'])}/{int(r['전체'])}개 "
                           f"({r['출하검사 비중']:.0f}%)"),
                    "filter": {"불량유형": r["불량유형"], "발견 공정": config.OUTFLOW_PROCESS, "주차": [week]},
                })
    return out


def rows_for(defects: pd.DataFrame, flt: dict) -> pd.DataFrame:
    m = pd.Series(True, index=defects.index)
    for k, v in flt.items():
        m &= defects[k].isin(v) if isinstance(v, list) else (defects[k] == v)
    return defects[m]

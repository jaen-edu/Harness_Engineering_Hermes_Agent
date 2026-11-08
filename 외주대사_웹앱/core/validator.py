"""판독 검산: 행별 수량×단가=공급가액, 명세서 인쇄 합계=행 합계."""
import pandas as pd


def check_rows(rows: pd.DataFrame) -> pd.DataFrame:
    """행마다 '검산' 메시지(문제 없으면 빈 문자열)를 붙인다."""
    rows = rows.copy()
    msgs = []
    for _, r in rows.iterrows():
        m = []
        if not r["일자"]:
            m.append(f"일자 해석 불가('{r['원본일자']}')")
        if not r["품번"]:
            m.append("품번 없음")
        q, p, a = r["수량"], r["단가"], r["공급가액"]
        if any(v is None or pd.isna(v) for v in (q, p, a)):
            m.append("수량/단가/공급가액 빈칸")
        elif abs(round(q * p) - a) >= 1:
            m.append(f"수량×단가={round(q * p):,} ≠ 공급가액 {a:,.0f}")
        msgs.append(" · ".join(m))
    rows["검산"] = msgs
    return rows


def check_totals(rows: pd.DataFrame, page_info: pd.DataFrame) -> pd.DataFrame:
    """파일별로 페이지를 차례로 더해 가다 인쇄 합계가 나오면 비교한다.

    월합계형(마지막 장에만 합계)과 건별형(장마다 합계)을 같은 규칙으로 처리한다.
    """
    out = []
    for fn, pi in page_info.groupby("파일", sort=False):
        pi = pi.sort_values("페이지")
        acc, start, seen_total = 0, None, False
        vcode = pi["업체코드"].iloc[0]
        for _, p in pi.iterrows():
            sub = rows[(rows["파일"] == fn) & (rows["페이지"] == p["페이지"])]
            acc += sub["공급가액"].fillna(0).sum()
            start = p["페이지"] if start is None else start
            total = p["인쇄공급가액합계"]
            if total is not None and not pd.isna(total):
                seen_total = True
                diff = acc - total
                out.append({"파일": fn, "업체코드": vcode,
                            "페이지": f"{start}" if start == p["페이지"] else f"{start}~{p['페이지']}",
                            "행합계": acc, "인쇄합계": total, "차이": diff,
                            "결과": "일치" if abs(diff) < 1 else "불일치"})
                acc, start = 0, None
        if not seen_total:
            out.append({"파일": fn, "업체코드": vcode, "페이지": "-", "행합계": acc, "인쇄합계": None,
                        "차이": None, "결과": "인쇄 합계 없음"})
        elif start is not None:
            out.append({"파일": fn, "업체코드": vcode, "페이지": f"{start}~", "행합계": acc, "인쇄합계": None,
                        "차이": None, "결과": "합계 뒤에 남은 행"})
    return pd.DataFrame(out, columns=["파일", "업체코드", "페이지", "행합계", "인쇄합계", "차이", "결과"])


def vendor_check_ok(rows: pd.DataFrame, totals: pd.DataFrame) -> dict:
    """업체코드 → 판독 검산 통과 여부."""
    ok = {}
    for v in set(rows["업체코드"]) | set(totals["업체코드"]):
        r_ok = (rows.loc[rows["업체코드"] == v, "검산"] == "").all()
        t_ok = (totals.loc[totals["업체코드"] == v, "결과"] == "일치").all()
        ok[v] = bool(r_ok and t_ok)
    return ok

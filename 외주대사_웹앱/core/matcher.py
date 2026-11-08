"""명세서 행 ↔ ERP 입고 행 대사 (계획서 5장 규칙).

1차: 업체+일자+품번(+반품 여부)으로 양쪽을 합산해 비교 → 수량/단가/금액 불일치, ERP 중복 의심
2차: 남은 행끼리 → 일자 불일치(품번·금액 같고 N일 이내), 품번 불일치(일자 같고 금액 또는 수량 같음)
잔여: ERP 미입고 / 반품 미반영 / 명세서 누락, 그리고 손글씨 정정은 참고 항목으로 추가
"""
from datetime import date

import pandas as pd

from .normalize import fmt_qty, fmt_won

ACTIONS = {
    "수량 불일치": "입고 전표 수량 확인",
    "단가 불일치": "단가 계약·발주 단가 확인",
    "금액 불일치": "업체 계산 오류 확인",
    "일자 불일치": "마감월 경계면 귀속월 확인",
    "품번 불일치": "ERP 품번 입력 오류 확인",
    "ERP 미입고": "입고 누락 처리",
    "명세서 누락": "업체에 명세서 추가 요청",
    "ERP 중복 의심": "중복 전표 취소 검토",
    "반품 미반영": "ERP 반품 전표 등록",
    "정정 표기": "정정 값 육안 확인(금액 영향 없으면 참고)",
}
TYPE_ORDER = list(ACTIONS)

ISSUE_COLUMNS = ["업체코드", "업체", "유형", "틀린 항목", "파일", "위치", "일자", "품번", "발주번호",
                 "명세서 값", "ERP 값", "차액", "ERP 입고번호", "조치", "비고", "참고", "묶음",
                 "refs", "erp_ids", "_sp", "_ep"]


class _Side:
    """한 쪽(명세서 또는 ERP)의 같은 키 묶음."""

    def __init__(self, df, idx, qty_col, price_col):
        sub = df.loc[list(idx)]
        self.idx = list(idx)
        self.sub = sub
        self.qty = float(sub[qty_col].fillna(0).sum())
        self.amt = float(sub["공급가액"].fillna(0).sum())
        prices = sub[price_col].dropna().unique()
        self.price = float(prices[0]) if len(prices) == 1 else (self.amt / self.qty if self.qty else None)
        first = sub.iloc[0]
        self.vcode, self.date, self.pkey, self.part = first["업체코드"], first["일자"], first["품번키"], first["품번"]
        self.ret = self.qty < 0
        self.pos = sorted({p for p in sub["발주번호"] if p})


def _d(s):
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _mmdd(s):
    return s[5:] if s else "-"


def reconcile(stmt: pd.DataFrame, erp: pd.DataFrame, vendor_names: dict, date_window: int = 7) -> pd.DataFrame:
    stmt = stmt.copy()
    erp = erp.copy()
    stmt["_ret"] = stmt["수량"].fillna(0) < 0
    erp["_ret"] = erp["입고수량"].fillna(0) < 0
    keys = ["업체코드", "일자", "품번키", "_ret"]
    s_groups = {k: v for k, v in stmt.groupby(keys, dropna=False).groups.items()}
    e_groups = {k: v for k, v in erp.groupby(keys, dropna=False).groups.items()}
    # 명세서가 올라온 업체만 대사한다 (명세서를 안 올린 업체의 ERP 행은 '명세서 누락'으로 쏟아지지 않게)
    stmt_vendors = set(stmt["업체코드"])
    e_groups = {k: v for k, v in e_groups.items() if k[0] in stmt_vendors}

    issues = []
    matched_erp_for_stmt = {}  # stmt_id -> ERP 묶음 (정정 표기 참고용)

    def add(type_, field, s: _Side | None, e: _Side | None, s_val, e_val, diff, note=""):
        vcode = (s or e).vcode
        rec = {
            "업체코드": vcode, "업체": vendor_names.get(vcode, vcode), "유형": type_, "틀린 항목": field,
            "파일": "", "위치": "", "일자": "", "품번": "", "발주번호": "",
            "명세서 값": s_val, "ERP 값": e_val, "차액": diff,
            "ERP 입고번호": ", ".join(e.sub["입고번호"]) if e else "",
            "조치": ACTIONS[type_], "비고": note, "참고": type_ == "정정 표기", "묶음": "",
            "refs": [], "erp_ids": list(e.sub["erp_id"]) if e else [],
            "_sp": s.price if s else None, "_ep": e.price if e else None,
        }
        if s:
            rec["파일"] = ", ".join(sorted(set(s.sub["파일"])))
            rec["위치"] = location_text(s.sub)
            rec["refs"] = [{"파일": r["파일"], "페이지": int(r["페이지"]), "순서": int(r["페이지내순서"]),
                            "행번호": int(r["행번호"]), "위치y": r["위치y"]} for _, r in s.sub.iterrows()]
        rec["일자"] = _mmdd(s.date if s else e.date)
        if s and e and s.date != e.date:
            rec["일자"] = f"명세서 {_mmdd(s.date)} / ERP {_mmdd(e.date)}"
        rec["품번"] = (s or e).part
        if s and e and s.pkey != e.pkey:
            rec["품번"] = f"명세서 {s.part} / ERP {e.part}"
        pos = (s.pos if s and s.pos else []) or (e.pos if e else [])
        rec["발주번호"] = ", ".join(pos)
        if s and e and s.pos and e.pos and set(s.pos) != set(e.pos):
            extra = f"발주번호 상이: 명세서 {', '.join(s.pos)} / ERP {', '.join(e.pos)}"
            rec["비고"] = f"{rec['비고']} · {extra}" if rec["비고"] else extra
        issues.append(rec)

    # ---- 1차 매칭
    s_left, e_left = [], []
    for k, idx in s_groups.items():
        s = _Side(stmt, idx, "수량", "단가")
        if k not in e_groups:
            s_left.append(s)
            continue
        e = _Side(erp, e_groups[k], "입고수량", "단가")
        for sid in stmt.loc[s.idx, "stmt_id"]:
            matched_erp_for_stmt[sid] = e
        qty_counts = e.sub["입고수량"].value_counts()
        dup = len(e.idx) >= 2 and qty_counts.max() >= 2
        diff = s.amt - e.amt
        if s.qty != e.qty:
            if dup:
                q = qty_counts.idxmax()
                add("ERP 중복 의심", "입고 행 수", s, e, f"{fmt_qty(s.qty)} ({len(s.idx)}행)",
                    f"{fmt_qty(q)} × {qty_counts.max()}행 = {fmt_qty(e.qty)}", diff)
            else:
                add("수량 불일치", "수량", s, e, fmt_qty(s.qty), fmt_qty(e.qty), diff)
        elif s.price is not None and e.price is not None and abs(s.price - e.price) >= 0.5:
            add("단가 불일치", "단가", s, e, fmt_won(s.price), fmt_won(e.price), diff)
        elif abs(diff) >= 1:
            add("금액 불일치", "공급가액", s, e, fmt_won(s.amt), fmt_won(e.amt), diff)
    for k, idx in e_groups.items():
        if k not in s_groups:
            e_left.append(_Side(erp, idx, "입고수량", "단가"))

    # ---- 2차 매칭: 일자 불일치
    for s in sorted(s_left, key=lambda x: (x.vcode, x.date or "")):
        sd = _d(s.date)
        cands = [e for e in e_left if e.vcode == s.vcode and e.pkey == s.pkey and e.ret == s.ret
                 and abs(e.amt - s.amt) < 1 and sd and _d(e.date) and abs((_d(e.date) - sd).days) <= date_window]
        if cands:
            e = min(cands, key=lambda x: abs((_d(x.date) - sd).days))
            add("일자 불일치", "일자", s, e, f"{_mmdd(s.date)} · {fmt_won(s.amt)}", f"{_mmdd(e.date)} · {fmt_won(e.amt)}",
                s.amt - e.amt, f"{abs((_d(e.date) - sd).days)}일 차이")
            s.done = e.done = True
    s_left = [s for s in s_left if not getattr(s, "done", False)]
    e_left = [e for e in e_left if not getattr(e, "done", False)]

    # ---- 2차 매칭: 품번 불일치
    for s in s_left:
        cands = [e for e in e_left if not getattr(e, "done", False) and e.vcode == s.vcode and e.date == s.date
                 and e.ret == s.ret and e.pkey != s.pkey and (abs(e.amt - s.amt) < 1 or e.qty == s.qty)]
        if cands:
            e = min(cands, key=lambda x: abs(x.amt - s.amt))
            add("품번 불일치", "품번", s, e, f"{s.part} · {fmt_won(s.amt)}", f"{e.part} · {fmt_won(e.amt)}",
                s.amt - e.amt)
            s.done = e.done = True
    s_left = [s for s in s_left if not getattr(s, "done", False)]
    e_left = [e for e in e_left if not getattr(e, "done", False)]

    # ---- 잔여
    for s in s_left:
        if s.ret:
            add("반품 미반영", "반품 행", s, None, f"{fmt_qty(s.qty)} · {fmt_won(s.amt)}", "없음", s.amt)
        else:
            add("ERP 미입고", "행 전체", s, None, f"{fmt_qty(s.qty)} · {fmt_won(s.amt)}", "없음", s.amt)
    for e in e_left:
        add("명세서 누락", "행 전체", None, e, "없음", f"{fmt_qty(e.qty)} · {fmt_won(e.amt)}", -e.amt)

    # ---- 손글씨 정정 (참고)
    for _, r in stmt[stmt["정정"]].iterrows():
        s = _Side(stmt, [r.name], "수량", "단가")
        e = matched_erp_for_stmt.get(r["stmt_id"])
        note = r["정정내용"] or "정정 표기"
        add("정정 표기", "정정 표기", s, e, f"{fmt_qty(s.qty)} ({note})", fmt_qty(e.qty) if e else "-", 0)

    df = pd.DataFrame(issues, columns=ISSUE_COLUMNS)
    if df.empty:
        return df
    df["_t"] = df["유형"].map(TYPE_ORDER.index)
    df["_f"] = df["refs"].map(lambda r: (r[0]["파일"], r[0]["페이지"], r[0]["순서"]) if r else ("~", 0, 0))
    df = df.sort_values(["업체코드", "_f", "_t"]).drop(columns=["_t", "_f"]).reset_index(drop=True)
    return _assign_bundles(df)


def location_text(sub: pd.DataFrame) -> str:
    """'1페이지 8·11행, 2페이지 17·19행' 형식."""
    parts = []
    for page, g in sub.sort_values(["페이지", "페이지내순서"]).groupby("페이지", sort=True):
        parts.append(f"{int(page)}페이지 " + "·".join(str(int(n)) for n in g["행번호"]) + "행")
    return ", ".join(parts)


def _assign_bundles(df: pd.DataFrame) -> pd.DataFrame:
    """같은 업체·발주번호·같은 단가 차이가 반복되는 단가 불일치를 한 묶음으로."""
    m = df["유형"] == "단가 불일치"
    n = 0
    for _, g in df[m].groupby([df["업체코드"], df["발주번호"], df["_sp"].round(2), df["_ep"].round(2)]):
        if len(g) >= 2:
            n += 1
            df.loc[g.index, "묶음"] = f"B{n}"
    return df


def collapse_bundles(issues: pd.DataFrame) -> pd.DataFrame:
    """묶음을 한 줄로 접은 리포트(묶음이 아닌 행은 그대로)."""
    if issues.empty:
        return issues.assign(건수=[])
    out = []
    for _, r in issues[issues["묶음"] == ""].iterrows():
        out.append({**r.to_dict(), "건수": 1})
    for b, g in issues[issues["묶음"] != ""].groupby("묶음", sort=False):
        first = g.iloc[0].to_dict()
        refs = [x for rs in g["refs"] for x in rs]
        sub = pd.DataFrame([{"페이지": x["페이지"], "페이지내순서": x["순서"], "행번호": x["행번호"]} for x in refs])
        dates = sorted(d for d in g["일자"] if d and d != "-")
        first.update({
            "위치": location_text(sub),
            "일자": f"{dates[0]}~{dates[-1]}" if len(dates) > 1 and dates[0] != dates[-1] else (dates[0] if dates else "-"),
            "품번": f"{first['품번']} ({first['발주번호']})" if first["발주번호"] else first["품번"],
            "차액": g["차액"].sum(),
            "ERP 입고번호": ", ".join(g["ERP 입고번호"]),
            "refs": refs, "erp_ids": [x for e in g["erp_ids"] for x in e],
            "비고": f"{len(g)}건 합", "건수": len(g),
        })
        out.append(first)
    df = pd.DataFrame(out)
    df["_t"] = df["유형"].map(TYPE_ORDER.index)
    df["_f"] = df["refs"].map(lambda r: (r[0]["파일"], r[0]["페이지"], r[0]["순서"]) if r else ("~", 0, 0))
    return df.sort_values(["업체코드", "_f", "_t"]).drop(columns=["_t", "_f"]).reset_index(drop=True)

"""견적 검증·보완(3-3)과 비교 계산(3-4). AI를 쓰지 않는다."""
import re
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from core.common import format_date, format_won, is_blank, normalize_supplier, to_date, to_number, to_text

# 영문 키 → 화면 열 이름 (추출 결과 표)
FIELD_LABELS = {
    "supplier": "협력사",
    "quote_no": "견적번호",
    "quote_date": "견적일",
    "item_name": "품목",
    "spec": "규격",
    "same_item": "품목일치",
    "quoted_qty": "견적수량",
    "unit": "단위",
    "unit_price": "단가",
    "supplied_amount": "공급가액",
    "vat_included": "부가세포함",
    "moq": "MOQ",
    "lead_time_days": "리드타임(일)",
    "freight_included": "운송비포함",
    "freight_amount": "운송비",
    "payment_terms": "결제조건",
    "validity_days": "유효기간(일)",
    "mill_sheet": "밀시트",
    "other_conditions": "기타조건",
}
BOOL_FIELDS = {"same_item", "vat_included", "freight_included", "mill_sheet"}
NUM_FIELDS = {"quoted_qty", "unit_price", "supplied_amount", "moq", "lead_time_days", "freight_amount", "validity_days"}
BOOL_TEXT = {True: "예", False: "아니오", None: "미기재"}
BOOL_OPTIONS = ["예", "아니오", "미기재"]
NULL_CHECK_FIELDS = ["quote_no", "quote_date", "unit_price", "moq", "lead_time_days",
                     "freight_included", "validity_days", "payment_terms", "mill_sheet"]
EXPIRY_WARN_DAYS = 7


def round_half_up(x):
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _supplier_rows(suppliers, name, item_group=None):
    norm = normalize_supplier(name)
    rows = suppliers[suppliers["협력사"].map(normalize_supplier) == norm]
    if item_group and not rows.empty:
        same_group = rows[rows["품목군"] == item_group]
        if not same_group.empty:
            rows = same_group
    return rows


# ---------------------------------------------------------------- 3-3 검증·보완

def validate(quotes, suppliers, request):
    """견적 dict 목록을 검사·보완한다 → (새 목록, 경고 목록).

    각 견적에 flags(확인사항), payment_terms_source, amount_check, include(처음 한 번만)를 붙인다.
    """
    out, warnings = [], []
    for q in quotes:
        q = dict(q)
        flags = []

        # 협력사 확인
        rows = _supplier_rows(suppliers, q.get("supplier"), request.get("품목군"))
        if rows.empty:
            flags.append("목록에 없는 협력사")
            q["supplier"] = to_text(q.get("supplier")) or "(협력사 미상)"
        else:
            q["supplier"] = rows.iloc[0]["협력사"]

        # 결제조건 보완
        if is_blank(q.get("payment_terms")):
            if not rows.empty and not is_blank(rows.iloc[0].get("결제 조건")):
                q["payment_terms"] = rows.iloc[0]["결제 조건"]
                q["payment_terms_source"] = "협력사목록"
            else:
                q["payment_terms"] = None
                q["payment_terms_source"] = "없음"
                flags.append("결제조건 미기재")
        elif q.get("payment_terms_source") not in ("협력사목록",):
            q["payment_terms_source"] = "견적서"

        # 금액 검산
        up, qty, amt = q.get("unit_price"), q.get("quoted_qty"), q.get("supplied_amount")
        if amt is not None and up is not None and qty is not None:
            expected = up * qty
            if abs(expected - amt) >= 1:
                q["amount_check"] = f"불일치 (단가×수량 {format_won(expected)} ≠ 견적서 {format_won(amt)})"
                flags.append("금액 불일치")
            else:
                q["amount_check"] = f"일치 ({format_won(amt)})"
        else:
            q["amount_check"] = "공급가액 없음"

        # 품목 확인
        if q.get("same_item") is False:
            flags.append("요청 품목과 다름")

        # 필수값
        if up is None:
            flags.append("단가 직접 입력 필요")

        # 운송비
        if q.get("freight_included") is None:
            flags.append("운송비 포함 여부 미기재")
        elif q.get("freight_included") is False and q.get("freight_amount") is None:
            flags.append("운송비 금액 미기재")

        if q.get("mill_sheet") is None:
            flags.append("밀시트 미기재")

        # 스캔 품질 등으로 빈 값이 많을 때
        nulls = sum(1 for f in NULL_CHECK_FIELDS if q.get(f) in (None, ""))
        if nulls >= 5:
            flags.append("읽은 값이 적음 — 원본 직접 확인 필요")

        if "include" not in q:
            q["include"] = q.get("same_item") is not False and up is not None
        q["flags"] = flags
        out.append(q)

    # 같은 협력사 견적이 2장 이상 → 견적일이 늦은 것만 포함 (처음 한 번만 판단)
    by_sup = {}
    for q in out:
        by_sup.setdefault(q["supplier"], []).append(q)
    for sup, qs in by_sup.items():
        if len(qs) < 2:
            continue
        if not any(q.get("_dedup_done") for q in qs):
            latest = max(qs, key=lambda q: to_date(q.get("quote_date")) or to_date("1900-01-01"))
            for q in qs:
                q["_dedup_done"] = True
                if q is not latest:
                    q["include"] = False
            warnings.append(f"{sup} 견적이 {len(qs)}장입니다. 견적일이 가장 늦은 {latest.get('_file', '')}만 비교에 넣었습니다.")

    for q in out:
        if "요청 품목과 다름" in q["flags"]:
            warnings.append(f"{q['supplier']} ({q.get('_file', '')}): 요청 품목과 다름 — "
                            f"{q.get('item_name', '')} {q.get('spec', '')}. 비교 포함 여부를 표에서 선택하세요.")
        if "단가 직접 입력 필요" in q["flags"]:
            warnings.append(f"{q['supplier']} ({q.get('_file', '')}): 단가를 읽지 못했습니다. 표에서 직접 입력해 주세요.")
        if "금액 불일치" in q["flags"]:
            warnings.append(f"{q['supplier']}: 금액 {q['amount_check']}")
        if "목록에 없는 협력사" in q["flags"]:
            warnings.append(f"{q['supplier']}: 협력사목록에 없는 협력사입니다.")
    return out, warnings


# ---------------------------------------------------------------- 표 ↔ dict

def quotes_to_table(quotes):
    rows = []
    for q in quotes:
        row = {"포함": bool(q.get("include", True))}
        for key, label in FIELD_LABELS.items():
            v = q.get(key)
            if key in BOOL_FIELDS:
                v = BOOL_TEXT.get(v, "미기재")
            elif key == "other_conditions":
                v = " / ".join(v or [])
            elif key in NUM_FIELDS:
                v = None if v is None else float(v)
            else:
                v = "" if v is None else str(v)
            row[label] = v
        row["결제조건 출처"] = q.get("payment_terms_source", "")
        row["확인사항"] = ", ".join(q.get("flags", []))
        row["파일"] = q.get("_file", "")
        rows.append(row)
    cols = ["포함", *FIELD_LABELS.values(), "결제조건 출처", "확인사항", "파일"]
    return pd.DataFrame(rows, columns=cols)


def table_to_quotes(df, previous=None):
    """화면에서 고친 표 → 견적 dict 목록. 근거(evidence) 등 표에 없는 값은 previous에서 이어받는다."""
    prev_by_file = {}
    for q in previous or []:
        prev_by_file.setdefault(q.get("_file", ""), []).append(q)
    out = []
    for _, r in df.iterrows():
        if all(is_blank(r.get(c)) for c in ["협력사", "단가"]):
            continue  # 비어 있는 추가 행
        file_ = to_text(r.get("파일")) or "(직접 입력)"
        base = {}
        if prev_by_file.get(file_):
            base = dict(prev_by_file[file_].pop(0))
        q = {"_file": file_, "evidence": base.get("evidence", []), "_dedup_done": True}
        for key, label in FIELD_LABELS.items():
            v = r.get(label)
            if key in BOOL_FIELDS:
                q[key] = {"예": True, "아니오": False}.get(to_text(v))
            elif key in NUM_FIELDS:
                q[key] = to_number(v)
            elif key == "other_conditions":
                q[key] = [s.strip() for s in to_text(v).split(" / ") if s.strip()]
            else:
                q[key] = to_text(v) or None
        # 직접 입력 행은 품목일치를 따로 고르지 않았으면 같은 품목으로 본다
        if file_ == "(직접 입력)" and q["same_item"] is None:
            q["same_item"] = True
        if to_text(r.get("결제조건 출처")) == "협력사목록" and q["payment_terms"] == base.get("payment_terms"):
            q["payment_terms_source"] = "협력사목록"
        q["include"] = bool(r.get("포함")) if not is_blank(r.get("포함")) else True
        out.append(q)
    return out


# ---------------------------------------------------------------- 3-4 비교 계산

def compare(quotes, request, order_date):
    """포함된 견적만 계산 → 비교표 DataFrame (순위순)."""
    req_qty = request["수량"]
    due = request.get("희망 납기")
    rows = []
    for q in quotes:
        if not q.get("include") or q.get("unit_price") is None:
            continue
        unit = q["unit_price"]
        moq = q.get("moq")
        buy_qty = max(req_qty, moq or 0)
        surplus = buy_qty - req_qty

        if q.get("freight_included") is True:
            freight, freight_note = 0, "포함"
        elif q.get("freight_included") is False and q.get("freight_amount") is not None:
            freight, freight_note = q["freight_amount"], "별도"
        else:
            freight, freight_note = None, "미기재(확인 필요)"

        total = unit * buy_qty + (freight or 0)
        eff_unit = round_half_up(total / req_qty) if req_qty else None

        lead = q.get("lead_time_days")
        arrival = order_date + timedelta(days=int(lead)) if lead is not None else None
        if due is None:
            due_status, due_rank, delay = ("희망 납기 없음" if arrival else "리드타임 미기재"), 0, None
        elif arrival is None:
            due_status, due_rank, delay = "확인 필요", 1, None
        elif arrival <= due:
            due_status, due_rank, delay = "충족", 0, 0
        else:
            delay = (arrival - due).days
            due_status, due_rank = f"{delay}일 지연", 2

        qdate = to_date(q.get("quote_date"))
        validity = q.get("validity_days")
        expiry = qdate + timedelta(days=int(validity)) if qdate and validity is not None else None
        if expiry is None:
            expiry_status = "확인 필요"
        elif expiry < order_date:
            expiry_status = "만료됨"
        elif (expiry - order_date).days <= EXPIRY_WARN_DAYS:
            expiry_status = "만료 임박"
        else:
            expiry_status = "유효"

        rows.append({
            "협력사": q["supplier"],
            "단가": unit,
            "MOQ": moq,
            "실구매수량": buy_qty,
            "잉여수량": surplus,
            "운송비": freight,
            "운송비 조건": freight_note,
            "총액": total,
            "실질단가": eff_unit,
            "리드타임(일)": lead,
            "예상 입고일": arrival,
            "납기 충족": due_status,
            "견적일": qdate,
            "유효기간(일)": validity,
            "견적 만료일": expiry,
            "만료 상태": expiry_status,
            "결제조건": q.get("payment_terms") or "",
            "결제조건 출처": q.get("payment_terms_source", ""),
            "밀시트": BOOL_TEXT.get(q.get("mill_sheet"), "미기재"),
            "금액 검산": q.get("amount_check", ""),
            "기타조건": " / ".join(q.get("other_conditions") or []),
            "확인사항": ", ".join(q.get("flags", [])),
            "_due_rank": due_rank,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values(["_due_rank", "실질단가", "총액"], kind="stable").drop(columns="_due_rank")
    df.insert(0, "순위", range(1, len(df) + 1))
    return df.reset_index(drop=True)


def _mode(values):
    """가장 많이 나온 값 (같으면 큰 값/먼저 나온 값)."""
    vals = [v for v in values if v not in (None, "")]
    if not vals:
        return None
    counts = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    top = max(counts.values())
    cands = [v for v in vals if counts[v] == top]
    return max(cands) if all(isinstance(v, (int, float)) for v in cands) else cands[0]


def build_basis(quotes, request=None, due=None, qty=None):
    """비교 계산의 기준을 만든다 → (basis dict, 안내 목록).

    기본은 수신한 견적서 기준: 품목·규격·단위는 견적서에서 가장 많이 나온 값, 수량은 가장 많이 적힌 견적수량.
    구매요청서를 고른 경우에만 그 값을 참고로 쓴다. due·qty는 화면에서 직접 넣은 값(우선 적용).
    """
    usable = [q for q in quotes if q.get("include", True) and q.get("same_item") is not False] or quotes
    notes = []
    if request:
        basis = {**request, "출처": "구매요청서 " + request["요청번호"], "label": request["요청번호"]}
    else:
        basis = {
            "요청번호": "",
            "품목군": None,
            "품목": _mode([to_text(q.get("item_name")) for q in usable]) or "(품목 미상)",
            "규격": "",
            "수량": _mode([q.get("quoted_qty") for q in usable]),
            "단위": _mode([to_text(q.get("unit")) for q in usable]) or "EA",
            "희망 납기": None,
            "출처": "수신 견적서",
        }
        # 규격은 기준 품목명을 쓴 견적서에서 고른다 (영문·한글 표기가 섞이지 않게)
        same_name = [q for q in usable if to_text(q.get("item_name")) == basis["품목"]] or usable
        basis["규격"] = _mode([to_text(q.get("spec")) for q in same_name]) or ""
        basis["label"] = re.sub(r'[\\/:*?"<>|\s]', "", basis["품목"]) or "견적"
        items = {(to_text(q.get("item_name")), to_text(q.get("spec"))) for q in usable}
        if len(items) > 1:
            notes.append("견적서마다 품목명·규격 표기가 다릅니다: "
                         + " / ".join(f"{q['supplier']}: {to_text(q.get('item_name'))} {to_text(q.get('spec'))}" for q in usable)
                         + " — 같은 물건인지 확인하세요.")
        qtys = {q.get("quoted_qty") for q in usable if q.get("quoted_qty") is not None}
        if len(qtys) > 1:
            notes.append(f"견적수량이 서로 다릅니다({', '.join(format_won(v) for v in sorted(qtys))}). "
                         f"비교 기준 수량은 {format_won(basis['수량'])}로 잡았습니다. 필요하면 화면에서 바꾸세요.")
    if qty:
        basis["수량"] = qty
    if due:
        basis["희망 납기"] = due
    return basis, notes


def quotes_detail(quotes):
    """AI에 보낼 협력사별 견적 조건 (견적서에서 읽은 값 그대로)."""
    out = []
    for q in quotes:
        if not q.get("include"):
            continue
        d = {label: q.get(key) for key, label in FIELD_LABELS.items()}
        for key in BOOL_FIELDS:
            d[FIELD_LABELS[key]] = BOOL_TEXT.get(q.get(key), "미기재")
        d["결제조건 출처"] = q.get("payment_terms_source", "")
        d["확인사항"] = q.get("flags", [])
        out.append(d)
    return out


def comparison_records(df, request):
    """AI에 보낼 비교표 — 날짜는 글자로, 금액은 숫자 그대로."""
    recs = []
    for _, r in df.iterrows():
        rec = {}
        for c, v in r.items():
            if hasattr(v, "strftime"):
                v = format_date(v)
            elif v is None or (isinstance(v, float) and pd.isna(v)):
                v = None
            elif hasattr(v, "item"):
                v = v.item()
            rec[c] = v
        rec["순위(참고·실질단가순, 납기 미충족은 뒤로)"] = rec.pop("순위")
        recs.append(rec)
    return recs


def supplier_info(suppliers, names, item_group=None):
    info = []
    for n in names:
        rows = _supplier_rows(suppliers, n, item_group)
        if rows.empty:
            info.append({"협력사": n, "비고": "협력사목록에 없음"})
            continue
        r = rows.iloc[0]
        info.append({k: r.get(k, "") for k in ["협력사", "담당자", "직급", "결제 조건", "거래 시작", "비고"]})
    return info


def best_values(df):
    """화면·엑셀 강조용: 열 이름 → 가장 유리한 값."""
    if df.empty:
        return {}
    best = {}
    for c in ["단가", "총액", "실질단가", "리드타임(일)"]:
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if not s.empty:
            best[c] = s.min()
    d = df["예상 입고일"].dropna()
    if not d.empty:
        best["예상 입고일"] = d.min()
    e = df["견적 만료일"].dropna()
    if not e.empty:
        best["견적 만료일"] = e.max()
    return best


# ---------------------------------------------------------------- 메일 초안 검사 (T17)

def _amount_patterns(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return []
    n = round_half_up(v)
    if n < 100:  # 작은 숫자(일수 등)는 오탐이 많아 검사하지 않음
        return []
    return [f"{n:,}", str(n)]


def check_email_leaks(strategy, cmp_df, all_suppliers=None):
    """메일 초안에 다른 협력사 이름·금액이 들어 있으면 위반 목록을 돌려준다."""
    names = set(all_suppliers or []) | set(cmp_df["협력사"] if not cmp_df.empty else [])
    amounts = {}
    for _, r in (cmp_df.iterrows() if not cmp_df.empty else []):
        amounts[r["협력사"]] = {p for c in ["단가", "총액", "실질단가", "운송비"] for p in _amount_patterns(r[c])}

    problems = []
    for mail in strategy.get("email_drafts", []):
        to = normalize_supplier(mail.get("supplier"))
        text = f"{mail.get('subject', '')}\n{mail.get('body', '')}"
        flat = normalize_supplier(text)
        own = next((n for n in names if normalize_supplier(n) == to), mail.get("supplier"))
        own_amounts = amounts.get(own, set())
        for other in names:
            if normalize_supplier(other) == to:
                continue
            if normalize_supplier(other) and normalize_supplier(other) in flat:
                problems.append(f"{mail.get('supplier')} 메일에 타사명 '{other}' 포함")
            for p in amounts.get(other, set()) - own_amounts:
                if re.search(rf"(?<![\d,]){re.escape(p)}(?![\d,])", text):
                    problems.append(f"{mail.get('supplier')} 메일에 {other} 견적 금액 '{p}' 포함")
    return problems

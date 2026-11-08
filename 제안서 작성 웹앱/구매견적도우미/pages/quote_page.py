"""메뉴 2 — 견적 분석·협상전략 화면."""
import hashlib
from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st

from core import ai_client, prompts, quote_calc, quote_reader, report
from core.common import (
    DEFAULT_SUPPLIERS, ColumnError, format_date, format_won, load_requests, load_suppliers, request_info,
)

PRIORITIES = ["가격 우선", "납기 우선", "균형"]
DISCLAIMER = "AI 추천 결과입니다. 최종 결정 전에 원본 견적서를 확인하세요."


def _digest(data):
    return hashlib.md5(data).hexdigest()[:12]


# ---------------------------------------------------------------- 분석 단계

def extract_all(files, request, progress):
    """3-1 + 3-2: 파일마다 변환 → AI 추출. (견적 목록, 실패 목록, 미리보기)"""
    quotes, failed, previews = [], [], {}
    for i, (name, data) in enumerate(files, 1):
        progress(f"견적서 읽는 중 ({i}/{len(files)}) — {name}", (i - 1) / (len(files) + 2))
        try:
            ai_input = quote_reader.to_ai_input(name, data)
        except quote_reader.UnsupportedFile as e:
            failed.append((name, str(e)))
            continue
        previews[name] = ai_input["preview"]
        content = ai_input["blocks"] + [{"type": "text", "text": prompts.extract_request_text(request)}]
        try:
            q = ai_client.call_tool(prompts.EXTRACT_SYSTEM, content, prompts.EXTRACT_SCHEMA, effort="medium")
        except ai_client.AIError as e:
            failed.append((name, f"AI 추출 실패: {e}"))
            continue
        q["_file"] = name
        quotes.append(q)
    return quotes, failed, previews


def calc_and_strategy(quotes, request, due, qty, suppliers, order_date, priority, memo, progress):
    """3-3 ~ 3-5. 비교 기준은 수신 견적서에서 정하고(구매요청서는 선택 참고), AI 호출은 전략 1회."""
    progress("비교 계산 중", 0.8)
    quotes, warnings = quote_calc.validate(quotes, suppliers, request or {})
    basis, notes = quote_calc.build_basis(quotes, request, due, qty)
    result = {"quotes": quotes, "warnings": warnings, "basis": basis, "basis_notes": notes,
              "compare": pd.DataFrame(), "strategy": None, "strategy_error": None, "leaks": []}
    if not isinstance(basis["수량"], (int, float)) or basis["수량"] <= 0:
        result["strategy_error"] = "견적서에서 비교 기준 수량을 읽지 못했습니다. ②의 '비교 기준 수량'을 입력한 뒤 [다시 분석]을 눌러 주세요."
        return result
    cmp_df = quote_calc.compare(quotes, basis, order_date)
    result["compare"] = cmp_df
    if cmp_df.empty:
        result["strategy_error"] = "비교할 견적이 없습니다(포함된 견적이 없거나 단가가 비어 있음). 표를 고친 뒤 [다시 분석]을 눌러 주세요."
        return result

    progress("협상전략 작성 중", 0.9)
    names = list(cmp_df["협력사"])
    basis_for_ai = {
        "출처": basis["출처"], "품목": basis["품목"], "규격": basis["규격"],
        "비교_기준_수량": basis["수량"], "단위": basis["단위"],
        "희망_납기": format_date(basis.get("희망 납기")) or "없음(지정 안 함)",
        "발주_예정일": format_date(order_date),
    }
    text = prompts.strategy_request_text(
        basis_for_ai,
        quote_calc.comparison_records(cmp_df, basis),
        quote_calc.quotes_detail(quotes),
        quote_calc.supplier_info(suppliers, names, basis.get("품목군")),
        warnings + notes,
        priority, memo,
    )
    try:
        strategy = ai_client.call_tool(prompts.STRATEGY_SYSTEM, [{"type": "text", "text": text}],
                                       prompts.STRATEGY_SCHEMA, effort="high", max_tokens=16000)
    except ai_client.AIError as e:
        result["strategy_error"] = f"협상전략 작성 실패: {e}"
        return result
    result["strategy"] = strategy
    result["leaks"] = quote_calc.check_email_leaks(strategy, cmp_df, [q["supplier"] for q in quotes])
    return result


# ---------------------------------------------------------------- 화면

st.title("📊 견적 분석·협상전략")
st.caption("협력사에서 받은 견적서를 올리고 [분석]을 누르면, AI가 견적서를 읽고 Python이 비교 계산을 한 뒤 "
           "AI가 견적서 분석 결과를 바탕으로 협상전략을 제안합니다.")

has_key, model = ai_client.status()
if not has_key:
    st.warning(
        "**AI API 키가 설정되지 않았습니다.** 이 메뉴는 Claude API를 사용합니다.\n\n"
        "왼쪽 사이드바의 **AI 설정**에 API 키를 붙여 넣고 [저장]을 누르면 `.env` 파일에 저장되고 바로 연결됩니다. "
        "(키 발급: https://console.anthropic.com)\n\n"
        "제안요청서 작성 메뉴는 키 없이 그대로 쓸 수 있습니다."
    )

try:
    suppliers = load_suppliers(DEFAULT_SUPPLIERS)
except Exception as e:
    st.error(f"협력사목록을 읽을 수 없습니다: {e}")
    st.stop()

# ① 견적서 올리기
st.header("① 견적서 올리기")
quote_files = st.file_uploader("협력사에서 받은 견적서 (여러 장 가능: xlsx, pdf, png, jpg)",
                               accept_multiple_files=True, key="qa_files")
files = [(f.name, f.getvalue()) for f in quote_files or []]
if files:
    st.caption("올린 파일: " + ", ".join(n for n, _ in files))
    for n in [n for n, _ in files if not n.lower().endswith(tuple(quote_reader.SUPPORTED))]:
        st.warning(f"{n}: 지원하지 않는 파일입니다. PDF로 저장 후 올려 주세요.")

# ② 비교 기준 (선택)
st.header("② 비교 기준 (선택)")
st.caption("비워 두면 견적서에서 읽은 품목과 견적수량을 기준으로 비교합니다. 희망 납기를 넣으면 납기 충족 여부도 판정합니다.")
NO_PR = "(연결 안 함 — 견적서만으로 분석)"
request = None
with st.expander("구매요청서 연결 (선택)", expanded=bool(st.session_state.get("qa_pr") not in (None, NO_PR))):
    shared = st.session_state.get("shared_req")
    req_upload = st.file_uploader("구매요청서 (.xlsx)" + (" — 비워 두면 앞서 올린 파일 사용" if shared else ""),
                                  type=["xlsx"], key="qa_req_file")
    if req_upload is not None:
        st.session_state["shared_req"] = {"name": req_upload.name, "bytes": req_upload.getvalue()}
        shared = st.session_state["shared_req"]
    options = [NO_PR]
    labels = {NO_PR: NO_PR}
    requests = None
    if shared:
        try:
            requests = load_requests(BytesIO(shared["bytes"]))
            for _, r in requests.iterrows():
                options.append(r["요청번호"])
                labels[r["요청번호"]] = f"{r['요청번호']} · {r['품목']} ({r['상태']})"
        except ColumnError as e:
            st.error(f"구매요청서에 필수 열이 없습니다: **{', '.join(e.missing)}**")
        except Exception as e:
            st.error(f"구매요청서를 읽을 수 없습니다: {e}")
    pr_no = st.selectbox("참고할 구매요청", options, format_func=labels.get, key="qa_pr")
    if pr_no != NO_PR and requests is not None:
        request = request_info(requests, pr_no)
        if not isinstance(request["수량"], (int, float)) or request["수량"] <= 0:
            st.error(f"{pr_no}의 수량('{request['수량']}')을 숫자로 읽을 수 없어 참고할 수 없습니다.")
            request = None
        else:
            st.caption(f"참고: {request['품목']} ({request['규격']}) · {format_won(request['수량'])} {request['단위']} · "
                       f"희망 납기 {format_date(request['희망 납기']) or '없음'}")

c1, c2 = st.columns(2)
with c1:
    default_due = request["희망 납기"] if request and request.get("희망 납기") else None
    use_due = st.checkbox("희망 납기 지정", value=default_due is not None, key=f"qa_use_due_{pr_no}")
    due = st.date_input("희망 납기", value=default_due or date.today(), format="YYYY-MM-DD",
                        disabled=not use_due, key=f"qa_due_{pr_no}")
    due = due if use_due else None
with c2:
    qty = st.number_input("비교 기준 수량 (비우면 견적서의 견적수량 사용)", min_value=0, step=1, format="%d",
                          value=int(request["수량"]) if request else None, key=f"qa_qty_{pr_no}")
    qty = qty or None

# ③ 분석 설정
st.header("③ 분석 설정")
c1, c2 = st.columns([1, 2])
with c1:
    order_date = st.date_input("발주 예정일", value=date.today(), format="YYYY-MM-DD", key="qa_order_date")
    priority = st.radio("협상 우선순위", PRIORITIES, index=2, horizontal=True, key="qa_priority")
with c2:
    memo = st.text_area("메모 (선택)", placeholder="예: 이번 달 예산 빠듯함 / 경동스틸 지난달 납기 지연", key="qa_memo", height=110)

# ④ 분석
st.header("④ 분석")
signature = (pr_no, tuple(_digest(d) for _, d in files))
analyze = st.button("분석", type="primary", disabled=not (has_key and files), key="qa_analyze",
                    help=None if has_key else "API 키를 먼저 설정해 주세요.")
if not files:
    st.caption("견적서를 올리면 [분석]을 누를 수 있습니다.")

if analyze:
    bar = st.progress(0.0, text="준비 중")

    def progress(text, frac):
        bar.progress(min(frac, 1.0), text=text)

    extracted, failed, previews = extract_all(files, request, progress)
    result = calc_and_strategy(extracted, request, due, qty, suppliers, order_date, priority, memo, progress)
    bar.progress(1.0, text="완료")
    st.session_state["qa"] = {
        "signature": signature, "request": request, "order_date": order_date, "priority": priority,
        "failed": failed, "previews": previews, "version": st.session_state.get("qa", {}).get("version", 0) + 1,
        **result,
    }

qa = st.session_state.get("qa")
if not qa:
    st.caption(DISCLAIMER)
    st.stop()

if qa["signature"] != signature:
    st.warning("견적서 파일이나 연결한 구매요청이 바뀌었습니다. 아래 결과는 이전 분석 기준이니 [분석]을 다시 눌러 주세요.")

b = qa["basis"]
st.markdown(f"**비교 기준** ({b['출처']}): {b['품목']} {b['규격']} · **{format_won(b['수량']) if b['수량'] else '?'} {b['단위']}** · "
            f"희망 납기 {format_date(b.get('희망 납기')) or '없음'} · 발주 예정일 {format_date(qa['order_date'])}")
for n in qa["basis_notes"]:
    st.info(n)

# ⑤ 추출 결과
st.header("⑤ 추출 결과 확인")
for name, err in qa["failed"]:
    st.error(f"{name}: {err}")
if qa["failed"]:
    st.caption("읽지 못한 견적은 아래 표 맨 아래 빈 행에 직접 입력할 수 있습니다.")
for w in qa["warnings"]:
    st.warning(w)

st.caption("AI가 읽은 값입니다. 틀린 값은 고치고 [다시 분석]을 누르세요. (견적서 재추출 없이 계산·전략만 다시 합니다)")
table = quote_calc.quotes_to_table(qa["quotes"])
bool_col = lambda label: st.column_config.SelectboxColumn(label, options=quote_calc.BOOL_OPTIONS)
num_col = lambda label: st.column_config.NumberColumn(label, format="localized")
edited = st.data_editor(
    table,
    key=f"qa_editor_{qa['version']}",
    num_rows="dynamic",
    hide_index=True,
    width="stretch",
    disabled=["결제조건 출처", "확인사항", "파일"],
    column_config={
        "포함": st.column_config.CheckboxColumn("포함", help="체크를 풀면 비교에서 뺍니다.", default=True),
        "품목일치": bool_col("품목일치"), "부가세포함": bool_col("부가세포함"),
        "운송비포함": bool_col("운송비포함"), "밀시트": bool_col("밀시트"),
        "단가": num_col("단가"), "공급가액": num_col("공급가액"), "운송비": num_col("운송비"),
        "견적수량": num_col("견적수량"), "MOQ": num_col("MOQ"),
        "리드타임(일)": num_col("리드타임(일)"), "유효기간(일)": num_col("유효기간(일)"),
        "확인사항": st.column_config.TextColumn("⚠ 확인사항"),
    },
)

with st.expander("원문 근거 보기"):
    for q in qa["quotes"]:
        st.markdown(f"**{q['supplier']}** — `{q.get('_file', '')}`")
        if q.get("same_item_reason"):
            st.caption(f"품목일치 판단: {q['same_item_reason']}")
        ev = q.get("evidence") or []
        if ev:
            st.dataframe(pd.DataFrame(ev).rename(columns={"field": "항목", "text": "원문"}), hide_index=True, width="stretch")
        if q.get("_file") in qa["previews"]:
            st.text_area("변환된 원문", qa["previews"][q["_file"]], height=150, disabled=True,
                         key=f"qa_prev_{qa['version']}_{q.get('_file')}")

if st.button("다시 분석", key="qa_reanalyze", disabled=not has_key,
             help="고친 값과 ②의 비교 기준으로 비교 계산과 협상전략만 다시 만듭니다."):
    bar = st.progress(0.0, text="준비 중")
    new_quotes = quote_calc.table_to_quotes(edited, previous=qa["quotes"])
    result = calc_and_strategy(new_quotes, qa["request"], due, qty, suppliers, order_date, priority, memo,
                               lambda t, f: bar.progress(f, text=t))
    bar.progress(1.0, text="완료")
    qa.update(result, order_date=order_date, priority=priority, version=qa["version"] + 1)
    st.rerun()

# ⑥ 비교표
st.header("⑥ 비교표")
cmp_df = qa["compare"]
if cmp_df.empty:
    st.info("비교할 견적이 없습니다.")
else:
    st.caption(f"발주 예정일 {format_date(qa['order_date'])} 기준 · 실질단가 = 총액 ÷ 비교 기준 수량 · "
               "초록색은 가장 유리한 값, 주황색은 확인이 필요한 값입니다. 순위는 실질단가 순(납기 미충족은 뒤로)입니다.")
    best = quote_calc.best_values(cmp_df)

    def _style(col):
        out = []
        for v in col:
            s = ""
            if col.name in best and v is not None and not (isinstance(v, float) and pd.isna(v)) and v == best[col.name]:
                s = "background-color: #d9f2d9; font-weight: bold"
            if col.name == "납기 충족" and "지연" in str(v):
                s = "background-color: #fce4d6"
            if col.name == "만료 상태" and v in ("만료 임박", "만료됨"):
                s = "background-color: #fce4d6"
            if col.name == "운송비 조건" and "미기재" in str(v):
                s = "background-color: #fce4d6"
            out.append(s)
        return out

    show = cmp_df.drop(columns=["기타조건"])
    fmt = {c: (lambda v: format_won(v) if v is not None and not pd.isna(v) else "-")
           for c in ["단가", "MOQ", "실구매수량", "잉여수량", "운송비", "총액", "실질단가"]}
    fmt.update({c: (lambda v: format_date(v) if v is not None and not pd.isna(v) else "-")
                for c in ["예상 입고일", "견적일", "견적 만료일"]})
    st.dataframe(show.style.apply(_style).format(fmt, na_rep="-"), hide_index=True, width="stretch")

# ⑦ 협상전략
st.header("⑦ 협상전략")
if qa["strategy_error"]:
    st.error(qa["strategy_error"])
strategy = qa["strategy"]
if strategy:
    for p in qa["leaks"]:
        st.error(f"⚠ 메일 초안 점검: {p} — 보내기 전에 꼭 지워 주세요.")
    st.info(strategy.get("summary", ""))
    st.subheader("추천 순위")
    ranking = sorted(strategy.get("ranking", []), key=lambda r: r.get("rank", 99))
    st.dataframe(pd.DataFrame(ranking).rename(columns={"rank": "순위", "supplier": "협력사", "reason": "이유"}),
                 hide_index=True, width="stretch")

    points = strategy.get("supplier_points", [])
    mails = {m.get("supplier"): m for m in strategy.get("email_drafts", [])}
    names = [p.get("supplier") for p in points] + [n for n in mails if n not in [p.get("supplier") for p in points]]
    if names:
        st.subheader("협력사별 협상 포인트")
        for tab, name in zip(st.tabs(names), names):
            with tab:
                sp = next((p for p in points if p.get("supplier") == name), None)
                if sp:
                    a, b, c = st.columns(3)
                    a.markdown("**강점**\n" + "".join(f"\n- {s}" for s in sp.get("strengths", [])))
                    b.markdown("**약점**\n" + "".join(f"\n- {s}" for s in sp.get("weaknesses", [])))
                    c.markdown("**요청할 사항**\n" + "".join(f"\n- {s}" for s in sp.get("requests", [])))
                    st.markdown(f"**목표 조건:** {sp.get('target_terms', '')}")
                    st.caption(f"근거: {sp.get('rationale', '')}")
                m = mails.get(name)
                if m:
                    st.markdown("**협상 요청 메일 초안** (오른쪽 위 아이콘으로 복사)")
                    st.code(f"제목: {m.get('subject', '')}\n\n{m.get('body', '')}", language=None, wrap_lines=True)

    sc = strategy.get("scenario", {})
    st.subheader("협상 시나리오")
    st.markdown(f"1. **1차 협상안** — {sc.get('first_offer', '')}\n"
                f"2. **결렬 시 대안** — {sc.get('fallback', '')}\n"
                f"3. **최종 선택지** — {sc.get('final_options', '')}")
    st.subheader("리스크·확인 필요")
    st.markdown("".join(f"\n- {r}" for r in strategy.get("risks", [])))

# ⑧ 다운로드
if not cmp_df.empty:
    st.header("⑧ 다운로드")
    basis = qa["basis"]
    d1, d2 = st.columns(2)
    xlsx = report.comparison_xlsx(cmp_df, qa["quotes"], basis, qa["order_date"])
    d1.download_button("📥 견적비교표.xlsx", data=xlsx, file_name=report.comparison_filename(basis["label"], date.today()),
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", on_click="ignore",
                       key="qa_dl_xlsx")
    if strategy:
        docx = report.strategy_docx(basis, cmp_df, strategy, qa["order_date"], qa["priority"],
                                    qa["warnings"] + qa["basis_notes"])
        d2.download_button("📥 협상전략.docx", data=docx, file_name=report.strategy_filename(basis["label"], date.today()),
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                           on_click="ignore", key="qa_dl_docx")
    else:
        d2.caption("협상전략이 만들어지면 워드 보고서를 받을 수 있습니다.")

st.divider()
st.markdown(f"**⚠ {DISCLAIMER}**")

"""외주명세서 대사 웹앱 (Streamlit).

판독 결과·리포트는 이 브라우저 세션 메모리에만 있고 PC·서버에 저장하지 않는다.
남기려면 [엑셀 내려받기] 또는 [판독 결과 JSON 내려받기]를 쓴다.
"""
import hashlib
import io
import os
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from core.erp_loader import ErpFormatError, load_erp
from core.normalize import fmt_won
from core.pdf_reader import (detect_row_bands, dump_reading_json, highlight_page, load_reading_json, make_client,
                             page_count, read_pdf_ai, render_page, rows_to_pages)
from core.pipeline import build_statement, run_reconcile, validate
from core.report import reply_text, to_excel
from core.vendors import detect_by_filename, detect_by_name, load_vendors, vendor_name

APP_DIR = Path(__file__).resolve().parent
load_dotenv(APP_DIR / ".env")

st.set_page_config(page_title="외주명세서 대사", page_icon="📑", layout="wide")
st.markdown("""<style>
.block-container {padding-top: 1.6rem;}
div[data-testid="stMetricValue"] {font-size: 1.6rem;}
</style>""", unsafe_allow_html=True)

ss = st.session_state
ss.setdefault("files", {})          # 파일명 → 판독 페이지 목록 (원본)
ss.setdefault("read_cache", {})     # PDF 해시 → 판독 페이지 목록 (같은 파일 재판독 방지)
ss.setdefault("rows", None)         # 작업용 판독 표 (수정 반영)
ss.setdefault("page_info", None)
ss.setdefault("result", None)
ss.setdefault("editor_ver", 0)
ss.setdefault("read_errors", [])

vendors = load_vendors()
VCODES = [v["code"] for v in vendors]


def vlabel(code):
    return f"{code} · {vendor_name(code, vendors)}" if code else "(업체 선택)"


@st.cache_data(show_spinner=False, max_entries=8)
def cached_erp(data: bytes):
    return load_erp(io.BytesIO(data))


@st.cache_data(show_spinner=False, max_entries=64)
def cached_page_png(key: str, _pdf: bytes, page: int) -> bytes:
    return render_page(_pdf, page, long_edge=1400)


@st.cache_data(show_spinner=False, max_entries=64)
def cached_bands(key: str, _pdf: bytes, page: int, min_rows: int):
    return detect_row_bands(_pdf, page, min_rows)


def sha(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()


# ================================================================ 사이드바
with st.sidebar:
    st.header("📑 외주명세서 대사")
    erp_file = st.file_uploader("① ERP 외주입고이력 (엑셀)", type=["xlsx", "xls"])
    pdf_files = st.file_uploader("② 거래명세서 PDF (여러 개)", type=["pdf"], accept_multiple_files=True)
    pdfs = {f.name: f.getvalue() for f in (pdf_files or [])}

    erp = None
    if erp_file:
        try:
            erp = cached_erp(erp_file.getvalue())
            st.caption(f"ERP {len(erp)}행 · {erp['업체코드'].nunique()}개 업체 · "
                       f"{erp['일자'].min()} ~ {erp['일자'].max()}")
        except ErpFormatError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"ERP 엑셀을 읽지 못했습니다: {e}")

    # ---- 업체 인식
    names = list(dict.fromkeys(list(pdfs) + list(ss.files)))
    vmap = {}
    if names:
        st.markdown("**업체 인식**")
        for fn in names:
            auto = detect_by_filename(fn, vendors)
            if not auto and fn in ss.files and ss.files[fn]:
                auto = detect_by_name(ss.files[fn][0].get("supplier_name", ""), vendors)
            opts = [""] + VCODES
            pick = st.selectbox(fn, opts, index=opts.index(auto) if auto in opts else 0, format_func=vlabel,
                                key=f"vsel_{fn}")
            vmap[fn] = pick
        if any(not v for v in vmap.values()):
            st.warning("업체를 찾지 못한 파일이 있습니다. 드롭다운에서 지정해 주세요.")

    # ---- 판독 방식
    st.markdown("**③ 판독**")
    env_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    mode = st.radio("판독 방식", ["AI 판독 (Claude API)", "판독 파일 불러오기 (JSON)"],
                    index=0 if env_key else 1, label_visibility="collapsed")
    api_key, reading_json = env_key, None
    if mode.startswith("AI"):
        if not env_key:
            api_key = st.text_input("Claude API 키", type="password",
                                    help=".env 파일에 ANTHROPIC_API_KEY 를 넣어 두면 매번 입력하지 않아도 됩니다. "
                                         "여기 입력한 키는 저장되지 않습니다.").strip()
        model = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
        effort = os.getenv("CLAUDE_EFFORT", "high")
        st.caption(f"모델 {model} · 페이지당 1회 호출 · 같은 파일은 다시 호출하지 않음")
    else:
        reading_json = st.file_uploader("판독 결과 JSON", type=["json"],
                                        help="이 앱에서 내려받은 판독 결과(수정본)나 테스트용 정답 파일 "
                                             "(tests/sample_202609/판독정답_202609.json)")

    start_read = st.button("판독 시작", type="primary", width="stretch")
    with st.expander("대사 설정"):
        date_window = st.number_input("일자 불일치 허용 범위(일)", 1, 31, 7)
    run_btn = st.button("대사 실행", width="stretch", disabled=ss.rows is None or erp is None)
    progress_box = st.empty()
    st.caption("🔒 판독 결과와 리포트는 저장되지 않습니다. 창을 닫으면 사라지니 필요하면 엑셀로 내려받으세요.")


# ================================================================ 동작
def default_year():
    if erp is not None and erp["일자"].notna().any():
        return Counter(d[:4] for d in erp["일자"].dropna()).most_common(1)[0][0]
    return None


def rebuild_from_files():
    yr = default_year()
    rows, info = build_statement(ss.files, vmap, vendors, int(yr) if yr else None)
    ss.rows, ss.page_info = rows, info
    ss.editor_ver += 1


def apply_vendor_map():
    """사이드바에서 바꾼 업체 지정을 작업 표에 반영."""
    if ss.rows is None:
        return
    for fn, code in vmap.items():
        m = ss.rows["파일"] == fn
        if m.any() and (ss.rows.loc[m, "업체코드"] != code).any():
            ss.rows.loc[m, "업체코드"] = code
            ss.rows.loc[m, "업체"] = vendor_name(code, vendors) if code else ""
            ss.page_info.loc[ss.page_info["파일"] == fn, "업체코드"] = code
            ss.result = None


def do_reconcile():
    apply_vendor_map()
    if erp is None or ss.rows is None:
        return
    if (ss.rows["업체코드"] == "").any():
        st.sidebar.error("업체가 지정되지 않은 파일이 있어 대사할 수 없습니다.")
        return
    ss.result = run_reconcile(ss.rows, ss.page_info, erp, vendors, int(date_window))


if start_read:
    ss.read_errors = []
    if mode.startswith("AI"):
        if not pdfs:
            st.sidebar.error("명세서 PDF를 먼저 올려 주세요.")
        elif not api_key:
            st.sidebar.error("Claude API 키가 필요합니다.")
        else:
            client = make_client(api_key)
            total = sum(page_count(b) for b in pdfs.values())
            done = [0]
            bar = progress_box.progress(0.0, text="판독 준비 중…")

            def tick(fn, p, n):
                done[0] += 1
                bar.progress(done[0] / total, text=f"판독 중 {done[0]}/{total} 페이지 · {fn} {p}p")

            files = {}
            for fn, b in pdfs.items():
                h = sha(b)
                if h in ss.read_cache:
                    files[fn] = ss.read_cache[h]
                    for p in range(1, len(files[fn]) + 1):
                        tick(fn, p, len(files[fn]))
                    continue
                code = vmap.get(fn)
                hint = next((v["reading_notes"] for v in vendors if v["code"] == code), "")
                try:
                    pages = read_pdf_ai(client, b, fn, model=model, effort=effort, vendor_hint=hint, on_page_done=tick)
                except Exception as e:
                    ss.read_errors.append(f"{fn}: {e}")
                    continue
                if not any(p.get("error") for p in pages):
                    ss.read_cache[h] = pages
                files[fn] = pages
                for p in pages:
                    if p.get("error"):
                        ss.read_errors.append(f"{fn} {p['page']}페이지: {p['error']}")
            bar.empty()
            ss.files = files
    else:
        if not reading_json:
            st.sidebar.error("판독 결과 JSON 파일을 올려 주세요.")
        else:
            try:
                ss.files = load_reading_json(reading_json.getvalue())
            except Exception as e:
                st.sidebar.error(f"판독 파일을 읽지 못했습니다: {e}")
    if ss.files:
        for fn in ss.files:  # 새로 생긴 파일의 업체 자동 인식
            if fn not in vmap or not vmap[fn]:
                vmap[fn] = detect_by_filename(fn, vendors) or detect_by_name(
                    (ss.files[fn] or [{}])[0].get("supplier_name", ""), vendors) or ""
        rebuild_from_files()
        ss.result = None
        do_reconcile()
        st.rerun()

if run_btn:
    do_reconcile()

apply_vendor_map()

# ================================================================ 본문
for err in ss.read_errors:
    st.error(f"판독 실패 — {err}")

if ss.rows is None:
    st.title("외주명세서 대사")
    st.markdown("""
왼쪽에서 **① ERP 엑셀**과 **② 명세서 PDF**를 올린 뒤 **판독 시작** 버튼을 누르세요.
판독이 끝나면 대사가 자동으로 실행됩니다.

| 탭 | 내용 |
|---|---|
| 업체별 요약 | 업체별 명세서·ERP 합계, 차이, 불일치 건수, 판정 · 엑셀 내려받기 |
| 불일치 리포트 | 틀린 행을 업체·파일·페이지·행·항목까지 표시, 행을 고르면 PDF 페이지에 위치 표시 |
| 판독 결과 확인 | AI가 읽은 표를 확인·수정 (검산 실패 행 ⚠) 후 다시 대사 |

API 키가 없으면 판독 방식을 **판독 파일 불러오기**로 바꾸고
`tests/sample_202609/판독정답_202609.json` 을 올리면 9월 샘플로 동작을 확인할 수 있습니다.
""")
    st.stop()

res = ss.result
tab1, tab2, tab3 = st.tabs(["📊 업체별 요약", "🔍 불일치 리포트", "✏️ 판독 결과 확인"])


def won(v):
    return "" if v is None or pd.isna(v) else f"{v:,.0f}"


# ---------------------------------------------------------------- 탭 1
with tab1:
    if res is None:
        st.info("ERP 엑셀을 올리고 **대사 실행** 버튼을 누르면 요약이 나옵니다." if erp is None
                else "**대사 실행** 버튼을 눌러 주세요.")
    else:
        sm = res.summary
        done = sm[sm["판정"] != "명세서 없음"]
        n_bad = int(res.collapsed["참고"].eq(False).sum()) if not res.collapsed.empty else 0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("전체 차액 (명세서−ERP)", f"{done['차이(명세서−ERP)'].sum():+,.0f}원")
        c2.metric("불일치 업체", f"{(done['판정'] == '불일치').sum()} / {len(done)}개")
        c3.metric("불일치 건수", f"{n_bad}건", help="묶음은 1건으로 셉니다. 손글씨 정정 등 참고 항목은 제외")
        c4.metric("명세서 합계", f"{done['명세서 공급가액'].sum():,.0f}원",
                  help=f"ERP 합계 {done['ERP 공급가액'].sum():,.0f}원")

        def style_summary(row):
            if row["판독 검산"] == "확인 필요":
                return ["background-color: #fff2b3"] * len(row)
            if row["판정"] == "불일치":
                return ["color: #b00020"] * len(row)
            if row["판정"] == "일치":
                return ["color: #1b7f3b"] * len(row)
            return ["color: #888"] * len(row)

        money = ["명세서 공급가액", "ERP 공급가액", "차이(명세서−ERP)", "명세서 세액(참고)", "ERP 부가세(참고)"]
        st.dataframe(sm.style.apply(style_summary, axis=1).format({c: won for c in money}),
                     hide_index=True, width="stretch")
        st.caption("노란색 = 판독 검산 실패(‘판독 결과 확인’ 탭에서 확인). 세액은 업체 반올림·ERP 절사 차이가 있어 "
                   "비교하지 않고 참고로만 표시합니다.")
        if (sm["판정"] == "명세서 없음").any():
            miss = ", ".join(sm.loc[sm["판정"] == "명세서 없음", "업체"])
            st.warning(f"ERP에는 있지만 명세서를 올리지 않은 업체: {miss}")

        st.download_button("📥 엑셀 내려받기 (요약·불일치 리포트·판독 원본)",
                           to_excel(res.summary, res.issues, res.rows),
                           file_name="외주대사_결과.xlsx", type="primary",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        with st.expander("판독 합계 검산 (명세서 인쇄 합계 = 행 합계)"):
            t = res.totals.copy()
            st.dataframe(t.style.apply(lambda r: ["background-color: #fff2b3" if r["결과"] != "일치" else ""] * len(r),
                                       axis=1).format({"행합계": won, "인쇄합계": won, "차이": won}),
                         hide_index=True, width="stretch")

        with st.expander("업체 회신용 문구 초안"):
            period = ""
            if erp is not None and erp["일자"].notna().any():
                d = erp["일자"].dropna().min()
                period = f"{d[:4]}년 {int(d[5:7])}월분"
            vend_with = [c for c in sm["업체코드"] if not res.collapsed.empty
                         and (~res.collapsed.loc[res.collapsed["업체코드"] == c, "참고"]).any()]
            if not vend_with:
                st.write("확인 요청할 불일치가 없습니다.")
            for c in vend_with:
                nm = vendor_name(c, vendors)
                st.text_area(nm, reply_text(nm, res.collapsed[res.collapsed["업체코드"] == c], period), height=220,
                             key=f"reply_{c}")


# ---------------------------------------------------------------- 탭 2
def show_page(fn: str, page: int, ref_orders: list[int], ys: list):
    """PDF 페이지와 강조 띠."""
    if fn not in pdfs:
        st.info(f"'{fn}' PDF가 올라와 있지 않아 페이지를 표시할 수 없습니다. 사이드바에 PDF를 올려 주세요.")
        return
    b = pdfs[fn]
    key = sha(b)
    n_rows = int(((ss.rows["파일"] == fn) & (ss.rows["페이지"] == page)).sum())
    bands = cached_bands(key, b, page, max(n_rows, 1))
    marks, missing = [], False
    for o, y in zip(ref_orders, ys):
        if o < len(bands) and len(bands) >= n_rows:
            marks.append(bands[o])
        elif y is not None and not pd.isna(y):
            marks.append((max(0.0, y - 0.016), min(1.0, y + 0.016)))
        else:
            missing = True
    png = cached_page_png(key, b, page)
    st.image(highlight_page(png, marks) if marks else png, width="stretch")
    if missing:
        st.caption("행 위치를 찾지 못해 페이지만 표시했습니다. 행번호를 보고 확인해 주세요.")


with tab2:
    if res is None:
        st.info("대사를 실행하면 불일치 리포트가 나옵니다.")
    elif res.collapsed.empty:
        st.success("불일치가 없습니다. 모든 업체의 명세서와 ERP가 일치합니다.")
    else:
        f1, f2, f3 = st.columns([3, 3, 1.4])
        all_v = list(dict.fromkeys(res.collapsed["업체"]))
        all_t = list(dict.fromkeys(res.collapsed["유형"]))
        sel_v = f1.multiselect("업체", all_v, placeholder="전체 업체")
        sel_t = f2.multiselect("유형", all_t, placeholder="전체 유형")
        expand = f3.toggle("묶음 펼치기", help="같은 발주번호의 반복 단가 오류를 한 줄씩 펼쳐 봅니다")
        src = res.issues.assign(건수=1) if expand else res.collapsed
        mask = pd.Series(True, index=src.index)
        if sel_v:
            mask &= src["업체"].isin(sel_v)
        if sel_t:
            mask &= src["유형"].isin(sel_t)
        view = src[mask].reset_index(drop=True)

        left, right = st.columns([1.35, 1])
        with left:
            cols = ["업체", "유형", "위치", "일자", "품번", "명세서 값", "ERP 값", "차액", "건수", "파일", "ERP 입고번호",
                    "조치", "비고"]
            disp = view[cols]
            event = st.dataframe(
                disp.style.apply(lambda r: ["color: #888"] * len(r) if view.loc[r.name, "참고"] else [""] * len(r),
                                 axis=1).format({"차액": lambda v: f"{v:+,.0f}"}),
                hide_index=True, width="stretch", height=min(38 * (len(disp) + 1) + 4, 640),
                on_select="rerun", selection_mode="single-row", key=f"report_{expand}_{len(view)}",
                column_config={"위치": st.column_config.TextColumn(width="medium"),
                               "명세서 값": st.column_config.TextColumn(width="medium"),
                               "ERP 값": st.column_config.TextColumn(width="medium")})
            st.caption(f"{len(view)}건 · 행을 클릭하면 오른쪽에 명세서 페이지가 열립니다. 회색 = 참고 항목")
        with right:
            picked = event.selection.rows if event and event.selection else []
            if not picked:
                st.info("왼쪽 표에서 행을 선택하세요.")
            else:
                r = view.iloc[picked[0]]
                st.markdown(f"#### {r['업체']} · {r['유형']}")
                st.markdown(f"**{r['파일'] or '명세서에 해당 행 없음'}** {r['위치']}  \n"
                            f"일자 {r['일자']} · 품번 {r['품번']}" + (f" · 발주 {r['발주번호']}" if r["발주번호"] else ""))
                st.markdown(
                    "| 명세서 | ERP | 차액 (명세서−ERP) |\n|---|---|---:|\n"
                    f"| **{r['명세서 값']}** | **{r['ERP 값']}** | **{fmt_won(r['차액'])}** |")
                st.markdown(f"**틀린 항목**: {r['틀린 항목']} · **조치**: {r['조치']}"
                            + (f"  \n**비고**: {r['비고']}" if r["비고"] else ""))
                if r["erp_ids"]:
                    er = erp[erp["erp_id"].isin(r["erp_ids"])][["입고일자", "입고번호", "발주번호", "품번", "품명",
                                                               "입고수량", "단가", "공급가액"]]
                    with st.expander(f"ERP 입고 행 {len(er)}건", expanded=not r["refs"]):
                        st.dataframe(er.assign(입고일자=er["입고일자"].astype(str).str[:10]).style.format(
                            {"단가": won, "공급가액": won, "입고수량": won}), hide_index=True, width="stretch")
                refs = r["refs"]
                if refs:
                    pages = list(dict.fromkeys((x["파일"], x["페이지"]) for x in refs))
                    if len(pages) > 1:
                        pi = st.radio("페이지", range(len(pages)), horizontal=True,
                                      format_func=lambda i: f"{pages[i][1]}페이지", key=f"pg_{picked[0]}")
                    else:
                        pi = 0
                    fn, pg = pages[pi]
                    sel = [x for x in refs if x["파일"] == fn and x["페이지"] == pg]
                    st.caption(f"{fn} · {pg}페이지 · " + ", ".join(f"{x['행번호']}행" for x in sel))
                    show_page(fn, pg, [x["순서"] for x in sel], [x["위치y"] for x in sel])


# ---------------------------------------------------------------- 탭 3
EDIT_COLS = ["페이지", "행번호", "일자", "발주번호", "품번", "품명", "수량", "단가", "공급가액", "세액", "반품", "정정",
             "정정내용", "비고", "검산"]

with tab3:
    rows_v, totals_v, _ = validate(ss.rows, ss.page_info)
    files_sorted = sorted(ss.rows["파일"].unique(), key=lambda f: (ss.rows.loc[ss.rows["파일"] == f, "업체코드"].iloc[0], f))
    bad_files = set(rows_v.loc[rows_v["검산"] != "", "파일"]) | set(totals_v.loc[totals_v["결과"] != "일치", "파일"])
    if ss.get("tab3_file") not in files_sorted:
        ss.pop("tab3_file", None)
    fn = st.selectbox("파일", files_sorted, key="tab3_file",
                      format_func=lambda f: f"{f} ({vendor_name(vmap.get(f, ''), vendors) if vmap.get(f) else '업체 미지정'})")
    if bad_files:
        st.caption("⚠️ 검산 확인이 필요한 파일: " + ", ".join(sorted(bad_files)))
    if fn in bad_files:
        st.warning("이 파일은 판독 검산에 실패한 곳이 있습니다. 아래 노란색 행·합계를 PDF와 비교해 주세요.")
    else:
        st.success("이 파일은 판독 검산(수량×단가, 인쇄 합계)을 모두 통과했습니다.")
    sub = rows_v[rows_v["파일"] == fn]
    tt = totals_v[totals_v["파일"] == fn]
    info = ss.page_info[ss.page_info["파일"] == fn]
    m1, m2, m3 = st.columns(3)
    m1.metric("판독 행", f"{len(sub)}행 / {info['페이지'].nunique()}페이지")
    m2.metric("행 합계", f"{sub['공급가액'].fillna(0).sum():,.0f}원")
    printed = tt["인쇄합계"].dropna().sum() if tt["인쇄합계"].notna().any() else None
    m3.metric("인쇄 합계", f"{printed:,.0f}원" if printed is not None else "없음",
              delta=None if (tt["결과"] == "일치").all() else "합계 불일치", delta_color="inverse")
    for _, p in info.iterrows():
        if p["오류"]:
            st.error(f"{p['페이지']}페이지 판독 실패: {p['오류']}")
        if p["판독메모"]:
            st.caption(f"AI 메모 ({p['페이지']}p): {p['판독메모']}")
    if (tt["결과"] != "일치").any():
        st.dataframe(tt.style.apply(lambda r: ["background-color: #fff2b3"] * len(r), axis=1)
                     .format({"행합계": won, "인쇄합계": won, "차이": won}), hide_index=True, width="stretch")
    badrows = sub[sub["검산"] != ""]
    if len(badrows):
        st.markdown("**검산 실패 행**")
        st.dataframe(badrows[EDIT_COLS].style.apply(lambda r: ["background-color: #fff2b3"] * len(r), axis=1),
                     hide_index=True, width="stretch")

    ed_col, pdf_col = st.columns([1.5, 1])
    with ed_col:
        with st.form(f"edit_{fn}_{ss.editor_ver}"):
            base = sub[EDIT_COLS].copy()
            base["검산"] = base["검산"].map(lambda m: f"⚠️ {m}" if m else "")
            edited = st.data_editor(
                base, hide_index=True, width="stretch", num_rows="dynamic", height=min(36 * (len(base) + 2), 720),
                key=f"editor_{fn}_{ss.editor_ver}",
                column_config={
                    "페이지": st.column_config.NumberColumn(width="small", min_value=1, step=1),
                    "행번호": st.column_config.NumberColumn(width="small", min_value=1, step=1),
                    "일자": st.column_config.TextColumn(help="YYYY-MM-DD"),
                    "수량": st.column_config.NumberColumn(format="localized"),
                    "단가": st.column_config.NumberColumn(format="localized"),
                    "공급가액": st.column_config.NumberColumn(format="localized"),
                    "세액": st.column_config.NumberColumn(format="localized"),
                    "검산": st.column_config.TextColumn(disabled=True, width="medium"),
                })
            saved = st.form_submit_button("수정 반영 후 다시 대사", type="primary")
        if saved:
            keep = ss.rows[ss.rows["파일"] != fn]
            old = ss.rows[ss.rows["파일"] == fn]
            new = edited.drop(columns=["검산"]).copy()
            for c in ["업체코드", "업체", "파일"]:
                new[c] = old[c].iloc[0] if len(old) else ""
            new["파일"] = fn
            new["원본일자"] = new.index.map(lambda i: old["원본일자"].get(i, "") if i in old.index else "")
            new["위치y"] = new.index.map(lambda i: old["위치y"].get(i) if i in old.index else None)
            new["페이지"] = new["페이지"].fillna(1).astype(int)
            new["반품"] = new["반품"].fillna(False).astype(bool)
            new["정정"] = new["정정"].fillna(False).astype(bool)
            for c in ["일자", "발주번호", "품번", "품명", "정정내용", "비고"]:
                new[c] = new[c].fillna("").astype(str)
            new["일자"] = new["일자"].map(lambda s: s or None)
            # 반품 표시와 수량·금액 부호를 맞춘다
            for c in ["수량", "공급가액", "세액"]:
                new[c] = [(-abs(v) if rt else v) if v is not None and not pd.isna(v) else v
                          for v, rt in zip(new[c], new["반품"])]
            new = new.sort_values(["페이지", "행번호"], kind="stable")
            new["페이지내순서"] = new.groupby("페이지").cumcount()
            new["행번호"] = new["행번호"].fillna(0).astype(int)
            ss.rows = pd.concat([keep, new[ss.rows.columns.drop(["품번키", "stmt_id"], errors="ignore")]],
                                ignore_index=True)
            missing_pages = set(new["페이지"]) - set(ss.page_info.loc[ss.page_info["파일"] == fn, "페이지"])
            for p in missing_pages:
                ss.page_info.loc[len(ss.page_info)] = {"파일": fn, "페이지": p, "업체코드": vmap.get(fn, ""),
                                                       "공급자상호": "", "기간표기": "", "명세서번호": "",
                                                       "인쇄공급가액합계": None, "인쇄세액합계": None, "판독메모": "", "오류": ""}
            ss.editor_ver += 1
            do_reconcile()
            st.rerun()
        st.caption("숫자를 고친 뒤 '수정 반영 후 다시 대사' 버튼을 누르세요. 표 아래 빈 줄에 행을 추가할 수 있습니다. "
                   "반품 행은 '반품'을 체크하면 수량·금액이 음수로 바뀝니다.")
        st.download_button("💾 판독 결과(수정본) JSON 내려받기",
                           dump_reading_json(rows_to_pages(ss.rows, ss.page_info)),
                           file_name="판독결과.json", mime="application/json",
                           help="다음에 '판독 파일 불러오기'로 올리면 AI를 다시 부르지 않고 이어서 작업할 수 있습니다.")
    with pdf_col:
        pgs = sorted(info["페이지"].unique())
        if pgs:
            pg = st.selectbox("명세서 페이지", pgs, format_func=lambda p: f"{p}페이지", key=f"tab3pg_{fn}")
            show_page(fn, int(pg), [], [])

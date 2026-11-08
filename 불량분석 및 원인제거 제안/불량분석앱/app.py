"""불량 분석 및 원인제거 방안 제안 — Streamlit 앱 (사이드바 + 탭 4개)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

import config
from core import aggregate, ai_advisor, analyze, loader, report

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / "sample_data"
load_dotenv(ROOT / ".env", override=True)

st.set_page_config(page_title="불량 분석 · 원인제거 제안", page_icon="📊", layout="wide")
st.markdown("""
<style>
.kpi {border:1px solid rgba(128,128,128,.25); border-radius:10px; padding:14px 16px; height:100%;}
.kpi .lbl {font-size:.85rem; opacity:.7;}
.kpi .val {font-size:1.6rem; font-weight:700; margin-top:2px;}
.kpi .dlt {font-size:.85rem; margin-top:2px;}
.up {color:#d62728;} .down {color:#1f77b4;} .flat {opacity:.6;}
</style>""", unsafe_allow_html=True)

COLORS = ["#2a6fdb", "#e4572e", "#17a398", "#f3a712", "#8e5ad6", "#6c757d"]


def arrow(v: float, unit: str, fmt: str = "{:+.2f}", neutral: bool = False) -> str:
    """상승 빨강 ▲ / 하락 파랑 ▼ (불량 지표는 상승이 나쁨). neutral이면 회색."""
    if v is None:
        return '<span class="flat">전주 없음</span>'
    cls, a = ("up", "▲") if v > 0 else ("down", "▼") if v < 0 else ("flat", "—")
    if neutral:
        cls = "flat"
    return f'<span class="{cls}">{a} {fmt.format(v)}{unit}</span>'


def kpi_card(col, label, value, delta_html):
    col.markdown(f'<div class="kpi"><div class="lbl">{label}</div><div class="val">{value}</div>'
                 f'<div class="dlt">{delta_html}</div></div>', unsafe_allow_html=True)


def fmt_rate_table(df: pd.DataFrame) -> pd.DataFrame:
    return df.map(lambda v: f"{v:.2f}%" if pd.notna(v) else "-")


# ── 사이드바: 입력 ───────────────────────────────────────────
ai = ai_advisor.api_settings()
with st.sidebar:
    st.header("📂 입력")
    use_sample = st.toggle("샘플 데이터 사용 (W38~W42)", value=False,
                           help="sample_data 폴더의 파일로 바로 실행합니다. 업로드한 파일보다 우선합니다.")
    up_prod = st.file_uploader("① 생산수량 (xlsx·csv)", type=["xlsx", "xls", "csv"], disabled=use_sample)
    up_def = st.file_uploader("② 불량기록 (여러 개 가능)", type=["xlsx", "xls", "csv"],
                              accept_multiple_files=True, disabled=use_sample)
    up_rep = st.file_uploader("③ 지난주 리포트 (docx, 선택)", type=["docx"], disabled=use_sample)
    up_memo = st.file_uploader("④ 현장 메모 (md·txt, 선택)", type=["md", "txt"], disabled=use_sample)
    memo_paste = st.text_area("현장 메모 붙여넣기", height=120,
                              placeholder="메모 파일 대신 여기에 붙여넣어도 됩니다. 둘 다 있으면 합쳐서 씁니다.")

if use_sample:
    prod_src = SAMPLE / "생산수량_주별.xlsx"
    def_src = sorted((SAMPLE / "불량기록").glob("*.xlsx"))
    rep_src = SAMPLE / "지난주_불량분석리포트_W41.docx"
    memo_text = loader.read_text(SAMPLE / "참고_이번주_현장메모.md")
else:
    prod_src, def_src, rep_src = up_prod, up_def, up_rep
    memo_text = loader.read_text(up_memo) if up_memo else ""
if memo_paste.strip():
    memo_text = (memo_text + "\n\n" + memo_paste).strip()

st.title("📊 불량 분석 및 원인제거 방안 제안")

if not prod_src or not def_src:
    st.info("왼쪽에서 **생산수량** 1개와 **불량기록** 파일(여러 개 가능)을 올리세요. "
            "바로 확인하려면 **샘플 데이터 사용**을 켜세요.")
    with st.sidebar:
        st.divider()
        st.caption("AI 연결: " + ("✅ 연결됨" if ai["has_key"] else "⚠️ 키 없음"))
    st.stop()

# ── 불러오기·검증 ────────────────────────────────────────────
prod_res = loader.load_production(prod_src)
if prod_res.errors:
    for e in prod_res.errors:
        st.error(e)
    st.stop()
prod = prod_res.data
def_res = loader.load_defects(def_src, prod)
for e in def_res.errors:
    st.error(e)
if def_res.data.empty:
    st.stop()

raw = def_res.data
last_report = None
if rep_src:
    try:
        last_report = loader.load_last_report(rep_src)
    except Exception as e:  # noqa: BLE001
        st.warning(f"지난주 리포트를 읽지 못했습니다: {e}")

bad_rows = raw[raw["문제"] != ""]
with st.expander(f"✅ 입력 검증 — 불량기록 {len(raw)}행 · 문제 {len(bad_rows)}행 · 경고 {len(def_res.warnings) + len(prod_res.warnings)}건",
                 expanded=bool(len(bad_rows) or def_res.warnings or def_res.errors)):
    files_summary = raw.groupby("원본파일").agg(행수=("불량수량", "size")).reset_index()
    st.dataframe(files_summary, hide_index=True)
    for w in prod_res.warnings + def_res.warnings:
        st.warning(w)
    exclude = True
    if len(bad_rows):
        st.error(f"문제가 있는 행 {len(bad_rows)}개")
        st.dataframe(bad_rows[["원본파일", "원본행", "문제", "발생일", "라인", "품번", "불량유형", "불량수량"]],
                     hide_index=True)
        exclude = st.checkbox("문제 행을 집계에서 제외", value=True)
    nonstd = loader.non_standard_actions(raw)
    if not nonstd.empty:
        st.caption("비표준 조치 값 (‘기타’로 묶어 집계, 원문 보존)")
        st.dataframe(nonstd, hide_index=True)

defects = raw[raw["문제"] == ""].copy() if exclude else raw.copy()
if not exclude:  # 제외하지 않으면 계산 가능한 행만 남김
    defects = defects[defects["불량수량"].notna() & (defects["주차"] != "")]
defects["불량수량"] = defects["불량수량"].astype(int)
defects_valid = defects[defects["라인"].isin(prod["라인"]) & defects["주차"].isin(prod["주차"])]

wl = aggregate.week_line(defects_valid, prod)
all_weeks = aggregate.sorted_weeks(defects_valid["주차"])
if not all_weeks:
    st.error("집계할 수 있는 불량기록이 없습니다.")
    st.stop()

with st.sidebar:
    st.divider()
    st.header("⚙️ 분석 설정")
    week = st.selectbox("분석 주차", all_weeks[::-1], index=0)
    n_weeks = st.number_input("비교 주 수", min_value=2, max_value=max(2, len(all_weeks)),
                              value=min(config.DEFAULT_COMPARE_WEEKS, max(2, len(all_weeks))))
    st.divider()
    if ai["has_key"]:
        st.success(f"AI 연결됨 · {ai['model']}")
    else:
        st.warning("AI 키 없음\n\n`.env`에 ANTHROPIC_API_KEY를 넣으세요.")

weeks = aggregate.window(all_weeks, week, int(n_weeks))
k = aggregate.kpi(wl, week)
type_qty = aggregate.type_trend(defects_valid, weeks, "qty")
type_cnt = aggregate.type_trend(defects_valid, weeks, "count")
rp = aggregate.rate_pivot(wl, weeks)
workdays = prod.groupby("주차")["근무일수"].max().to_dict()
changes = analyze.detect_changes(defects_valid, wl, week, weeks)
prod_dates = prod.loc[prod["주차"] == week, ["시작일", "종료일"]].iloc[0].tolist() if (prod["주차"] == week).any() else (None, None)

tab1, tab2, tab3, tab4 = st.tabs(["① 집계 대시보드", "② 분석 대시보드", "③ AI 제안", "④ 내보내기"])

# ── 탭 1: 집계 ──────────────────────────────────────────────
with tab1:
    st.subheader(f"{week} 주간 요약" + (f" (근무일 {k['근무일수']}일)" if k.get("근무일수") else ""))
    c = st.columns(5)
    has_prev = k.get("전주") is not None

    def pct_change(cur, prev):
        return (cur - prev) / prev * 100 if prev else None

    kpi_card(c[0], "생산수량", f"{k['생산수량']:,}개",
             arrow(pct_change(k["생산수량"], k.get("전주_생산수량")), "%", "{:+.1f}", neutral=True) if has_prev else arrow(None, ""))
    kpi_card(c[1], "불량 수량", f"{k['불량수량']:,}개",
             arrow(k["불량수량"] - k["전주_불량수량"], "개", "{:+,}") if has_prev else arrow(None, ""))
    kpi_card(c[2], "불량 건수", f"{k['불량건수']}건",
             arrow(k["불량건수"] - k["전주_불량건수"], "건", "{:+d}") if has_prev else arrow(None, ""))
    kpi_card(c[3], "불량률", f"{k['불량률']:.2f}%",
             f"전주 {k['전주_불량률']:.2f}%" if has_prev else arrow(None, ""))
    kpi_card(c[4], "전주 대비 증감", arrow(k.get("불량률_증감pp"), "%p") if has_prev else "-",
             f"{k['전주']} → {week}" if has_prev else "")

    st.markdown("#### 주차 × 라인 불량률")
    left, right = st.columns([1, 1.3])
    with left:
        tbl = fmt_rate_table(rp)
        tot = aggregate.week_total(wl).set_index("주차")
        tbl.loc["전체"] = [f"{tot.loc[w, '불량률']:.2f}%" for w in rp.columns]
        tbl.loc["근무일수"] = [f"{workdays.get(w, '-')}일" for w in rp.columns]
        st.dataframe(tbl, width="stretch")
        with st.expander("생산수량 · 불량수량 상세"):
            det = wl[wl["주차"].isin(weeks)].copy()
            det["불량률"] = det["불량률"].map(lambda v: f"{v:.2f}%")
            st.dataframe(det, hide_index=True, width="stretch")
    with right:
        fig = go.Figure()
        xlabels = [f"{w}<br>({workdays.get(w, '-')}일)" for w in rp.columns]
        for i, (line, r) in enumerate(rp.iterrows()):
            fig.add_scatter(x=xlabels, y=r.values, mode="lines+markers", name=line,
                            line=dict(color=COLORS[i % len(COLORS)], width=2.5),
                            hovertemplate=f"{line} %{{x}}<br>불량률 %{{y:.2f}}%<extra></extra>")
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=40, b=10), yaxis_title="불량률 (%)",
                          legend=dict(orientation="h", y=-0.25), title="라인별 불량률 추이 (괄호: 근무일수)")
        st.plotly_chart(fig, width="stretch")

    st.markdown(f"#### 불량유형별 추이 (최근 {len(weeks)}주)")
    left, right = st.columns([1, 1.3])
    with left:
        st.caption("수량 (개) — 순위는 이번 주 수량 기준")
        st.dataframe(type_qty, width="stretch")
        st.caption("건수 (건)")
        st.dataframe(type_cnt.reindex(type_qty.index).fillna(0).astype(int), width="stretch")
    with right:
        fig = go.Figure()
        for i, (t, r) in enumerate(type_qty[weeks].iterrows()):
            cnt = type_cnt.reindex(type_qty.index).fillna(0).loc[t, weeks].astype(int).tolist()
            fig.add_scatter(x=weeks, y=r.values, mode="lines+markers", name=t, customdata=cnt,
                            line=dict(color=COLORS[i % len(COLORS)], width=2.5),
                            hovertemplate=f"{t} %{{x}}<br>%{{y}}개 / %{{customdata}}건<extra></extra>")
        fig.update_layout(height=400, margin=dict(l=10, r=10, t=40, b=10), yaxis_title="불량 수량 (개)",
                          legend=dict(orientation="h", y=-0.15), title="불량유형별 수량 추이")
        st.plotly_chart(fig, width="stretch")


# ── 탭 2: 분석 ──────────────────────────────────────────────
def pareto_fig(par: pd.DataFrame, label: str, title: str):
    fig = go.Figure()
    x = par[label].astype(str)
    fig.add_bar(x=x, y=par["불량수량"], name="불량 수량", marker_color=COLORS[0],
                hovertemplate="%{x}<br>%{y}개<extra></extra>")
    fig.add_scatter(x=x, y=par["누적점유율"], name="누적 점유율", yaxis="y2", mode="lines+markers",
                    line=dict(color=COLORS[1]), hovertemplate="%{x}<br>누적 %{y:.1f}%<extra></extra>")
    fig.add_hline(y=80, line_dash="dash", line_color="gray", yref="y2",
                  annotation_text="80%", annotation_position="top left")
    fig.update_layout(height=360, title=title, margin=dict(l=10, r=10, t=40, b=10),
                      yaxis=dict(title="불량 수량 (개)"),
                      yaxis2=dict(title="누적 점유율 (%)", overlaying="y", side="right", range=[0, 105], dtick=20),
                      legend=dict(orientation="h", y=-0.2))
    return fig


with tab2:
    st.subheader(f"{week} 분석")
    st.markdown("#### 🚨 변화점 알림")
    if not changes:
        st.success("감지된 변화점이 없습니다.")
    icons = {"유형 급증": "📈", "연속 상승": "⤴️", "하루 집중": "📅", "유출 위험": "🚚"}
    for i, ch in enumerate(changes):
        with st.expander(f"{icons.get(ch['규칙'], '•')} **[{ch['규칙']}]** {ch['내용']}"):
            rows = analyze.rows_for(defects_valid, ch["filter"])
            st.caption(f"해당 원본 행 {len(rows)}개")
            st.dataframe(rows[["원본파일", "원본행", "발생일", "라인", "품번", "품명", "출하처", "불량유형",
                               "불량수량", "발견 공정", "조치", "기록자"]],
                         hide_index=True, width="stretch",
                         column_config={"발생일": st.column_config.DateColumn(format="YYYY-MM-DD")})
    st.caption(f"기준: 유형 급증 +{config.SURGE_PCT:.0f}% 이상 & +{config.SURGE_QTY}개 이상 · "
               f"연속 상승 {config.CONSEC_RISE_STEPS}회 이상 · 하루 집중 {config.DAY_CONC_SHARE:.0%} 이상(주간 {config.DAY_CONC_MIN_QTY}개 이상) · "
               f"유출 위험 출하검사 비중 {config.OUTFLOW_SHARE:.0%} 이상  (config.py에서 변경)")

    c1, c2 = st.columns(2)
    par_t = analyze.pareto(defects_valid, week, "불량유형")
    par_p = analyze.pareto(defects_valid, week, "품번")
    c1.plotly_chart(pareto_fig(par_t, "불량유형", "불량유형 파레토"), width="stretch")
    c2.plotly_chart(pareto_fig(par_p, "품번", "품번 파레토"), width="stretch")
    st.caption("품번별 생산수량이 없어 품번은 불량률 대신 수량·점유율로 표시합니다.")

    st.markdown("#### 라인 × 품번 × 유형 상위 10")
    ct = analyze.cross_top(defects_valid, week, 10)
    st.dataframe(ct, hide_index=True, width="stretch",
                 column_config={"점유율": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)})

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 출하처별 분포")
        st.dataframe(analyze.distribution(defects_valid, week, "출하처"), width="stretch")
    with c2:
        st.markdown("#### 발견 공정별 분포")
        st.dataframe(analyze.distribution(defects_valid, week, "발견 공정"), width="stretch")
        of = analyze.outflow_share(defects_valid, week)
        st.caption("유형별 출하검사 발견 비중 (유출 위험)")
        st.dataframe(of, hide_index=True, width="stretch",
                     column_config={"출하검사 비중": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100)})


# ── 탭 3: AI 제안 ───────────────────────────────────────────
ss = st.session_state
ss.setdefault("ai_ver", 0)
ss.setdefault("ai_result", None)


def edited_proposals() -> list[dict]:
    """화면에서 고친 카드 내용을 모은다 (내보내기에 사용)."""
    res = ss.get("ai_result")
    if not res or not res.get("ok"):
        return []
    v, out = ss["ai_ver"], []
    for i, p in enumerate(res["data"]["proposals"]):
        g = lambda f, d="": ss.get(f"v{v}_p{i}_{f}", d)  # noqa: E731
        lst = lambda f: [x.strip() for x in str(g(f, "\n".join(p.get(f, [])))).splitlines() if x.strip()]  # noqa: E731
        causes = ss.get(f"v{v}_p{i}_causes_df")
        causes = causes.to_dict("records") if isinstance(causes, pd.DataFrame) else p.get("suspected_causes", [])
        out.append({
            "rank": i + 1,
            "defect_type": p.get("defect_type", ""),
            "phenomenon": g("phenomenon", p.get("phenomenon", "")),
            "suspected_causes": [c for c in causes if str(c.get("cause", "")).strip()],
            "verification": lst("verification"), "short_term": lst("short_term"), "permanent": lst("permanent"),
            "owner": g("owner", p.get("owner", "")), "claim_link": g("claim_link", p.get("claim_link", "")),
            "last_week_check": g("last_week_check", p.get("last_week_check", "")),
        })
    return out


with tab3:
    st.subheader(f"{week} TOP{config.TOP_N} 원인·제거방안 AI 제안")
    rank_df = aggregate.top_types(defects_valid, week, n=len(type_qty))
    types = rank_df["불량유형"].tolist()
    st.caption("기본 순위는 이번 주 불량 **수량** 기준입니다. 필요하면 순서를 바꾸세요.")
    st.dataframe(rank_df.head(6).assign(순위=range(1, min(6, len(rank_df)) + 1))[["순위", "불량유형", "불량수량", "불량건수"]],
                 hide_index=True)
    cols = st.columns(config.TOP_N)
    top3 = []
    for i in range(min(config.TOP_N, len(types))):
        top3.append(cols[i].selectbox(f"{i + 1}순위", types, index=i, key=f"top_{i}"))
    if len(set(top3)) < len(top3):
        st.error("같은 유형이 두 번 선택되었습니다.")

    prompt = ai_advisor.build_user_prompt(defects_valid, week, weeks, top3, type_qty, type_cnt, changes, k,
                                          memo_text, last_report)
    with st.expander("AI에 보내는 입력 보기"):
        st.code(prompt, language="markdown")
    if not memo_text:
        st.info("현장 메모가 없으면 원인은 모두 '추정'으로 표시됩니다.")

    if not ai["has_key"]:
        st.warning("AI 기능이 꺼져 있습니다. `.env` 파일에 `ANTHROPIC_API_KEY=sk-ant-...`를 넣고 앱을 다시 실행하세요. "
                   "집계·분석·내보내기는 그대로 쓸 수 있습니다.")
    clicked = st.button("🤖 AI 제안 받기", type="primary",
                        disabled=not ai["has_key"] or len(set(top3)) < len(top3))
    if clicked:
        with st.spinner(f"{ai['model']}에 요청 중… (최대 {ai['timeout']:.0f}초)"):
            ss["ai_result"] = ai_advisor.suggest(prompt)
            ss["ai_result"]["week"] = week
            ss["ai_ver"] += 1

    res = ss.get("ai_result")
    if res and not res["ok"]:
        st.error(f"AI 제안 실패: {res['error']}")
        if res.get("raw"):
            st.markdown("**원문 응답**")
            st.code(res["raw"])
    elif res and res["ok"]:
        if res.get("week") != week:
            st.warning(f"아래 제안은 {res.get('week')} 기준입니다. 현재 주차로 다시 받으세요.")
        v = ss["ai_ver"]
        st.caption("카드 내용은 직접 고칠 수 있으며, 고친 내용이 내보내기에 들어갑니다.")
        for i, p in enumerate(res["data"]["proposals"]):
            with st.container(border=True):
                st.markdown(f"### {i + 1}순위 · {p.get('defect_type', '')}")
                badges = " ".join(
                    (":green-badge[근거 있음]" if c.get("evidence_status") == "근거 있음" else ":orange-badge[추정]")
                    + f" {c.get('category', '')}·신뢰도 {c.get('confidence', '')}"
                    for c in p.get("suspected_causes", []))
                if badges:
                    st.markdown(badges)
                st.text_input("현상", p.get("phenomenon", ""), key=f"v{v}_p{i}_phenomenon")
                st.markdown("**추정 원인 (4M)**")
                cdf = pd.DataFrame(p.get("suspected_causes", []),
                                   columns=["category", "cause", "evidence", "evidence_status", "confidence"])
                ss[f"v{v}_p{i}_causes_df"] = st.data_editor(
                    cdf, num_rows="dynamic", hide_index=True, width="stretch", key=f"v{v}_p{i}_causes",
                    column_config={
                        "category": st.column_config.SelectboxColumn("4M", options=["사람", "설비", "자재", "방법"], width="small"),
                        "cause": st.column_config.TextColumn("원인", width="medium"),
                        "evidence": st.column_config.TextColumn("근거", width="large"),
                        "evidence_status": st.column_config.SelectboxColumn("근거", options=["근거 있음", "추정"], width="small"),
                        "confidence": st.column_config.SelectboxColumn("신뢰도", options=["상", "중", "하"], width="small"),
                    })
                a, b, c3 = st.columns(3)
                a.text_area("확인 방법", "\n".join(p.get("verification", [])), key=f"v{v}_p{i}_verification", height=130)
                b.text_area("단기 조치 (1주 이내)", "\n".join(p.get("short_term", [])), key=f"v{v}_p{i}_short_term", height=130)
                c3.text_area("근본 대책", "\n".join(p.get("permanent", [])), key=f"v{v}_p{i}_permanent", height=130)
                a, b = st.columns(2)
                a.text_input("담당 부서", p.get("owner", ""), key=f"v{v}_p{i}_owner")
                b.text_input("관련 클레임", p.get("claim_link", ""), key=f"v{v}_p{i}_claim_link")
                st.text_input("지난주 조치 평가", p.get("last_week_check", ""), key=f"v{v}_p{i}_last_week_check")


# ── 탭 4: 내보내기 ──────────────────────────────────────────
with tab4:
    st.subheader("주간 리포트 내보내기")
    props = edited_proposals()
    notes = st.text_area("5. 특이사항 추가 메모 (한 줄에 하나)", height=100,
                         placeholder="예) 다음 주 품질회의에 구매팀(도료 담당) 참석")
    top_info = [(r["불량유형"], int(r["불량수량"]), int(r["불량건수"]))
                for _, r in rank_df.set_index("불량유형").loc[top3].reset_index().iterrows()]
    ctx = dict(week=week, weeks=weeks, kpi=k, prod_dates=tuple(prod_dates), type_qty=type_qty,
               type_cnt=type_cnt.reindex(type_qty.index).fillna(0).astype(int), wl_week=wl[wl["주차"] == week],
               rate_pivot=rp, workdays=workdays, changes=changes, proposals=props, notes=notes,
               nonstd=loader.non_standard_actions(raw), top=top_info, author="품질팀")

    if not props:
        st.info("AI 제안이 없으면 4장은 TOP3 수량만 들어갑니다. ③ AI 제안 탭에서 먼저 제안을 받을 수 있습니다.")

    with st.expander("리포트 미리보기", expanded=True):
        st.markdown(f"**불량 유형 주간 분석 리포트 — {week}**")
        st.markdown(f"**1. 분석 개요** — 생산 {k['생산수량']:,}개 · 불량 {k['불량건수']}건 / {k['불량수량']:,}개 · "
                    f"불량률 {k['불량률']:.2f}%"
                    + (f" (전주 대비 {k['불량률_증감pp']:+.2f}%p)" if k.get("전주") else ""))
        st.markdown(f"**2. 유형별 수량 · 건수 (최근 {len(weeks)}주)**")
        st.dataframe(type_qty, width="stretch")
        st.markdown(f"**3. 라인별 불량률 ({week})**")
        st.dataframe(fmt_rate_table(rp), width="stretch")
        st.markdown("**4. 원인 추정 · 우선 점검 · 다음 주 조치**")
        if props:
            st.markdown(ai_advisor.proposals_to_markdown(props, week).split("\n", 2)[2])
        else:
            for i, (t, q, n) in enumerate(top_info, 1):
                st.markdown(f"- {i}순위 {t} — {q:,}개 ({n}건)")
        st.markdown("**5. 특이사항**")
        for ch in changes:
            st.markdown(f"- [{ch['규칙']}] {ch['내용']}")
        for line in notes.splitlines():
            if line.strip():
                st.markdown(f"- {line.strip()}")

    sheets = {
        "KPI": pd.DataFrame([{k2: v2 for k2, v2 in k.items()}]),
        "주차x라인": wl[wl["주차"].isin(weeks)],
        "라인별불량률": rp,
        "유형추이_수량": type_qty,
        "유형추이_건수": type_cnt,
        "파레토_유형": analyze.pareto(defects_valid, week, "불량유형"),
        "파레토_품번": analyze.pareto(defects_valid, week, "품번"),
        "교차분석_TOP10": analyze.cross_top(defects_valid, week, 10),
        "출하처별": analyze.distribution(defects_valid, week, "출하처"),
        "발견공정별": analyze.distribution(defects_valid, week, "발견 공정"),
        "변화점": pd.DataFrame([{kk: vv for kk, vv in c.items() if kk != "filter"} for c in changes]),
        "불량기록_원본": raw.drop(columns=[]),
    }
    c1, c2, c3 = st.columns(3)
    try:
        c1.download_button("📄 Word 리포트", report.build_docx(ctx), file_name=f"불량분석리포트_{week}.docx",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                           width="stretch", type="primary")
    except Exception as e:  # noqa: BLE001
        c1.error(f"Word 생성 실패: {e}")
    c2.download_button("📊 집계표 Excel", report.build_xlsx(sheets), file_name=f"불량집계표_{week}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    c3.download_button("📝 AI 제안 Markdown", report.build_markdown(props, week) if props else "AI 제안 없음",
                       file_name=f"AI제안_{week}.md", mime="text/markdown", width="stretch", disabled=not props)

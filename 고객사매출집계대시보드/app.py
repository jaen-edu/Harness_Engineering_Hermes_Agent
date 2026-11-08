"""고객사별 매출 집계 대시보드 화면."""
from __future__ import annotations

import html

import plotly.graph_objects as go
import streamlit as st

import calc
import export
import folders

st.set_page_config(page_title="고객사별 매출 집계", page_icon="📊", layout="wide")

STATUS_COLOR = {calc.UNDER: "#d03b3b", calc.CAUTION: "#c98500", calc.NORMAL: "#8a8a86", "": "#c4c4bf"}
STATUS_ICON = {calc.UNDER: "▼", calc.CAUTION: "!", calc.NORMAL: "●", "": "–"}
# 고객사 선 색: 검증된 범주 팔레트를 고객사명 가나다순으로 고정 배정(색은 고객사를 따라감)
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
OTHER = "#8a8a86"
INK, INK2, GRID = "#1f1f1d", "#5f5e5a", "#e6e5e0"

CSS = """
<style>
.block-container{padding-top:2rem;max-width:1400px}
.kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:4px 0 18px}
.kpi{border:1px solid #e3e2dc;border-radius:10px;padding:12px 16px;background:#fff}
.kpi .lab{font-size:13px;color:#5f5e5a}
.kpi .val{font-size:24px;font-weight:700;color:#1f1f1d;margin-top:2px;font-variant-numeric:tabular-nums;white-space:nowrap}
.kpi .sub{font-size:12px;color:#5f5e5a;margin-top:2px}
.warn{background:#fff7dc;border:1px solid #efd27c;border-radius:10px;padding:12px 18px;margin:0 0 20px}
.warn .ttl{font-weight:700;color:#7a5600;margin-bottom:6px}
.warn ul{margin:0;padding-left:18px}.warn li{margin:3px 0;color:#3d3a30;font-size:14px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:14px;margin-bottom:26px}
.card{border:1px solid #e3e2dc;border-left:6px solid var(--st);border-radius:10px;padding:14px 16px 12px;background:#fff}
.card .top{display:flex;align-items:center;gap:8px}
.card .nm{font-size:17px;font-weight:700;color:#1f1f1d}
.badge{display:inline-block;min-width:34px;text-align:center;border-radius:999px;padding:2px 8px;font-size:12px;font-weight:700;color:#fff;background:#1f1f1d}
.badge.r1{background:#b8860b}.badge.r2{background:#6f7782}.badge.r3{background:#a0623a}
.judge{margin-left:auto;font-weight:700;font-size:14px;color:var(--st)}
.amt{font-size:22px;font-weight:700;color:#1f1f1d;margin:8px 0 0;font-variant-numeric:tabular-nums}
.tgt{font-size:13px;color:#5f5e5a}
.rate{display:flex;justify-content:space-between;font-size:13px;color:#5f5e5a;margin:10px 0 4px}
.rate b{color:#1f1f1d;font-size:15px}
.bar{position:relative;height:8px;border-radius:4px;background:#eeede8;overflow:visible}
.bar .fill{height:8px;border-radius:4px;background:#2a78d6}
.bar .tick{position:absolute;left:90%;top:-3px;width:2px;height:14px;background:#1f1f1d;opacity:.55}
.note{font-size:12px;color:#d03b3b;margin-top:4px}
.rows{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;font-size:13px;color:#5f5e5a;margin-top:10px}
.rows span:nth-child(even){text-align:right;color:#1f1f1d;font-weight:600;font-variant-numeric:tabular-nums}
table.tbl{border-collapse:collapse;width:100%;font-size:14px;margin-bottom:26px;background:#fff}
.tbl th{background:#ddebf7;border:1px solid #c9ced6;padding:7px 10px;text-align:center;font-weight:700;color:#1f1f1d}
.tbl td{border:1px solid #d9d8d2;padding:6px 10px;text-align:right;font-variant-numeric:tabular-nums;color:#1f1f1d}
.tbl td:first-child{text-align:left}.tbl td:last-child{text-align:center}
.tbl tr.sum td{font-weight:700;background:#f6f6f3}
.tbl td.red{background:#ffc7ce}.tbl td.yel{background:#ffeb9c}
.side-st{font-size:13px;margin:-6px 0 14px;line-height:1.5}
.side-st .ok{color:#1d7a3a;font-weight:700}.side-st .need{color:#b3261e;font-weight:700}
.side-st .err{color:#b3261e}
.side-st .path{color:#5f5e5a;font-size:12px}
.side-st .file{color:#1f1f1d;font-size:12px}.side-st .skip{color:#8a8a86;font-size:12px}
@media (max-width:1000px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""

esc = html.escape


def put(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def folder_status(title: str, folder, ok: bool, text: str, picked: folders.Picked, key: str) -> None:
    st.sidebar.markdown(f"**{esc(title)}**")
    head = '<span class="ok">✔ 읽음</span>' if ok else '<span class="need">● 파일 필요</span>'
    body = f"{head} · {esc(text)}" if text else head
    body += f'<div class="path">{esc(str(folder.relative_to(folders.BASE.parent)))}</div>'
    for f in picked.used:
        for name in f.name.split(", "):
            body += f'<div class="file">📄 {esc(name)}</div>'
    for s_ in picked.skipped:
        body += f'<div class="skip">↷ {esc(s_)}</div>'
    for e in picked.errors:
        body += f'<div class="err">{esc(e)}</div>'
    st.sidebar.markdown(f'<div class="side-st">{body}</div>', unsafe_allow_html=True)
    if st.sidebar.button("📂 폴더 열기", key=f"open_{key}"):
        folders.open_folder(folder)


# ---------------------------------------------------------------- 사이드바

put(CSS)
folders.ensure_folders()
st.sidebar.header("입력 파일 폴더")
st.sidebar.caption("각 폴더에 엑셀 파일을 넣어 두면 자동으로 읽습니다. 파일을 바꿨으면 '다시 읽기'를 누르세요.")
st.sidebar.button("🔄 다시 읽기", type="primary", width="stretch")  # 누르면 화면 전체를 다시 실행

ship_pick = folders.pick_shipments()
ships = ship_pick.used
recognized = ", ".join(f"{f.main_month[1]}월" for f in ships)
folder_status("① 출하실적 (3개월, 3개)", folders.SHIP_DIR, len(ships) == 3 and not ship_pick.errors,
              f"{len(ships)}/3개" + (f" — {recognized}" if recognized else ""), ship_pick, "ship")

target_pick = folders.pick_targets()
target = target_pick.used[0] if target_pick.used else None
folder_status("② 고객사 분기목표", folders.TARGET_DIR, target is not None and not target_pick.errors,
              f"분기: {', '.join(target.quarters)}" if target else "", target_pick, "target")

prev_label = folders.prev_quarter_label(ships)
last_pick = folders.pick_last_quarter(prev_label)
last = last_pick.used[0] if last_pick.used else None
folder_status("③ 지난분기 매출집계표", folders.LAST_DIR, last is not None and not last_pick.errors,
              f"{last.label or '분기 미확인'} · 고객사 {len(last.totals)}곳" if last else "", last_pick, "last")

# ---------------------------------------------------------------- 집계

st.title("고객사별 매출 집계 대시보드")

problems: list[str] = ship_pick.errors + target_pick.errors + last_pick.errors
summary = None
if not problems:
    need = []
    if len(ships) < 3:
        msg = f"출하실적 파일이 {len(ships)}개입니다. 3개월 치 3개를 '{folders.SHIP_DIR.name}' 폴더에 넣어 주세요."
        if ships:
            try:
                calc.check_quarter(ships)
            except calc.StopError as exc:
                msg = str(exc).replace("올려 주세요", f"'{folders.SHIP_DIR.name}' 폴더에 넣어 주세요")
        need.append(msg)
    if target is None:
        need.append(f"고객사_분기목표.xlsx를 '{folders.TARGET_DIR.name}' 폴더에 넣어 주세요.")
    if last is None:
        need.append(f"지난분기_매출집계표.xlsx를 '{folders.LAST_DIR.name}' 폴더에 넣어 주세요.")
    if need:
        st.info(f"'{folders.BASE}' 아래 폴더 3개에 파일을 넣고 '다시 읽기'를 누르면 집계가 표시됩니다.\n\n"
                + "\n".join(f"- {n}" for n in need))
    else:
        try:
            summary = calc.compute(ships, target, last)
        except calc.StopError as exc:
            problems.append(str(exc))

if problems:
    st.error("집계를 멈췄습니다. 폴더의 파일을 확인한 뒤 '다시 읽기'를 눌러 주세요.\n\n"
             + "\n".join(f"- {p}" for p in problems))

st.sidebar.divider()
if summary:
    st.sidebar.download_button("📥 엑셀로 저장", export.build(summary), file_name=export.file_name(summary),
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               type="primary", width="stretch")
else:
    st.sidebar.button("📥 엑셀로 저장", disabled=True, width="stretch",
                      help="폴더 3개에 파일이 모두 있고 집계가 끝나면 저장할 수 있습니다.")

if not summary:
    st.stop()

s = summary
mlast, mprev = s.month_names[2], s.month_names[1]
prev_q = s.prev_label.split(" ")[-1]  # 예: 2분기

# ---------------------------------------------------------------- 요약 줄


def kpi(label, value, sub="", title=""):
    t = f' title="{esc(title)}"' if title else ""
    return (f'<div class="kpi"{t}><div class="lab">{esc(label)}</div><div class="val">{esc(value)}</div>'
            f'<div class="sub">{esc(sub)}</div></div>')


tot = s.total
put('<div class="kpis">'
    + kpi("집계 분기", s.label, f"출하실적 {s.month_names[0]}~{mlast}")
    + kpi("전체 분기 매출", calc.fmt_won(tot.total))
    + kpi("전체 목표", calc.fmt_won(tot.target))
    + kpi("전체 달성률", calc.fmt_pct(tot.rate, none_text="—"), "",
          f"반올림 전 {calc.fmt_exact(tot.rate)}" if tot.rate is not None else "")
    + kpi(f"{prev_q} 대비", tot.vs_prev_text,
          f"{s.prev_label} {calc.fmt_won(tot.prev_total)}" if tot.prev_total else "")
    + "</div>")

# ---------------------------------------------------------------- 경고

if s.warnings:
    items = "".join(f"<li>{esc(w)}</li>" for w in s.warnings)
    put(f'<div class="warn"><div class="ttl">⚠ 확인이 필요한 항목 {len(s.warnings)}건</div><ul>{items}</ul></div>')

# ---------------------------------------------------------------- 고객사 카드


def boundary_note(c: calc.CustomerResult) -> str:
    """반올림한 숫자와 판정이 어긋나 보이는 경우 실제 값을 함께 보여준다."""
    notes = []
    if c.rate is not None and c.rate < calc.RATE_LIMIT <= calc.round1(c.rate):
        notes.append(f"실제 달성률 {calc.fmt_exact(c.rate)} → 90% 미만이라 미달")
    if c.mom is not None and c.mom > calc.MOM_LIMIT >= calc.round1(c.mom):
        notes.append(f"실제 전월 대비 {calc.fmt_exact(c.mom)} → −20% 초과라 주의 아님")
    return "".join(f'<div class="note">{esc(n)}</div>' for n in notes)


def card(c: calc.CustomerResult) -> str:
    color = STATUS_COLOR[c.judgment]
    badge = f'<span class="badge r{c.rank}">{c.rank}위</span>' if c.rank else ""
    judge = f'{STATUS_ICON[c.judgment]} {c.judgment}' if c.judgment else "판정 없음"
    if c.rate is not None:
        width = max(0.0, min(float(c.rate), 100.0))
        bar_color = color if c.judgment in (calc.UNDER, calc.CAUTION) else "#2a78d6"
        rate_html = (
            f'<div class="rate" title="반올림 전 {esc(calc.fmt_exact(c.rate))}"><span>달성률</span>'
            f'<b>{calc.fmt_pct(c.rate)}</b></div>'
            f'<div class="bar" title="90% 선 표시"><div class="fill" style="width:{width:.2f}%;background:{bar_color}"></div>'
            f'<div class="tick"></div></div>{boundary_note(c)}')
    else:
        rate_html = '<div class="rate"><span>달성률</span><b>—</b></div><div class="note">분기목표에 없는 고객사</div>'
    mom_title = f' title="반올림 전 {esc(calc.fmt_exact(c.mom))}"' if c.mom is not None else ""
    return (
        f'<div class="card" style="--st:{color}">'
        f'<div class="top">{badge}<span class="nm">{esc(c.name)}</span><span class="judge">{esc(judge)}</span></div>'
        f'<div class="amt">{calc.fmt_won(c.total)}</div>'
        f'<div class="tgt">목표 {calc.fmt_won(c.target)}</div>'
        f'{rate_html}'
        f'<div class="rows"><span>전월 대비 ({mlast} vs {mprev})</span><span{mom_title}>{esc(c.mom_text)}</span>'
        f'<span>{prev_q} 대비</span><span>{esc(c.vs_prev_text)}</span></div>'
        f'</div>')


st.subheader("고객사별 현황")
st.caption("분기 매출 상위 3곳을 맨 앞에 두고, 나머지는 매출액 순입니다. 왼쪽 테두리 색: 빨강 미달 · 노랑 주의 · 회색 정상. "
           "막대의 검은 눈금은 90% 선입니다.")
put('<div class="cards">' + "".join(card(c) for c in s.cards) + "</div>")

# ---------------------------------------------------------------- 월별 통계 표


def table_row(c: calc.CustomerResult, cls: str = "") -> str:
    rate_cls = "red" if c.judgment == calc.UNDER else ""
    judge_cls = {"미달": "red", "주의": "yel"}.get(c.judgment, "")
    rate_title = f' title="반올림 전 {esc(calc.fmt_exact(c.rate))}"' if c.rate is not None else ""
    cells = [f"<td>{esc(c.name)}</td>"]
    cells += [f"<td>{v:,}</td>" for v in c.months]
    cells += [f"<td>{c.total:,}</td>", f"<td>{esc(calc.fmt_won(c.target, ''))}</td>",
              f'<td class="{rate_cls}"{rate_title}>{calc.fmt_pct(c.rate)}</td>',
              f"<td>{esc(c.mom_text)}</td>", f'<td class="{judge_cls}">{esc(c.judgment)}</td>']
    return f'<tr class="{cls}">' + "".join(cells) + "</tr>"


st.subheader("월별 통계")
st.caption("지난분기 집계표와 같은 열 구성입니다(단위: 원, 고객사명 가나다순).")
heads = ["고객사", *s.month_names, "분기 합계", "분기 목표", "달성률", "전월 대비", "판정"]
put('<table class="tbl"><thead><tr>' + "".join(f"<th>{h}</th>" for h in heads) + "</tr></thead><tbody>"
    + "".join(table_row(c) for c in s.customers) + table_row(s.total, "sum") + "</tbody></table>")

# ---------------------------------------------------------------- 그래프

FONT = dict(family="Pretendard, 'Malgun Gothic', sans-serif", size=13, color=INK2)


def base_layout(fig: go.Figure, title: str) -> None:
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=INK)), font=FONT,
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", height=420,
        margin=dict(l=10, r=10, t=60, b=10),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=GRID, font=dict(color=INK)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1, title=None),
    )
    fig.update_yaxes(gridcolor=GRID, zeroline=True, zerolinecolor="#c4c4bf", tickformat=",", ticksuffix="원",
                     rangemode="tozero")
    fig.update_xaxes(showgrid=False, linecolor="#c4c4bf")


left, right = st.columns(2)

with left:
    fig = go.Figure()
    for i, c in enumerate(s.customers):  # 가나다순 고정 색
        fig.add_trace(go.Scatter(
            x=s.month_names, y=c.months, name=c.name, mode="lines+markers",
            line=dict(width=2, color=SERIES[i] if i < len(SERIES) else OTHER),
            marker=dict(size=8, line=dict(width=2, color="#ffffff")),
            hovertemplate="%{fullData.name}: %{y:,}원<extra></extra>"))
    base_layout(fig, "고객사별 월 매출 추이")
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})

with right:
    ranked = sorted(s.customers, key=lambda c: (c.rate is None, -(c.rate or 0)))
    labels = [f"{c.name}<br>{calc.fmt_pct(c.rate, none_text='목표 없음')}" for c in ranked]
    hover = [f"{c.name}<br>실적 {calc.fmt_won(c.total)}<br>목표 {calc.fmt_won(c.target)}"
             f"<br>달성률 {calc.fmt_pct(c.rate, none_text='—')}" for c in ranked]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=[c.total for c in ranked], name="분기 실적", marker_color="#2a78d6",
                         hovertext=hover, hoverinfo="text"))
    fig.add_trace(go.Scatter(
        x=[lab for lab, c in zip(labels, ranked) if c.target is not None],
        y=[c.target for c in ranked if c.target is not None],
        name="분기 목표", mode="markers",
        marker=dict(symbol="line-ew", size=46, line=dict(width=3, color=INK)),
        hovertext=[h for h, c in zip(hover, ranked) if c.target is not None], hoverinfo="text"))
    base_layout(fig, "고객사별 목표 대비 실적 (달성률 순)")
    fig.update_layout(barcornerradius=4, bargap=0.45)
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})

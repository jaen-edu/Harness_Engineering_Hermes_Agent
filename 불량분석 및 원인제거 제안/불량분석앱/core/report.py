"""Word·Excel·Markdown 내보내기. 리포트 그래프는 matplotlib으로 다시 그린다."""
from __future__ import annotations

import io
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt, RGBColor  # noqa: E402

from core.ai_advisor import proposals_to_markdown  # noqa: E402

FONT = "맑은 고딕"
for f in ("Malgun Gothic", "AppleGothic", "NanumGothic"):
    if any(f == x.name for x in matplotlib.font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f
        break
plt.rcParams["axes.unicode_minus"] = False
COLORS = ["#2a6fdb", "#e4572e", "#17a398", "#f3a712", "#8e5ad6", "#6c757d"]


# ── 그래프 이미지 ────────────────────────────────────────────
def _png(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def chart_line_rate(rate_pivot: pd.DataFrame, workdays: dict) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(7, 3.2))
    for i, (line, r) in enumerate(rate_pivot.iterrows()):
        ax.plot(r.index, r.values, marker="o", color=COLORS[i % len(COLORS)], label=line, linewidth=2)
    ax.set_xticks(range(len(rate_pivot.columns)))
    ax.set_xticklabels([f"{w}\n({workdays.get(w, '-')}일)" for w in rate_pivot.columns])
    ax.set_ylabel("불량률 (%)")
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(ncol=4, frameon=False, loc="upper left", fontsize=8)
    ax.set_title("라인별 불량률 추이 (괄호: 근무일수)", fontsize=10)
    return _png(fig)


def chart_type_trend(type_qty: pd.DataFrame, weeks: list[str]) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(7, 3.2))
    for i, (t, r) in enumerate(type_qty[weeks].iterrows()):
        ax.plot(weeks, r.values, marker="o", color=COLORS[i % len(COLORS)], label=t, linewidth=2)
    ax.set_ylabel("불량 수량 (개)")
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(ncol=3, frameon=False, loc="upper left", fontsize=8)
    ax.set_title("불량유형별 수량 추이", fontsize=10)
    return _png(fig)


def chart_pareto(par: pd.DataFrame, label: str) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.bar(par[label].astype(str), par["불량수량"], color=COLORS[0])
    ax.set_ylabel("불량 수량 (개)")
    ax2 = ax.twinx()
    ax2.plot(par[label].astype(str), par["누적점유율"], color=COLORS[1], marker="o")
    ax2.axhline(80, color="gray", linestyle="--", linewidth=1)
    ax2.set_ylim(0, 105)
    ax2.set_ylabel("누적 점유율 (%)")
    ax.spines[["top"]].set_visible(False)
    ax2.spines[["top"]].set_visible(False)
    ax.set_title(f"{label} 파레토 (점선: 80%)", fontsize=10)
    plt.setp(ax.get_xticklabels(), rotation=0, fontsize=8)
    return _png(fig)


# ── Word ─────────────────────────────────────────────────────
def _set_font(doc):
    st = doc.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(10)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    for name in ("Title", "Heading 1", "Heading 2", "List Bullet"):
        s = doc.styles[name]
        s.font.name = FONT
        rpr = s.element.get_or_add_rPr()
        rpr.get_or_add_rFonts().set(qn("w:eastAsia"), FONT)


def _heading(doc, text):
    p = doc.add_heading(text, level=1)
    for r in p.runs:
        r.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
        r.font.size = Pt(13)


def _table(doc, header: list[str], rows: list[list], widths=None):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = str(h)
        c.paragraphs[0].runs[0].bold = True
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = str(v)
            cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER if i else WD_ALIGN_PARAGRAPH.LEFT
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    return t


def _bullet(doc, text, bold_prefix: str | None = None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_prefix:
        p.add_run(bold_prefix).bold = True
    p.add_run(text)
    return p


def build_docx(ctx: dict) -> bytes:
    """ctx: week, weeks, kpi, prod_dates, type_qty, type_cnt, wl_week(DataFrame), rate_pivot,
    workdays, changes, proposals(list|None), notes(str), nonstd(DataFrame), author"""
    week, weeks, k = ctx["week"], ctx["weeks"], ctx["kpi"]
    doc = Document()
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(2)
        s.top_margin = s.bottom_margin = Cm(2)
    _set_font(doc)

    title = doc.add_paragraph()
    r = title.add_run(f"불량 유형 주간 분석 리포트 — {week}")
    r.bold, r.font.size = True, Pt(18)
    doc.add_paragraph(f"{ctx.get('author') or '품질팀'} · 작성일 {date.today():%Y-%m-%d} · 품질회의 보고용")

    # 1. 분석 개요
    _heading(doc, "1. 분석 개요")
    s, e = ctx.get("prod_dates", (None, None))
    period = f" ({pd.Timestamp(s):%Y-%m-%d} ~ {pd.Timestamp(e):%m-%d}, 근무일 {k['근무일수']}일)" if s is not None else ""
    _bullet(doc, f"분석 주: {week}{period}")
    _bullet(doc, f"생산수량 {k['생산수량']:,}개 · 불량 건수 {k['불량건수']}건 · 불량 수량 {k['불량수량']:,}개")
    line = f"불량률 {k['불량률']:.2f}%"
    if k.get("전주"):
        line += f" (전주 {k['전주']} {k['전주_불량률']:.2f}% 대비 {k['불량률_증감pp']:+.2f}%p)"
    _bullet(doc, line)
    _bullet(doc, f"비교 범위: 최근 {len(weeks)}주 ({weeks[0]} ~ {weeks[-1]}) · 순위와 TOP3는 불량 수량 기준")

    # 2. 유형별 수량·건수
    _heading(doc, f"2. 유형별 수량 · 건수 (최근 {len(weeks)}주)")
    tq, tc = ctx["type_qty"], ctx["type_cnt"]
    header = ["불량 유형"] + weeks + ["지난주 대비"]
    rows = []
    for t in tq.index:
        cells = [t]
        for w in weeks:
            cells.append(f"{int(tq.loc[t, w]):,} ({int(tc.loc[t, w]) if t in tc.index else 0}건)")
        diff = int(tq.loc[t, "전주 대비"]) if "전주 대비" in tq.columns else 0
        cells.append(f"{diff:+d}")
        rows.append(cells)
    _table(doc, header, rows)
    doc.add_paragraph("표 값: 불량 수량(개), 괄호 안은 건수", style=None).runs[0].font.size = Pt(8)
    doc.add_picture(chart_type_trend(tq, weeks), width=Cm(16))

    # 3. 라인별 불량률
    _heading(doc, f"3. 라인별 불량률 ({week})")
    wlw = ctx["wl_week"]
    rp = ctx["rate_pivot"]
    prev = weeks[-2] if len(weeks) >= 2 else None
    rows = []
    for _, r in wlw.iterrows():
        row = [r["라인"], f"{int(r['생산수량']):,}", f"{int(r['불량수량']):,}", f"{r['불량률']:.2f}%"]
        if prev and prev in rp.columns:
            pv = rp.loc[r["라인"], prev]
            row += [f"{pv:.2f}%", f"{r['불량률'] - pv:+.2f}%p"]
        rows.append(row)
    tot = [ "합계", f"{k['생산수량']:,}", f"{k['불량수량']:,}", f"{k['불량률']:.2f}%"]
    if prev and prev in rp.columns:
        tot += [f"{k.get('전주_불량률', 0):.2f}%", f"{k.get('불량률_증감pp', 0):+.2f}%p"]
    rows.append(tot)
    header = ["라인", "생산수량", "불량 수량", "불량률"] + ([f"전주({prev})", "증감"] if prev and prev in rp.columns else [])
    _table(doc, header, rows)
    doc.add_picture(chart_line_rate(rp, ctx["workdays"]), width=Cm(16))

    # 4. 원인 추정 · 우선 점검 · 다음 주 조치
    _heading(doc, "4. 원인 추정 · 우선 점검 · 다음 주 조치")
    props = ctx.get("proposals") or []
    if props:
        for p in props:
            _bullet(doc, f" {p.get('phenomenon', '')}", bold_prefix=f"{p.get('rank', '')}순위 {p.get('defect_type', '')} —")
            for c in p.get("suspected_causes", []):
                doc.add_paragraph(
                    f"  · 추정 원인 [{c.get('category', '')}] {c.get('cause', '')} "
                    f"({c.get('evidence_status', '')}, 신뢰도 {c.get('confidence', '')}): {c.get('evidence', '')}")
            if p.get("verification"):
                doc.add_paragraph("  · 확인 방법: " + " / ".join(p["verification"]))
            if p.get("short_term"):
                doc.add_paragraph("  · 단기 조치: " + " / ".join(p["short_term"]))
            if p.get("permanent"):
                doc.add_paragraph("  · 근본 대책: " + " / ".join(p["permanent"]))
            doc.add_paragraph(f"  · 담당: {p.get('owner', '')} · 관련 클레임: {p.get('claim_link', '')}")
            doc.add_paragraph(f"  · 지난주 조치 평가: {p.get('last_week_check', '')}")
    else:
        for i, (t, q, n) in enumerate(ctx.get("top", []), 1):
            _bullet(doc, f" 이번 주 {q:,}개 ({n}건). AI 제안 미작성 — 원인 추정은 회의에서 보완.",
                    bold_prefix=f"{i}순위 {t} —")

    # 5. 특이사항
    _heading(doc, "5. 특이사항")
    for c in ctx.get("changes", []):
        _bullet(doc, f"[{c['규칙']}] {c['내용']}")
    wd = ctx["workdays"]
    short = [f"{w} {d}일" for w, d in wd.items() if w in weeks and d and d < 5]
    if short:
        _bullet(doc, "근무일수 차이: " + ", ".join(short) + " — 추이는 불량률 기준으로 판단")
    nonstd = ctx.get("nonstd")
    if nonstd is not None and not nonstd.empty:
        _bullet(doc, "비표준 조치 값(‘기타’로 집계): " + ", ".join(f"{a} {n}건" for a, n in nonstd.values))
    for line in (ctx.get("notes") or "").splitlines():
        if line.strip():
            _bullet(doc, line.strip().lstrip("-•· "))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ── Excel ────────────────────────────────────────────────────
def build_xlsx(sheets: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df = df.copy()
            keep_index = df.index.name is not None or not isinstance(df.index, pd.RangeIndex)
            df.to_excel(xw, sheet_name=name[:31], index=keep_index)
            ws = xw.sheets[name[:31]]
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max(10, width * 1.6), 50)
                for c in col:
                    if isinstance(c.value, float):
                        c.number_format = "0.00"
            ws.freeze_panes = "B2"
    return buf.getvalue()


def build_markdown(proposals: list[dict], week: str) -> str:
    return proposals_to_markdown(proposals, week)

"""견적비교표(.xlsx)와 협상전략 보고서(.docx) 작성."""
from datetime import date
from io import BytesIO

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from core.common import format_date, format_won
from core.quote_calc import BOOL_TEXT, FIELD_LABELS, best_values

FONT = "맑은 고딕"
MONEY_COLS = {"단가", "운송비", "총액", "실질단가", "MOQ", "실구매수량", "잉여수량"}
DATE_COLS = {"예상 입고일", "견적일", "견적 만료일"}
BEST_FILL = PatternFill("solid", fgColor="D9F2D9")
WARN_FILL = PatternFill("solid", fgColor="FCE4D6")
HEAD_FILL = PatternFill("solid", fgColor="DDEBF7")
THIN = Side(style="thin", color="999999")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def comparison_filename(label, d):
    return f"견적비교_{label}_{d:%Y%m%d}.xlsx"


def strategy_filename(label, d):
    return f"협상전략_{label}_{d:%Y%m%d}.docx"


def _basis_title(b):
    return " ".join(x for x in [b.get("요청번호"), b.get("품목"), f"({b['규격']})" if b.get("규격") else ""] if x)


def _basis_line(b, order_date):
    return (f"비교 기준({b.get('출처', '')}): {format_won(b['수량'])} {b['단위']} · "
            f"희망 납기 {format_date(b.get('희망 납기')) or '없음'} · 발주 예정일 {format_date(order_date)}")


# ---------------------------------------------------------------- 엑셀

def _write_table(ws, start_row, headers, rows):
    for j, h in enumerate(headers, 1):
        c = ws.cell(start_row, j, h)
        c.font = Font(name=FONT, bold=True)
        c.fill = HEAD_FILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX
    for i, row in enumerate(rows, start_row + 1):
        for j, v in enumerate(row, 1):
            c = ws.cell(i, j, v)
            c.font = Font(name=FONT)
            c.border = BOX
            c.alignment = Alignment(vertical="center", wrap_text=isinstance(v, str) and len(v) > 20)


def comparison_xlsx(df, quotes, request, order_date):
    """시트1 비교표, 시트2 추출 원값과 근거."""
    wb = Workbook()
    ws = wb.active
    ws.title = "비교표"
    ws["A1"] = f"견적 비교표 — {_basis_title(request)}"
    ws["A1"].font = Font(name=FONT, bold=True, size=14)
    ws["A2"] = f"{_basis_line(request, order_date)} · 작성일 {format_date(date.today())}"
    ws["A2"].font = Font(name=FONT, color="555555")

    headers = list(df.columns)
    rows = [[(v.to_pydatetime().date() if hasattr(v, "to_pydatetime") else v) for v in r] for r in df.itertuples(index=False)]
    rows = [[None if (isinstance(v, float) and v != v) else v for v in r] for r in rows]
    _write_table(ws, 4, headers, rows)

    best = best_values(df)
    for i in range(len(rows)):
        for j, h in enumerate(headers, 1):
            c = ws.cell(5 + i, j)
            if h in MONEY_COLS or h in ("리드타임(일)", "유효기간(일)"):
                c.number_format = "#,##0"
            if h in DATE_COLS:
                c.number_format = "yyyy-mm-dd"
            if h in best and c.value is not None and c.value == best[h]:
                c.fill = BEST_FILL
                c.font = Font(name=FONT, bold=True)
            if h == "납기 충족" and c.value and "지연" in str(c.value):
                c.fill = WARN_FILL
            if h == "만료 상태" and c.value in ("만료 임박", "만료됨"):
                c.fill = WARN_FILL
            if h == "운송비 조건" and c.value and "미기재" in str(c.value):
                c.fill = WARN_FILL
    note_row = 6 + len(rows)
    ws.cell(note_row, 1, "초록색: 가장 유리한 값 / 주황색: 확인 필요. 실질단가 = 총액 ÷ 비교 기준 수량. "
                         "순위는 실질단가 순(납기 미충족은 뒤로)이며 참고용입니다.").font = Font(name=FONT, color="555555")
    ws.cell(note_row + 1, 1, "AI 추천 결과입니다. 최종 결정 전에 원본 견적서를 확인하세요.").font = Font(name=FONT, color="C00000")
    widths = {"협력사": 14, "운송비 조건": 16, "납기 충족": 11, "결제조건": 18, "금액 검산": 26, "기타조건": 40, "확인사항": 36}
    for j, h in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(j)].width = widths.get(h, 12)
    ws.freeze_panes = "C5"

    # 시트2: 추출 원값과 근거
    ws2 = wb.create_sheet("추출 원값과 근거")
    h2 = ["파일", "포함", *FIELD_LABELS.values(), "결제조건 출처", "금액 검산", "확인사항", "근거(원문)"]
    rows2 = []
    for q in quotes:
        vals = []
        for key in FIELD_LABELS:
            v = q.get(key)
            if key in ("same_item", "vat_included", "freight_included", "mill_sheet"):
                v = BOOL_TEXT.get(v, "미기재")
            elif key == "other_conditions":
                v = " / ".join(v or [])
            vals.append(v)
        evidence = "\n".join(f"{e.get('field')}: {e.get('text')}" for e in q.get("evidence") or [])
        if q.get("same_item_reason"):
            evidence = f"품목일치 판단: {q['same_item_reason']}\n" + evidence
        rows2.append([q.get("_file", ""), "예" if q.get("include") else "아니오", *vals,
                      q.get("payment_terms_source", ""), q.get("amount_check", ""), ", ".join(q.get("flags", [])), evidence])
    _write_table(ws2, 1, h2, rows2)
    for j, h in enumerate(h2, 1):
        ws2.column_dimensions[get_column_letter(j)].width = 60 if h == "근거(원문)" else (30 if h in ("기타조건", "확인사항") else 14)
    for r in ws2.iter_rows(min_row=2):
        for c in r:
            c.alignment = Alignment(vertical="top", wrap_text=True)
    ws2.freeze_panes = "B2"

    out = BytesIO()
    wb.save(out)
    return out.getvalue()


# ---------------------------------------------------------------- 워드

def _set_korean_font(doc):
    for name in ["Normal", "Heading 1", "Heading 2", "Heading 3", "Title"]:
        try:
            st = doc.styles[name]
        except KeyError:
            continue
        st.font.name = FONT
        rpr = st.element.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = rpr.makeelement(qn("w:rFonts"), {})
            rpr.append(rfonts)
        for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rfonts.set(qn(attr), FONT)
    doc.styles["Normal"].font.size = Pt(10)


def _table(doc, headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, h in enumerate(headers):
        cell = t.rows[0].cells[j]
        cell.text = ""
        run = cell.paragraphs[0].add_run(str(h))
        run.bold = True
        run.font.size = Pt(9)
    for r in rows:
        cells = t.add_row().cells
        for j, v in enumerate(r):
            cells[j].text = ""
            run = cells[j].paragraphs[0].add_run("" if v is None else str(v))
            run.font.size = Pt(9)
    return t


def _bullets(doc, items):
    for s in items or []:
        doc.add_paragraph(str(s), style="List Bullet")


def _fmt(col, v):
    if v is None or (isinstance(v, float) and v != v):
        return "-"
    if col in DATE_COLS:
        return format_date(v)
    if col in MONEY_COLS or col in ("리드타임(일)",):
        return format_won(v)
    return str(v)


def strategy_docx(request, df, strategy, order_date, priority, warnings=None):
    doc = Document()
    _set_korean_font(doc)
    doc.add_heading(f"협상전략 보고서 — {_basis_title(request)}", level=0)
    p = doc.add_paragraph()
    p.add_run("수신한 견적서를 분석한 결과를 바탕으로 작성했습니다.\n")
    p.add_run(f"{_basis_line(request, order_date)} · 협상 우선순위: {priority} · 작성일: {format_date(date.today())}")

    doc.add_heading("1. 요약", level=1)
    doc.add_paragraph(strategy.get("summary", ""))

    doc.add_heading("2. 추천 순위", level=1)
    ranking = sorted(strategy.get("ranking", []), key=lambda r: r.get("rank", 99))
    _table(doc, ["순위", "협력사", "이유"], [[r.get("rank"), r.get("supplier"), r.get("reason")] for r in ranking])

    doc.add_heading("3. 견적 비교표 (Python 계산값)", level=1)
    cols = ["순위", "협력사", "단가", "MOQ", "실구매수량", "운송비", "총액", "실질단가", "예상 입고일", "납기 충족", "견적 만료일", "결제조건", "밀시트"]
    cols = [c for c in cols if c in df.columns]
    _table(doc, cols, [[_fmt(c, r[c]) for c in cols] for _, r in df.iterrows()])
    doc.add_paragraph("실질단가 = 총액 ÷ 비교 기준 수량. 순위는 실질단가 순(납기 미충족은 뒤로)이며 참고용입니다.").runs[0].font.size = Pt(8)

    doc.add_heading("4. 협력사별 협상 포인트", level=1)
    for sp in strategy.get("supplier_points", []):
        doc.add_heading(sp.get("supplier", ""), level=2)
        for title, key in [("강점", "strengths"), ("약점", "weaknesses"), ("요청할 사항", "requests")]:
            doc.add_paragraph().add_run(title).bold = True
            _bullets(doc, sp.get(key))
        para = doc.add_paragraph()
        para.add_run("목표 조건: ").bold = True
        para.add_run(sp.get("target_terms", ""))
        para = doc.add_paragraph()
        para.add_run("근거: ").bold = True
        para.add_run(sp.get("rationale", ""))

    doc.add_heading("5. 협상 시나리오", level=1)
    sc = strategy.get("scenario", {})
    for title, key in [("1차 협상안", "first_offer"), ("결렬 시 대안", "fallback"), ("최종 선택지", "final_options")]:
        para = doc.add_paragraph()
        para.add_run(f"{title}: ").bold = True
        para.add_run(sc.get(key, ""))

    doc.add_heading("6. 리스크·확인 필요", level=1)
    _bullets(doc, strategy.get("risks"))
    if warnings:
        doc.add_paragraph().add_run("검증 경고 (프로그램)").bold = True
        _bullets(doc, warnings)

    doc.add_heading("7. 협상 요청 메일 초안", level=1)
    for m in strategy.get("email_drafts", []):
        doc.add_heading(f"{m.get('supplier', '')}", level=2)
        para = doc.add_paragraph()
        para.add_run("제목: ").bold = True
        para.add_run(m.get("subject", ""))
        for line in (m.get("body", "") or "").split("\n"):
            doc.add_paragraph(line)

    doc.add_paragraph()
    warn = doc.add_paragraph().add_run("AI 추천 결과입니다. 최종 결정 전에 원본 견적서를 확인하세요.")
    warn.bold = True
    warn.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

    out = BytesIO()
    doc.save(out)
    return out.getvalue()

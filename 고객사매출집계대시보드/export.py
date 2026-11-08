"""지난분기_매출집계표.xlsx와 같은 배치·서식의 집계표 엑셀 만들기.

값은 계산된 숫자로 넣고 엑셀 수식은 쓰지 않는다(열자마자 값이 보이도록).
"""
from __future__ import annotations

import io
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

import calc

HEADER_FILL = PatternFill("solid", fgColor="DDEBF7")
RED_FILL = PatternFill("solid", fgColor="FFC7CE")
YELLOW_FILL = PatternFill("solid", fgColor="FFEB9C")
THIN = Side(style="thin")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WON = "#,##0"
PCT = "0.0%"
WIDTHS = {"A": 12, "B": 12, "C": 12, "D": 12, "E": 13, "F": 13, "G": 9, "H": 10, "I": 8}


def file_name(s: calc.Summary) -> str:
    return f"{s.year}년_{s.quarter}분기_고객사별_매출집계표.xlsx"


def _ratio(value):
    """Fraction(%) → 엑셀 백분율 서식용 비율(0.96 = 96%)."""
    return None if value is None else float(value / 100)


def _write_row(ws, r: int, c: calc.CustomerResult, bold: bool = False) -> None:
    values = [
        c.name, *c.months, c.total,
        c.target if c.target is not None else "없음",
        _ratio(c.rate),
        _ratio(c.mom) if c.mom is not None else "비교불가",
        c.judgment or None,
    ]
    for col, value in enumerate(values, start=1):
        cell = ws.cell(row=r, column=col, value=value)
        cell.border = BOX
        if bold:
            cell.font = Font(bold=True)
        if 2 <= col <= 6 and isinstance(value, int):
            cell.number_format = WON
        elif col in (7, 8) and isinstance(value, float):
            cell.number_format = PCT
        elif isinstance(value, str) and col > 1:
            cell.alignment = Alignment(horizontal="right" if col < 9 else "center")
    if c.judgment == calc.UNDER:
        ws.cell(row=r, column=7).fill = RED_FILL  # 지난 분기 파일처럼 달성률 칸도 빨강
        ws.cell(row=r, column=9).fill = RED_FILL
    elif c.judgment == calc.CAUTION:
        ws.cell(row=r, column=9).fill = YELLOW_FILL


def build(s: calc.Summary, created: date | None = None) -> bytes:
    created = created or date.today()
    first, last = s.months[0][1], s.months[-1][1]

    wb = Workbook()
    ws = wb.active
    ws.title = f"{s.quarter}분기 집계"

    ws["A1"] = f"{s.label} 고객사별 매출 집계표"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"작성: {created:%Y-%m-%d} · 출하실적 {first}~{last}월 기준 (단위: 원)"

    headers = ["고객사", *s.month_names, "분기 합계", "분기 목표", "달성률", "전월 대비", "판정"]
    for col, text in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=col, value=text)
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        cell.border = BOX

    r = 5
    for c in s.customers:  # 고객사명 가나다순(지난 분기와 같은 순서)
        _write_row(ws, r, c)
        r += 1
    _write_row(ws, r, s.total, bold=True)

    r += 2  # 지난 분기 파일처럼 합계 아래 한 줄 비움
    ws.cell(row=r, column=1, value="분기 합계 상위 3").font = Font(bold=True)
    ws.cell(row=r, column=2, value=" → ".join(c.name for c in s.top3))
    r += 1
    ws.cell(row=r, column=1, value="판정 기준")
    ws.cell(row=r, column=2, value=calc.CRITERIA_TEXT)

    if s.warnings:
        r += 2
        ws.cell(row=r, column=1, value="경고").font = Font(bold=True)
        for w in s.warnings:
            r += 1
            ws.cell(row=r, column=1, value=w)

    for col, width in WIDTHS.items():
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A5"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

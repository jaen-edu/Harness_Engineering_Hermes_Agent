"""업체별 요약, 엑셀 내보내기, 업체 회신용 문구."""
import io

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .normalize import fmt_won

SUMMARY_COLUMNS = ["업체코드", "업체", "명세서 파일", "명세서 행수", "명세서 공급가액", "ERP 행수", "ERP 공급가액",
                   "차이(명세서−ERP)", "불일치 건수", "참고 건수", "판독 검산", "명세서 세액(참고)",
                   "ERP 부가세(참고)", "판정"]


def build_summary(stmt: pd.DataFrame, erp: pd.DataFrame, collapsed: pd.DataFrame, check_ok: dict,
                  vendor_names: dict) -> pd.DataFrame:
    codes = sorted(set(erp["업체코드"]) | set(stmt["업체코드"]))
    out = []
    for c in codes:
        s, e = stmt[stmt["업체코드"] == c], erp[erp["업체코드"] == c]
        iss = collapsed[collapsed["업체코드"] == c] if not collapsed.empty else collapsed
        n_bad = int((~iss["참고"]).sum()) if len(iss) else 0
        n_ref = int(iss["참고"].sum()) if len(iss) else 0
        s_amt, e_amt = float(s["공급가액"].fillna(0).sum()), float(e["공급가액"].fillna(0).sum())
        if s.empty:
            verdict = "명세서 없음"
        elif abs(s_amt - e_amt) < 1 and n_bad == 0:
            verdict = "일치"
        else:
            verdict = "불일치"
        name = vendor_names.get(c) or (e["업체명"].iloc[0] if len(e) else c)
        out.append({
            "업체코드": c, "업체": name, "명세서 파일": ", ".join(sorted(set(s["파일"]))),
            "명세서 행수": len(s), "명세서 공급가액": s_amt, "ERP 행수": len(e), "ERP 공급가액": e_amt,
            "차이(명세서−ERP)": s_amt - e_amt if len(s) else None, "불일치 건수": n_bad, "참고 건수": n_ref,
            "판독 검산": ("통과" if check_ok.get(c, True) else "확인 필요") if len(s) else "-",
            "명세서 세액(참고)": float(s["세액"].fillna(0).sum()) if len(s) and s["세액"].notna().any() else None,
            "ERP 부가세(참고)": float(e["부가세"].fillna(0).sum()) if len(e) else None,
            "판정": verdict,
        })
    df = pd.DataFrame(out, columns=SUMMARY_COLUMNS)
    order = {"불일치": 0, "명세서 없음": 1, "일치": 2}
    return df.sort_values(["판정", "업체코드"], key=lambda col: col.map(order) if col.name == "판정" else col
                          ).reset_index(drop=True)


REPORT_EXPORT_COLUMNS = ["업체", "유형", "틀린 항목", "파일", "위치", "일자", "품번", "발주번호", "명세서 값",
                         "ERP 값", "차액", "ERP 입고번호", "조치", "묶음", "비고"]
READING_EXPORT_COLUMNS = ["업체", "파일", "페이지", "행번호", "일자", "원본일자", "발주번호", "품번", "품명",
                          "수량", "단가", "공급가액", "세액", "반품", "정정", "정정내용", "비고", "검산"]

_HEAD = PatternFill("solid", fgColor="1F4E78")
_YELLOW = PatternFill("solid", fgColor="FFF2B3")
_RED = PatternFill("solid", fgColor="FCE4E4")


def to_excel(summary: pd.DataFrame, issues: pd.DataFrame, rows: pd.DataFrame) -> bytes:
    """요약·불일치 리포트·판독 원본 3개 시트."""
    buf = io.BytesIO()
    sheets = {
        "업체별요약": summary,
        "불일치리포트": issues[REPORT_EXPORT_COLUMNS] if not issues.empty else pd.DataFrame(columns=REPORT_EXPORT_COLUMNS),
        "판독원본": rows[READING_EXPORT_COLUMNS],
    }
    money_cols = {"명세서 공급가액", "ERP 공급가액", "차이(명세서−ERP)", "명세서 세액(참고)", "ERP 부가세(참고)",
                  "차액", "수량", "단가", "공급가액", "세액"}
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name, index=False)
            ws = xw.sheets[name]
            for j, col in enumerate(df.columns, 1):
                c = ws.cell(row=1, column=j)
                c.fill, c.font = _HEAD, Font(bold=True, color="FFFFFF")
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                width = max([len(str(col))] + [len(str(v)) for v in df[col].head(300)]) * 1.3 + 2
                ws.column_dimensions[get_column_letter(j)].width = min(max(width, 8), 48)
                if col in money_cols:
                    for i in range(2, len(df) + 2):
                        ws.cell(row=i, column=j).number_format = "#,##0;[Red]-#,##0"
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            # 강조: 요약은 불일치/검산 확인 필요, 판독원본은 검산 실패 행
            for i, (_, r) in enumerate(df.iterrows(), 2):
                fill = None
                if name == "업체별요약":
                    fill = _YELLOW if r["판독 검산"] == "확인 필요" else (_RED if r["판정"] == "불일치" else None)
                elif name == "판독원본" and r["검산"]:
                    fill = _YELLOW
                if fill:
                    for j in range(1, len(df.columns) + 1):
                        ws.cell(row=i, column=j).fill = fill
    return buf.getvalue()


def reply_text(vendor: str, issues: pd.DataFrame, period: str = "") -> str:
    """업체에 보낼 확인 요청 문구 초안 (F10)."""
    iss = issues[~issues["참고"]]
    if iss.empty:
        return ""
    lines = [f"{vendor} 담당자님 안녕하세요.", "",
             f"{period + ' ' if period else ''}거래명세서를 당사 입고 내역과 대사한 결과, 아래 {len(iss)}건이 서로 달라 확인을 부탁드립니다.", ""]
    for n, (_, r) in enumerate(iss.iterrows(), 1):
        where = f" ({r['파일']} {r['위치']})" if r["위치"] else ""
        lines.append(f"{n}. [{r['유형']}] {r['일자']} {r['품번']}{where}")
        lines.append(f"   - 명세서: {r['명세서 값']} / 당사 입고: {r['ERP 값']} (차액 {fmt_won(r['차액'])})")
    lines += ["", "명세서 수정이 필요한 건은 수정본을, 당사 입고 누락으로 보이는 건은 납품 근거(인수증 등)를 회신해 주시면 확인 후 반영하겠습니다.",
              "", "감사합니다."]
    return "\n".join(lines)

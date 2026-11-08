"""9월 샘플 정답지 테스트 (계획서 3장 표 기준).

    .venv\\Scripts\\python tests\\run_sample_test.py

판독 정답(tests/sample_202609/판독정답_202609.json) → 검산 → 대사를 돌려
업체별 합계, 행 단위 불일치 11건(유형·위치), 한울도금 '일치', 엑셀 3개 시트를 확인한다.
"""
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import openpyxl  # noqa: E402

from core.erp_loader import load_erp  # noqa: E402
from core.pdf_reader import detect_row_bands, dump_reading_json, load_reading_json, rows_to_pages  # noqa: E402
from core.pipeline import build_statement, run_reconcile  # noqa: E402
from core.report import reply_text, to_excel  # noqa: E402
from core.vendors import detect_by_filename, detect_by_name, load_vendors  # noqa: E402

SAMPLE = ROOT / "tests" / "sample_202609"
ERP_FILE = ROOT / "ERP_입고이력" / "ERP_외주입고이력_202609.xlsx"
PDF_DIR = ROOT / "거래명세서_스캔"

EXPECTED_TOTALS = {  # 업체코드: (명세서, ERP)
    "V001": (10_750_000, 10_434_000), "V005": (9_583_773, 10_006_773), "V003": (6_039_000, 5_723_000),
    "V004": (5_564_800, 5_656_800), "V006": (3_785_500, 3_724_750), "V007": (2_753_700, 2_785_500),
    "V002": (7_211_000, 7_211_000),
}
# (업체코드, 유형, 위치, 차액)
EXPECTED_ISSUES = {
    ("V001", "수량 불일치", "1페이지 1행", 225_000),
    ("V001", "단가 불일치", "1페이지 8·11행, 2페이지 17·19행", 91_000),
    ("V005", "명세서 누락", "", -423_000),
    ("V003", "ERP 중복 의심", "1페이지 1행", -64_000),
    ("V003", "ERP 미입고", "2페이지 17행", 380_000),
    ("V004", "품번 불일치", "1페이지 14행", -92_000),
    ("V004", "일자 불일치", "1페이지 10행", 0),
    ("V006", "수량 불일치", "1페이지 1행", 60_750),
    ("V006", "일자 불일치", "1페이지 9행", 0),
    ("V007", "반품 미반영", "5페이지 3행", -31_800),
    ("V004", "정정 표기", "1페이지 1행", 0),
}

failures = []


def check(cond, msg):
    print(("  OK   " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)


def main():
    vendors = load_vendors()
    files = load_reading_json((SAMPLE / "판독정답_202609.json").read_bytes())
    vmap = {fn: detect_by_filename(fn, vendors) for fn in files}

    print("[업체 인식]")
    check(all(vmap.values()) and len(set(vmap.values())) == 7, f"파일명으로 7개 업체 인식: {vmap}")
    for fn, pages in files.items():
        check(detect_by_name(pages[0]["supplier_name"], vendors) == vmap[fn], f"상호로 인식 {pages[0]['supplier_name']}")

    erp = load_erp(ERP_FILE)
    rows, info = build_statement(files, vmap, vendors)
    res = run_reconcile(rows, info, erp, vendors)

    print("[판독·검산]")
    check(len(erp) == 135, f"ERP 135행 (실제 {len(erp)})")
    check(len(res.rows) == 134, f"명세서 134행 (실제 {len(res.rows)})")
    check(res.rows["일자"].notna().all(), "모든 일자 YYYY-MM-DD 로 정규화(연도 보충 포함)")
    check((res.rows["검산"] == "").all(), "행별 수량×단가=공급가액 전부 통과")
    check((res.totals["결과"] == "일치").all() and len(res.totals) == 15,
          f"인쇄 합계 검산 15건 모두 일치 (월합계 6 + 한성 건별 9) → {res.totals['결과'].value_counts().to_dict()}")
    sw = res.rows[res.rows["업체코드"] == "V006"]
    check(list(sw["행번호"]) == list(range(1, 15)), "성원금속(번호 열 없음) 행번호 1~14 자동 부여")
    hs = res.rows[(res.rows["업체코드"] == "V007") & res.rows["반품"]]
    check(len(hs) == 1 and hs.iloc[0]["공급가액"] == -31_800, "한성유압 △반품 행 음수 처리")

    print("[업체별 합계]")
    s = res.summary.set_index("업체코드")
    for code, (st, ep) in EXPECTED_TOTALS.items():
        check(s.loc[code, "명세서 공급가액"] == st and s.loc[code, "ERP 공급가액"] == ep,
              f"{code} {s.loc[code, '업체']}: 명세서 {s.loc[code, '명세서 공급가액']:,.0f} / ERP {s.loc[code, 'ERP 공급가액']:,.0f}")
    check(s["명세서 공급가액"].sum() == 45_687_773 and s["ERP 공급가액"].sum() == 45_541_823, "전체 합계 45,687,773 / 45,541,823")
    check(s.loc["V002", "판정"] == "일치", "한울도금 '일치'")
    check((s.drop(index="V002")["판정"] == "불일치").all(), "나머지 6개 업체 '불일치'")

    print("[행 단위 불일치 11건]")
    got = {(r["업체코드"], r["유형"], r["위치"], round(r["차액"])) for _, r in res.collapsed.iterrows()}
    for _, r in res.collapsed.iterrows():
        print(f"       {r['업체']:<10} {r['유형']:<8} {r['위치'] or '—':<28} {r['일자']:<22} {r['품번']:<28} "
              f"{r['명세서 값']} | {r['ERP 값']} | {r['차액']:+,.0f}")
    check(len(res.collapsed) == 11, f"묶음 기준 11건 (실제 {len(res.collapsed)})")
    for e in sorted(EXPECTED_ISSUES):
        check(e in got, f"검출: {e}")
    for g in sorted(got - EXPECTED_ISSUES):
        check(False, f"예상 밖 검출: {g}")
    check((res.issues["묶음"] != "").sum() == 4, "대성정밀 PO2609-0133 단가 4건이 한 묶음")

    print("[PDF 위치 표시]")
    for fn, pages in files.items():
        pdf = (PDF_DIR / fn).read_bytes()
        for p in pages:
            n = len(p["rows"])
            check(len(detect_row_bands(pdf, p["page"], n)) >= n, f"{fn} {p['page']}p 행 위치 {n}개 이상 검출")

    print("[내보내기]")
    xlsx = to_excel(res.summary, res.issues, res.rows)
    wb = openpyxl.load_workbook(io.BytesIO(xlsx))
    check(wb.sheetnames == ["업체별요약", "불일치리포트", "판독원본"], f"엑셀 3개 시트 {wb.sheetnames}")
    check(wb["판독원본"].max_row == 135, "판독원본 134행 + 머리글")
    again = load_reading_json(dump_reading_json(rows_to_pages(res.rows, info)))
    rows2, info2 = build_statement(again, vmap, vendors)
    res2 = run_reconcile(rows2, info2, erp, vendors)
    check(len(res2.collapsed) == 11 and res2.summary["명세서 공급가액"].sum() == 45_687_773,
          "수정본 JSON 내려받기 → 다시 불러오기 결과 동일")
    txt = reply_text("(주)대성정밀", res.collapsed[res.collapsed["업체코드"] == "V001"], "2026년 9월")
    check("단가 불일치" in txt and "수량 불일치" in txt, "업체 회신 문구 생성")

    print("[검산 이상 탐지 — 판독값 하나를 일부러 바꿔 넣기]")
    bad = res.rows.copy()
    i = bad.index[(bad["업체코드"] == "V002") & (bad["행번호"] == 5)][0]
    bad.loc[i, "공급가액"] = 199_000
    res3 = run_reconcile(bad, info, erp, vendors)
    check(res3.rows.loc[i, "검산"] != "", "바꾼 행이 검산 실패로 표시")
    check(res3.summary.set_index("업체코드").loc["V002", "판독 검산"] == "확인 필요", "한울도금 요약이 '확인 필요'로 표시")

    print()
    if failures:
        print(f"실패 {len(failures)}건")
        sys.exit(1)
    print("전체 통과")


if __name__ == "__main__":
    main()

"""개발계획서 9장 기준값 검증 (W38~W42 샘플)."""
import io
import sys
from pathlib import Path

import pandas as pd
import pytest
from docx import Document

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import aggregate, analyze, loader, report  # noqa: E402
from core.ai_advisor import _extract_json, build_user_prompt  # noqa: E402

SAMPLE = ROOT / "sample_data"


@pytest.fixture(scope="module")
def data():
    prod = loader.load_production(SAMPLE / "생산수량_주별.xlsx")
    files = sorted((SAMPLE / "불량기록").glob("*.xlsx"))
    dfx = loader.load_defects(files, prod.data)
    wl = aggregate.week_line(dfx.data, prod.data)
    return prod, dfx, wl


def test_row_counts(data):
    _, dfx, _ = data
    assert not dfx.errors
    assert len(dfx.data) == 223
    assert dfx.data.groupby("주차").size().to_dict() == {"W38": 37, "W39": 40, "W40": 46, "W41": 46, "W42": 54}
    assert (dfx.data["문제"] == "").all()
    assert not dfx.warnings  # 파일명 주차 = 발생일 주차


def test_w41_line_rates(data):
    _, _, wl = data
    r = wl[wl["주차"] == "W41"].set_index("라인")["불량률"].round(2).to_dict()
    assert r == {"1라인": 3.64, "2라인": 4.76, "3라인": 3.23, "4라인": 4.60}


def test_w42_total(data):
    _, _, wl = data
    k = aggregate.kpi(wl, "W42")
    assert (k["불량수량"], k["생산수량"]) == (552, 13950)
    assert round(k["불량률"], 2) == 3.96
    assert round(k["전주_불량률"], 2) == 3.98


def test_w42_line_rates(data):
    _, _, wl = data
    r = wl[wl["주차"] == "W42"].set_index("라인")["불량률"].round(2).to_dict()
    assert r == {"1라인": 4.70, "2라인": 5.92, "3라인": 1.16, "4라인": 4.01}


def test_w42_top3(data):
    _, dfx, _ = data
    t = aggregate.top_types(dfx.data, "W42", 3)
    assert list(zip(t["불량유형"], t["불량수량"])) == [("버(burr)", 198), ("도장불량", 193), ("치수불량", 90)]


def test_change_points(data):
    _, dfx, wl = data
    weeks = aggregate.window(wl["주차"], "W42", 5)
    ch = analyze.detect_changes(dfx.data, wl, "W42", weeks)
    got = {(c["규칙"], c["대상"]) for c in ch}
    assert got == {
        ("유형 급증", "도장불량"), ("유형 급증", "치수불량"),
        ("연속 상승", "1라인"),
        ("하루 집중", "2라인 PN-1003 치수불량"),
        ("유출 위험", "도장불량"), ("유출 위험", "이물·오염"),
    }
    text = " ".join(c["내용"] for c in ch)
    assert "107 → 193" in text and "49 → 90" in text and "112/193" in text and "9/9" in text


def test_focus_cells(data):
    _, dfx, _ = data
    top = analyze.cross_top(dfx.data, "W42", 10)
    first = top.iloc[0]
    assert (first["라인"], first["품번"], first["불량유형"], first["불량수량"]) == ("1라인", "PN-1011", "도장불량", 146)
    row = top[(top["품번"] == "PN-1003") & (top["불량유형"] == "치수불량")].iloc[0]
    assert row["불량수량"] == 64


def test_nonstandard_action(data):
    _, dfx, _ = data
    ns = loader.non_standard_actions(dfx.data)
    assert ns.values.tolist() == [["10/13 생산분 전수 선별", 9]]


def test_last_report_parse():
    r = loader.load_last_report(SAMPLE / "지난주_불량분석리포트_W41.docx")
    assert "W41" in r["title"]
    assert "도장불량" in r["cause_section"] and "디버링" in r["cause_section"]


def test_invalid_inputs(data):
    prod, _, _ = data
    bad = pd.DataFrame({
        "발생 일": ["2026-10-12", "2026-10-13", "2026-11-30"],   # 별칭/공백 다른 열 이름
        "라인": ["1 라인", "9라인", "2라인"],
        "품번": ["PN-1"] * 3, "품명": ["x"] * 3, "출하처": ["a"] * 3, "불량유형": ["버(burr)"] * 3,
        "불량수량": [3, "많음", 2], "발견공정": ["공정검사"] * 3, "조치": ["폐기"] * 3, "기록자": ["k"] * 3,
    })
    buf = io.BytesIO()
    bad.to_excel(buf, index=False)
    buf.name = "불량기록_W42_test.xlsx"
    buf.seek(0)
    res = loader.load_defects([buf], prod.data)
    # '발생 일'은 표준 이름으로 매칭됨(공백 무시)
    assert not res.errors
    p = res.data["문제"].tolist()
    assert p[0] == ""                               # '1 라인' → '1라인' 정규화
    assert "생산수량에 없는 라인" in p[1] and "숫자가 아님" in p[1]
    assert "생산수량에 없는 주차" in p[2]
    assert any("W49" in w for w in res.warnings)    # 파일명 주차와 불일치 경고

    missing = pd.DataFrame({"날짜X": [1], "라인": ["1라인"]})
    buf2 = io.BytesIO()
    missing.to_excel(buf2, index=False)
    buf2.name = "wrong.xlsx"
    buf2.seek(0)
    res2 = loader.load_defects([buf2], prod.data)
    assert res2.errors and "필수 열 없음" in res2.errors[0] and "발생일" in res2.errors[0]


def test_prompt_and_exports(data):
    prod, dfx, wl = data
    d = dfx.data
    weeks = aggregate.window(wl["주차"], "W42", 5)
    tq = aggregate.type_trend(d, weeks, "qty")
    tc = aggregate.type_trend(d, weeks, "count")
    k = aggregate.kpi(wl, "W42")
    ch = analyze.detect_changes(d, wl, "W42", weeks)
    memo = (SAMPLE / "참고_이번주_현장메모.md").read_text(encoding="utf-8")
    last = loader.load_last_report(SAMPLE / "지난주_불량분석리포트_W41.docx")
    prompt = build_user_prompt(d, "W42", weeks, ["버(burr)", "도장불량", "치수불량"], tq, tc, ch, k, memo, last)
    assert "CL-2610-03" in prompt and "MCT-02" in prompt and "107 → 193" in prompt

    proposals = _extract_json('```json\n{"proposals":[{"rank":1,"defect_type":"도장불량","phenomenon":"x",'
                              '"suspected_causes":[],"verification":["a"],"short_term":["b"],"permanent":["c"],'
                              '"owner":"구매팀","claim_link":"CL","last_week_check":"y"}]}\n```')["proposals"]
    rp = aggregate.rate_pivot(wl, weeks)
    wd = prod.data.groupby("주차")["근무일수"].max().to_dict()
    ctx = dict(week="W42", weeks=weeks, kpi=k, prod_dates=("2026-10-12", "2026-10-16"), type_qty=tq,
               type_cnt=tc, wl_week=wl[wl["주차"] == "W42"], rate_pivot=rp, workdays=wd, changes=ch,
               proposals=proposals, notes="메모", nonstd=loader.non_standard_actions(d), top=[])
    doc = Document(io.BytesIO(report.build_docx(ctx)))
    heads = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
    assert [h.split(".")[0] for h in heads] == ["1", "2", "3", "4", "5"]
    assert len(doc.tables) == 2 and len(doc.inline_shapes) == 2

    xb = report.build_xlsx({"주차x라인": wl, "유형추이": tq})
    assert pd.read_excel(io.BytesIO(xb), sheet_name=None).keys() == {"주차x라인", "유형추이"}
    assert "1순위 도장불량" in report.build_markdown(proposals, "W42")

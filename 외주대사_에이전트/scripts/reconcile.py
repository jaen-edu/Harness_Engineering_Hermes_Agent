# -*- coding: utf-8 -*-
"""외주거래명세서(판독 결과) ↔ ERP 외주입고이력 대사 스크립트

사용법:
    python scripts/reconcile.py --month 2026-09

입력:
    work/<월>/추출/<업체코드>_명세서추출.csv   (Claude가 스캔본을 판독해 만든 파일)
    work/<월>/추출/<업체코드>_명세서합계.json  (명세서 하단에 인쇄된 합계)
    input/<월>/ERP_입고이력/*.xlsx               (ERP에서 내려받은 입고이력)
    config/업체마스터.csv, config/대사기준.json
출력:
    output/<월>/외주대사결과_<YYYYMM>.xlsx
    output/<월>/대사요약_<YYYYMM>.md
"""
import argparse, glob, json, os, sys
from datetime import date
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ------------------------------------------------------------------ 로딩
def load_config():
    with open(os.path.join(BASE, "config", "대사기준.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    master = pd.read_csv(os.path.join(BASE, "config", "업체마스터.csv"), dtype=str, encoding="utf-8-sig")
    return cfg, master

def load_erp(month, cfg):
    files = glob.glob(os.path.join(BASE, "input", month, "ERP_입고이력", "*.xls*"))
    files = [f for f in files if not os.path.basename(f).startswith("~$")]
    if not files:
        sys.exit(f"[오류] input/{month}/ERP_입고이력/ 에 엑셀 파일이 없습니다.")
    col = cfg["erp_columns"]           # 표준명 -> ERP 실제 헤더명
    frames = []
    for f in files:
        raw = pd.read_excel(f, header=None, dtype=object)
        # 헤더 행 자동 탐지(ERP 다운로드 파일 상단에 제목/조회조건이 붙는 경우 대비)
        hdr_row = next(i for i in range(min(15, len(raw)))
                       if col["입고일자"] in [str(x).strip() for x in raw.iloc[i].tolist()])
        df = pd.read_excel(f, header=hdr_row, dtype=object)
        df.columns = [str(c).strip() for c in df.columns]
        missing = [v for v in col.values() if v not in df.columns]
        if missing:
            sys.exit(f"[오류] {os.path.basename(f)} 에 컬럼이 없습니다: {missing}  → config/대사기준.json 의 erp_columns 를 확인하세요.")
        df = df[list(col.values())].rename(columns={v: k for k, v in col.items()})
        df["ERP파일"] = os.path.basename(f)
        df["ERP행"] = df.index + hdr_row + 2
        frames.append(df)
    erp = pd.concat(frames, ignore_index=True)
    erp = erp[erp["입고일자"].notna()].copy()
    erp["입고일자"] = pd.to_datetime(erp["입고일자"]).dt.date
    for c in ["입고수량", "단가", "공급가액", "부가세"]:
        erp[c] = pd.to_numeric(erp[c].astype(str).str.replace(",", ""), errors="coerce").fillna(0).round().astype(int)
    for c in ["발주번호", "업체코드", "품번", "입고번호"]:
        erp[c] = erp[c].astype(str).str.strip().str.upper()
    return erp

def load_statements(month):
    d = os.path.join(BASE, "work", month, "추출")
    files = sorted(glob.glob(os.path.join(d, "*_명세서추출.csv")))
    if not files:
        sys.exit(f"[오류] {d} 에 판독 결과(*_명세서추출.csv)가 없습니다. 먼저 스캔본을 판독하세요.")
    st = pd.concat([pd.read_csv(f, dtype=str, encoding="utf-8-sig") for f in files], ignore_index=True)
    st["납품일자"] = pd.to_datetime(st["납품일자"]).dt.date
    for c in ["페이지", "순번", "수량", "단가", "공급가액"]:
        st[c] = pd.to_numeric(st[c].str.replace(",", ""), errors="coerce").fillna(0).astype(int)
    # 세액: 라인별 세액이 없는 양식(하단 일괄 부가세)은 빈칸 → None 으로 두고 비교에서 제외
    st["세액"] = pd.to_numeric(st["세액"].fillna("").str.replace(",", ""), errors="coerce")
    for c in ["발주번호", "업체코드", "품번"]:
        st[c] = st[c].fillna("").astype(str).str.strip().str.upper()
    st["수기정정"] = st["수기정정"].fillna("N")
    st["비고"] = st["비고"].fillna("")
    # 선택 컬럼: 명세서번호(납품건별 명세서), 순번표기(인쇄 / 줄위치)
    st["명세서번호"] = st["명세서번호"].fillna("") if "명세서번호" in st else ""
    st["순번표기"] = st["순번표기"].fillna("인쇄").replace("", "인쇄") if "순번표기" in st else "인쇄"
    st["행위치"] = st.groupby(["파일명", "페이지"])["순번"].rank(method="first").astype(int)
    totals = {}
    for f in glob.glob(os.path.join(d, "*_명세서합계.json")):
        with open(f, encoding="utf-8") as fh:
            t = json.load(fh)
        totals[t["업체코드"]] = t
    return st, totals

# ------------------------------------------------------------------ 매칭
def match_vendor(S, E, cfg):
    """S: 명세서 라인(DataFrame), E: ERP 행. 반환: [(s_idx, e_idx, 매칭방법)], 남은 S, 남은 E"""
    tol_days = cfg["입고일자_허용일수"]
    s_left = list(S.sort_values(["페이지", "순번"]).index)
    e_left = list(E.sort_values(["입고일자", "입고번호"]).index)
    pairs = []

    def run(cond, method, key=lambda s, e: 0):
        for si in list(s_left):
            s = S.loc[si]
            cands = [ei for ei in e_left if cond(s, E.loc[ei])]
            if cands:
                ei = min(cands, key=lambda ei: key(s, E.loc[ei]))
                pairs.append((si, ei, method)); s_left.remove(si); e_left.remove(ei)

    dd = lambda s, e: abs((s["납품일자"] - e["입고일자"]).days)
    # 1) 완전일치: 발주번호+품번+수량+일자
    run(lambda s, e: s["발주번호"] == e["발주번호"] and s["품번"] == e["품번"]
        and s["수량"] == e["입고수량"] and s["납품일자"] == e["입고일자"], "완전일치")
    # 2) 발주번호+품번+일자 (수량/단가 차이 후보)
    run(lambda s, e: s["발주번호"] == e["발주번호"] and s["품번"] == e["품번"]
        and s["납품일자"] == e["입고일자"], "발주+품번+일자")
    # 3) 발주번호+품번+수량, 일자 허용범위 내 (일자 차이 후보)
    run(lambda s, e: s["발주번호"] == e["발주번호"] and s["품번"] == e["품번"]
        and s["수량"] == e["입고수량"] and dd(s, e) <= tol_days, "발주+품번+수량", dd)
    # 4) 발주번호+일자, 품번 다름 (품번 오기 후보)
    run(lambda s, e: s["발주번호"] == e["발주번호"] and dd(s, e) <= 1, "발주+일자(품번상이)", dd)
    # 5) 품번+일자, 발주번호 다름
    run(lambda s, e: s["품번"] == e["품번"] and s["납품일자"] == e["입고일자"],
        "품번+일자" , lambda s, e: abs(s["수량"] - e["입고수량"]))
    # 6) 발주번호+품번, 일자 허용범위 내 (수량·일자 모두 다름)
    run(lambda s, e: s["발주번호"] == e["발주번호"] and s["품번"] == e["품번"] and dd(s, e) <= tol_days,
        "발주+품번", dd)
    # 7) 명세서에 발주번호가 없는 양식: 품번+수량, 일자 허용범위 내
    run(lambda s, e: s["발주번호"] == "" and s["품번"] == e["품번"] and s["수량"] == e["입고수량"]
        and dd(s, e) <= tol_days, "품번+수량(발주번호 없음)", dd)
    # 8) 분할입고: 남은 ERP 행이 이미 짝지어진 ERP 행과 같은 발주·품번·일자·단가이고, 두 수량 합 = 명세서 수량
    for ei in list(e_left):
        e = E.loc[ei]
        for k, (si, e1, method) in enumerate(pairs):
            if isinstance(e1, list):
                continue
            x, s = E.loc[e1], S.loc[si]
            if (x["발주번호"], x["품번"], x["입고일자"], x["단가"]) == (e["발주번호"], e["품번"], e["입고일자"], e["단가"]) \
                    and s["수량"] == x["입고수량"] + e["입고수량"] and s["수량"] != x["입고수량"]:
                pairs[k] = (si, [e1, ei], "분할입고(합산)"); e_left.remove(ei)
                break
    return pairs, s_left, e_left

def erp_view(E, ei):
    """짝지어진 ERP 행. 분할입고면 여러 행을 합산한 가상의 1행으로 돌려준다."""
    if not isinstance(ei, list):
        return E.loc[ei]
    rows = E.loc[ei]
    e = rows.iloc[0].copy()
    for c in ["입고수량", "공급가액", "부가세"]:
        e[c] = int(rows[c].sum())
    e["입고번호"] = ", ".join(rows["입고번호"])
    e["분할수량"] = " + ".join(f"{q:,}" for q in rows["입고수량"])
    return e

def where(s):
    """담당자가 원본에서 찾는 좌표 문구"""
    w = f"{s['파일명']} {s['페이지']}페이지"
    if s["명세서번호"]:
        w += f" (명세서 {s['명세서번호']})"
    if s["순번표기"] == "줄위치":
        return w + f" 표 위에서 {s['행위치']}번째 줄"
    return w + f" No.{s['순번']}"

SEV = {"수량 상이": "중요", "단가 상이": "중요", "품번 상이": "중요", "공급가액 상이": "중요",
       "ERP 입고누락": "중요", "ERP 중복입고 의심": "중요", "명세서 미기재(ERP에만 있음)": "중요",
       "입고일자 상이": "확인", "발주번호 상이": "확인", "세액 상이": "확인",
       "세액 끝전차이": "참고", "수기정정 확인": "참고", "ERP 반품처리 누락": "중요", "ERP 분할입고": "참고"}
ACTION = {"수량 상이": "명세서 원본 수량 재확인 후 ERP 입고수량 수정 또는 업체에 정정 요청",
          "단가 상이": "구매단가 계약(단가합의서) 확인 → ERP 단가 갱신 또는 업체 명세서 정정 요청",
          "품번 상이": "실물/발주서 확인 후 ERP 입고 품번 정정(단가도 함께 변경됨)",
          "공급가액 상이": "수량×단가 계산 재확인",
          "ERP 입고누락": "실입고 여부 확인 → 입고처리 누락이면 ERP 입고 등록",
          "ERP 중복입고 의심": "ERP 입고번호 2건 비교 → 중복이면 1건 입고취소",
          "명세서 미기재(ERP에만 있음)": "전월/익월 명세서 포함 여부 확인, 없으면 업체에 명세서 추가 발행 요청",
          "입고일자 상이": "마감월이 바뀌지 않으면 참고 처리, 월이 바뀌면 귀속월 정리",
          "발주번호 상이": "어느 발주로 입고됐는지 확인 후 ERP 발주 연결 정정",
          "세액 상이": "세액 계산 기준 확인",
          "세액 끝전차이": "반올림/절사 차이 — 세금계산서 합계 기준으로 처리(조치 불필요)",
          "수기정정 확인": "정정값으로 대사함. 업체 정정 날인 여부만 확인",
          "ERP 반품처리 누락": "반품 실물 출고 확인 → ERP 반품(입고취소) 처리",
          "ERP 분할입고": "합계 일치 — 조치 불필요(필요시 ERP 1건으로 통합)"}

def compare(s, e, cfg):
    diffs = []  # (유형, 명세서값, ERP값)
    if s["품번"] != e["품번"]:
        diffs.append(("품번 상이", s["품번"], e["품번"]))
    if s["수량"] != e["입고수량"]:
        diffs.append(("수량 상이", f"{s['수량']:,}", f"{e['입고수량']:,}"))
    if s["단가"] != e["단가"]:
        diffs.append(("단가 상이", f"{s['단가']:,}", f"{e['단가']:,}"))
    if s["공급가액"] != e["공급가액"] and s["수량"] == e["입고수량"] and s["단가"] == e["단가"]:
        diffs.append(("공급가액 상이", f"{s['공급가액']:,}", f"{e['공급가액']:,}"))
    if s["납품일자"] != e["입고일자"]:
        diffs.append(("입고일자 상이", str(s["납품일자"]), str(e["입고일자"])))
    if s["발주번호"] and s["발주번호"] != e["발주번호"]:
        diffs.append(("발주번호 상이", s["발주번호"], e["발주번호"]))
    vd = 0 if pd.isna(s["세액"]) else int(s["세액"]) - e["부가세"]
    if vd != 0 and s["공급가액"] == e["공급가액"]:
        t = "세액 끝전차이" if abs(vd) <= cfg["세액_끝전_허용원"] else "세액 상이"
        diffs.append((t, f"{s['세액']:,}", f"{e['부가세']:,}"))
    if e.get("분할수량"):
        diffs.append(("ERP 분할입고", f"{s['수량']:,}", f"{e['분할수량']} ({e['입고번호']})"))
    if s["수기정정"] == "Y":
        diffs.append(("수기정정 확인", s["비고"] or "수기정정", f"{e['입고수량']:,}"))
    return diffs

# ------------------------------------------------------------------ 메인
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", required=True, help="마감월 YYYY-MM")
    a = ap.parse_args()
    month = a.month
    cfg, master = load_config()
    erp = load_erp(month, cfg)
    st, totals = load_statements(month)

    vendors = master.to_dict("records")
    vname = {v["업체코드"]: v["업체명"] for v in vendors}
    diff_rows, match_rows, summary = [], [], []

    for v in vendors:
        vc = v["업체코드"]
        S = st[st["업체코드"] == vc]
        E = erp[erp["업체코드"] == vc]
        if S.empty and E.empty:
            continue
        pairs, s_left, e_left = match_vendor(S, E, cfg)
        for si, ei, method in pairs:
            s, e = S.loc[si], erp_view(E, ei)
            ds = compare(s, e, cfg)
            match_rows.append([vc, vname[vc], s["파일명"], s["페이지"], s["순번"], s["명세서번호"], s["납품일자"], s["발주번호"],
                               s["품번"], s["수량"], s["단가"], s["공급가액"], "" if pd.isna(s["세액"]) else int(s["세액"]),
                               e["입고번호"], e["입고일자"], e["발주번호"], e["품번"], e["입고수량"], e["단가"],
                               e["공급가액"], e["부가세"], method, ", ".join(d[0] for d in ds) or "일치"])
            amt_done = False   # 한 라인에 차이가 여러 개여도 금액차이는 한 번만 기재(합계 중복 방지)
            for t, sv, ev in ds:
                amt_type = t in ("수량 상이", "단가 상이", "품번 상이", "공급가액 상이")
                amt = int(s["공급가액"] - e["공급가액"]) if amt_type and not amt_done else 0
                amt_done = amt_done or amt_type
                diff_rows.append(dict(업체코드=vc, 업체명=vname[vc], 심각도=SEV[t], 차이유형=t, 찾는위치=where(s),
                                      명세서파일=s["파일명"], 페이지=s["페이지"], 순번=s["순번"], 명세서번호=s["명세서번호"],
                                      납품일자=s["납품일자"], 발주번호=s["발주번호"], 품번=s["품번"], 품명=s["품명"],
                                      명세서값=sv, ERP값=ev, ERP입고번호=e["입고번호"],
                                      공급가액차이=amt,
                                      조치제안=ACTION[t]))
        for si in s_left:
            s = S.loc[si]
            t = "ERP 반품처리 누락" if s["수량"] < 0 else "ERP 입고누락"
            diff_rows.append(dict(업체코드=vc, 업체명=vname[vc], 심각도="중요", 차이유형=t, 찾는위치=where(s),
                                  명세서파일=s["파일명"], 페이지=s["페이지"], 순번=s["순번"], 명세서번호=s["명세서번호"],
                                  납품일자=s["납품일자"],
                                  발주번호=s["발주번호"], 품번=s["품번"], 품명=s["품명"],
                                  명세서값=f"수량 {s['수량']:,} / 공급가액 {s['공급가액']:,}", ERP값="없음",
                                  ERP입고번호="", 공급가액차이=int(s["공급가액"]), 조치제안=ACTION[t]))
        for ei in e_left:
            e = E.loc[ei]
            twin = next((m for m in pairs if not isinstance(m[1], list) and E.loc[m[1]]["발주번호"] == e["발주번호"] and E.loc[m[1]]["품번"] == e["품번"]
                         and E.loc[m[1]]["입고수량"] == e["입고수량"] and E.loc[m[1]]["입고일자"] == e["입고일자"]), None)
            if twin:
                s = S.loc[twin[0]]
                t = "ERP 중복입고 의심"
                loc = dict(찾는위치=where(s), 명세서파일=s["파일명"], 페이지=s["페이지"], 순번=s["순번"],
                           명세서번호=s["명세서번호"], 납품일자=s["납품일자"])
                sv = f"1건(수량 {s['수량']:,})"
                ev = f"2건 — {E.loc[twin[1]]['입고번호']}, {e['입고번호']}"
            else:
                t = "명세서 미기재(ERP에만 있음)"
                loc = dict(찾는위치=f"명세서에 없음 (ERP 엑셀 {e['ERP행']}행, {e['입고번호']})", 명세서파일="(해당 명세서에 없음)",
                           페이지=None, 순번=None, 명세서번호="", 납품일자=e["입고일자"])
                sv = "없음"
                ev = f"수량 {e['입고수량']:,} / 공급가액 {e['공급가액']:,}"
            diff_rows.append(dict(업체코드=vc, 업체명=vname[vc], 심각도="중요", 차이유형=t, **loc,
                                  발주번호=e["발주번호"], 품번=e["품번"], 품명=e["품명"], 명세서값=sv, ERP값=ev,
                                  ERP입고번호=e["입고번호"], 공급가액차이=-int(e["공급가액"]), 조치제안=ACTION[t]))
        tot = totals.get(vc, {})
        line_vat = S["세액"].dropna()
        no_line_vat = len(S) > 0 and line_vat.empty   # 라인 세액이 없는 양식 → 인쇄 합계 세액 사용
        summary.append(dict(업체코드=vc, 업체명=vname[vc], 명세서파일=S["파일명"].iloc[0] if len(S) else "(없음)",
                            명세서라인=len(S), ERP행=len(E), 매칭=len(pairs),
                            명세서공급가액=int(S["공급가액"].sum()), ERP공급가액=int(E["공급가액"].sum()),
                            명세서세액=int(tot.get("세액합계", 0)) if no_line_vat else int(line_vat.sum()),
                            ERP세액=int(E["부가세"].sum()),
                            인쇄합계_공급가액=tot.get("공급가액합계"),
                            판독검증="OK" if tot and tot.get("공급가액합계") == int(S["공급가액"].sum())
                            and (no_line_vat or tot.get("세액합계") == int(line_vat.sum())) else ("합계 불일치-재판독" if tot else "합계 미입력")))

    order = {"중요": 0, "확인": 1, "참고": 2}
    diff_rows.sort(key=lambda r: (r["업체코드"], r["페이지"] if r["페이지"] is not None else 999,
                                  r["순번"] if r["순번"] is not None else 999, order[r["심각도"]]))
    out_dir = os.path.join(BASE, "output", month); os.makedirs(out_dir, exist_ok=True)
    ym = month.replace("-", "")
    xlsx = os.path.join(out_dir, f"외주대사결과_{ym}.xlsx")
    write_xlsx(xlsx, month, summary, diff_rows, match_rows, st)
    md = os.path.join(out_dir, f"대사요약_{ym}.md")
    write_md(md, month, summary, diff_rows)
    print(f"[완료] {xlsx}\n[완료] {md}")
    print(f"상이 {len(diff_rows)}건 (중요 {sum(r['심각도']=='중요' for r in diff_rows)}, "
          f"확인 {sum(r['심각도']=='확인' for r in diff_rows)}, 참고 {sum(r['심각도']=='참고' for r in diff_rows)})")

# ------------------------------------------------------------------ 출력
HF = PatternFill("solid", fgColor="44546A")
SEV_FILL = {"중요": PatternFill("solid", fgColor="F8CBAD"), "확인": PatternFill("solid", fgColor="FFE699"),
            "참고": PatternFill("solid", fgColor="DDEBF7")}
thin = Side(style="thin", color="BFBFBF")

def style_header(ws, ncol, row=1):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = Font(name="Arial", bold=True, color="FFFFFF"); cell.fill = HF
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

def body_font(ws, start=2):
    for row in ws.iter_rows(min_row=start):
        for c in row:
            if c.font is None or not c.font.bold:
                c.font = Font(name="Arial", size=10)
            c.border = Border(bottom=thin)

def widths(ws, ws_):
    for i, w in enumerate(ws_, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

def write_xlsx(path, month, summary, diffs, matches, st):
    wb = Workbook()
    # 요약
    ws = wb.active; ws.title = "요약"
    ws["A1"] = f"외주거래명세서 ↔ ERP 입고이력 대사 결과 ({month})"; ws["A1"].font = Font(name="Arial", bold=True, size=14)
    ws["A2"] = "기준: 외주거래명세서 스캔본. 차이금액 = 명세서 − ERP (공급가액). 건수는 '상이내역' 시트에서 자동 집계됩니다."
    ws["A2"].font = Font(name="Arial", size=9, italic=True, color="595959")
    hdr = ["업체코드", "업체명", "명세서파일", "명세서 라인수", "ERP 행수", "매칭", "명세서 공급가액", "ERP 공급가액",
           "공급가액 차이", "명세서 세액", "ERP 세액", "세액 차이", "중요", "확인", "참고", "판정", "판독검증"]
    ws.append([]); ws.append(hdr); style_header(ws, len(hdr), 4)
    n = len(diffs) + 1
    for i, s in enumerate(summary):
        r = 5 + i
        ws.append([s["업체코드"], s["업체명"], s["명세서파일"], s["명세서라인"], s["ERP행"], s["매칭"],
                   s["명세서공급가액"], s["ERP공급가액"], f"=G{r}-H{r}", s["명세서세액"], s["ERP세액"], f"=J{r}-K{r}",
                   f'=COUNTIFS(상이내역!$A$2:$A${n},A{r},상이내역!$C$2:$C${n},"중요")',
                   f'=COUNTIFS(상이내역!$A$2:$A${n},A{r},상이내역!$C$2:$C${n},"확인")',
                   f'=COUNTIFS(상이내역!$A$2:$A${n},A{r},상이내역!$C$2:$C${n},"참고")',
                   f'=IF(M{r}+N{r}=0,"일치","차이있음")', s["판독검증"]])
    last = 4 + len(summary)
    ws.append(["합계", "", "", f"=SUM(D5:D{last})", f"=SUM(E5:E{last})", f"=SUM(F5:F{last})", f"=SUM(G5:G{last})",
               f"=SUM(H5:H{last})", f"=SUM(I5:I{last})", f"=SUM(J5:J{last})", f"=SUM(K5:K{last})", f"=SUM(L5:L{last})",
               f"=SUM(M5:M{last})", f"=SUM(N5:N{last})", f"=SUM(O5:O{last})", "", ""])
    body_font(ws, 5)
    for c in ws[last + 1]: c.font = Font(name="Arial", bold=True)
    for row in ws.iter_rows(min_row=5, max_row=last + 1):
        for c in row[6:12]: c.number_format = '#,##0;[Red]-#,##0;"-"'
    widths(ws, [9, 14, 30, 8, 8, 7, 14, 14, 13, 12, 12, 10, 6, 6, 6, 9, 13])
    ws.freeze_panes = "A5"

    # 상이내역
    ws = wb.create_sheet("상이내역")
    cols = ["업체코드", "업체명", "심각도", "차이유형", "찾는위치", "명세서파일", "페이지", "순번", "명세서번호", "납품일자",
            "발주번호", "품번", "품명", "명세서값", "ERP값", "ERP입고번호", "공급가액차이", "조치제안", "확인결과(담당자 기재)"]
    ws.append(cols); style_header(ws, len(cols))
    for d in diffs:
        ws.append([d.get(c, "") for c in cols[:-1]] + [""])
        ws.cell(row=ws.max_row, column=3).fill = SEV_FILL[d["심각도"]]
    body_font(ws)
    for row in ws.iter_rows(min_row=2):
        row[9].number_format = "yyyy-mm-dd"; row[16].number_format = '#,##0;[Red]-#,##0;"-"'
        row[17].alignment = Alignment(wrap_text=True, vertical="top")
    widths(ws, [9, 12, 7, 20, 46, 28, 6, 6, 13, 11, 13, 13, 18, 22, 30, 14, 12, 42, 22])
    ws.freeze_panes = "E2"; ws.auto_filter.ref = ws.dimensions

    # 매칭내역
    ws = wb.create_sheet("매칭내역")
    cols = ["업체코드", "업체명", "명세서파일", "페이지", "순번", "명세서번호", "명세서 일자", "명세서 발주", "명세서 품번", "명세서 수량",
            "명세서 단가", "명세서 공급가액", "명세서 세액", "ERP 입고번호", "ERP 일자", "ERP 발주", "ERP 품번", "ERP 수량",
            "ERP 단가", "ERP 공급가액", "ERP 세액", "매칭방법", "결과"]
    ws.append(cols); style_header(ws, len(cols))
    for m in sorted(matches, key=lambda x: (x[0], x[3], x[4])):
        ws.append(m)
    body_font(ws)
    for row in ws.iter_rows(min_row=2):
        for i in (9, 10, 11, 12, 17, 18, 19, 20): row[i].number_format = "#,##0"
        row[6].number_format = row[14].number_format = "yyyy-mm-dd"
        if row[22].value != "일치":
            row[22].fill = SEV_FILL["확인"]
    widths(ws, [9, 12, 28, 6, 6, 13, 11, 13, 13, 9, 9, 12, 10, 24, 11, 13, 13, 9, 9, 12, 10, 22, 24])
    ws.freeze_panes = "F2"; ws.auto_filter.ref = ws.dimensions

    # 명세서 판독원본
    ws = wb.create_sheet("명세서판독")
    out = st.drop(columns=["행위치"]).astype(object).where(st.drop(columns=["행위치"]).notna(), "")
    ws.append(list(out.columns)); style_header(ws, len(out.columns))
    for r in out.itertuples(index=False): ws.append(list(r))
    body_font(ws); ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
    widths(ws, [9, 28, 6, 6, 11, 13, 13, 18, 8, 9, 12, 10, 22, 8, 9, 13, 8, 6])

    wb.calculation.fullCalcOnLoad = True
    wb.save(path)

def write_md(path, month, summary, diffs):
    L = [f"# 외주 대사 요약 ({month})", "", "기준: 외주거래명세서 스캔본 / 차이금액 = 명세서 − ERP (공급가액)", "",
         "| 업체 | 명세서 공급가액 | ERP 공급가액 | 차이 | 중요 | 확인 | 참고 | 판독검증 |", "|---|---:|---:|---:|---:|---:|---:|---|"]
    for s in summary:
        ds = [d for d in diffs if d["업체코드"] == s["업체코드"]]
        c = lambda k: sum(d["심각도"] == k for d in ds)
        L.append(f"| {s['업체명']} | {s['명세서공급가액']:,} | {s['ERP공급가액']:,} | "
                 f"{s['명세서공급가액'] - s['ERP공급가액']:,} | {c('중요')} | {c('확인')} | {c('참고')} | {s['판독검증']} |")
    L.append("")
    for s in summary:
        ds = [d for d in diffs if d["업체코드"] == s["업체코드"] and d["심각도"] != "참고"]
        L.append(f"## {s['업체명']}")
        if not ds:
            L.append("- 차이 없음 (참고 사항은 엑셀 '상이내역' 시트 확인)"); L.append(""); continue
        for d in ds:
            L.append(f"- [{d['심각도']}] {d['차이유형']} — {d['찾는위치']} | {d['납품일자']} {d['품번']} | "
                     f"명세서 {d['명세서값']} / ERP {d['ERP값']}")
        L.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))

if __name__ == "__main__":
    main()

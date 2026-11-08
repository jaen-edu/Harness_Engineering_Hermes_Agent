# -*- coding: utf-8 -*-
"""판독 결과 자체검증 — 대사 전에 반드시 실행

검사 항목
  1. 필수 컬럼 존재
  2. 순번이 1부터 빠짐없이 이어지는지 (누락 행 탐지) — 납품건별 명세서는 명세서번호별로
  3. 수량 × 단가 = 공급가액 (라인별)
  4. 라인 공급가액·세액 합계 = 명세서 하단 인쇄 합계 (_명세서합계.json)
     (라인 세액 칸이 없는 양식은 세액을 빈칸으로 두며, 이때 세액 합계 검사는 건너뜀)
     (명세서합계.json 에 '명세서별합계'가 있으면 명세서번호별로도 검사)
  5. 날짜가 마감월 안에 있는지

사용법: python scripts/validate_extraction.py --month 2026-09
종료코드: 0 = 통과, 1 = 재판독 필요
"""
import argparse, glob, json, os, sys
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQ = ["업체코드", "파일명", "페이지", "순번", "납품일자", "발주번호", "품번", "품명", "수량", "단가",
       "공급가액", "세액", "비고", "수기정정", "판독확신도"]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--month", required=True); a = ap.parse_args()
    d = os.path.join(BASE, "work", a.month, "추출")
    files = sorted(glob.glob(os.path.join(d, "*_명세서추출.csv")))
    if not files:
        sys.exit(f"[오류] {d} 에 *_명세서추출.csv 가 없습니다.")
    problems = 0
    for f in files:
        name = os.path.basename(f); vc = name.split("_")[0]
        df = pd.read_csv(f, dtype=str, encoding="utf-8-sig")
        miss = [c for c in REQ if c not in df.columns]
        if miss:
            print(f"[FAIL] {name}: 컬럼 누락 {miss}"); problems += 1; continue
        for c in ["페이지", "순번", "수량", "단가", "공급가액", "세액"]:
            df[c] = pd.to_numeric(df[c].str.replace(",", ""), errors="coerce")
        msgs = []
        if "명세서번호" not in df: df["명세서번호"] = ""
        df["명세서번호"] = df["명세서번호"].fillna("")
        vat_blank = df["세액"].isna()
        if vat_blank.any() and not vat_blank.all():
            msgs.append(f"세액이 일부 행만 비어 있음 순번: {df.loc[vat_blank, '순번'].tolist()} (라인 세액 칸이 없는 양식이면 전부 빈칸)")
        bad_num = df[df[["순번", "수량", "단가", "공급가액"]].isna().any(axis=1)]
        for _, r in bad_num.iterrows():
            msgs.append(f"p.{r['페이지']} No.{r['순번']}: 숫자 판독 실패")
        for sheet, g in df.groupby("명세서번호"):
            tag = f"[명세서 {sheet}] " if sheet else ""
            nos = sorted(g["순번"].dropna().astype(int))
            gap = sorted(set(range(1, max(nos) + 1)) - set(nos)) if nos else []
            if gap: msgs.append(f"{tag}순번 누락: {gap}")
            dup = g[g["순번"].duplicated()]["순번"].tolist()
            if dup: msgs.append(f"{tag}순번 중복: {dup} (납품건별 명세서라면 명세서번호 칸을 채우세요)")
        for _, r in df.iterrows():
            if pd.notna(r["수량"]) and pd.notna(r["단가"]) and r["수량"] * r["단가"] != r["공급가액"]:
                msgs.append(f"p.{int(r['페이지'])} No.{int(r['순번'])}: 수량×단가({int(r['수량']*r['단가']):,}) ≠ 공급가액({int(r['공급가액']):,})")
        dates = pd.to_datetime(df["납품일자"], errors="coerce")
        if dates.isna().any():
            msgs.append(f"날짜 형식 오류 순번: {df.loc[dates.isna(), '순번'].astype(int).tolist()} (YYYY-MM-DD로 기재)")
        out = df.loc[dates.notna() & (dates.dt.strftime('%Y-%m') != a.month), "순번"].astype(int).tolist()
        if out: msgs.append(f"마감월 밖 날짜 순번: {out} (명세서가 정말 그렇게 적혀 있으면 비고에 기록)")
        tf = os.path.join(d, f"{vc}_명세서합계.json")
        if os.path.exists(tf):
            t = json.load(open(tf, encoding="utf-8"))
            sa, sv = int(df["공급가액"].sum()), int(df["세액"].sum())
            if sa != t["공급가액합계"]:
                msgs.append(f"공급가액 라인합 {sa:,} ≠ 인쇄합계 {t['공급가액합계']:,} (차 {sa - t['공급가액합계']:,})")
            if not vat_blank.all() and sv != t["세액합계"]:
                msgs.append(f"세액 라인합 {sv:,} ≠ 인쇄합계 {t['세액합계']:,} (차 {sv - t['세액합계']:,})")
            if t.get("라인수") and t["라인수"] != len(df):
                msgs.append(f"라인수 {len(df)} ≠ 명세서 마지막 순번 {t['라인수']}")
            for b in t.get("명세서별합계", []):
                g = df[df["명세서번호"] == b["명세서번호"]]
                if len(g) == 0:
                    msgs.append(f"명세서 {b['명세서번호']}: 판독된 행 없음"); continue
                if int(g["공급가액"].sum()) != b["공급가액"]:
                    msgs.append(f"명세서 {b['명세서번호']}: 공급가액 {int(g['공급가액'].sum()):,} ≠ 장 합계 {b['공급가액']:,}")
                if "세액" in b and not vat_blank.all() and int(g["세액"].sum()) != b["세액"]:
                    msgs.append(f"명세서 {b['명세서번호']}: 세액 {int(g['세액'].sum()):,} ≠ 장 합계 {b['세액']:,}")
        else:
            msgs.append("명세서합계.json 없음 — 하단 인쇄 합계를 기록하세요")
        low = df[df["판독확신도"].isin(["하"])]
        if len(low):
            msgs.append(f"판독확신도 '하' 순번: {low['순번'].astype(int).tolist()} — 원본 재확인 필요")
        if msgs:
            problems += 1
            print(f"[FAIL] {name}"); [print("   -", m) for m in msgs]
        else:
            print(f"[OK]   {name}  ({len(df)}라인, 공급가액 {int(df['공급가액'].sum()):,})")
    sys.exit(1 if problems else 0)

if __name__ == "__main__":
    main()

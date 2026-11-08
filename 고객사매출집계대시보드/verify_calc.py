"""calc.py 검산: 개발설계서 9장 기준값과 한 원이라도 다르면 실패.

사용법: .venv\\Scripts\\python.exe verify_calc.py [입력 엑셀 5개가 있는 폴더]
       폴더를 생략하면 앱처럼 입력파일 폴더 3개에서 읽는다.
"""
import sys
from pathlib import Path

import calc
import folders

# 고객사: (7월, 8월, 9월, 분기 합계, 목표, 달성률, 전월 대비, 2분기 대비, 판정)
EXPECTED = {
    "라온산업": (6707000, 5625000, 5625000, 17957000, 18700000, "96.0%", "0.0%", "−1.9%", "정상"),
    "다온기계": (5200000, 4600000, 4755000, 14555000, 16000000, "91.0%", "+3.4%", "−1.0%", "정상"),
    "누리전자": (4000000, 6000000, 2052000, 12052000, 13300000, "90.6%", "−65.8%", "+2.1%", "주의"),
    "가온모터스": (2400000, 2200000, 2000000, 6600000, 8000000, "82.5%", "−9.1%", "−10.8%", "미달"),
    "바다정공": (2200000, 2100000, 2108000, 6408000, 7120000, "90.0%", "+0.4%", "+0.1%", "정상"),
    "마루밸브": (2600000, 0, 2248000, 4848000, 6000000, "80.8%", "비교불가", "−20.5%", "미달"),
    "합계": (23107000, 20525000, 18788000, 62420000, 69120000, "90.3%", "−8.5%", "−3.5%", ""),
}
EXPECTED_TOP3 = ["라온산업", "다온기계", "누리전자"]


def row_of(c):
    return (*c.months, c.total, c.target, calc.fmt_pct(c.rate), c.mom_text, c.vs_prev_text, c.judgment)


def load_folder(folder: Path):
    """엑셀 5개가 한 폴더에 있을 때."""
    def load(path):
        return path.name, path.read_bytes()

    ships = [calc.read_shipments(*load(p)) for p in sorted(folder.glob("출하실적_*.xlsx"))]
    targets = calc.read_targets(*load(folder / "고객사_분기목표.xlsx"))
    last = calc.read_last_quarter(*load(folder / "지난분기_매출집계표.xlsx"))
    return ships, targets, last


def load_input_folders():
    """앱과 같은 방식으로 입력파일 폴더 3개에서 읽을 때."""
    picks = [folders.pick_shipments(), folders.pick_targets()]
    picks.append(folders.pick_last_quarter(folders.prev_quarter_label(picks[0].used)))
    errors = [e for p in picks for e in p.errors]
    if errors:
        raise calc.StopError(" / ".join(errors))
    return picks[0].used, picks[1].used[0], picks[2].used[0]


def main(folder: Path | None) -> int:
    ships, targets, last = load_folder(folder) if folder else load_input_folders()
    s = calc.compute(ships, targets, last)

    print(f"집계 분기: {s.label} / 지난 분기: {s.prev_label} / 출하 행 {sum(len(f.rows) for f in ships)}개")
    fails = 0
    for c in s.customers + [s.total]:
        got, want = row_of(c), EXPECTED.get(c.name)
        ok = got == want
        fails += not ok
        print(("OK  " if ok else "FAIL"), c.name, got if ok else f"\n     결과 {got}\n     기준 {want}")
    if {c.name for c in s.customers} != set(EXPECTED) - {"합계"}:
        fails += 1
        print("FAIL 고객사 목록이 다릅니다")
    top3 = [c.name for c in s.top3]
    fails += top3 != EXPECTED_TOP3
    print(("OK  " if top3 == EXPECTED_TOP3 else "FAIL"), "Top 3:", " → ".join(top3))
    print("카드 순서:", " → ".join(f"{c.name}{f'({c.rank}위)' if c.rank else ''}" for c in s.cards))
    print("\n경고:")
    for w in s.warnings:
        print(" -", w)
    print("\n결과:", "모두 일치" if fails == 0 else f"{fails}건 불일치")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else None))

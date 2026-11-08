"""AI 판독 정확도 테스트 (API 키 필요, 호출 비용 발생 — 9월 기준 21페이지).

    .venv\\Scripts\\python tests\\run_ai_reading_test.py

9월 PDF 7개를 Claude 로 판독해 정답(판독정답_202609.json)과 칸 단위로 비교한다.
합격 기준(계획서 8장): 금액·수량·품번·일자 오류 0건.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from core.pdf_reader import load_reading_json, make_client, read_pdf_ai  # noqa: E402
from core.pipeline import build_statement  # noqa: E402
from core.vendors import detect_by_filename, load_vendors  # noqa: E402

load_dotenv(ROOT / ".env")
FIELDS = ["일자", "발주번호", "품번", "수량", "단가", "공급가액", "반품"]


def main():
    if not os.getenv("ANTHROPIC_API_KEY"):
        print(".env 에 ANTHROPIC_API_KEY 가 없어 건너뜁니다.")
        return
    vendors = load_vendors()
    truth = load_reading_json((ROOT / "tests" / "sample_202609" / "판독정답_202609.json").read_bytes())
    client = make_client()
    model, effort = os.getenv("CLAUDE_MODEL", "claude-opus-5-5"), os.getenv("CLAUDE_EFFORT", "high")
    got = {}
    for fn in truth:
        code = detect_by_filename(fn, vendors)
        hint = next(v["reading_notes"] for v in vendors if v["code"] == code)
        print(f"판독 중: {fn}")
        got[fn] = read_pdf_ai(client, (ROOT / "거래명세서_스캔" / fn).read_bytes(), fn, model=model, effort=effort,
                              vendor_hint=hint)
    vmap = {fn: detect_by_filename(fn, vendors) for fn in truth}
    t_rows, _ = build_statement(truth, vmap, vendors, 2026)
    g_rows, _ = build_statement(got, vmap, vendors, 2026)
    errors = 0
    for fn in truth:
        t = t_rows[t_rows["파일"] == fn].reset_index(drop=True)
        g = g_rows[g_rows["파일"] == fn].reset_index(drop=True)
        if len(t) != len(g):
            print(f"  {fn}: 행 수 다름 정답 {len(t)} / 판독 {len(g)}")
            errors += abs(len(t) - len(g))
        for i in range(min(len(t), len(g))):
            for f in FIELDS:
                if t.loc[i, f] != g.loc[i, f]:
                    errors += 1
                    print(f"  {fn} {t.loc[i, '페이지']}p {t.loc[i, '행번호']}행 {f}: 정답 {t.loc[i, f]} / 판독 {g.loc[i, f]}")
    print(f"\n칸 단위 오류 {errors}건 ({len(t_rows)}행 × {len(FIELDS)}칸)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()

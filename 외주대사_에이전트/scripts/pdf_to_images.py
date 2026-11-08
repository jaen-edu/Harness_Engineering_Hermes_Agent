# -*- coding: utf-8 -*-
"""거래명세서 스캔 PDF를 페이지별 PNG로 변환 (Claude가 이미지를 직접 보고 판독하기 위함)

사용법:
    python scripts/pdf_to_images.py --month 2026-09            # 해당 월 전체
    python scripts/pdf_to_images.py --month 2026-09 --dpi 250  # 글씨가 작을 때
출력: work/<월>/이미지/<파일명>_p<페이지>.png
"""
import argparse, glob, os
import pypdfium2 as pdfium

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", required=True)
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--file", help="특정 PDF 하나만 변환할 때 파일명")
    a = ap.parse_args()
    src = os.path.join(BASE, "input", a.month, "거래명세서_스캔")
    dst = os.path.join(BASE, "work", a.month, "이미지")
    os.makedirs(dst, exist_ok=True)
    pdfs = sorted(glob.glob(os.path.join(src, "*.pdf")))
    if a.file:
        pdfs = [p for p in pdfs if os.path.basename(p) == a.file]
    if not pdfs:
        raise SystemExit(f"[오류] {src} 에 PDF가 없습니다.")
    for p in pdfs:
        stem = os.path.splitext(os.path.basename(p))[0]
        doc = pdfium.PdfDocument(p)
        for i in range(len(doc)):
            out = os.path.join(dst, f"{stem}_p{i + 1}.png")
            doc[i].render(scale=a.dpi / 72).to_pil().save(out)
            print(out)
        doc.close()

if __name__ == "__main__":
    main()

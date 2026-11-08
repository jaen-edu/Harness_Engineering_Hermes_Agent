---
description: 외주거래명세서 스캔본과 ERP 입고이력을 업체별로 대사합니다. 사용법 /reconcile 2026-09
argument-hint: [마감월 YYYY-MM]
---

마감월 $ARGUMENTS 의 외주 대사를 CLAUDE.md 4장 절차(0~6단계)대로 처음부터 끝까지 수행해줘.

- 마감월이 비어 있으면 input/ 폴더에 있는 가장 최근 월을 제안하고 확인을 받아.
- 명세서 판독은 .claude/skills/statement-reading/SKILL.md 규칙을 따르고, validate_extraction.py를 통과한 뒤에만 reconcile.py를 실행해.
- 최종 보고는 CLAUDE.md 4장 6단계 형식으로, 모든 차이에 명세서 파일명·페이지·No를 붙여서.

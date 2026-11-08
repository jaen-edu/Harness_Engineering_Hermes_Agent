# 7교시: 1일차 Skill Pack 통합 실습 및 리뷰
**시간**: 17:00–18:00 | **유형**: 통합 실습 + 회고

---

## 학습 목표

이 교시가 끝나면 수강생은:
1. 5개의 Skills를 체이닝하여 새로운 프로젝트(계산기 앱)를 처음부터 끝까지 개발합니다.
2. Skills 간 충돌·오동작 패턴을 인식하고 원인을 진단합니다.
3. 본인 Skill Pack의 개선점을 스스로 도출합니다.

---

## 1. 1일차 Skill Pack 최종 구조

```
.skills/
├── prd-writer/
│   └── SKILL.md          ← 기능 → PRD.md
├── task-breakdown/
│   └── SKILL.md          ← PRD.md → TASK.md
├── tdd-red/
│   └── SKILL.md          ← TASK 항목 → test_*.py (FAILED)
├── tdd-green/
│   └── SKILL.md          ← test_*.py → *.py (PASSED)
└── tdd-refactor/
    └── SKILL.md          ← *.py → *.py (개선 + PASSED)
```

### Skill Pack 전체 흐름

```
사용자 요청
    │
    ▼
[prd-writer]    → PRD.md
    │
    ▼
[task-breakdown] → TASK.md (T01, T02, T03...)
    │
    ▼ (TASK별 반복)
[tdd-red]       → test_calculator.py (FAILED)
    │
    ▼
[tdd-green]     → calculator.py (PASSED)
    │
    ▼
[tdd-refactor]  → calculator.py (개선 + PASSED)
    │
    ▼
완료된 기능 ✓
```

---

## 2. 통합 실습: 계산기 앱 처음부터 끝까지

### 목표

5개의 Skills를 순서대로 사용하여 Python 계산기 CLI 앱을 개발합니다.  
단, 각 단계에서 직접 구현하지 않고 **Skills를 통해 AI가 산출물을 생성**하도록 합니다.

### Step 1: PRD 생성 (prd-writer Skill)

```
prd-writer Skill을 사용해서 아래 정보로 PRD.md를 생성해줘.

- 프로젝트: SimpleCalc (Python CLI 계산기)
- 기능: 두 수의 덧셈, 뺄셈, 곱셈, 나눗셈
- 대상: Python 학습자
- 제약: 나눗셈 시 0으로 나누면 오류 처리 필요
```

### Step 2: TASK 분해 (task-breakdown Skill)

```
PRD.md를 읽고 task-breakdown Skill로 TASK.md를 생성해줘.
각 연산(+, -, *, /)을 별도 TASK로 분리하고,
입력 검증도 별도 TASK로 만들어줘.
```

### Step 3~5: 각 TASK에 대해 TDD 사이클 반복

TASK T01(덧셈)부터 시작:

```
# Red
TASK.md의 T01(덧셈)에 대해 tdd-red Skill로 테스트를 작성해줘.

# Green
test_calculator.py의 실패 테스트를 tdd-green Skill로 통과시켜줘.

# Refactor
calculator.py를 tdd-refactor Skill로 개선해줘.
```

나머지 TASK(뺄셈, 곱셈, 나눗셈, 검증)도 동일하게 반복합니다.

### 완료 후 최종 확인

```powershell
pytest test_calculator.py -v --cov=calculator --cov-report=term-missing
```

기댓값:
```
PASSED test_calculator.py::test_add_positive_numbers
PASSED test_calculator.py::test_subtract_numbers
PASSED test_calculator.py::test_multiply_numbers
PASSED test_calculator.py::test_divide_numbers
PASSED test_calculator.py::test_divide_by_zero_raises_error
5 passed, 0 failed
Coverage: 100%
```

---

## 3. 흔한 충돌·오동작 패턴

### 패턴 1: 컨텍스트 혼선

**증상**: tdd-green이 이전 프로젝트의 코드를 참조함  
**원인**: Agent의 대화 컨텍스트에 여러 프로젝트 파일이 섞임  
**해결**: 새 TASK 시작 시 Chat 창 초기화 또는 파일을 명시적으로 지정

### 패턴 2: 형식 불일치

**증상**: task-breakdown이 TASK.md를 생성했지만 tdd-red가 읽지 못함  
**원인**: TASK.md의 섹션 구조가 Skill에서 기대하는 형식과 다름  
**해결**: SKILL.md에 정확한 파싱 포인트를 명시 (예: `### T01:` 패턴 사용)

### 패턴 3: 과잉 구현

**증상**: tdd-green이 테스트 통과를 위해 지나치게 복잡한 코드를 작성  
**원인**: Skill 지시문에 "최소한"의 정의가 불명확  
**해결**: `"테스트를 통과하는 가장 짧은 코드를 작성하라, 함수 하나에 5줄을 넘기지 마라"` 추가

### 패턴 4: 테스트 수정

**증상**: tdd-green이 테스트를 통과하는 대신 테스트를 변경함  
**원인**: Skill에 "테스트 수정 금지" 지침 없음  
**해결**: `"test_*.py 파일은 절대 수정하지 않는다"` 명시

---

## 4. Skill Pack 개선 워크숍

### 개인 리뷰 (5분)

각자의 SKILL.md를 검토하고 다음을 찾습니다:
- 모호한 표현 ("적절히", "필요한 경우")
- 빠진 제약사항
- 출력 형식 불명확

### 짝 리뷰 (10분)

옆 사람의 Skill을 사용해 테스트합니다:
1. 상대방의 SKILL.md를 읽고
2. 동일한 프롬프트를 실행하여
3. 결과의 품질 차이를 비교

---

## 5. 1일차 학습 정리

### 오늘 만든 것

| 파일 | 역할 |
|------|------|
| `setup.ps1` | 환경 자동화 |
| `.github/copilot-instructions.md` | 전역 지침 |
| `.github/instructions/*.instructions.md` | 로컬 지침 |
| `.github/prompts/*.prompt.md` | 재사용 프롬프트 |
| `.github/chatmodes/skill-designer.chatmode.md` | 커스텀 에이전트 |
| `.skills/prd-writer/SKILL.md` | PRD 자동 작성 |
| `.skills/task-breakdown/SKILL.md` | TASK 자동 분해 |
| `.skills/tdd-red/SKILL.md` | 실패 테스트 생성 |
| `.skills/tdd-green/SKILL.md` | 최소 구현 생성 |
| `.skills/tdd-refactor/SKILL.md` | 코드 개선 자동화 |

### 핵심 인사이트

```
전통 개발: 요구사항 → [개발자 판단] → 코드
AI-Native:  요구사항 → [Skill 설계] → AI 실행 → [개발자 검증] → 완성
```

- Skills는 개발자의 판단을 **재사용 가능한 형식**으로 저장합니다.
- 좋은 SKILL.md는 "트리거 조건, 입력, 출력, 제약사항"이 명확합니다.
- 체이닝에서 핵심은 **파일명과 출력 형식의 일관성**입니다.

---

## 6. Q&A 및 2일차 예고

### 2일차에서 다룰 것

- Git Skill: 자동 커밋 메시지 생성
- 코드 리뷰 Skill: AI 자기 검토
- 문서화 Skill: README 자동 생성
- 실전 프로젝트: Streamlit 앱 개발
- GitHub Actions 자동화

---

## 구성 이유

개별 Skill 실습 후 반드시 통합 실행 시간이 필요합니다. 각 Skill이 독립적으로는 동작해도 체이닝 시 컨텍스트 충돌이 발생할 수 있으며, 이를 직접 경험·수정하는 것이 2일차 심화 학습의 토대가 됩니다.

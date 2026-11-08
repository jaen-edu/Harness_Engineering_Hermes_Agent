# 6교시: TDD Skill 설계 — tdd-green → tdd-refactor
**시간**: 16:00–17:00 | **유형**: 구현 + 리팩토링 실습

---

## 학습 목표

이 교시가 끝나면 수강생은:
1. "최소한의 코드로 통과"의 원칙이 왜 중요한지 설명합니다.
2. `tdd-green` Skill로 테스트를 통과시키는 구현을 작성합니다.
3. `tdd-refactor` Skill로 테스트를 유지하면서 코드를 개선합니다.

---

## 1. Green 단계: 최소한의 구현

> **Green 단계**  
> Red 단계에서 작성한 실패 테스트를 통과시키는 코드를 작성합니다.  
> 핵심 원칙: **테스트를 통과하는 가장 단순한 코드만 작성합니다.**

### 왜 "최소한"이어야 하는가?

```python
# 나쁜 예: 미래를 위한 과잉 설계
class TodoManager:
    def __init__(self, db_connection, cache_layer, event_bus):
        ...
    def add(self, item: str, priority: int = 0, tags: list = None):
        ...
```

```python
# 좋은 예: 테스트만 통과하는 최소 구현
def add(items: list, item: str) -> list:
    if not item:
        raise ValueError("항목은 빈 문자열일 수 없습니다.")
    return items + [item]
```

> 단순한 코드가 Refactor에서 개선하기 쉽습니다.  
> 복잡한 코드는 Refactor 단계에서 테스트를 깨뜨릴 위험이 높습니다.

---

## 2. tdd-green Skill 설계

### Skill 지시문 핵심 규칙

```
1. 현재 실패하는 테스트를 모두 읽는다.
2. 각 테스트가 통과하는 데 필요한 최소한의 코드를 작성한다.
3. 클래스, 추상화, 패턴을 미리 도입하지 않는다.
4. pytest를 실행하여 모든 테스트가 PASSED인지 확인한다.
5. PASSED가 아니면 오류 메시지를 분석하여 수정한다.
```

### Green 단계 완료 기준

```powershell
uv run pytest tests\test_add-task.py -v
# 기댓값:
# PASSED test_todo.py::test_add_todo_returns_item
# PASSED test_todo.py::test_add_empty_string_raises_error
# 2 passed, 0 failed
```

---

## 3. Refactor 단계: 테스트를 유지하면서 개선

> **Refactor(리팩토링)**  
> 외부 동작(테스트 결과)을 바꾸지 않으면서 내부 구조를 개선하는 과정입니다.  
> 반대 개념: 기능 추가(Feature Addition)는 새로운 동작을 추가합니다.  
> TDD에서 리팩토링은 테스트라는 안전망이 있기 때문에 안전하게 수행 가능합니다.

### 리팩토링 체크리스트

| 개선 항목 | 확인 질문 | 예시 |
|----------|----------|------|
| 중복 제거 | 동일한 로직이 두 곳 이상 있는가? | 검증 로직 통합 |
| 함수 분리 | 함수가 두 가지 이상 하는가? | `validate` 분리 |
| 명명 개선 | 변수/함수명이 의도를 드러내는가? | `x` → `item_text` |
| 매직 넘버 | 하드코딩된 숫자/문자열이 있는가? | `MAX_ITEMS = 100` |
| 타입 힌트 | 파라미터/반환 타입이 명시되었는가? | `-> list[str]` |

### Refactor 단계의 철칙

```
리팩토링 전: pytest → 전부 PASSED 확인
리팩토링 중: 작은 단위로 변경
리팩토링 후: pytest → 전부 PASSED 확인 (필수!)
```

---

## 4. tdd-refactor Skill 설계

### Skill 지시문 핵심 규칙

```
1. pytest를 실행하여 현재 Green 상태임을 확인한다.
2. 다음 순서로 리팩토링한다:
   a. 중복 코드 제거
   b. 함수명/변수명 개선
   c. 타입 힌트 추가
   d. 상수 추출
3. 각 변경 후 즉시 pytest를 실행한다.
4. 테스트가 실패하면 즉시 마지막 변경을 롤백한다.
5. 새로운 기능을 추가하지 않는다.
```

---

## 5. 실습: 5교시 Red 테스트 → Green → Refactor

### Step 1: tdd-green으로 구현

```
tests/test_add_task.py의 실패하는 테스트들을 통과시키는 simpletask/tasks.py를 tdd-green Skill로 작성해줘.
최소한의 코드로만 통과시켜줘. 클래스나 추상화는 필요 없어.
```

Green 확인:
```powershell
uv run pytest tests/test_add_task.py -v
# → 모두 PASSED 확인
```

### Step 2: tdd-refactor로 개선

```
todo.py를 tdd-refactor Skill로 개선해줘.
중복을 제거하고 타입 힌트를 추가해줘.
리팩토링 후에도 pytest가 통과해야 해.
```

Refactor 후 확인:
```powershell
uv run pytest tests\test_add_task.py -v --cov=todo --cov-report=term-missing
```

### Step 3: 커버리지 확인

```
Name      Stmts   Miss  Cover
-------------------------------
todo.py       8      0   100%
```

> 100% 커버리지가 목표가 아닙니다. 의미 있는 테스트인지가 중요합니다.

---

## 6. Red-Green-Refactor 사이클 요약

```
┌───────────────────────────────────────────────────┐
│                                                   │
│  tdd-red Skill         →  test_todo.py (FAILED)  │
│  tdd-green Skill       →  todo.py (PASSED)       │
│  tdd-refactor Skill    →  todo.py (개선 + PASSED) │
│                                                   │
│  이 사이클이 TASK 하나의 완료를 의미합니다.          │
└───────────────────────────────────────────────────┘
```

### 확인 체크리스트

```
[ ] Green: 모든 테스트가 PASSED인가?
[ ] Green: 불필요한 클래스/패턴이 없는가?
[ ] Refactor: 중복 코드가 제거되었는가?
[ ] Refactor: 타입 힌트가 추가되었는가?
[ ] Refactor: pytest가 여전히 모두 PASSED인가?
[ ] Refactor: 새로운 기능이 추가되지 않았는가?
```

---

## 구성 이유

Red-Green-Refactor를 하나의 자동화된 Skills 흐름으로 만드는 것이 이 과정의 핵심 실습입니다. Refactor Skill은 "테스트를 깨지 않는 범위의 개선"이라는 제약을 명시적으로 Skill에 담는 방법을 훈련합니다.

# 5교시: TDD Skill 설계 — tdd-red (실패하는 테스트 먼저)
**시간**: 15:00–16:00 | **유형**: 개념 + Red 단계 실습

---

## 학습 목표

이 교시가 끝나면 수강생은:
1. TDD의 Red 단계가 왜 "요구사항을 코드로 표현하는 과정"인지 설명합니다.
2. `tdd-red` Skill을 설계하고 실패하는 테스트를 생성할 수 있습니다.
3. `pytest`로 Red 상태를 확인하는 워크플로우를 실행합니다.

---

## 1. TDD 사이클: Red → Green → Refactor

> **TDD(Test-Driven Development, 테스트 주도 개발)**  
> 구현보다 테스트를 먼저 작성하여 요구사항을 코드로 명확히 표현한 뒤, 테스트를 통과하는 코드를 작성하는 개발 방식입니다.  
> 반대 개념: 코드 후 테스트 작성(Test-After Development)은 이미 작성된 코드에 맞춰 테스트를 추가합니다.

```
     ┌─────────────────────────────────────────────────┐
     │                  TDD 사이클                      │
     │                                                  │
     │   ① Red          ② Green         ③ Refactor     │
     │  테스트 작성  ──→  최소 구현   ──→  코드 개선    │
     │  (실패 확인)       (통과 확인)     (테스트 유지)  │
     │       └────────────────────────────────┘         │
     └─────────────────────────────────────────────────┘
```

### 왜 Red 단계가 중요한가?

| 없이 개발 시 | Red 단계 후 개발 시 |
|------------|-------------------|
| 요구사항이 코드에 흩어짐 | 요구사항이 테스트에 명시됨 |
| 완료 기준 불명확 | 테스트 통과 = 완료 |
| 과잉 구현 가능성 | 테스트만 통과하는 최소 구현 |
| AI가 방향을 잃기 쉬움 | AI가 명확한 목표를 가짐 |

---

## 2. Red 단계의 규칙

### 핵심 규칙

1. **구현 코드 없이 테스트를 먼저 작성합니다.**
2. **테스트가 `ImportError` 없이 실패해야 합니다.**  
   (빈 함수나 `pass`로 구현 파일의 껍데기는 만들어도 됩니다)
3. **테스트 실패 메시지가 명확해야 합니다.**  
   `FAILED test_calculator.py::test_add - AssertionError: assert 0 == 3`

### Given / When / Then 패턴

```python
def test_add_two_positive_numbers():
    # Given: 두 양의 정수
    a, b = 2, 3

    # When: add 함수 호출
    result = add(a, b)

    # Then: 두 수의 합 반환
    assert result == 5
```

### 필수 테스트 케이스 유형

| 유형 | 목적 | 예시 |
|------|------|------|
| Happy Path | 정상 동작 확인 | `add(2, 3)` → 5 |
| Edge Case | 경계값 처리 | `add(0, 0)` → 0 |
| Error Case | 예외 발생 확인 | `add("a", 1)` → TypeError |

---

## 3. tdd-red Skill 설계

### 트리거 조건 설계

```
TASK.md의 특정 항목을 지정하며
"테스트를 먼저 만들어달라" / "Red 단계 진행" / "TDD 시작"
등의 표현이 포함될 때 발동
```

### 입력 / 출력 설계

```
입력:
  - TASK.md (특정 TASK ID 지정)
  - 또는 기능 설명 직접 입력

출력:
  - test_<모듈명>.py (pytest 테스트 파일)
  - <모듈명>.py (빈 함수 껍데기만 포함 - ImportError 방지용)
```

### 제약사항

- 구현 코드를 작성하지 않습니다 (빈 함수 `pass`만 허용)
- `pytest` 실행 시 반드시 `FAILED` 상태를 확인합니다
- 테스트가 `PASSED`라면 Skill이 잘못 동작한 것입니다

### 완성된 Skill 파일

`d01/lessons/.skills/tdd-red/SKILL.md` 참조

---

## 4. 실습: Red 상태 테스트 작성 및 확인

### Step 1: tdd-red Skill로 테스트 생성

Agent Mode에서:
```
TASK.md의 T01(할 일 추가 기능)에 대한 테스트를 tdd-red Skill을 사용해 작성해줘.
구현 코드는 작성하지 말고, 테스트 파일과 빈 함수 껍데기만 만들어줘.
```

### Step 2: Red 상태 확인

```powershell
uv run pytest test_add_task.py -v
```

기댓값:
```
FAILED test_todo.py::test_add_todo_returns_item - AssertionError
FAILED test_todo.py::test_add_empty_string_raises_error - AssertionError
...
2 failed, 0 passed
```

> **중요**: `PASSED`가 뜨면 테스트가 의미 없는 것입니다. `FAILED`가 뜨는 것이 정상입니다.

### Step 3: Red 상태 검증 체크리스트

```
[ ] 테스트 파일이 test_*.py 규칙을 따르는가?
[ ] ImportError 없이 테스트가 실행되는가?
[ ] 모든 테스트가 FAILED 상태인가?
[ ] Given/When/Then 주석이 있는가?
[ ] Happy Path, Edge Case, Error Case가 포함되었는가?
[ ] 실패 메시지가 구체적인가? (무엇이 기대값이고 실제값인가)
```

---

## 5. 흔한 실수와 해결법

| 실수 | 현상 | 해결법 |
|------|------|--------|
| 구현 코드 미리 작성 | 테스트가 PASSED | 구현 코드 삭제 후 재확인 |
| import 오류 | `ModuleNotFoundError` | 빈 `todo.py` 파일 생성 |
| 너무 구체적인 구현 예상 | 나중에 Refactor가 힘들어짐 | 인터페이스만 테스트 |
| 테스트가 너무 많음 | Red 단계에 시간 과다 | TASK 1개당 3–5개로 제한 |

---

## 구성 이유

TDD의 Red 단계는 "구현보다 요구사항을 먼저 코드로 표현"하는 사고 훈련입니다. 이 Skill이 있어야 다음 교시의 Green(구현) Skill과 의미 있는 흐름이 만들어집니다. 별도 교시로 분리해 각 단계의 의미를 충분히 체득하게 합니다.

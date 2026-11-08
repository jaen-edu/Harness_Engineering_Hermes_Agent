---
description: TASK 항목을 입력받아 TDD Red→Green→Refactor 전체 사이클을 실행합니다. 테스트 작성 후 최소 구현, 리팩토링까지 한 흐름으로 진행합니다.
agent: agent
tools: ['edit/editFiles', 'search/codebase', 'execute/runInTerminal', 'execute/getTerminalOutput']
---
# TDD 사이클 프롬프트

`TASK.md`에서 TASK ID `{{task_id}}`를 선택하여 TDD 사이클을 실행합니다.

## 실행 순서

### 1단계: Red (실패하는 테스트 작성)

`test_{{module_name}}.py`에 pytest 테스트를 작성합니다.
- Given/When/Then 구조를 사용합니다.
- 정상 케이스, 경계값, 오류 케이스를 모두 포함합니다.
- 구현 없이 테스트만 작성하고 `pytest`로 실패를 확인합니다.

### 2단계: Green (최소 구현)

`{{module_name}}.py`에 테스트를 통과시키는 **최소한의 코드**를 작성합니다.
- 과도한 추상화나 미리 보기 설계를 금지합니다.
- `pytest`로 모든 테스트가 통과(Green)하는지 확인합니다.

### 3단계: Refactor (개선)

테스트가 통과하는 상태를 유지하면서 코드를 개선합니다.
- 중복 코드를 제거합니다.
- 함수명/변수명을 의미있게 개선합니다.
- 리팩토링 후 `pytest`를 다시 실행하여 여전히 Green인지 확인합니다.

## 각 단계 후 수행할 명령

```bash
pytest -v           # 테스트 결과 확인
pytest --cov        # 커버리지 확인 (Refactor 후)
```

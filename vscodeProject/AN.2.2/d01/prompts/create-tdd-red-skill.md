# 메타 프롬프트: tdd-red SKILL.md 생성
# 이 프롬프트를 Agent Mode에서 실행하면 tdd-red SKILL.md가 생성됩니다.

---

아래 명세를 따르는 `.skills/tdd-red/SKILL.md` 파일을 생성해 주세요.

## Skill 명세

**이름**: tdd-red  
**목적**: TASK 항목을 입력받아 실패하는 pytest 테스트를 먼저 작성합니다. 구현 코드는 작성하지 않습니다.

### 트리거 조건
- "테스트 먼저 작성해줘", "Red 단계 시작"
- "tdd-red Skill 사용해서"
- "실패하는 테스트 만들어줘"
- "TDD 시작", "TASK T0X에 대한 테스트"

### 입력
- TASK ID (예: T01) 또는 기능 설명
- TASK.md (있으면 참조, 없으면 기능 설명으로 진행)

### 출력
- `test_<모듈명>.py`: pytest 테스트 파일 (실패 상태)
- `<모듈명>.py`: 빈 함수 껍데기만 포함 (ImportError 방지용)

### 테스트 작성 규칙
1. 모든 테스트는 Given/When/Then 주석을 포함합니다.
2. 각 TASK당 최소 3가지 케이스: Happy Path, Edge Case, Error Case
3. 함수명: `test_<함수명>_<시나리오>` 형식
4. pytest.raises()로 예외를 테스트합니다.

### 제약사항 (가장 중요)
- **구현 코드를 절대 작성하지 않습니다.** `pass` 또는 `raise NotImplementedError()`만 허용.
- **테스트가 PASSED 상태가 되면 안 됩니다.** 반드시 FAILED여야 합니다.
- 테스트를 실행(`pytest test_*.py -v`)하여 FAILED를 직접 확인합니다.
- PASSED가 나오면 "테스트가 의미 없습니다. 다시 작성합니다."라고 알립니다.

### SKILL.md 완성 후 수행할 것
1. `.skills/tdd-red/SKILL.md` 경로에 파일 생성
2. 즉시 테스트: `add(a, b) -> int` 함수에 대한 테스트 작성 요청
3. `pytest test_calculator.py -v` 실행 → 모두 FAILED인지 확인

# 메타 프롬프트: task-breakdown SKILL.md 생성
# 이 프롬프트를 Agent Mode에서 실행하면 task-breakdown SKILL.md가 생성됩니다.

---

아래 명세를 따르는 `.skills/task-breakdown/SKILL.md` 파일을 생성해 주세요.

## Skill 명세

**이름**: task-breakdown  
**목적**: PRD.md를 읽고 원자적 개발 작업 목록(TASK.md)으로 분해합니다.

### 트리거 조건
- "TASK 분해해줘", "TASK.md 만들어줘"
- "task-breakdown Skill 사용해서"
- "PRD를 작업 목록으로 변환"

### 입력
- `PRD.md` (없으면 오류 메시지 출력 후 중단)

### 출력
- `TASK.md` 파일 (프로젝트 루트에 생성)

### TASK.md 필수 형식
각 TASK 항목은 반드시 다음을 포함:
- ID: `T01`, `T02` 형식
- 우선순위: High / Medium / Low
- 완료 조건: pytest로 검증 가능한 구체적 조건 (체크박스 형식)
- 의존 관계: 선행 TASK ID 또는 "없음"
- 예상 테스트명: `test_함수명_시나리오` 형식

### TASK 분해 원칙
- 하나의 TASK = 하나의 함수/동작
- TASK 하나를 완료하는 데 30분~2시간 예상
- 에픽(3시간 이상)은 반드시 더 쪼갭니다

### 제약사항
- PRD의 "범위 밖" 섹션에 있는 기능을 TASK로 만들지 않습니다.
- 모호한 완료 조건을 작성하지 않습니다. ("잘 동작한다" X)
- TASK 수가 10개를 초과하면 우선순위 조정을 권장합니다.

### SKILL.md 완성 후 수행할 것
1. `.skills/task-breakdown/SKILL.md` 경로에 파일 생성
2. 즉시 테스트: `prd-writer` Skill로 먼저 PRD.md를 생성한 뒤, 이 Skill로 TASK.md 생성
3. 생성된 TASK.md에 완료 조건이 pytest로 검증 가능한지 확인

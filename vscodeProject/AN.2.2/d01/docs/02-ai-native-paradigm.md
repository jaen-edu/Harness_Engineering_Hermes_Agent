# 2교시: AI-Native 개발 패러다임과 Agent Skills 개념
**시간**: 11:00–12:00 | **유형**: 개념 + 실습

---

## 학습 목표

이 교시가 끝나면 수강생은:
1. 전통적 개발과 AI-Native 개발의 차이를 설명할 수 있습니다.
2. GitHub Copilot의 세 가지 빌트인 모드(Ask / Agent / Plan)의 차이를 구별합니다.
3. `.github/` 디렉터리의 4가지 파일 유형이 각각 언제 동작하는지 설명합니다.
4. Skills와 다른 커스터마이징 파일의 차이를 이해합니다.

---

## 1. 전통적 개발 vs AI-Native 개발

| 비교 항목 | 전통적 개발 | AI-Native 개발 |
|----------|------------|---------------|
| 코드 작성 | 개발자가 직접 작성 | AI가 초안, 개발자가 검토 |
| 요구사항 전달 | 구두, 문서, 티켓 | 구조화된 프롬프트/Skill |
| 반복 작업 | 개발자가 수동 반복 | Skill로 자동화 |
| 품질 보증 | 코드 리뷰, 테스트 | TDD Skill + 자동 검증 |
| 지식 재사용 | 위키, 문서, 코드 스니펫 | Skill Pack |

### 핵심 변화

```
전통 방식: 개발자 → [생각] → 코드 → 테스트 → 리뷰
AI-Native: 요구사항 → [Skill] → AI 초안 → 개발자 검증 → 완성
```

> AI-Native 개발의 핵심은 AI를 대체재로 보는 것이 아니라,  
> **개발자가 설계한 Skill 위에서 AI가 반복 가능한 방식으로 동작**하게 하는 것입니다.

---

## 2. GitHub Copilot의 세 가지 모드

최신 VS Code Copilot Chat 기준으로, 기본 선택지는 **Ask / Agent / Plan**입니다.

### 2-1. Ask 모드

- **용도**: 빠른 질의응답, 코드 설명, 아이디어 비교
- **동작**: 질문 중심으로 답변을 생성하며, 보통 분석/설명에 강함
- **적합한 요청 예시**: "이 함수의 시간복잡도 설명해줘", "구현 방법 3가지 비교해줘"
- **한계**: 구현 작업의 자동 실행보다 탐색/설명에 초점

### 2-2. Agent 모드

- **용도**: 실제 구현 작업 실행 (파일 수정, 명령 실행 포함)
- **동작**: 작업에 필요한 단계를 자율적으로 판단해 워크스페이스에 변경을 적용
- **적합한 요청 예시**: "PRD를 읽고 TASK.md 생성해줘", "테스트 실패 원인 고치고 다시 실행해줘"
- **강점**: 멀티 파일 편집, 터미널 작업, 반복적인 구현 흐름 자동화

### 2-3. Plan 모드

- **용도**: 구현 전에 단계별 실행 계획 수립
- **동작**: 요구사항을 분석해 계획 초안을 제시하고, 확인 질문을 통해 계획을 정교화
- **진입 방법**: 에이전트 선택기에서 `Plan` 선택 또는 `/plan` 명령 사용
- **핵심 흐름**: 계획 검토/수정 → `Start Implementation`으로 구현 에이전트에 인계

```
Ask: "이 구조의 장단점 설명해줘" → 설명/비교 중심 응답
Plan: "검색 기능 추가 계획 세워줘" → 단계/검증 기준 포함 계획 수립
Agent: "그 계획대로 구현 진행해줘" → 파일 수정/명령 실행 포함 구현
```

> 참고: Inline 자동완성은 에디터에서 계속 제공되지만, Chat의 빌트인 모드 분류는 Ask/Agent/Plan 기준으로 설명하는 것이 최신 문서와 일치합니다.

---

## 3. `.github/` 디렉터리: 4가지 커스터마이징 파일

GitHub Copilot Agent는 워크스페이스의 `.github/` 디렉터리에서 동작 방식을 정의하는 파일을 읽습니다.

```
.github/
├── copilot-instructions.md          ← 전역 지침
├── instructions/
│   ├── python-coding.instructions.md  ← 로컬 지침
│   └── tdd.instructions.md            ← 로컬 지침
├── prompts/
│   ├── prd-writer.prompt.md          ← 프롬프트 파일
│   └── tdd-cycle.prompt.md           ← 프롬프트 파일
└── agents/
    └── skill-designer.agent.md       ← 커스텀 에이전트
```

### 3-1. 전역 지침 (Global Instructions)

> **파일**: `.github/copilot-instructions.md`  
> **동작**: 워크스페이스에서 Copilot을 사용하는 **모든 대화**에 자동으로 포함됩니다.  
> **용도**: 프로젝트 전체에 적용할 코딩 원칙, 언어 설정, 아키텍처 결정 등

```markdown
<!-- .github/copilot-instructions.md 예시 -->
- 주 언어: Python 3.12
- 테스트: pytest 사용
- 응답 언어: 한국어
```

**특징**: 항상 적용, 파일 패턴 없음, 간결하게 작성 권장

### 3-2. 로컬 지침 (Local Instructions)

> **파일**: `.github/instructions/*.instructions.md`  
> **동작**: `applyTo` 프론트매터(frontmatter)에 지정한 파일 패턴에 해당하는 파일을 편집할 때만 포함됩니다.  
> **용도**: 특정 파일 유형에만 적용하는 상세 코딩 표준

```markdown
---
applyTo: "**/*.py"
---
# Python 코딩 표준
- 타입 힌트 필수
- f-string 선호
```

**특징**: 조건부 적용, 상세 규칙 작성 가능, 전역 지침의 구체화

### 3-3. 프롬프트 파일 (Prompt Files)

> **파일**: `.github/prompts/*.prompt.md`  
> **동작**: Chat/Agent Mode에서 `/파일명` 슬래시 명령으로 호출합니다.  
> (예: `/prd-writer`, `/tdd-cycle`)  
> **용도**: 반복적으로 사용하는 복잡한 지시를 재사용 가능한 템플릿으로 저장

```markdown
<!-- 호출 방법 -->
/prd-writer project_name="Todo App" feature_summary="할 일 관리"
```

**특징**: 사용자가 명시적으로 호출, 변수 치환 가능, 복잡한 작업 흐름

### 3-4. 커스텀 에이전트 (Custom Agent)

> **파일**: `.github/agents/*.agent.md`  
> **동작**: Chat 에이전트 셀렉터에서 에이전트를 선택하여 특정 역할의 AI로 전환합니다.  
> **용도**: 특정 작업(예: Skill 설계, 코드 리뷰, 보안 감사)에 특화된 에이전트 정의

```markdown
---
description: Skills 설계 전문 에이전트
name: Skill Designer
tools: ['search/codebase', 'edit/editFiles', 'execute/runInTerminal', 'execute/getTerminalOutput']
---
당신은 Skill 설계 전문가입니다...
```

**특징**: `name`으로 에이전트 표시명 지정, `tools` 목록으로 접근 가능한 도구 제한, 역할 전환, 지속적 페르소나

---

## 4. Skills와 다른 파일의 차이

| 비교 | `copilot-instructions.md` | `instructions/*.instructions.md` | `prompts/*.prompt.md` | `agents/*.agent.md` | `skills/*/SKILL.md` |
|-----|--------------------------|----------------------------------|----------------------|--------------------|--------------------|
| 성격 | 전역 원칙 | 파일별 코딩 표준 | 재사용 템플릿 | 특화 에이전트 | 작업 단위 자동화 |
| 활성화 | 항상 자동 | `applyTo` 패턴 매칭 | `/명령어` 수동 호출 | 에이전트 셀렉터 선택 | 컨텍스트 인식 |
| 주요 frontmatter | 없음 | `applyTo` | `description`, `agent`, `tools` | `description`, `name`, `tools` | `name`, `description` |
| 목적 | 방향 설정 | 표준 강제 | 반복 작업 자동화 | 역할 특화 | 복잡 작업 위임 |

> **Skills의 차별점**: SKILL.md는 단순한 지침이 아니라 **"입력 → 처리 → 출력"의 완결된 작업 흐름**을 정의합니다. 
> 다른 Skill과 체이닝하여 파이프라인을 구성할 수 있습니다.

---

## 5. 실습: Skills 디렉터리 구조 생성

Agent Mode에서 다음 프롬프트를 실행합니다:

```
.github에 아래 구조의 skills 디렉터리를 생성해 주세요.
각 SKILL.md는 placeholder 내용으로 만들어도 됩니다.

.skills/
├── prd-writer/SKILL.md
├── task-breakdown/SKILL.md
├── tdd-red/SKILL.md
├── tdd-green/SKILL.md
└── tdd-refactor/SKILL.md
```

### 확인 포인트

```
[ ] .guthub/skills/ 디렉터리가 생성되었는가?
[ ] 5개의 SKILL.md가 각 서브디렉터리에 있는가?
[ ] Agent Mode가 .github/copilot-instructions.md를 자동으로 읽었는가?
```

---

## 구성 이유

Skills를 직접 만들기 전에, Copilot Agent가 어떤 원리로 Skills를 인식·선택하는지 이해해야 "왜 이렇게 작성해야 하는가"에 대한 근거를 갖고 설계할 수 있습니다. 개념 없이 복붙하는 학습을 방지합니다.

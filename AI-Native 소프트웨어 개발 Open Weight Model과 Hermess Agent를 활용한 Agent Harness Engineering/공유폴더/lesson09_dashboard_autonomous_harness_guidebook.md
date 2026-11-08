# 제9교시 — Dashboard 탭 구현과 자율형 Harness 검증

**과정:** Open Weight Model과 Hermes Agent를 활용한 Agent Harness Engineering  
**프로젝트:** AI Work Request Manager v3  
**실습 환경:** Windows 11 · Docker Desktop · Hermes Agent · OpenRouter · Playwright Runner  
**학습 목표:** 제8교시 Requests 기능을 보존한 채 Dashboard를 구현하고, Hermes Agent가 새 검증 Harness를 생성하여 **빌드 → 단위·통합 테스트 → E2E → 오류 수정·재검증 → Requests 회귀 테스트 → 반복 검증**을 자율적으로 수행하도록 한다.

> **선행 조건:** 제7교시의 v3 환경과 제8교시 Requests 구현·검증이 완료되어 있어야 합니다. 이 교시에서는 Docker 컨테이너 재생성, 클린 정리, v2/Reference Project 변경 또는 기존 Requests 구현 삭제를 진행하지 않습니다.

## 1. 학습 목표와 완료 기준

| 학습 항목 | 수행할 작업 | 완료 기준 |
|---|---|---|
| 명세 기반 구현 | 제9교시 계획·Dashboard 명세·UI 지침 확인 | AC09-01~AC09-06 준수 |
| 결정적 지표 계산 | 상태별·우선순위별 건수를 순수 함수로 산출 | 같은 데이터에서 같은 값, 분포 합계 = 전체 |
| 데이터 연동 | Requests에서 사용 중인 API를 Dashboard가 그대로 활용 | 등록·수정·상태 변경 후 Dashboard 갱신 |
| 화면 구현 | 지표 카드·우선순위 분포·상태 필터·빈 상태 | 반응형 및 키보드 접근성 충족 |
| 자율형 검증 | 신규 `verify-dashboard.sh` 구성 및 실행 | 빌드·단위·통합·E2E 전 단계 PASS |
| 회귀 방지 | 기존 `verify-requests.sh`를 변경 없이 실행 | 제8교시 AC08-01~06 유지 |
| 재현성·기록 | 동일 Dashboard Harness 2회 연속 실행 및 증거 작성 | 두 실행 모두 종료 코드 0 |

**구현 범위:** Dashboard 탭만 추가합니다. Requests 탭, 데이터 구조, 제8교시 검증 증거와 Harness를 가능한 한 그대로 보존합니다. 새로운 차트 라이브러리, 외부 데이터베이스 및 별도 Dashboard 전용 저장소는 필요하지 않습니다.

### 기본 경로

```text
C:\AI-Native\
├── hermes-training-v3\                 # 제7교시 Docker Compose 환경
└── work-request-manager-v3\            # 컨테이너 안에서는 /workspace
    ├── AGENTS.md
    ├── docs\
    │   ├── project-overview.md
    │   └── ui-guidelines.md
    ├── specs\
    │   ├── dashboard.md
    │   └── acceptance-criteria.md
    ├── plans\lesson09-dashboard-plan.md
    ├── data\fixtures\requests.seed.json
    ├── client\src\                   # 기존 Requests + 신규 Dashboard
    │   ├── App.tsx
    │   ├── DashboardTab.tsx            # 신규 Dashboard 컴포넌트 예시
    │   └── metrics.js                 # 지표 계산 순수 함수 예시
    ├── server\                        # 제8교시 API·영속 저장소 유지
    ├── tests\
    │   ├── unit\
    │   ├── integration\
    │   └── e2e\
    │       ├── requests.spec.cjs      # 제8교시 계약 파일
    │       └── dashboard.spec.cjs     # 제9교시 계약 파일
    ├── scripts\
    │   ├── verify-requests.sh         # 제8교시 Harness, 보존
    │   └── verify-dashboard.sh        # 제9교시 Harness, 신규
    ├── evidence\
    │   ├── lesson08-verification.md   # 보존
    │   ├── lesson09-verification.md   # 신규
    │   └── logs\
    └── progress.md
```

파일 경로 규칙: 프런트엔드 루트는 `/workspace/client/`, 소스는 `/workspace/client/src/`입니다. `/workspace/src/`를 별도로 만들지 않습니다. 위의 신규 파일명 가운데 `dashboard.spec.cjs`와 `verify-dashboard.sh`는 실습 계약상 고정하고, 지표 모듈의 세부 파일명은 기존 계획과 일치하도록 작성합니다.

## 2. STEP 1 — 제8교시 결과와 제9교시 계획 확인

1. Docker Desktop이 실행 중인 상태에서 Windows 브라우저로 **Hermes Dashboard: http://127.0.0.1:9130**에 접속합니다.
2. 이전 교시의 Requests 화면은 **http://127.0.0.1:5174**에서 확인할 수 있습니다. 해당 주소는 Windows 브라우저용입니다.
3. Hermes Dashboard에서 **새 Chat**을 만들고, 작업공간을 `/workspace`로 사용합니다. 제7~8교시에서 구성한 OpenRouter 모델 설정을 유지합니다.
4. 아래 프롬프트를 입력하여 **읽기 전용 계획 점검**을 수행합니다. 이 단계에서는 소스를 변경하거나 테스트를 실행하지 않습니다.

### Hermes Agent 프롬프트 ① — 구현 범위 분석

```text
현재는 제9교시 Agent Harness Engineering 실습입니다.
AI Work Request Manager v3의 Dashboard 탭 구현을 준비합니다.

작업공간은 /workspace입니다. 다음 파일을 먼저 읽으세요.
- AGENTS.md
- docs/project-overview.md
- docs/ui-guidelines.md
- plans/lesson09-dashboard-plan.md
- specs/dashboard.md
- specs/acceptance-criteria.md
- progress.md
- evidence/lesson08-verification.md
- scripts/verify-requests.sh

다음 사항을 한국어로 보고하세요.
1. Dashboard 구현 범위와 필요한 지표
2. 지표 계산 기준과 전체·우선순위 합계의 불변 조건
3. 기존 Requests API를 단일 데이터 원본으로 사용하는 방식
4. AC09-01~AC09-06별 검증 방법
5. 기존 Requests의 변경을 최소화하는 회귀 테스트 전략
6. verify-requests.sh를 수정하지 않고 신규 verify-dashboard.sh를 만드는 전략
7. Requests·Dashboard E2E가 같은 데이터를 사용할 때의 초기화·순차 실행 방법

현재는 계획 확인 단계입니다.
파일 수정, 구현, 테스트 실행, 서버 재시작은 하지 마세요.
기존 계획에 없는 기능을 추가하지 마세요.
```

**정상 확인:** Hermes가 Dashboard의 네 가지 지표, 세 가지 우선순위 건수, 상태 필터, 빈 상태, Requests 연동, AC09 검증 방법을 정리하여 보고합니다. 이때 제8교시는 완료 상태, 제9교시는 구현 시작 전 상태여야 합니다.

### 계산 기준 이해하기

고정 초기 데이터 3건의 상태는 `todo`, `in_progress`, `done`이 각각 1건이고, 우선순위는 `low`, `medium`, `high`가 각각 1건입니다.

| 지표 | 초기 기대 건수 |
|---|---:|
| 전체 (`total`) | 3 |
| 할 일 (`todo`) | 1 |
| 진행 중 (`in_progress`) | 1 |
| 완료 (`done`) | 1 |
| 우선순위 낮음·보통·높음 | 각각 1 |

따라서 기본 상태에서 **전체 = 상태별 건수 합계 = 우선순위별 건수 합계 = 3**입니다. 실제 사용자가 요청을 등록하거나 상태를 변경하면 화면의 값은 달라지지만, 동일 데이터에 대해 위 합계 관계는 유지되어야 합니다. 상태 필터를 적용했을 때는 **필터된 데이터 집합에 대해** 지표와 분포를 동일한 기준으로 계산합니다.

## 3. STEP 2 — Hermes Agent가 Dashboard 구현·검증 수행

STEP 1의 분석이 완료되면 **같은 제9교시 Hermes Chat**에 아래 프롬프트를 입력합니다. 이번 단계에서는 교육생이 별도의 PowerShell 검증 명령을 실행하지 않습니다.

### Hermes Agent 프롬프트 ② — 구현과 자율 검증

```text
제9교시 STEP 1의 분석 결과를 바탕으로 Dashboard 탭을 구현하고,
재사용 가능한 자율형 검증 Harness를 구성하여 실제 실행하세요.

[1. 변경 범위와 고정 기준]
- 작업공간은 /workspace입니다.
- AGENTS.md, plans/lesson09-dashboard-plan.md, specs/dashboard.md,
  specs/acceptance-criteria.md, docs/ui-guidelines.md를 고정 기준으로 사용하세요.
- AC09-01~AC09-06의 기준을 약화하지 마세요.
- 기존 v2 및 Reference Project는 읽거나 변경하지 마세요.
- 제8교시 Requests 기능, server/ API, tests/e2e/requests.spec.cjs,
  scripts/verify-requests.sh 및 evidence/lesson08-verification.md를 보존하세요.
- Dashboard 구현에 필요한 연결 부분만 최소 수정하세요.

[2. Dashboard 구현]
- client/src/에 테스트 가능한 순수 지표 계산 모듈을 작성하세요.
- 상태별 total, todo, in_progress, done 지표 카드를 표시하세요.
- 우선순위 low, medium, high 건수를 표시하고 합계가 total과 일치하게 하세요.
- 상태 필터를 제공하고 현재 활성 필터를 화면에 명확하게 표시하세요.
- 상태 필터 적용 시 필터된 요청 집합을 기준으로 지표·분포를 함께 계산하세요.
- 데이터가 0건이면 모든 건수를 0으로 표시하고 빈 상태 안내를 제공하세요.
  0으로 나누는 계산을 수행하지 마세요.
- Requests 탭과 같은 API 데이터를 사용하고 별도 복사 저장소를 만들지 마세요.
- Requests에서 요청 등록·수정·상태 변경 후 Dashboard로 이동하거나
  브라우저를 새로고침하면 실제 저장 데이터가 반영되도록 하세요.
- 기존 디자인 토큰과 모바일·데스크톱 레이아웃, 키보드 접근성 지침을 따르세요.
- 명세에 없는 기능이나 새 외부 서비스를 추가하지 마세요.

[3. 자동 테스트]
- 지표 계산, 우선순위 합계, 상태 필터, 빈 데이터 순수 함수의 단위 테스트를 작성하세요.
- Requests API 데이터 변경과 Dashboard 지표 연동의 통합 테스트를 작성하세요.
- tests/e2e/dashboard.spec.cjs를 작성하여 AC09-01~AC09-06을 검증하세요.
- Playwright Runner 주소는 http://playwright:3000입니다.
- 브라우저 대상 주소는 http://hermes:5174입니다.
  Docker 컨테이너 IP를 직접 사용하지 마세요.
- 초기 데이터는 data/fixtures/requests.seed.json을 기준으로 하세요.

[4. 독립 실행 Dashboard Harness]
- scripts/verify-requests.sh는 수정하지 마세요.
- 별도 scripts/verify-dashboard.sh를 작성하세요.
- 기존 Harness의 실행 방식과 결과 기록 형식을 참고하되
  다음을 하나의 실행 흐름으로 수행하세요.
  1) 프런트엔드 빌드
  2) 단위 테스트
  3) 통합 테스트
  4) 앱 서버·클라이언트의 안전한 중지
  5) 초기 데이터 3건 복원과 서비스 재시작·헬스 확인
  6) POST http://playwright:3000/run 에 {"test":"dashboard"} 요청
  7) 성공·실패 여부와 관계없이 E2E 후 초기 데이터 복원·재시작 시도
  8) 단계별 종료 코드, PASS/FAIL, 로그 확인 및 기록
- 포트 번호만 일치한다는 이유로 무관한 프로세스를 종료하지 마세요.
  기존 프로세스의 소유 관계를 확인할 수 없으면 FAIL로 보고하세요.
- 서버가 실제로 중지되지 않았다면 데이터 파일을 덮어쓰지 마세요.
- 서버 시작 오류나 Runner 실패를 다른 프로세스의 정상 응답으로 오인하지 마세요.
- 데이터 공유 충돌 방지를 위해 Requests와 Dashboard E2E는 순차 실행하세요.

[5. 자율 오류 복구]
- Hermes가 직접 검증을 실행하고 실패 로그를 분석하세요.
- 최소 범위로 수정하고 동일한 검증을 재실행하세요.
- 문제당 최대 3회까지만 수정·재검증하고, 해결되지 않으면 FAIL로 보고하세요.
- 실패 테스트를 삭제하거나 조건을 약화하거나 무조건 PASS로 바꾸지 마세요.
- Playwright 응답의 status, exitCode, timedOut을 확인하세요.

[6. 기존 기능 회귀와 반복 실행]
- Dashboard Harness가 PASS한 다음 기존 scripts/verify-requests.sh를
  변경 없이 순차 실행하고 AC08-01~AC08-06을 다시 확인하세요.
- Requests 회귀 테스트가 FAIL이면 제9교시 완료로 보고하지 마세요.
- 이후 동일한 verify-dashboard.sh를 추가 수정 없이 2회 연속 실행하세요.
  두 실행 모두 전체 단계 PASS, 종료 코드 0이어야 합니다.
- 각 E2E 종료 후 서버 정상 상태와 초기 데이터 3건 복원을 확인하세요.

[7. 최종 증거]
- evidence/lesson09-verification.md에 AC09-01~06의 판정,
  빌드/단위/통합/E2E 결과, 실패와 수정, 반복 검증,
  제8교시 회귀 결과 및 최종 데이터·서버 상태를 기록하세요.
- evidence/logs/에 단계별 로그와 반복 실행 기록을 남기세요.
- progress.md에서 제8교시 완료 상태를 유지하고 제9교시만 갱신하세요.
- 최종 보고에는 변경 파일, Runner 종료 코드, 남은 문제를 포함하세요.
- 교육생에게 PowerShell 검증 명령을 요청하지 마세요.

계획만 작성하지 말고 구현 → Harness 작성 → 실제 실행 → 오류 복구
→ Requests 회귀 테스트 → Dashboard Harness 2회 연속 검증 → 증거 기록까지 직접 수행하세요.
```

> **데이터 주의:** 이 실습의 Harness는 E2E 실행 전후 저장 데이터를 초기 시드 3건으로 복원합니다. 브라우저에서 별도로 추가한 실습 요청은 Harness 재실행 시 초기화될 수 있습니다. Requests와 Dashboard Harness는 **동시에 실행하지 않습니다.**

## 4. STEP 3 — Agent의 자율 수정·재검증 과정 관찰

Hermes Chat의 도구 실행 기록을 보며 에이전트가 구현과 검증을 실제로 수행하는지 확인합니다.

| 관찰할 행동 | 도구·로그 예시 | 의미 |
|---|---|---|
| 고정 명세 읽기 | `Read File("dashboard.md")`, `Read File("lesson09-dashboard-plan.md")` | 요구사항 확인 |
| 계산 모듈 작성 | `Write File("/workspace/client/src/metrics.js")` | 순수 함수 구현 |
| 화면 연결 | `DashboardTab.tsx`, `App.tsx` 변경 | Dashboard 활성화 |
| 테스트 추가 | `tests/unit/`, `tests/integration/`, `tests/e2e/dashboard.spec.cjs` | AC09 검증 체계 구성 |
| 신규 Harness 생성 | `Write File("/workspace/scripts/verify-dashboard.sh")` | 기존 Requests Harness와 독립된 검증 경로 |
| 검증 실행 | `bash scripts/verify-dashboard.sh` | 빌드·테스트·복원 실행 |
| 자율 복구 | FAIL 로그 읽기 → `Patch` → 재실행 | 오류 원인에 따른 최소 수정 |
| 회귀 테스트 | `bash scripts/verify-requests.sh` | 제8교시 기능 유지 확인 |
| 반복 검증 | 동일 Dashboard Harness 2회 연속 PASS | 재실행 가능성 확인 |

실행 로그에 일시적인 FAIL이 보일 수 있습니다. 중요한 것은 **실패 원인을 근거로 수정하고, 같은 검증을 다시 수행하여 최종 결과가 PASS가 되는지**입니다. 실행 중에는 Hermes의 도구 호출을 PowerShell 수동 테스트로 대신하지 않습니다.

### 대표적인 문제와 해결 방향

| 문제 상황 | 확인할 곳 | 해결 방향 |
|---|---|---|
| TypeScript 미사용 import 오류 | 빌드 로그·Dashboard 컴포넌트 | 불필요한 import 제거 후 재빌드 |
| `ReferenceError`가 E2E의 `waitForFunction`에서 발생 | `tests/e2e/dashboard.spec.cjs` | 브라우저 컨텍스트 밖 변수는 인자로 전달 |
| `hermes:5174` 접근 실패 | Vite 로그·설정, Harness 로그 | 앱 실행 여부, `allowedHosts`, `strictPort` 확인 |
| `EADDRINUSE` | 서버 로그·PID 관리 코드 | 기존 서버 종료 여부 및 소유 관계 확인 |
| `/proc/net/tcp`에서 PID 탐색 오류 | 종료 함수·프로세스 탐색 로그 | 포트 탐색·inode·PID 추출을 구분해 확인, 무한 반복 방지 |
| E2E 후 시드 개수 불일치 | 데이터 파일·복원 단계·E2E 로그 | 실제 시드 ID `REQ-001`~`REQ-003` 기준 복원 여부 검증 |
| Requests 회귀 실패 | Requests Harness 로그 | Dashboard 변경의 영향 파악 후 최소 수정 |

**주의:** 오류가 났다는 이유만으로 테스트 판정을 PASS로 바꾸거나, E2E 검증 조건을 삭제하지 않습니다. 수정 횟수 상한을 넘거나 안전한 복원이 불가능하면 **차단 요인을 명시하고 종료**합니다.

## 5. STEP 4 — 검증 증거와 반복 실행 결과 확인

Hermes가 완료를 보고하면 다음 파일을 확인합니다.

```text
/workspace/scripts/verify-dashboard.sh
/workspace/scripts/verify-requests.sh
/workspace/tests/e2e/dashboard.spec.cjs
/workspace/evidence/lesson09-verification.md
/workspace/evidence/logs/
/workspace/progress.md
```

Hermes Chat에 아래의 **읽기 전용 확인 프롬프트**를 입력할 수 있습니다. 필요하지 않다면 최종 보고와 증거 파일 확인만으로 마칠 수 있습니다.

```text
제9교시 산출물을 읽기 전용으로 점검하세요.

1. scripts/verify-dashboard.sh의 존재 여부와 자동 실행 순서를 설명하세요.
2. scripts/verify-requests.sh가 제8교시 상태로 보존되었는지 확인하세요.
3. evidence/lesson09-verification.md에서 AC09-01~AC09-06별 PASS/FAIL을 제시하세요.
4. Dashboard Harness의 빌드·단위·통합·E2E 로그 이름, 종료 코드,
   Runner status/exitCode/timedOut을 확인하세요.
5. 수정 없이 2회 연속 실행한 Dashboard Harness 로그와 PASS 결과를 확인하세요.
6. 제8교시 Requests 회귀 실행 결과와 종료 코드를 확인하세요.
7. 최종 데이터가 REQ-001~REQ-003의 3건인지,
   API와 Vite 앱의 정상 응답 근거가 있는지 확인하세요.
8. progress.md에서 제8교시 완료와 제9교시 완료가 구분되는지 확인하세요.

테스트 실행, 파일 수정, 서버 재시작은 하지 마세요.
증거가 없는 항목은 PASS로 판정하지 마세요.
```

### 인수 기준 점검표

| 기준 | 확인할 내용 | 검증 방식 |
|---|---|---|
| AC09-01 | 지표 건수가 원본 데이터와 정확히 일치 | 계산 단위 테스트 + API 데이터 비교 + E2E |
| AC09-02 | `low + medium + high = total` | 분포 단위 테스트 + E2E |
| AC09-03 | 빈 데이터에서 모두 0건, 빈 상태 안내 | 단위·통합 + E2E |
| AC09-04 | Requests 변경이 Dashboard에 반영 | 통합 + 탭 이동·새로고침 E2E |
| AC09-05 | 데스크톱·모바일·키보드 접근성 | E2E |
| AC09-06 | 빌드·관련 단위·통합·E2E 전체 PASS | Harness 및 Runner 종료 코드 |
| AC08 회귀 | 기존 Requests 기능이 유지됨 | **기존 `verify-requests.sh`** |

**정상 완료:** AC09-01~06 PASS, Playwright Runner `status=PASS`, `exitCode=0`, `timedOut=false`, Dashboard Harness 수정 없는 연속 2회 `exit=0`, Requests 회귀 PASS, E2E 후 시드 3건·서비스 정상, 증거 기록 완료.

참고로 테스트 구성 예시에서는 단위 16건, 통합 10건, Dashboard E2E 22개 항목을 검증할 수 있습니다. **항목 수가 정확히 같을 필요는 없으며, 고정 인수 기준을 실제 테스트하고 종료 코드로 확인하는 것이 우선**입니다.

## 6. STEP 5 — 브라우저에서 Dashboard 확인

Windows 브라우저에서 **http://127.0.0.1:5174**에 접속합니다.

1. 상단의 **Dashboard** 탭을 선택합니다.
2. 초기 시드 3건을 기준으로 전체 3건, 할 일 1건, 진행 중 1건, 완료 1건을 확인합니다.
3. 우선순위 낮음·보통·높음이 각각 1건이고 합계가 3건인지 확인합니다.
4. 상태 필터를 `할 일`로 바꾸어 활성 필터 표시와 지표 변경을 확인하고, 다시 `전체`로 돌립니다.
5. **Requests** 탭에서 요청을 새로 등록하거나 상태를 변경한 뒤 Dashboard로 돌아와 변경된 건수가 반영되는지 확인합니다.
6. 브라우저를 새로고침해도 수정된 지표가 유지되는지 확인합니다.
7. 브라우저 창 폭을 줄여 모바일 1열 구성, 가로 스크롤 유무, 키보드 Tab 포커스를 확인합니다.

**빈 상태 검증은 Hermes가 자동 E2E에서 수행**합니다. 화면에서 직접 모든 요청을 삭제할 필요는 없습니다. 또한 이 단계에서 등록·변경한 요청은 다음 Harness 재실행에서 시드 3건으로 초기화될 수 있습니다.

## 7. STEP 6 — 오류 대응 및 완료 보고

제9교시는 Dashboard 구현만 완료했다고 끝나는 것이 아닙니다. **새 Dashboard 검증과 기존 Requests 회귀 검증이 모두 PASS해야 완료**입니다.

완료 보고에는 다음 정보를 포함합니다.

- **구현:** Dashboard 지표·우선순위 분포·상태 필터·빈 상태·Requests 데이터 연동
- **신규 Harness:** `scripts/verify-dashboard.sh`의 생성 및 실행
- **검증:** 빌드·단위·통합·Dashboard E2E 결과와 종료 코드
- **자율 복구:** 발견한 실패, 수정 파일, 같은 검증 재실행 결과
- **반복 실행:** 수정 없는 Dashboard Harness 2회 연속 결과
- **회귀 검증:** 기존 Requests Harness의 PASS/FAIL
- **데이터·서비스:** 최종 초기 데이터 3건과 서버 응답 상태
- **증거:** `evidence/lesson09-verification.md`, `evidence/logs/`, `progress.md`

증거가 부족하면 Hermes Chat에 **확인 또는 보완을 요청**하되, 이미 PASS한 단계 전체를 불필요하게 반복할 필요는 없습니다. 안전한 초기화·복원 없이 데이터를 임의로 지우지 않습니다.

## 8. 제9교시 정리 및 다음 교시 연결

이번 교시의 핵심은 **기존 기능을 유지한 채 새 기능을 확장하고, 기능별 Harness를 독립적으로 실행하면서 회귀 테스트와 데이터 복원까지 자동화하는 것**입니다.

제8교시의 `verify-requests.sh`와 제9교시의 `verify-dashboard.sh`는 **공유된 API 데이터에 접근하므로 순차 실행**합니다. 두 Harness의 E2E는 매번 초기 시드 데이터로 시작하고, 종료 후 데이터를 복원합니다.

제9교시가 완료되면 Dashboard와 Requests의 구현 코드, 두 검증 Harness, 단위·통합·E2E 테스트, 각 교시의 검증 증거를 그대로 보존합니다. **다음 교시에서는 이 완료 상태를 기준으로 실습을 이어갑니다.**

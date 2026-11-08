# 제8교시 — Requests 탭 구현과 자율형 Harness 검증

**과정:** Open Weight Model과 Hermes Agent를 활용한 Agent Harness Engineering  
**프로젝트:** AI Work Request Manager v3  
**실습 환경:** Windows 11 · Docker Desktop · Hermes Agent · OpenRouter · Playwright Runner  
**핵심 목표:** Hermes Agent가 고정된 명세를 읽고 Requests 탭을 구현한 다음, 재사용 가능한 검증 Harness를 통해 **빌드 → 단위 테스트 → 통합 테스트 → E2E → 오류 분석·수정·재검증**을 자율적으로 수행한다.

> **선행 조건:** 제7교시에서 v3 Docker 환경, OpenRouter 모델 설정, Playwright Runner, 구현 계획 파일 구성을 마친 상태입니다. 이 교시에서는 Docker 설치·재설치·기존 프로젝트 정리 절차를 수행하지 않습니다. 기존 v2 환경과 Reference Project는 변경하지 않습니다.

## 1. 학습 목표와 완료 기준

| 학습 항목 | 활동 | 완료 기준 |
|---|---|---|
| 명세 기반 개발 | `AGENTS.md`, 제8교시 계획, UI 가이드, 인수 기준 읽기 | AC08-01~AC08-06 준수 |
| 기능 구현 | Requests 화면, Node.js API, 파일 저장소 구성 | 초기 데이터 3건과 요청 관리 기능 제공 |
| 자동 검증 | 재사용 가능한 `scripts/verify-requests.sh` 구성 | 빌드·단위·통합·E2E 자동 실행 |
| 실패 복구 | 오류 로그 분석, 최소 수정, 동일 검증 재실행 | 실패 은폐 없이 수정·재검증 |
| 반복 가능성 | 완성한 동일 Harness를 수정 없이 2회 실행 | 2회 모두 PASS, 종료 코드 0 |
| 증거 기록 | 검증 결과와 변경 사항 기록 | `evidence/lesson08-verification.md`, `progress.md` 확인 |

이번 교시의 구현 범위는 **Requests 탭**입니다. Dashboard의 지표 계산과 차트는 제9교시에 구현합니다. Dashboard에는 `NOT_IMPLEMENTED` 안내만 제공할 수 있습니다.

### 실습 작업공간

```text
C:\AI-Native\
├── hermes-training-v3\                # 기존 Docker Compose 환경
└── work-request-manager-v3\           # Docker 내부 /workspace
    ├── AGENTS.md
    ├── docs\ui-guidelines.md
    ├── specs\requests.md
    ├── specs\acceptance-criteria.md
    ├── plans\lesson08-requests-plan.md
    ├── data\fixtures\requests.seed.json
    ├── client\                       # React + TypeScript + Vite
    │   └── src\                       # 프런트엔드 소스
    ├── server\                       # Node.js API + 영속 데이터
    ├── tests\unit\
    ├── tests\integration\
    ├── tests\e2e\requests.spec.cjs
    ├── scripts\verify-requests.sh     # 재사용 가능한 검증 Harness
    ├── evidence\lesson08-verification.md
    └── progress.md
```

**경로 규칙:** 프런트엔드 소스는 반드시 `/workspace/client/src/`에 둡니다. `/workspace/src/`는 만들지 않습니다.

## 2. STEP 1 — 개발 환경 및 제7교시 계획 확인

1. Docker Desktop이 실행 중인지 확인합니다.
2. Hermes Dashboard **http://127.0.0.1:9130**에 접속합니다.
3. Hermes와 Playwright Runner가 실행 중인지, 제7교시에서 만든 제8교시 구현 계획이 있는지 확인합니다.

Docker 서비스 상태를 확인할 필요가 있을 때만 다음 **읽기 전용** PowerShell 블록을 실행합니다. 이후 구현 및 자동 검증을 PowerShell에서 수동 실행하지 않습니다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $runtime = 'C:\AI-Native\hermes-training-v3'
    $workspace = 'C:\AI-Native\work-request-manager-v3'
    Set-Location -LiteralPath $runtime

    $configText = docker compose config --format json
    if ($LASTEXITCODE -ne 0) { throw 'Compose 설정 확인 실패' }
    $config = $configText | ConvertFrom-Json
    if ($config.name -ne 'hermes-training-v3') { throw 'Compose 프로젝트 불일치' }
    $appPort = @($config.services.hermes.ports | Where-Object {
        [string]$_.published -eq '5174' -and [int]$_.target -eq 5174
    })
    if ($appPort.Count -ne 1) { throw '앱 포트 5174:5174 설정 확인 실패' }

    $running = @(docker compose ps --services --status running)
    if ($LASTEXITCODE -ne 0 -or 'hermes' -notin $running -or 'playwright' -notin $running) {
        throw 'Hermes 또는 Playwright Runner가 실행 중이지 않습니다.'
    }

    foreach ($relative in @(
        'AGENTS.md',
        'plans\lesson08-requests-plan.md',
        'plans\lesson09-dashboard-plan.md',
        'specs\requests.md',
        'specs\acceptance-criteria.md',
        'docs\ui-guidelines.md',
        'data\fixtures\requests.seed.json'
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $workspace $relative) -PathType Leaf)) {
            throw "필수 파일 없음: $relative"
        }
    }

    docker compose ps
    Write-Host '[PASS] 제8교시 환경·계획·포트 준비' -ForegroundColor Green
}
```

**정상 확인:** Hermes 및 Playwright 컨테이너가 실행 중이고, 앱 포트 매핑이 `127.0.0.1:5174 → 5174/tcp`이며, 마지막 줄에 `[PASS]`가 나타납니다. 컨테이너 내부에서 Playwright가 애플리케이션에 접근할 때는 **`http://hermes:5174`**를 사용합니다. Windows 브라우저의 접속 주소와 구별합니다.

## 3. STEP 2 — Hermes Agent Chat에서 자율형 구현·검증 시작

Hermes Dashboard에서 **New Chat**을 만들고, 작업공간 `/workspace`와 제7교시에서 설정한 OpenRouter 모델을 확인합니다. 아래 프롬프트를 **전체 복사하여 한 번에 입력**합니다.

### Hermes Agent 실습 프롬프트

```text
현재는 제8교시 Agent Harness Engineering 실습입니다.

AI Work Request Manager v3의 Requests 탭을 구현하고, 재사용 가능한 자율형 검증 Harness를 구성하여 실제 실행하세요.

[1. 작업 범위]
- 작업공간은 /workspace입니다.
- AGENTS.md, plans/lesson08-requests-plan.md, specs/requests.md,
  specs/acceptance-criteria.md, docs/ui-guidelines.md,
  data/fixtures/requests.seed.json을 먼저 읽으세요.
- 변경 범위는 /workspace 내부로 제한하고, v2 및 Reference Project는 변경하지 마세요.
- AC08-01~AC08-06은 고정된 인수 기준으로 취급하세요.
- Dashboard 지표 기능은 구현하지 마세요.

[2. Requests 구현]
- client/: React + TypeScript + Vite
- client/src/: 프런트엔드 소스 (루트 /workspace/src/ 사용 금지)
- server/: Node.js API 및 파일 기반 영속 저장소
- tests/unit/, tests/integration/, tests/e2e/: 자동 검증
- 초기 요청 3건, 등록·수정·상태 변경·검색·상태 필터·필터 초기화 구현
- 서버 측 필수 입력 검증, 기계 판독 가능한 오류 코드, 실패 메시지 표시
- 재시작 후 데이터 유지, 반응형 카드 UI, 키보드 접근성 구현
- E2E 스크립트는 tests/e2e/requests.spec.cjs에 작성하세요.

[3. 재사용 가능한 검증 Harness]
- scripts/verify-requests.sh를 생성하세요.
- 한 번의 스크립트 호출로 아래 단계를 자동 실행하세요.
  1) 프런트엔드 빌드
  2) 단위 테스트
  3) 통합 테스트
  4) 앱 서버 안전 종료
  5) 초기 데이터 3건 복원 및 앱 서버 재시작
  6) Playwright Runner POST http://playwright:3000/run
     요청 본문: {"test":"requests"}
  7) E2E 종료 후 서버 안전 종료, 초기 데이터 복원, 서버 재시작
  8) 각 단계의 종료 코드와 PASS/FAIL 검증 및 로그 보존
- Playwright 브라우저 대상 주소는 http://hermes:5174를 사용하세요.
  고정 컨테이너 IP를 사용하지 마세요.
- 5174 앱 접속과 API 연동이 모두 가능하도록 서버를 실행하세요.
- 기존 포트 사용자나 무관한 프로세스를 임의 종료하지 마세요.
  안전한 종료를 확인하지 못하면 FAIL 처리하고 데이터 복원을 강행하지 마세요.
- 데이터 초기화는 이 실습의 테스트 데이터에 한정합니다.
  E2E 실패 시에도 가능한 범위에서 사후 복원을 수행하고 실패를 숨기지 마세요.

[4. 자율 오류 복구]
- 작성한 Harness를 직접 실행하고 빌드·단위·통합·E2E 결과를 확인하세요.
- 실패하면 로그·종료 코드를 분석하고 최소 범위로 수정한 다음
  동일한 검증을 다시 실행하세요. 문제당 최대 3회까지 재시도하세요.
- 인수 기준을 약화하거나 테스트를 무조건 PASS로 만들지 마세요.

[5. 반복 실행과 완료 기록]
- 모든 검증을 통과하면 같은 verify-requests.sh를 추가 수정 없이
  2회 연속 실행하세요. 두 실행 모두 exit=0 및 모든 단계 PASS여야 합니다.
- 테스트가 끝난 뒤 초기 요청 3건과 앱 서버 정상 실행을 확인하세요.
- evidence/lesson08-verification.md에 실행 명령, 결과, 종료 코드,
  실패 원인·수정 사항, 2회 반복 실행 결과를 기록하세요.
- progress.md에 제8교시 완료 상태를 기록하고
  제9교시는 NOT_IMPLEMENTED로 유지하세요.
- AC08-01~AC08-06별 PASS/FAIL을 최종 보고하세요.
- 교육생에게 PowerShell 검증 명령을 요청하지 마세요.

계획만 제출하지 말고 구현 → Harness 생성 → 실제 실행 → 오류 수정
→ 연속 2회 검증 → 증거 기록까지 직접 수행하세요.
```

**정상 진행:** Hermes가 명세·계획을 읽은 뒤 `client/`, `server/`, `tests/`, `scripts/`를 작성합니다. 이후 테스트를 직접 실행하고, 실패가 발생하면 로그를 분석하여 코드를 수정한 다음 재실행합니다.

> **중요:** E2E 테스트는 생성·수정·상태 변경을 수행합니다. 이 교시에서는 **초기 요청 3건으로 데이터를 되돌리는 것**을 검증 절차에 포함합니다. 개인적으로 추가한 요청이 있는 작업공간에 적용하면 해당 변경 내용은 유지되지 않습니다.

## 4. STEP 3 — Hermes의 실행 과정 관찰

Hermes Chat의 도구 실행 내역을 살펴보면서 다음 사항을 확인합니다.

| 확인할 행동 | 예시 로그 또는 산출물 | 의미 |
|---|---|---|
| 명세 읽기 | `Read File("AGENTS.md")`, `Read File("acceptance-criteria.md")` | 고정 요구사항 확인 |
| 기능 구현 | `Write File("/workspace/client/src/...")`, `Write File("/workspace/server/...")` | 소스 생성 |
| 검증 스크립트 생성 | `Write File("/workspace/scripts/verify-requests.sh")` | 재사용 가능한 Harness 구성 |
| 빌드·테스트 | `npm run build`, `node --test ...`, `bash scripts/verify-requests.sh` | 실제 검증 실행 |
| 실패 복구 | 실패 로그 확인 → `Patch` → 테스트 재실행 | 자율적인 수정 루프 |
| Runner 호출 | `POST http://playwright:3000/run` | 브라우저 E2E 수행 |
| 반복 검증 | 동일 Harness 2회 연속 `exit=0` | 반복 실행 가능성 확인 |

**예상되는 문제 해결 사례:** TypeScript 미사용 변수, API 응답 형식 불일치, Vite의 `hermes` 호스트 접근 제한, 서버 포트 충돌, E2E 초기 데이터 가정 오류 등이 발생할 수 있습니다. 오류 종류나 발생 횟수는 구현 결과에 따라 달라질 수 있습니다.

**실습 원칙:** Hermes가 실행 중이라면 중간에 PowerShell로 테스트를 별도 수행하지 않습니다. 로그가 계속 갱신되고 있다면 현재 작업을 관찰하고, 도구 실행이 멈추거나 FAIL로 종료된 경우 해당 메시지를 토대로 원인을 확인합니다.

## 5. STEP 4 — 자율 검증 결과 확인

Hermes가 완료를 보고하면 Chat의 최종 메시지와 다음 파일을 확인합니다.

```text
/workspace/scripts/verify-requests.sh
/workspace/evidence/lesson08-verification.md
/workspace/evidence/logs/
/workspace/progress.md
```

Hermes Chat에 아래 확인 프롬프트를 입력할 수 있습니다. **읽기와 요약만 요청**하며, 검증을 다시 실행하지 않습니다.

```text
제8교시 최종 산출물을 읽기 전용으로 점검하세요.

1. scripts/verify-requests.sh의 존재 여부와 자동 수행 단계를 요약하세요.
2. evidence/lesson08-verification.md에서 최초 실패·수정·재검증 결과를 요약하세요.
3. 수정 없이 연속 실행한 두 Harness 로그의 이름, 종료 코드,
   빌드/단위/통합/E2E PASS 여부를 확인하세요.
4. E2E 실행 주소가 http://hermes:5174인지 확인하세요.
5. 초기 요청 3건 복원과 앱 서버 정상 실행을 확인한 증거를 제시하세요.
6. progress.md에서 제8교시 완료 및 제9교시 NOT_IMPLEMENTED를 확인하세요.
7. AC08-01~AC08-06 결과를 표로 보고하세요.

파일 수정, 테스트 재실행, 서버 재시작은 하지 마세요.
증거가 없는 내용은 PASS라고 표시하지 마세요.
```

### 검증 결과 판정표

| 기준 | 확인 항목 |
|---|---|
| AC08-01 | 초기 요청 3건 및 카드 정보 |
| AC08-02 | 등록·수정·상태 변경·검색·필터·초기화 |
| AC08-03 | 입력 검증과 오류 메시지 |
| AC08-04 | 서버 재시작 후 영속성 |
| AC08-05 | 반응형 화면과 키보드 접근성 |
| AC08-06 | 빌드·단위·통합·E2E 자동 검증과 결과 기록 |

**정상 완료:** 모든 인수 기준 PASS, Runner `status=PASS`, `exitCode=0`, `timedOut=false`, 두 연속 Harness 실행 `exit=0`, E2E 종료 후 초기 데이터 3건 복원, 앱 서버 정상 실행, 검증 증거 파일 존재.

테스트 항목 수는 구현한 테스트에 따라 달라질 수 있습니다. 항목 수 자체보다 **고정 인수 기준의 충족과 실제 종료 코드**를 우선 확인합니다.

## 6. STEP 5 — 브라우저에서 Requests 화면 확인

Windows 브라우저에서 **http://127.0.0.1:5174**에 접속합니다.

- **초기 표시:** Requests 탭에 시드 요청 3건이 카드 형태로 보입니다.
- **요청 등록:** 제목·요청자·설명·우선순위를 입력하면 카드가 추가됩니다.
- **요청 수정:** 기존 카드의 값을 수정하고 저장하면 화면에 반영됩니다.
- **상태 변경:** 할 일·진행 중·완료 상태를 변경할 수 있습니다.
- **검색·필터:** 제목 등 검색 및 상태 필터가 동작하고, 필터 초기화로 원래 목록을 표시합니다.
- **입력 오류:** 필수 입력을 비우면 오류 메시지가 표시됩니다.
- **화면 구성:** 창 너비에 따라 카드 레이아웃이 조정되고, 키보드 포커스를 확인할 수 있습니다.
- **Dashboard:** 제9교시 미구현 상태로 유지됩니다.

**주의:** 브라우저에서 새로운 요청을 등록하거나 수정하면 현재 영속 데이터도 변경됩니다. 이후 Harness를 다시 실행하면 테스트용 초기 3건으로 복원됩니다.

## 7. STEP 6 — 오류 발생 시 대응

| 증상 | 점검 위치 | 조치 원칙 |
|---|---|---|
| `hermes:5174` 연결 실패 | `evidence/logs/client.log`, Harness 로그 | Vite 서버 시작 여부·5174 포트 확인 |
| `Blocked request. This host ("hermes") is not allowed` | `client/vite.config.ts` | `server.allowedHosts`에 Docker 서비스 이름 허용 |
| `EADDRINUSE` | `evidence/logs/server.log`, Harness의 PID 처리 | 기존 서버 프로세스 소유 관계를 확인한 뒤 안전 종료 |
| E2E 초기 카드 수 불일치 | 시드 파일, 복원 절차, E2E 로그 | E2E 직전·직후 시드 3건 복원 검증 |
| 단위·통합 실패 | 해당 테스트 로그 | 명세와 실제 API/모듈 사이의 불일치 수정 |
| 테스트 실패를 PASS라고 보고 | Runner 응답, 종료 코드, 증거 기록 | 종료 코드와 실패 건수를 기준으로 다시 판정 |

**오류 수정은 Hermes Agent Chat에서 수행합니다.** 교육생이 직접 테스트를 통과시키기 위해 명세를 수정하거나, 실패한 테스트를 삭제하거나, 무조건 PASS를 출력하도록 변경하지 않습니다.

## 8. 제8교시 정리 및 제9교시 연결

이번 교시의 핵심은 Requests 화면 자체보다 **Hermes Agent가 명세에 따라 코드를 작성하고 도구를 호출하여 결과를 검증한 후, 실패를 스스로 복구하는 구조**입니다.

완료 후 보존할 산출물은 `client/`, `server/`, `tests/`, `scripts/verify-requests.sh`, `evidence/lesson08-verification.md`, `progress.md`입니다. 이 산출물은 제9교시 Dashboard 구현의 기반이 됩니다.

**제9교시에는 기존 Requests 기능과 검증 Harness를 유지한 채 Dashboard 기능을 추가**합니다.

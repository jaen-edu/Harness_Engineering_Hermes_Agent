# 제7교시 — v3 독립 환경 구성과 Agent Harness 준비

**과정:** Open Weight Model과 Hermes Agent를 활용한 Agent Harness Engineering  
**실습 프로젝트:** AI Work Request Manager v3  
**실습 범위:** 독립 환경 설치, Docker Compose, Hermes Dashboard 로그인, OpenRouter CLI 모델 설정과 Agent Chat 확인, Playwright Runner/Chromium 확인, 명세 읽기와 제8~9교시 구현 계획  
**제7교시에서는 애플리케이션 UI·API·빌드 설정·애플리케이션 테스트를 구현하지 않습니다.**

## 준비물과 디렉터리

- Windows 11, PowerShell 7, Docker Desktop(Linux containers), 인터넷 접속
- **단 하나의 Starter:** `lesson07_starter_v3.zip` (다운로드 폴더에 저장)
- 이 ZIP에 **통합 `hermes-training-v3/compose.yaml`이 포함**됩니다. 별도 `lesson07_compose_v3.yaml`을 받거나 YAML을 수동으로 만들지 않습니다.
- 압축 해제 대상은 `C:\AI-Native\hermes-training-v3` 및 `C:\AI-Native\work-request-manager-v3`입니다.
- 기존 v2 및 Reference Project에 접근하거나 변경하지 않습니다. 이번 가이드북에서는 삭제·재설치·클린 정리를 진행하지 않습니다.
- 모든 명령은 `& { ... }` 단일 실행 블록입니다. **한 블록 실행 후 결과를 확인하고 다음 단계로 진행합니다.**

### 전체 진행 순서

| 단계 | 목적 | 정상 확인 |
|---|---|---|
| 1 | 신규 설치 가능 여부 | v3 폴더 없음, Docker 응답, 포트 확인 |
| 2 | Starter ZIP 설치 | 두 v3 폴더 배치 |
| 3 | 명세·데이터 및 Compose 정적 검사 | 3개 초기 레코드, 2개 서비스 |
| 4 | v3 자격증명 생성 | `.env` 생성, Compose 유효 |
| 5 | Docker 서비스 시작 | 두 서비스 running |
| 6 | Dashboard 웹 로그인 | `student`, 화면 하단 `via basic` |
| 7 | Hermes CLI 모델 설정 및 Agent Chat 확인 | `hermes model` 완료, OpenRouter 모델 응답·도구 호출 성공 |
| 8 | Hermes→Playwright HTTP와 브라우저 실행 | `/health` 및 `/run` PASS |
| 9 | 애플리케이션 미구현 확인 | 소스 없음, 미리보기 미실행 |
| 10 | 구현 계획 저장 | `plans/`의 제8~9교시 Markdown 계획 파일 2개 생성·확인 |

## 1 — 사전 점검(읽기 전용)

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Write-Host '=== 신규 설치 사전 점검 ===' -ForegroundColor Cyan
    foreach ($relative in @('hermes-training-v2','work-request-manager-v2','hermes-training-v3','work-request-manager-v3')) {
        $path = Join-Path 'C:\AI-Native' $relative
        Write-Host ('{0}: {1}' -f $relative, (Test-Path -LiteralPath $path))
    }
    foreach ($path in @('C:\AI-Native\hermes-training-v3','C:\AI-Native\work-request-manager-v3')) {
        if (Test-Path -LiteralPath $path) { throw "v3 경로가 이미 존재합니다. 신규 설치 금지: $path" }
    }
    docker compose version
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose 사용 불가' }
    docker ps --format 'table {{.Names}}\t{{.Ports}}'
    if ($LASTEXITCODE -ne 0) { throw 'Docker Engine 사용 불가' }
    $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -in @(9130,5174) })
    if ($listeners.Count) {
        $listeners | Select-Object LocalAddress,LocalPort,OwningProcess | Format-Table
        throw 'v3 예정 포트가 이미 사용 중입니다. 기존 서비스 확인 후 진행하세요.'
    }
    Write-Host '[PASS] 신규 설치 준비' -ForegroundColor Green
}
```

## 2 — ZIP 설치

기존 디렉터리에 압축 파일 전체를 **덮어쓰지 않습니다**. ZIP 경로가 정상인지 확인한 뒤 임시 폴더에서 풀어 두 v3 폴더만 이동합니다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $root = 'C:\AI-Native'
    $zipPath = Join-Path $HOME 'Downloads\lesson07_starter_v3.zip'
    $names = @('hermes-training-v3','work-request-manager-v3')
    if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) { throw "Starter ZIP 없음: $zipPath" }
    foreach ($name in $names) {
        if (Test-Path -LiteralPath (Join-Path $root $name)) { throw "기존 v3 경로 보호: $name" }
    }
    Add-Type -AssemblyName System.IO.Compression
    $zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName.Replace('\','/')
            if (-not ($name -eq 'README.md' -or $name.StartsWith('hermes-training-v3/') -or $name.StartsWith('work-request-manager-v3/')) -or
                $name.StartsWith('/') -or $name -match '(^|/)\.\.(/|$)' -or $name.Contains(':')) {
                throw "ZIP 경로가 허용 범위 밖입니다: $name"
            }
        }
    } finally { $zip.Dispose() }
    $temp = Join-Path $env:TEMP ('lesson07_' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $temp | Out-Null
    try {
        Expand-Archive -LiteralPath $zipPath -DestinationPath $temp -ErrorAction Stop
        foreach ($name in $names) {
            if (-not (Test-Path -LiteralPath (Join-Path $temp $name) -PathType Container)) { throw "ZIP 필수 폴더 누락: $name" }
        }
        New-Item -ItemType Directory -Path $root -Force | Out-Null
        foreach ($name in $names) {
            Move-Item -LiteralPath (Join-Path $temp $name) -Destination $root -ErrorAction Stop
            Write-Host "[PASS] 설치: $name" -ForegroundColor Green
        }
    } finally { if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force } }
    Write-Host '[PASS] 신규 Starter 설치' -ForegroundColor Green
}
```

## 3 — Starter/Compose 검사(읽기 전용)

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $runtime = 'C:\AI-Native\hermes-training-v3'
    $app = 'C:\AI-Native\work-request-manager-v3'
    foreach ($relative in @('compose.yaml','.env.example','playwright-service\server.cjs','playwright-service\browser-smoke.cjs')) {
        if (-not (Test-Path -LiteralPath (Join-Path $runtime $relative) -PathType Leaf)) { throw "런타임 파일 누락: $relative" }
    }
    foreach ($relative in @('AGENTS.md','docs\project-overview.md','docs\ui-guidelines.md','specs\requests.md','specs\dashboard.md','specs\acceptance-criteria.md','data\fixtures\requests.seed.json')) {
        if (-not (Test-Path -LiteralPath (Join-Path $app $relative) -PathType Leaf)) { throw "명세 파일 누락: $relative" }
    }
    $data = @(Get-Content -LiteralPath (Join-Path $app 'data\fixtures\requests.seed.json') -Raw -Encoding UTF8 | ConvertFrom-Json)
    if ($data.Count -ne 3) { throw "초기 데이터 건수 불일치: $($data.Count)" }
    $compose = Get-Content -LiteralPath (Join-Path $runtime 'compose.yaml') -Raw -Encoding UTF8
    if ($compose -notmatch 'NODE_PATH: /opt/playwright-runtime/node_modules') { throw 'Playwright NODE_PATH 누락' }
    if ($compose -match 'hermes-training-v2|work-request-manager-v2') { throw 'v2 참조 발견' }
    Write-Host '[PASS] 필수 파일 / 3건 데이터 / NODE_PATH / v2 비참조' -ForegroundColor Green
}
```

## 4 — v3 전용 `.env` 생성 및 Compose 검사

암호는 로컬에만 저장합니다. **화면·수업 제출물·채팅에 비밀번호를 공유하지 않습니다.** 이 스크립트는 `.env`가 이미 있으면 중단합니다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $runtime = 'C:\AI-Native\hermes-training-v3'
    $envPath = Join-Path $runtime '.env'
    if (Test-Path -LiteralPath $envPath) { throw '.env가 이미 있습니다. 덮어쓰지 않습니다.' }
    $passwordBytes = [byte[]]::new(24)
    $secretBytes = [byte[]]::new(48)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($passwordBytes)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($secretBytes)
    $password = [Convert]::ToHexString($passwordBytes)
    $secret = [Convert]::ToHexString($secretBytes)
    [System.IO.File]::WriteAllLines($envPath, @("DASHBOARD_PASSWORD=$password", "DASHBOARD_SECRET=$secret"), [System.Text.UTF8Encoding]::new($false))
    Set-Location -LiteralPath $runtime
    docker compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Compose 설정 오류' }
    $json = docker compose config --format json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $json.name -ne 'hermes-training-v3') { throw 'Compose 프로젝트 이름 오류' }
    $services = @($json.services.PSObject.Properties.Name)
    if ($services.Count -ne 2 -or 'hermes' -notin $services -or 'playwright' -notin $services) { throw '서비스 구성 오류' }
    Write-Host '[PASS] .env 생성 및 통합 Compose 검사' -ForegroundColor Green
    Write-Host '로그인 계정: student (암호는 v3 .env에 보관)' -ForegroundColor Cyan
}
```

## 5 — 이미지 다운로드 및 서비스 실행

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v3'
    docker compose pull
    if ($LASTEXITCODE -ne 0) { throw '이미지 다운로드 실패' }
    docker compose up -d --no-build
    if ($LASTEXITCODE -ne 0) { throw '서비스 시작 실패' }
    $running = @(docker compose ps --services --status running)
    if ($LASTEXITCODE -ne 0 -or 'hermes' -notin $running -or 'playwright' -notin $running) {
        docker compose ps -a
        throw '서비스가 running 상태가 아닙니다. 로그를 확인하세요.'
    }
    docker compose ps
    Write-Host '[PASS] Hermes / Playwright 컨테이너 실행' -ForegroundColor Green
}
```

## 6 — Dashboard 웹 로그인

1. Chrome/Edge에서 **http://127.0.0.1:9130** 접속.
2. 사용자명 **`student`**와 `C:\AI-Native\hermes-training-v3\.env`의 `DASHBOARD_PASSWORD` 값으로 로그인.
3. Dashboard 화면과 왼쪽 하단의 **`student` / `via basic`**, **Gateway Status: Running**을 확인.

PowerShell로 `.env`를 편집기에서 열 때는 `notepad 'C:\AI-Native\hermes-training-v3\.env'`를 사용할 수 있으나, **암호 화면이나 내용을 공유하지 마세요.** 인증이 없는 별도의 보호 대상 API가 401을 반환할 수 있으며, 단순 `Authorization: Basic` 헤더의 200/401 결과를 웹 로그인 성공 판정의 대체 수단으로 사용하지 않습니다.

**교육용 판정:** 브라우저에서 로그인하여 `student / via basic`이 나타나면 Dashboard 웹 로그인 PASS. 이 판정은 모든 API의 접근 통제에 대한 보안 감사를 의미하지 않습니다.

## 7 — OpenRouter 모델 설정 및 Agent Chat 검증

Dashboard 로그인과 LLM 모델 설정은 별개입니다. **모델 설정은 Hermes CLI에서 한 번만 진행**하고, **응답 확인은 Hermes Dashboard의 Chat**에서 진행합니다. Dashboard의 Keys/Models 메뉴를 따로 사용하지 않습니다.

### 7-1. 모델 설정

OpenRouter 계정에서 발급받은 개인 API 키를 준비합니다. 모델 이용 요금과 잔액을 확인하고 API 키는 다른 사람에게 공개하지 않습니다.

PowerShell에서 다음 블록을 **통째로 실행**합니다. `hermes model`은 대화형 명령이므로 입력 화면의 안내에 따라 OpenRouter API 키를 등록하고 교육에서 지정한 GLM 모델을 선택합니다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v3'
    docker compose exec hermes hermes model
    if ($LASTEXITCODE -ne 0) { throw 'Hermes 모델 설정 실패' }
    Write-Host '[PASS] Hermes 모델 설정 명령 완료' -ForegroundColor Green
}
```

**화면 예시(설정에 따라 달라질 수 있음):**

```text
API key saved.
Default model set to: z-ai/glm-5.3-flash (via OpenRouter)
Reasoning effort set to: medium
[PASS] Hermes 모델 설정 명령 완료
```

`z-ai/glm-5.3-flash`는 이 과정의 실행 예시입니다. 교육 운영 시 지정한 모델이 다르면 강사가 안내한 모델을 선택합니다. API 키나 인증정보가 출력되면 이를 공유하지 않습니다.

### 7-2. Hermes Dashboard Chat에서 실제 응답 확인

1. Chrome 또는 Edge에서 **http://127.0.0.1:9130**에 접속한 뒤 `student` 계정으로 로그인합니다.
2. Dashboard의 **Chat**에서 새 대화를 열어 아래 프롬프트를 입력합니다.
3. 모델 응답과 Terminal 도구 실행 결과를 확인합니다. **앱 소스나 테스트 파일을 생성하지 않습니다.**

**실습 프롬프트**

```text
현재 작업 환경을 확인해주세요.

1. 현재 사용 중인 LLM 제공자와 모델명을 알려주세요. 확인할 수 있는 설정값을 근거로 답해주세요.
2. 현재 작업 디렉터리를 확인해주세요.
3. /workspace/AGENTS.md 파일이 존재하는지 확인해주세요.
4. 파일을 생성하거나 수정하지 마세요.

마지막에 "제7교시 Hermes Agent 연결 확인 완료"라고 출력해주세요.
```

**정상 응답 예시**

```text
1. LLM 제공자/모델: z-ai/glm-5.3-flash (provider: openrouter)
2. 현재 작업 디렉터리: /opt/data
3. /workspace/AGENTS.md: 존재함
4. 파일 생성·수정 없음

제7교시 Hermes Agent 연결 확인 완료
```

**PASS 기준:** (1) `hermes model`에서 OpenRouter 모델이 설정됨, (2) Chat에서 실제 응답이 생성됨, (3) Terminal 도구 호출로 `/workspace/AGENTS.md`의 존재가 확인됨. 모델의 자기 진술만으로 모델 ID를 확정하지 않고 설정 화면의 값과 함께 확인합니다. 작업 디렉터리가 `/opt/data`로 표시되는 것은 정상이며, 제8~9교시의 애플리케이션 작업 공간은 `/workspace`입니다.

**문제 해결:** 모델 응답이 없으면 `docker compose exec hermes hermes model`을 다시 실행해 제공자·모델·API 키 설정을 확인하고, OpenRouter 잔액 및 해당 모델의 사용 가능 여부를 점검합니다. 실제 API 키는 채팅이나 결과 캡처에 넣지 않습니다.

## 8 — Hermes → Playwright → Chromium 연동

이 검증은 **애플리케이션 테스트가 아니라 브라우저 실행 엔진 테스트**입니다. 다음 스크립트는 Hermes 컨테이너에서 HTTP로 Runner를 호출하고, JSON 결과의 실제 상태를 검사합니다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v3'
    docker compose exec -T hermes python -c @'
import json
import urllib.request

base = 'http://playwright:3000'
with urllib.request.urlopen(base + '/health', timeout=15) as response:
    health = json.load(response)
print('HEALTH:', health)
if health.get('status') != 'OK':
    raise SystemExit('Health status != OK')

request = urllib.request.Request(
    base + '/run',
    data=json.dumps({'test':'browser-smoke'}).encode('utf-8'),
    headers={'Content-Type':'application/json'},
    method='POST'
)
with urllib.request.urlopen(request, timeout=100) as response:
    result = json.load(response)
print('RUN:', json.dumps(result, ensure_ascii=False))
output = str(result.get('stdout','')) + str(result.get('stderr',''))
if (result.get('status') != 'PASS' or result.get('exitCode') != 0
    or result.get('timedOut') is not False
    or 'BROWSER_CLOSE_COMPLETE' not in output
    or 'TEST_COMPLETE' not in output):
    raise SystemExit('browser-smoke FAIL')
print('[PASS] AC07-04 / AC07-05')
'@
    if ($LASTEXITCODE -ne 0) { throw 'Playwright 연동 검증 실패' }
    Write-Host '[PASS] Hermes -> Playwright -> Chromium' -ForegroundColor Green
}
```

## 9 — 제7교시 구현 금지 상태 확인

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $root = 'C:\AI-Native\work-request-manager-v3'
    foreach ($relative in @('client','server','tests')) {
        $path = Join-Path $root $relative
        if (-not (Test-Path -LiteralPath $path -PathType Container)) { throw "폴더 누락: $relative" }
        $files = @(Get-ChildItem -LiteralPath $path -Recurse -File | Where-Object { $_.Name -ne '.gitkeep' })
        if ($files.Count) { throw "제7교시 구현 금지 파일 발견: $relative" }
        Write-Host "[PASS] $relative : 구현 파일 없음" -ForegroundColor Green
    }
    $patterns = @('package.json','index.html','vite.config.*','tsconfig*.json')
    foreach ($pattern in $patterns) {
        if (@(Get-ChildItem -LiteralPath $root -Recurse -File -Filter $pattern).Count -gt 0) { throw "앱 실행 설정 발견: $pattern" }
    }
    $listener = @(Get-NetTCPConnection -LocalPort 5174 -State Listen -ErrorAction SilentlyContinue)
    if ($listener.Count -gt 0) {
        try {
            $response = Invoke-WebRequest 'http://127.0.0.1:5174/' -TimeoutSec 5 -SkipHttpErrorCheck -UseBasicParsing
            throw "미리보기 서버 HTTP 응답: $([int]$response.StatusCode)"
        } catch {
            if ($_.Exception.Message -like '미리보기 서버 HTTP 응답:*') { throw }
            Write-Host '[PASS] 미리보기 HTTP 응답 없음' -ForegroundColor Green
        }
    } else { Write-Host '[PASS] 미리보기 포트 LISTEN 없음' -ForegroundColor Green }
    Write-Host '[PASS] AC07-06 (애플리케이션 미구현)' -ForegroundColor Green
}
```

## 10 — 제8~9교시 구현 계획을 Markdown 파일로 저장

Dashboard의 새 Hermes Agent Chat에 아래 프롬프트를 **블록 전체 복사하여 입력**합니다. 제7교시에는 두 계획 문서만 작성하며, 애플리케이션 코드는 생성하지 않습니다.

**Hermes Agent Chat 입력 프롬프트**

```text
현재는 제7교시입니다. 제8~9교시의 구현 계획 문서만 작성하고 애플리케이션은 구현하지 마세요.

1. 작업 범위를 /workspace로 한정하고 다음 문서를 먼저 읽으세요.
- /workspace/AGENTS.md
- /workspace/docs/project-overview.md
- /workspace/docs/ui-guidelines.md
- /workspace/specs/requests.md
- /workspace/specs/dashboard.md
- /workspace/specs/acceptance-criteria.md

2. 다음 디렉터리 구조를 계획에 반영하세요.
- client/: React + TypeScript + Vite 프런트엔드 프로젝트 루트
- client/src/: 프런트엔드 소스
- server/: Node.js 백엔드 API 및 영속 저장소
- tests/unit/: 단위 테스트
- tests/integration/: 통합 테스트
- tests/e2e/: Playwright E2E 테스트
- evidence/: 검증 증거
프로젝트 루트에 별도의 src/를 계획하거나 생성하지 마세요.

3. 반드시 다음 두 Markdown 파일을 실제로 생성하고 UTF-8로 저장하세요.
- /workspace/plans/lesson08-requests-plan.md
- /workspace/plans/lesson09-dashboard-plan.md
plans/ 디렉터리가 없다면 생성하세요. Chat 출력만으로 끝내지 마세요.

4. 첫 번째 계획 파일에는 제8교시 Requests 탭의 구현 순서, 예정 파일 경로,
초기 데이터와 서버 측 검증·영속성 처리, AC08-01~AC08-06별 단위·통합·E2E
검증 방법, Playwright 요청 테스트 파일(tests/e2e/requests.spec.cjs)을 포함하세요.

5. 두 번째 계획 파일에는 제9교시 Dashboard 탭의 구현 순서, 예정 파일 경로,
Requests와 공유하는 데이터 소스, 지표·우선순위 분포·빈 상태 처리,
AC09-01~AC09-06별 단위·통합·E2E 검증 방법,
Playwright 테스트 파일(tests/e2e/dashboard.spec.cjs)을 포함하세요.

6. 두 계획 모두 Hermes가 코드 수정과 재시험 반복을 담당하고 Playwright는
테스트 실행만 담당한다는 역할 분리를 명시하세요. 실패 시 로그 분석 → 최소 수정
→ 동일 테스트 재실행 → 증거 기록 순서를 적용하고, 문제당 재시도 최대 3회 및
미해결 시 중단·보고 기준을 적으세요. 미실행 테스트는 NOT_IMPLEMENTED로 표시하세요.

7. 제7교시에서 허용되는 변경은 plans/ 디렉터리와 위 두 계획 파일뿐입니다.
client/, server/, tests/ 내부 파일, package.json, Vite 설정 및 앱 소스를 만들거나
수정하지 마세요. 명세의 인수 기준을 약화하지 마세요. v2와 Reference Project에는
접근하거나 변경하지 마세요.

마지막으로 두 파일의 저장 경로와 저장 성공 여부를 Chat에 간결하게 보고하세요.
```

**저장 파일 확인 — Hermes 실행 완료 후 Windows PowerShell에서 실행**

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $root = 'C:\AI-Native\work-request-manager-v3'
    $plans = @('plans\lesson08-requests-plan.md','plans\lesson09-dashboard-plan.md')
    foreach ($relative in $plans) {
        $path = Join-Path $root $relative
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "계획 파일 누락: $relative" }
        $content = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        if ([string]::IsNullOrWhiteSpace($content) -or $content -notmatch '[가-힣]') { throw "계획 내용 확인 실패: $relative" }
        $prefix = if ($relative -match 'lesson08') { 'AC08' } else { 'AC09' }
        foreach ($n in 1..6) {
            $id = '{0}-{1:D2}' -f $prefix, $n
            if (-not $content.Contains($id)) { throw "인수 기준 누락: $relative / $id" }
        }
        if ($content -notmatch 'client/' -or $content -notmatch 'NOT_IMPLEMENTED') {
            throw "프로젝트 경로 또는 미구현 상태 누락: $relative"
        }
        Write-Host "[PASS] $relative" -ForegroundColor Green
    }
    foreach ($relative in @('client','server','tests')) {
        $files = @(Get-ChildItem -LiteralPath (Join-Path $root $relative) -Recurse -File |
            Where-Object { $_.Name -ne '.gitkeep' })
        if ($files.Count -gt 0) { throw "제7교시 구현 파일 발견: $relative" }
    }
    if (Test-Path -LiteralPath (Join-Path $root 'src')) { throw '루트 src 폴더 생성 금지' }
    Write-Host '[PASS] 제7교시 계획 2개 저장 / 애플리케이션 미구현' -ForegroundColor Green
}
```

**완료 기준:** `plans/` 아래 두 파일이 존재하고 각 교시의 인수 기준 6개가 포함되며, `client/`, `server/`, `tests/`에는 구현 파일이 없어야 합니다. 계획 작성 시점의 테스트 상태는 `NOT_IMPLEMENTED`입니다.

## 문제 해결(교육생용)

| 증상 | 점검 방향 |
|---|---|
| `docker compose` 오류 | Docker Desktop 실행, Linux containers 확인 |
| 9130 또는 5174 충돌 | 현재 포트를 사용하는 프로세스 확인; v2 강제 종료 금지 |
| Dashboard가 열리지 않음 | `docker compose logs --tail 80 hermes`와 컨테이너 상태 확인 |
| Playwright `/health` 실패 | `docker compose logs --tail 80 playwright`, 초기 npm 설치·네트워크 확인 |
| `Cannot find module 'playwright'` | ZIP의 통합 `compose.yaml`에 `NODE_PATH` 포함 여부 확인; v3 Playwright 서비스 재생성 필요 가능 |
| 제7교시 앱 화면 없음 | 정상: 제8교시부터 UI 구현 |
| v3 폴더가 이미 있음 | 신규 설치를 중단하고 강사에게 현재 환경 확인 요청 |

## 제7교시 완료 확인표

| 기준 | 완료 요건 |
|---|---|
| AC07-01 | v3 폴더만 별도 구성, v2/Reference 비변경 |
| AC07-02 | `docker compose config --quiet` 성공, `hermes`/`playwright` 서비스 확인 |
| AC07-03 | `127.0.0.1:9130`에서 `student / via basic`으로 Dashboard 웹 로그인 성공 |
| AC07-04 | Hermes→Playwright `GET /health` → `status=OK` |
| AC07-05 | `POST /run`의 `browser-smoke` → PASS, `exitCode=0`, `timedOut=false`, 종료/완료 마커 |
| AC07-06 | 앱 소스·설정·미리보기 서버가 존재하지 않음 |
| 모델 연결(교육 운영 필수) | `docker compose exec hermes hermes model`로 OpenRouter 모델 설정, Dashboard Chat에서 실제 응답·Terminal 도구 호출 확인 |
| 구현 계획(교육 운영 필수) | `plans/lesson08-requests-plan.md`, `plans/lesson09-dashboard-plan.md` 저장 및 내용 검사, 애플리케이션 미구현 |

> **인수 기준은 실제 실행 출력으로 판정합니다.** Starter에 파일이 있다는 사실만으로 실행 PASS를 주장하지 않습니다. 제8~9교시 테스트는 이 시점에서 `NOT_IMPLEMENTED`입니다. 모델 연결 및 계획 수립은 AC07-01~06을 변경하지 않고 교육 운영 완료 조건으로 별도 확인합니다.

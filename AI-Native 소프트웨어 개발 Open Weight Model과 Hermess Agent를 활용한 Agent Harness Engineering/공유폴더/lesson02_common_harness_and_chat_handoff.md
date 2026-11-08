# 제2교시. 공통 Agent Harness 적용과 Chat 세션 인계

**과정명:** Open Weight Model과 Hermes Agent를 활용한 Agent Harness Engineering  
**프로젝트:** AI Work Request Manager 2.0

## 학습 목표

- 제공된 Starter를 교육생 작업 공간에 적용한다.
- `AGENTS.md`에 정의된 Agent의 작업 범위와 변경 통제 정책을 확인한다.
- 프로젝트 진행 상태(`progress.md`)와 인계 문서(`handoff.md`)를 생성한다.
- 별도의 Hermes Agent Chat에서 작업 상태를 파일 기반으로 복원한다.

이번 실습에서는 애플리케이션 구현 코드를 작성하지 않는다.

## 준비물 및 경로

- Windows 11, PowerShell, Docker Desktop, Hermes Agent
- 제1교시에서 구성한 `C:\AI-Native\hermes-training-v2` (hermes 환결설정 폴더)
- 교육생 작업 공간 `C:\AI-Native\work-request-manager-v2` (작업폴더)
- 제공받은 `lesson02.zip` (기본 다운로드 위치: `$HOME\Downloads`)
- Hermes Dashboard: <http://127.0.0.1:9120/>

> **주의:** 새로 시작하는 경우에는 비어 있는 작업 공간을 사용한다. 기존 작업이 있다면 파일을 삭제하거나 덮어쓰지 않는다. 2-2의 명령으로 최초 설치와 실습 재개를 구분한다.

## 2-1. 개발 환경 및 작업 공간 확인

PowerShell에서 **아래 코드 블록 전체를 한 번에 복사하여 실행**한다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'

    Write-Host '=== Docker Compose ==='
    docker compose ps
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose 상태 확인 실패' }

    Write-Host '=== Hermes Dashboard ==='
    $httpCode = curl.exe --noproxy '*' --silent --show-error `
        --max-time 10 -o NUL -w '%{http_code}' `
        http://127.0.0.1:9120/
    if ($LASTEXITCODE -ne 0) { throw 'Dashboard 연결 실패' }
    Write-Host "Dashboard HTTP: $httpCode"
    if ($httpCode -notin @('200', '302')) {
        throw "예상하지 못한 Dashboard HTTP 상태: $httpCode"
    }

    Write-Host '=== Playwright Health ==='
    $health = docker compose exec -T hermes `
        curl --silent --show-error --max-time 10 `
        http://playwright:3000/health
    if ($LASTEXITCODE -ne 0) { throw 'Playwright 상태 확인 실패' }
    Write-Host $health
    if ($health -notmatch '"status"\s*:\s*"ok"') {
        throw 'Playwright Health가 정상 상태가 아닙니다.'
    }

    Write-Host '=== Workspace ==='
    docker compose exec -T hermes sh -lc 'ls -la /workspace'
    if ($LASTEXITCODE -ne 0) { throw '/workspace 접근 실패' }

    Write-Host 'Environment Check: PASS'
}
```

**정상 확인:** 마지막에 `Environment Check: PASS`가 출력된다. Docker Compose에서 `hermes`와 `playwright` 서비스가 실행 중이며, Dashboard는 정상적인 접속 또는 인증 전환 응답(예: HTTP 302)을 반환한다. Playwright 응답에는 `"status":"ok"`가 포함되고 `/workspace`에 접근할 수 있어야 한다.

## 2-2. Starter ZIP 적용 또는 기존 실습 재개

`lesson02.zip`에는 `AGENTS.md`, `docs/project-overview.md`, `scripts/verify-handoff.py`가 포함되어 있다. 다음 명령은 **최초 설치와 실습 재개를 자동으로 구분**한다.

- **최초 설치:** 지정된 파일이 모두 없으면 ZIP 구성과 파일 경로를 검사한 뒤 압축을 해제한다.
- **실습 재개:** 지정된 파일이 모두 존재하고 배포 ZIP 내부 파일과 내용이 같으면 압축을 해제하지 않고 다음 단계로 진행한다. 생성한 `progress.md`와 `handoff.md`도 유지한다.
- **일부 파일만 존재하거나 배포본과 내용이 다름:** 기존 파일을 수정하지 않고 중단한다. 강사에게 확인한다.

PowerShell에서 **아래 코드 블록 전체를 한 번에 복사하여 실행**한다. 블록 첫 줄의 `& {`부터 마지막 줄의 `}`까지 한 번의 명령으로 처리된다. 코드 일부만 나누어 실행하지 않는다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $zipPath = Join-Path $HOME 'Downloads\lesson02.zip'
    $targetPath = 'C:\AI-Native\work-request-manager-v2'
    $expected = @(
        'AGENTS.md',
        'docs/project-overview.md',
        'scripts/verify-handoff.py'
    )

    if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) {
        throw "ZIP 파일을 찾을 수 없습니다: $zipPath"
    }

    Add-Type -AssemblyName System.IO.Compression
    $archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    $mode = $null

    try {
        $entries = @($archive.Entries | Where-Object { $_.Name })
        $names = @($entries | ForEach-Object { $_.FullName.Replace('\', '/') })

        if ($names.Count -ne $expected.Count -or
            @($names | Where-Object { $_ -notin $expected }).Count -ne 0 -or
            @($expected | Where-Object { $_ -notin $names }).Count -ne 0) {
            throw 'Starter ZIP 파일 구성이 예상과 다릅니다.'
        }
        Write-Host 'ZIP Validation: PASS'

        $present = @($expected | Where-Object {
            Test-Path -LiteralPath (Join-Path $targetPath $_) -PathType Leaf
        })

        if ($present.Count -eq 0) {
            $mode = 'INSTALL'
        }
        elseif ($present.Count -eq $expected.Count) {
            foreach ($entry in $entries) {
                $relative = $entry.FullName.Replace('\', '/')
                $local = Join-Path $targetPath $relative
                $localHash = (Get-FileHash -LiteralPath $local -Algorithm SHA256).Hash
                $stream = $entry.Open()
                try {
                    $sha = [System.Security.Cryptography.SHA256]::Create()
                    try {
                        $zipHash = [System.BitConverter]::ToString(
                            $sha.ComputeHash($stream)
                        ).Replace('-', '')
                    }
                    finally { $sha.Dispose() }
                }
                finally { $stream.Dispose() }

                if ($localHash -ne $zipHash) {
                    throw "기존 파일과 배포본의 내용이 다릅니다: $relative"
                }
            }
            $mode = 'RESUME'
        }
        else {
            throw 'Starter 파일이 일부만 존재합니다. 삭제하거나 덮어쓰지 마세요.'
        }
    }
    finally {
        $archive.Dispose()
    }

    switch ($mode) {
        'INSTALL' {
            if (-not (Test-Path -LiteralPath $targetPath)) {
                New-Item -ItemType Directory -Path $targetPath | Out-Null
            }
            Expand-Archive -LiteralPath $zipPath -DestinationPath $targetPath -ErrorAction Stop
            Write-Host 'Starter Mode: INSTALL'
            break
        }
        'RESUME' {
            Write-Host 'Starter Mode: RESUME (압축 해제 생략)'
            break
        }
        default {
            throw "알 수 없는 Starter Mode: $mode"
        }
    }

    foreach ($name in $expected) {
        $exists = Test-Path -LiteralPath (Join-Path $targetPath $name) -PathType Leaf
        [PSCustomObject]@{ File = $name; Exists = $exists }
        if (-not $exists) {
            throw "필수 파일이 없습니다: $name"
        }
    }
    Write-Host 'Starter Check: PASS'
}
```

**정상 확인:** `ZIP Validation: PASS`와 `Starter Mode: INSTALL` 또는 `Starter Mode: RESUME`가 표시되고, 세 파일의 `Exists`가 모두 `True`이다. `RESUME`인 경우 기존 인계 문서와 작업 결과는 보존된다. 마지막에 `Starter Check: PASS`도 표시된다.

> **주의:** 오류 메시지가 출력되면 `Expand-Archive`를 따로 실행하지 않는다. `-Force`로 기존 고정 파일을 덮어쓰거나 `progress.md`, `handoff.md`를 삭제하지 않는다. 이미 제2교시를 마쳤다면 2-3~2-5의 생성 작업을 반복하지 않고, 2-6의 구조 검사 또는 다음 실습으로 넘어갈 수 있다.

## 2-3. 새 Hermes Agent Chat에서 공통 Harness 읽기

Hermes Dashboard(<http://127.0.0.1:9120/>)에 접속하여 **New Chat**을 만든다. 모델은 강사가 지정한 OpenRouter 모델을 선택한다.

아래 내용을 Chat에 입력한다.

```text
AI Work Request Manager 2.0 프로젝트의 작업을 시작한다.

작업 공간은 /workspace이다.

실제 파일 읽기 도구를 이용해 다음 두 파일을 순서대로 읽어줘.
1. /workspace/AGENTS.md
2. /workspace/docs/project-overview.md

작업 지시:
- 공통 Harness의 수정 허용 영역과 수정 금지 영역을 구분한다.
- 테스트 기반 Closed-loop 개선 규칙과 최대 반복 횟수를 확인한다.
- 프로젝트의 목적, 핵심 기능, 제외 범위를 요약한다.
- 두 파일의 내용이 충돌하는지 확인한다.
- 결과를 PASS/FAIL 표로 보고한다.

제약 조건:
- 파일을 생성, 수정, 삭제하지 않는다.
- /reference에 접근하지 않는다.
- Docker 명령을 사용하지 않는다.
- 실제로 확인하지 않은 내용을 PASS로 보고하지 않는다.
- 확인 결과만 보고하고 다음 지시를 기다린다.
```

**정상 확인:** Agent가 실제 파일 읽기 도구를 사용하고, `client/`, `server/`, `plans/`, `progress.md`, `handoff.md`의 조건부 수정 허용과 `docs/`, `specs/`, `contracts/`, `schemas/`, `design/`, `traceability/`, `tests/`, `e2e/`, `scripts/`의 수정 금지를 구분한다. 최초 테스트 후 자동 수정·재검증 최대 3회 규칙을 보고한다.

## 2-4. 변경 통제 정책 확인

같은 Chat에 다음 프롬프트를 입력한다.

```text
AI Work Request Manager 2.0의 Agent Harness 변경 통제 정책을 점검해줘.

다음 세 가지 가상 작업 요청을 AGENTS.md에 따라 판정한다.

A. 승인된 구현 범위 내에서 client/src/main.tsx 파일의 코드를 수정한다.
B. 고정 테스트가 실패했다는 이유로 tests/api.test.js의 기대값을 변경한다.
C. 명세에 없는 로그인 기능을 추가하고 인증 라이브러리를 설치한다.

각 요청에 대해 다음을 보고해줘.
1. 허용 / 금지 / 사전 승인 필요 중 하나로 판정
2. AGENTS.md의 해당 절과 근거
3. 실제로 수행할 수 있는 다음 행동

제약:
- 가상 시나리오에 대한 판단만 수행한다.
- 파일을 생성, 수정, 삭제하지 않는다.
- Docker 명령을 실행하지 않는다.
- /reference에 접근하지 않는다.
- 실제 작업을 수행하지 않는다.
- 결과를 표로 정리하고 다음 지시를 기다린다.
```

**정상 확인:** A는 승인된 범위 내에서 허용, B는 고정 테스트 변경이므로 금지, C는 제품 제외 범위에 충돌하므로 구현 중단 및 보고로 판단해야 한다. 이 단계에서 실제 코드를 수정해서는 안 된다.

## 2-5. 진행 상태 및 인계 문서 작성

같은 Chat에서 다음 프롬프트를 실행한다.

```text
AI Work Request Manager 2.0의 프로젝트 진행 상태와 다음 Chat 인계 문서를 작성해줘.

작업 공간: /workspace
먼저 AGENTS.md와 docs/project-overview.md를 읽어 현재 상태를 확인한다.

다음 두 파일만 생성한다.
1. /workspace/progress.md
2. /workspace/handoff.md

progress.md에는 아래 제목을 정확히 사용한다.
# 프로젝트 진행 상태
## 현재 단계
## 완료된 작업
## 검증 결과
## 미해결 문제
## 다음 작업

handoff.md에는 아래 제목을 정확히 사용한다.
# Chat 인계 문서
## 프로젝트 상태
## 완료된 작업
## 검증 결과
## 미해결 문제
## 다음 작업
## 다음 Chat에서 읽을 파일

기록할 사실:
- 개발 환경 구축 및 브라우저 Smoke Test 완료
- Starter에서 AGENTS.md와 프로젝트 개요 적용 완료
- 새 Chat에서 공통 Harness 규칙 로드 완료
- 변경 통제 가상 시나리오 A, B, C 판정 완료
- 애플리케이션 구현은 시작하지 않음
- 요구사항·상세 명세·UI 계약은 다음 실습에서 배치 및 확인 예정
- 현재 확인된 미해결 문제는 없음. 미검증 항목은 완료로 보고하지 않음

다음 작업은 고정 요구사항, 상세 명세, API·데이터 계약, 와이어프레임, 디자인 토큰을 읽고 인수 기준을 확인하는 것이다.

제약 조건:
- 위 두 파일 외 생성·수정·삭제 금지
- AGENTS.md와 docs/project-overview.md 수정 금지
- /reference 접근 금지, Docker 명령 금지
- 존재하지 않는 파일을 읽었다고 보고하지 않는다
- 빈 템플릿 문구를 남기지 않는다
- 두 파일 작성 후 실제로 다시 읽고 파일 경로와 필수 제목을 보고한다.
```

**정상 확인:** 두 파일이 생성되고 필수 제목이 모두 포함된다. 구현은 시작하지 않았다는 사실과 다음 실습에서 읽을 자산이 명확히 구분되어야 한다.

## 2-6. 인계 문서 구조 검사

배포된 `scripts/verify-handoff.py`를 Hermes 컨테이너의 Python으로 실행한다. Windows에 Python을 별도로 설치할 필요는 없다.

PowerShell에서 **아래 코드 블록 전체를 한 번에 복사하여 실행**한다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'

    $script = 'C:\AI-Native\work-request-manager-v2\scripts\verify-handoff.py'
    if (-not (Test-Path -LiteralPath $script -PathType Leaf)) {
        throw "검증 스크립트를 찾을 수 없습니다: $script"
    }

    Get-Content -Raw -Encoding UTF8 -LiteralPath $script |
        docker compose exec -T hermes python3 - --root /workspace

    $exitCode = $LASTEXITCODE
    Write-Host "Validation Exit Code: $exitCode"
    if ($exitCode -ne 0) {
        throw "인계 문서 검증 실패: 종료 코드 $exitCode"
    }
    Write-Host 'Handoff Check: PASS'
}
```

**정상 확인:** 아래 문구와 종료 코드 `0`이 출력된다.

```text
Handoff structure: PASS
Validation Exit Code: 0
Handoff Check: PASS
```

이 검사는 `progress.md`와 `handoff.md`의 필수 구조를 확인한다. 새 Chat에서 실제로 상태를 복원할 수 있는지는 다음 단계에서 확인한다.

## 2-7. 새 Chat에서 상태 복원

Hermes Dashboard에서 **새로운 Chat**을 만든다. 이전 Chat 내용을 복사하지 않는다.

```text
AI Work Request Manager 2.0 프로젝트를 이전 Chat에서 인계받는다.

작업 공간: /workspace

이전 Chat의 대화 내용을 알고 있다고 가정하지 말고, 실제 파일 읽기 도구로 다음 파일을 읽어줘.
1. /workspace/AGENTS.md
2. /workspace/docs/project-overview.md
3. /workspace/progress.md
4. /workspace/handoff.md

읽은 내용을 근거로 다음을 보고해줘.
- 현재 프로젝트 단계
- 완료된 작업
- 확인된 검증 결과
- 아직 수행하지 않은 작업
- 다음 작업과 필요한 고정 자산
- AGENTS.md의 변경 통제 규칙 및 Closed-loop 반복 상한

파일 내용을 읽지 못한 경우 추측하지 말고 실패로 보고한다.
이번 요청에서는 파일을 생성, 수정, 삭제하지 않는다.
Docker 명령과 /reference 접근은 금지한다.
마지막에 '인계 복원: PASS 또는 FAIL'을 근거와 함께 표시하고 다음 지시를 기다려줘.
```

**정상 확인:** 새 Chat에서 네 파일을 실제로 읽어 `인계 복원: PASS`를 보고하고, 현재 단계가 구현 전이며 다음 작업이 고정 명세와 인수 기준 확인이라는 사실을 복원한다.

## 문제 해결

| 증상 | 점검 방법 |
|---|---|
| `lesson02.zip`을 찾지 못함 | 실제 다운로드 위치를 확인하고 `$zipPath`를 수정한다. |
| `Starter Mode: RESUME` 출력 | 이미 Starter를 설치한 상태이다. 압축을 다시 풀지 않는다. 작성해 둔 인계 문서를 유지하고 필요한 검증 단계로 진행한다. |
| Starter 파일 일부 존재 또는 해시 불일치 | 기존 파일을 삭제·덮어쓰기하지 말고 강사에게 확인한다. 오류 후 `Expand-Archive`를 따로 실행하지 않는다. |
| Hermes Dashboard 접속 불가 | `C:\AI-Native\hermes-training-v2`에서 `docker compose ps`로 상태를 확인한다. |
| `/workspace`에서 파일을 찾지 못함 | Windows 작업 공간과 Docker bind mount 연결을 확인한다. |
| Agent가 문서를 수정하려 함 | 해당 요청을 중단하고 `AGENTS.md`의 변경 통제 규칙을 다시 읽도록 한다. |
| 인계 문서 검증이 실패 | 오류 내용을 확인하고 `progress.md` 또는 `handoff.md`의 내용과 제목을 점검한다. 검증 스크립트는 수정하지 않는다. |
| 새 Chat에서 인계 복원 실패 | 네 파일을 실제 읽었는지, 인계 문서의 다음 작업 기록이 있는지 확인한다. |

## 완료 확인

- [ ] Starter의 고정 문서 2개와 `scripts/verify-handoff.py`가 작업 공간에 배치되어 있다 (`INSTALL` 또는 `RESUME`).
- [ ] Hermes Agent가 고정 문서를 읽고 변경 통제 정책을 설명했다.
- [ ] 허용·금지·범위 충돌 사례를 정확히 판정했다.
- [ ] `progress.md`와 `handoff.md`를 생성했다.
- [ ] 두 문서의 필수 제목 확인을 통과했다.
- [ ] 새로운 Chat에서 파일 기반 작업 상태 복원에 성공했다.

**다음 작업:** 요구사항, 상세 명세, 인수 기준, API·데이터 계약, UI 설계 자료를 추가하고 이를 읽어 작업 범위를 확인한다.

**완료 확인:** 인계 구조 검사 `Handoff structure: PASS`, 새 Chat의 `인계 복원: PASS`를 확인한다.

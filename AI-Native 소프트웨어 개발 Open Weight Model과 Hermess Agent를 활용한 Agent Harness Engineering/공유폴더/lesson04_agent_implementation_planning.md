# 제4교시. Agent 구현 계획 수립과 작업 분해

**과정명:** Open Weight Model과 Hermes Agent를 활용한 Agent Harness Engineering  
**실습 프로젝트:** AI Work Request Manager 2.0

## 학습 목표

- 이전 Chat의 작업 상태를 인계 문서에서 복원한다.
- 고정 요구사항과 인수 기준에 근거하여 구현 작업을 분해한다.
- 구현 기준을 검토·승인하고 구현 계획과 검증 계획을 분리해 작성한다.
- 계획 문서의 필수 구조를 자동 검사하고 다음 Chat으로 인계한다.

이번 실습에서는 **애플리케이션 구현 코드를 작성하지 않는다.** `AGENTS.md`와 고정 Baseline, 프로젝트 설정 파일은 변경하지 않는다.

## 준비물 및 경로

- Hermes Agent Dashboard: <http://127.0.0.1:9120/>
- Docker Compose: `C:\AI-Native\hermes-training-v2`
- 교육생 프로젝트: `C:\AI-Native\work-request-manager-v2` (Hermes 컨테이너 내부 `/workspace`)
- 배포 파일: `lesson04.zip` (배포 폴더 또는 Downloads)
- Hermes Agent 모델: `z-ai/glm-5.3-flash`, Reasoning `medium`

PowerShell 명령은 **각 코드 블록의 `& {`부터 마지막 `}`까지 통째로 복사해 실행**한다. 이전 교시의 `progress.md`·`handoff.md`는 삭제하지 않는다.

## 4-1. Starter와 이전 작업 상태 확인

아래 코드는 파일을 변경하지 않고 이전 교시 필수 파일과 새 Starter 파일 구성을 확인한다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $targetPath = 'C:\AI-Native\work-request-manager-v2'
    $distributionZip = 'C:\AI-Native\work-request-manager-distribution\lesson04.zip'
    $downloadZip = Join-Path $HOME 'Downloads\lesson04.zip'

    Write-Host '=== Lesson 04 Starter Precheck ==='
    if (Test-Path -LiteralPath $distributionZip -PathType Leaf) {
        $zipPath = $distributionZip
    }
    elseif (Test-Path -LiteralPath $downloadZip -PathType Leaf) {
        $zipPath = $downloadZip
    }
    else { throw 'lesson04.zip 파일을 찾을 수 없습니다.' }

    if (-not (Test-Path -LiteralPath $targetPath -PathType Container)) {
        throw "작업 공간이 없습니다: $targetPath"
    }
    Write-Host "ZIP: $zipPath"

    $required = @(
        'AGENTS.md',
        'docs/project-overview.md',
        'specs/requirements.md',
        'docs/specification.md',
        'specs/acceptance-criteria.md',
        'contracts/openapi.json',
        'schemas/request.schema.json',
        'design/wireframes.md',
        'design/tokens.json',
        'scripts/verify-handoff.py',
        'progress.md',
        'handoff.md'
    )
    foreach ($name in $required) {
        if (-not (Test-Path -LiteralPath (Join-Path $targetPath $name) -PathType Leaf)) {
            throw "이전 교시 필수 파일이 없습니다: $name"
        }
    }
    Write-Host "Previous Lesson Files: PASS ($($required.Count) files)"

    Add-Type -AssemblyName System.IO.Compression
    $archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        $entries = @($archive.Entries | Where-Object { $_.Name })
        if ($entries.Count -eq 0) { throw 'ZIP 내부에 파일이 없습니다.' }
        $names = @($entries | ForEach-Object { $_.FullName.Replace('\', '/') })
        if (@($names | Select-Object -Unique).Count -ne $names.Count) {
            throw 'ZIP 내부에 중복 파일 경로가 있습니다.'
        }
        $results = @(
            foreach ($entry in $entries) {
                $relative = $entry.FullName.Replace('\', '/')
                if ($relative.StartsWith('/') -or
                    $relative -match '(^|/)\.\.?(/|$)' -or
                    $relative -match '^[A-Za-z]:' -or
                    $relative.Contains(':')) {
                    throw "허용되지 않는 ZIP 경로: $relative"
                }
                [PSCustomObject]@{
                    File = $relative
                    Size = $entry.Length
                    AlreadyExists = Test-Path -LiteralPath (Join-Path $targetPath $relative)
                }
            }
        )
        $results | Format-Table -AutoSize
        Write-Host "ZIP File Count: $($entries.Count)"
        Write-Host "Existing File Count: $(@($results | Where-Object AlreadyExists).Count)"
    }
    finally { $archive.Dispose() }
    Write-Host 'Lesson 04 Precheck: PASS'
}
```

**정상 확인:** `Previous Lesson Files: PASS (12 files)`, `ZIP File Count: 8`, `Lesson 04 Precheck: PASS`. ZIP 구성은 `.gitignore`, `index.html`, `package-lock.json`, `package.json`, `playwright.config.js`, `tsconfig.json`, `vite.config.js`, `vite.e2e.config.js`이다.

## 4-2. Starter 설치 또는 안전한 재개

새 설정 파일 8개를 기존 프로젝트에 추가한다. 이미 배치된 파일이 있으면 배포 ZIP과 **SHA-256을 비교**해 같은 경우에만 압축 해제를 생략한다. 일부만 배치되었거나 내용이 다르면 변경하지 않고 중단한다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $targetPath = 'C:\AI-Native\work-request-manager-v2'
    $distributionZip = 'C:\AI-Native\work-request-manager-distribution\lesson04.zip'
    $downloadZip = Join-Path $HOME 'Downloads\lesson04.zip'
    $expected = @(
        '.gitignore', 'index.html', 'package-lock.json', 'package.json',
        'playwright.config.js', 'tsconfig.json', 'vite.config.js',
        'vite.e2e.config.js'
    )
    Write-Host '=== Lesson 04 Starter ==='
    if (Test-Path -LiteralPath $distributionZip -PathType Leaf) {
        $zipPath = $distributionZip
    }
    elseif (Test-Path -LiteralPath $downloadZip -PathType Leaf) {
        $zipPath = $downloadZip
    }
    else { throw 'lesson04.zip 파일을 찾을 수 없습니다.' }
    if (-not (Test-Path -LiteralPath $targetPath -PathType Container)) {
        throw "작업 공간이 없습니다: $targetPath"
    }

    Add-Type -AssemblyName System.IO.Compression
    $archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        $entries = @($archive.Entries | Where-Object { $_.Name })
        $names = @($entries | ForEach-Object { $_.FullName.Replace('\', '/') })
        if ($names.Count -ne $expected.Count -or
            @($names | Where-Object { $_ -notin $expected }).Count -gt 0 -or
            @($expected | Where-Object { $_ -notin $names }).Count -gt 0) {
            throw '제4교시 ZIP 파일 구성이 예상과 다릅니다.'
        }
        Write-Host 'ZIP Validation: PASS'

        $present = @($expected | Where-Object {
            Test-Path -LiteralPath (Join-Path $targetPath $_)
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
                    throw "기존 파일과 배포본이 다릅니다: $relative"
                }
            }
            $mode = 'RESUME'
        }
        else { throw 'Starter 파일이 일부만 존재합니다. 삭제하거나 덮어쓰지 마세요.' }
    }
    finally { $archive.Dispose() }

    switch ($mode) {
        'INSTALL' {
            Expand-Archive -LiteralPath $zipPath -DestinationPath $targetPath -ErrorAction Stop
            Write-Host 'Starter Mode: INSTALL'
            break
        }
        'RESUME' {
            Write-Host 'Starter Mode: RESUME (압축 해제 생략)'
            break
        }
        default { throw "알 수 없는 Starter Mode: $mode" }
    }

    $results = @(
        foreach ($name in $expected) {
            $exists = Test-Path -LiteralPath (Join-Path $targetPath $name) -PathType Leaf
            if (-not $exists) { throw "필수 파일이 없습니다: $name" }
            [PSCustomObject]@{ File = $name; Exists = $exists }
        }
    )
    $results | Format-Table -AutoSize
    Write-Host 'Lesson 04 Starter: PASS'
}
```

**정상 확인:** 최초 적용은 `Starter Mode: INSTALL`, 재실행은 `Starter Mode: RESUME (압축 해제 생략)`을 출력한다. 두 경우 모두 `Lesson 04 Starter: PASS`가 출력되어야 한다.

## 4-3. 새로운 Hermes Agent Chat에서 Planning 상태 복원

Dashboard에서 **New Chat**을 생성하고 아래 프롬프트를 전체 복사해 입력한다.

```text
AI Work Request Manager 2.0 프로젝트의 구현 계획 수립 작업을 시작한다.

작업 공간: /workspace
이전 Chat의 내용을 기억한다고 가정하지 않는다.

실제 파일 읽기 도구를 사용해 다음 파일을 순서대로 읽어줘.
1. /workspace/AGENTS.md
2. /workspace/docs/project-overview.md
3. /workspace/progress.md
4. /workspace/handoff.md
5. /workspace/specs/requirements.md
6. /workspace/docs/specification.md
7. /workspace/specs/acceptance-criteria.md
8. /workspace/package.json
9. /workspace/tsconfig.json
10. /workspace/vite.config.js
11. /workspace/playwright.config.js

수행할 작업:
- 이전 교시까지 완료된 작업과 현재 프로젝트 단계를 복원한다.
- AGENTS.md의 Specification → Planning → Implementation → Verification → Handoff 순서를 확인한다.
- 수정 금지 Baseline과 구현·계획 파일의 수정 허용 범위를 구분한다.
- 프로젝트 설정의 실행·빌드·테스트 명령을 확인한다.
- 계획 작성 전에 검토해야 할 명세 해석 사항 3건을 확인한다.

제약:
- 파일 생성·수정·삭제 금지
- Docker 명령 실행 금지
- /reference 접근 금지
- 미해결 사항을 임의 확정하지 않는다.

파일별 읽기 결과, 현재 단계, 계획 준비 상태를 보고하고 다음 지시를 기다려줘.
```

**정상 확인:** 11개 파일을 읽고, 현재 단계가 Planning 착수 단계임을 보고한다. `tests/`, `e2e/` 파일은 아직 제공되지 않았으므로 실행했다고 보고하지 않는다.

## 4-4. 명세 해석 사항 검토

현재 Chat에서 아래 프롬프트를 입력한다. 여기서는 후보를 검토할 뿐 확정하지 않는다.

```text
AI Work Request Manager 2.0의 Planning에 앞서 명세 해석 사항 3건을 검토해줘.

다음은 사용자 검토 대상인 구현 기준 후보이며 아직 확정되지 않았다.
1. GET /api/requests의 total은 상태·우선순위 필터 적용 후 반환되는 항목 수로 정의한다.
2. 키보드 포커스는 기존 primary 토큰과 브라우저 기본 포커스 동작을 활용하며 고정 토큰 파일은 수정하지 않는다.
3. 잘못된 UUID 형식의 요청 ID는 HTTP 400 VALIDATION_ERROR, 유효하지만 존재하지 않는 ID는 HTTP 404 NOT_FOUND로 처리한다.

실제 고정 요구사항·상세 명세·인수 기준·OpenAPI 계약·데이터 스키마·와이어프레임·디자인 토큰을 필요한 만큼 다시 읽는다.

각 후보에 대해 다음을 표로 보고한다.
1. 관련 고정 문서와 근거
2. 문서 간 충돌 여부
3. AGENTS.md §7의 별도 변경 승인 대상인지
4. 구현 파일 수정만으로 적용 가능한지
5. 권장 또는 추가 확인 필요 판정

제약:
- 사용자 승인 전 확정하지 않는다.
- 파일 생성·수정·삭제, 구현 계획 작성, 구현 코드 작성 금지
- Docker 명령 및 /reference 접근 금지

최종적으로 사용자 결정이 필요한 사항을 보고하고 다음 지시를 기다려줘.
```

**정상 확인:** 세 후보의 계약 일치 여부와 승인 필요 여부를 설명한다. 고정 테스트가 아직 배치되지 않았다면 기대값을 추측해 확정하지 않는다.

## 4-5. 구현 기준 확정

검토 결과를 확인한 후 세 후보를 채택할 경우, **같은 Chat**에서 다음 프롬프트를 입력한다.

```text
앞서 검토한 구현 기준 A·B·C를 모두 채택한다.

1. GET /api/requests의 total은 필터 적용 후 반환되는 항목 수(items.length)로 계산한다.
2. 키보드 포커스는 기존 primary 디자인 토큰과 브라우저 기본 포커스 동작을 활용하며, 디자인 토큰 파일은 변경하지 않는다.
3. 잘못된 UUID 형식의 요청 ID는 HTTP 400 VALIDATION_ERROR, 형식은 올바르지만 존재하지 않는 ID는 HTTP 404 NOT_FOUND로 처리한다.

이는 구현 기준의 확정이며 고정 Baseline 파일 변경 승인이 아니다.

작업 지시:
1. 확정된 세 기준과 관련 REQ/API/UI 영향 범위를 표로 정리한다.
2. 고정 테스트가 배치되면 A·C의 기대값과 교차 확인할 필요가 있음을 명시한다.
3. 테스트와 충돌 시 임의 수정하지 말고 보고한다.

제약:
- 파일 생성·수정·삭제 금지
- 구현 계획 및 애플리케이션 코드 작성 금지
- Docker 명령 및 /reference 접근 금지

확정 내용만 보고하고 다음 지시를 기다려줘.
```

**정상 확인:** A·B·C를 구현 기준으로 정리한다. 고정 명세와 계약 파일을 수정하지 않는다.

## 4-6. 구현 계획과 검증 계획 생성

같은 Chat에서 다음 프롬프트를 입력해 **`plans/` 아래 두 파일만** 생성한다.

```text
AI Work Request Manager 2.0의 구현 계획과 검증 계획을 작성해줘.

작업 공간: /workspace
AGENTS.md의 Planning 규칙을 따르고, 사용자가 승인한 A·B·C 구현 기준을 반영한다.
1. total = 필터 적용 후 items.length
2. 기존 primary 토큰 + 브라우저 기본 포커스, 토큰 파일 무수정
3. 잘못된 UUID = 400 VALIDATION_ERROR, 형식 유효·미존재 UUID = 404 NOT_FOUND

먼저 아래 실제 파일을 읽어 계획의 근거를 확인한다.
AGENTS.md, docs/project-overview.md, specs/requirements.md,
docs/specification.md, specs/acceptance-criteria.md,
contracts/openapi.json, schemas/request.schema.json,
design/wireframes.md, design/tokens.json,
package.json, tsconfig.json, vite.config.js, playwright.config.js

오직 다음 두 파일만 작성한다.
1. /workspace/plans/implementation-plan.md
2. /workspace/plans/verification-plan.md

implementation-plan.md에 포함할 내용:
- 목표·구현 범위·제외 기능
- 수정 금지 영역과 구현 허용 영역
- REQ-001~REQ-008별 작업 분해와 대응 AC
- server/ 검증·오류 처리·저장소·라우트·시작 파일의 구현 순서
- client/ 공통 기반·목록·등록·상세/수정·접근성 구현 순서
- 예정 파일별 책임과 작업 의존성
- 완료 조건, 승인된 A·B·C 기준, 다음 구현 우선순위

verification-plan.md에 포함할 내용:
- AC-001~AC-014별 검증 대상과 방법
- 검증 순서: TypeScript 정적 검사 → 빌드 → API 테스트 → 영속성 검사 → Playwright E2E → 결과 보고
- package.json에 실제 있는 명령과 추후 제공될 테스트 자산 구분
- 아직 없는 tests/와 e2e/는 미제공·미실행으로 명시
- 고정 테스트 수정 금지, 로그 근거 기록
- 최초 검증 이후 자동 수정·재검증 최대 3회
- 고정 테스트 배치 후 A·C 구현 기준의 기대값 비교

제약:
- 위 plans/ 두 파일만 생성 또는 수정
- client/, server/ 코드 생성 금지
- 고정 Baseline, package.json, 설정 파일 수정 금지
- Docker 명령 실행 및 /reference 접근 금지
- 존재하지 않는 테스트의 실행 결과를 주장하지 않는다.

두 파일 작성 후 다시 읽어 필수 항목과 REQ 8개·AC 14개 포함 여부를 확인하고 결과만 보고해줘.
```

**정상 확인:** `plans/implementation-plan.md`, `plans/verification-plan.md`가 생성되고, 요구사항 8개·인수 기준 14개 및 Closed-loop 최대 3회 규칙이 기록된다. 테스트 파일이 없을 때는 미실행으로 구분한다.

## 4-7. 계획 문서 자동 검사

PowerShell에서 다음 블록 전체를 실행한다. **필수 파일, ID, 주요 규칙 존재 여부만 검사**하며 문서의 모든 의미적 정확성을 보증하지는 않는다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    Write-Host '=== Lesson 04 Planning Validation ==='

    $pythonCode = @'
from pathlib import Path
import re
import sys

root = Path("/workspace/plans")
implementation = root / "implementation-plan.md"
verification = root / "verification-plan.md"

try:
    for path in (implementation, verification):
        if not path.is_file():
            raise ValueError(f"Missing file: {path}")
        if not path.read_text(encoding="utf-8-sig").strip():
            raise ValueError(f"Empty file: {path}")
        print(f"{path.name}: PASS")

    impl = implementation.read_text(encoding="utf-8-sig")
    ver = verification.read_text(encoding="utf-8-sig")
    expected_req = {f"REQ-{i:03d}" for i in range(1, 9)}
    expected_ac = {f"AC-{i:03d}" for i in range(1, 15)}
    missing_req = expected_req - set(re.findall(r"REQ-\d{3}", impl))
    missing_ac = expected_ac - set(re.findall(r"AC-\d{3}", ver))
    if missing_req:
        raise ValueError(f"Missing REQ: {sorted(missing_req)}")
    if missing_ac:
        raise ValueError(f"Missing AC: {sorted(missing_ac)}")
    print("REQ-001~008 Coverage: PASS")
    print("AC-001~014 Coverage: PASS")

    for term in ("Planning", "Implementation", "Verification"):
        if term not in impl + ver:
            raise ValueError(f"Missing lifecycle term: {term}")
    for term in ("VALIDATION_ERROR", "NOT_FOUND"):
        if term not in impl:
            raise ValueError(f"Missing approved rule: {term}")
    if "3회" not in ver:
        raise ValueError("Missing Closed-loop retry limit")
    print("Planning Rules: PASS")
    print("Lesson 04 Planning Check: PASS")
except (OSError, ValueError) as exc:
    print(f"Lesson 04 Planning Check: FAIL - {exc}", file=sys.stderr)
    sys.exit(1)
'@

    $pythonCode | docker compose exec -T hermes python3 -
    $exitCode = $LASTEXITCODE
    Write-Host "Validation Exit Code: $exitCode"
    if ($exitCode -ne 0) { throw '제4교시 계획 문서 검증 실패' }
}
```

**정상 확인:** `REQ-001~008 Coverage: PASS`, `AC-001~014 Coverage: PASS`, `Lesson 04 Planning Check: PASS`, `Validation Exit Code: 0`.

## 4-8. Planning 완료 및 Chat 인계 갱신

현재 Chat에서 다음 프롬프트를 입력한다. `plans/`의 두 계획 파일은 변경하지 않는다.

```text
AI Work Request Manager 2.0 프로젝트의 Planning 결과를 기록하고 다음 Chat으로 인계해줘.

작업 공간: /workspace
먼저 다음 파일을 실제로 읽는다.
1. /workspace/AGENTS.md
2. /workspace/plans/implementation-plan.md
3. /workspace/plans/verification-plan.md
4. /workspace/progress.md
5. /workspace/handoff.md

기존 기록을 보존하면서 다음 두 파일만 갱신한다.
- /workspace/progress.md
- /workspace/handoff.md

progress.md에 반영할 항목:
- 현재 단계: Planning 완료, Implementation 착수 전
- 이전 교시의 완료 기록 보존
- 제4교시 Starter 8개 파일 적용
- 구현 계획과 검증 계획 작성 완료
- REQ-001~008 및 AC-001~014 포함 확인
- 사용자 승인 구현 기준 A·B·C와 변경 금지 Baseline 구분
- 사용자 제공 PowerShell 실행 결과: Lesson 04 Planning Check: PASS, 종료 코드 0
- tests/와 e2e/ 미배치·미실행, 애플리케이션 구현·테스트 미시작
- 다음 작업: 등록·목록·상세 기능 구현 전 고정 테스트 배치·확인

handoff.md에 반영할 항목:
- 제1~4교시 완료 상태와 Planning 완료 사실
- /workspace/plans/implementation-plan.md 및 verification-plan.md의 경로와 역할
- A. total = 필터 후 items.length
- B. 기존 primary 토큰 + 기본 포커스, 디자인 토큰 무수정
- C. 잘못된 UUID는 400 VALIDATION_ERROR, 유효·미존재 UUID는 404 NOT_FOUND
- 검증 계획은 작성했지만 애플리케이션 테스트는 실행하지 않았다는 사실
- 다음 Chat 필수 읽기 파일: AGENTS.md, 프로젝트 개요, 요구사항, 상세 명세, 두 계획 파일, progress.md, handoff.md

기록 원칙:
- 위 PASS는 사용자 PowerShell 로그를 근거로 기록하고 Hermes가 직접 실행했다고 쓰지 않는다.
- 계획의 필수 ID·문구 검사가 구현 성공을 보증한다고 쓰지 않는다.
- 과거 미해결 3건은 구현 기준 승인으로 해소되었음을 분명히 표시한다.
- 기존 기록은 보존한다.
- Self-improvement Skill 메시지를 필수 검증 조건으로 취급하지 않는다.

제약:
- progress.md와 handoff.md 외 수정 금지
- 계획 파일·고정 Baseline·설정 파일 변경 금지
- client/, server/ 코드 생성 금지
- Docker 명령 및 /reference 접근 금지

작성 후 두 파일을 다시 읽어 제목·갱신 내용·기존 기록 보존 여부를 확인하고 결과를 보고해줘.
```

**정상 확인:** 두 인계 파일에 Planning 완료와 다음 구현 범위가 기록되고, `plans/` 문서와 고정 자산은 변경되지 않는다.

## 4-9. 최종 인계 문서 구조 검사

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    Write-Host '=== Lesson 04 Final Handoff Check ==='

    $root = 'C:\AI-Native\work-request-manager-v2'
    $required = @(
        'AGENTS.md',
        'progress.md',
        'handoff.md',
        'plans/implementation-plan.md',
        'plans/verification-plan.md'
    )
    foreach ($file in $required) {
        $path = Join-Path $root $file
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "필수 파일이 없습니다: $file"
        }
        Write-Host "File Check: PASS - $file"
    }
    $script = Join-Path $root 'scripts/verify-handoff.py'
    if (-not (Test-Path -LiteralPath $script -PathType Leaf)) {
        throw '인계 검증 스크립트가 없습니다.'
    }
    Get-Content -Raw -Encoding UTF8 -LiteralPath $script |
        docker compose exec -T hermes python3 - --root /workspace
    $exitCode = $LASTEXITCODE
    Write-Host "Validation Exit Code: $exitCode"
    if ($exitCode -ne 0) { throw '인계 문서 구조 검증 실패' }
    Write-Host 'Lesson 04 Handoff Check: PASS'
}
```

**정상 확인:** `Handoff structure: PASS`, `Validation Exit Code: 0`, `Lesson 04 Handoff Check: PASS`.

## 문제 해결

| 증상 | 확인 및 조치 |
|---|---|
| `lesson04.zip`을 찾지 못함 | 배포 디렉터리 또는 `Downloads`에 파일이 있는지 확인한다. |
| `Starter 파일이 일부만 존재합니다` | 기존 파일을 삭제하거나 `-Force`로 덮어쓰지 않는다. 파일 상태를 확인한다. |
| 배포본과 기존 파일의 SHA-256 불일치 | 해당 설정 파일의 변경 원인을 확인한다. 고정 자산은 임의 수정하지 않는다. |
| Hermes가 이전 상태를 복원하지 못함 | `/workspace` 연결 및 `progress.md`, `handoff.md`의 존재를 확인한다. |
| 계획 검사에서 REQ/AC 누락 | Hermes Agent에 누락 ID와 파일 경로를 제시하고 `plans/` 문서만 보완하도록 요청한다. |
| `verify-handoff.py` 실행 오류 | Docker Compose 위치, Hermes 컨테이너의 `python3`, 검증 스크립트 경로를 확인한다. Windows Python 설치는 필요하지 않다. |
| Skill 자동 변경 메시지 표시 | 필수 확인 항목이 아니다. 고정 Baseline 변경 여부와 혼동하지 않는다. |

## 완료 확인

- [ ] `lesson04.zip`의 신규 설정 파일 8개를 배치했다.
- [ ] 새로운 Hermes Agent Chat에서 이전 상태를 복원했다.
- [ ] 구현 기준 A·B·C를 검토하고 확정했다.
- [ ] `plans/implementation-plan.md`를 작성했다.
- [ ] `plans/verification-plan.md`를 작성했다.
- [ ] REQ 8개·AC 14개와 Closed-loop 규칙을 확인했다.
- [ ] 계획 문서 구조 검사에서 PASS를 확인했다.
- [ ] `progress.md`·`handoff.md`를 갱신했다.
- [ ] 인계 문서 구조 검사에서 PASS를 확인했다.
- [ ] 고정 Baseline과 설정 파일을 변경하지 않았다.

다음 작업에서는 기존 파일을 유지하고 신규 Starter를 누적 적용한 뒤, 승인된 계획에 따라 구현을 시작한다.

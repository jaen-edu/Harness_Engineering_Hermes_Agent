# 제3교시. 요구사항·상세 명세·API·UI 계약 분석

**과정명:** Open Weight Model과 Hermes Agent를 활용한 Agent Harness Engineering  
**실습 프로젝트:** AI Work Request Manager 2.0

## 학습 목표

- 이전 Chat의 작업 상태를 프로젝트 파일에서 복원한다.
- 요구사항(REQ), 인수 기준(AC), API 계약, JSON Schema, 화면 설계, 디자인 토큰을 읽고 연결 관계를 분석한다.
- 고정 JSON 계약의 구문과 핵심 구조를 독립적으로 검사한다.
- 확정되지 않은 항목을 임의로 구현하거나 Baseline을 수정하지 않고 다음 작업에 인계한다.

이번 실습에서는 **애플리케이션 구현 코드를 작성하지 않는다.** `AGENTS.md`, `docs/`, `specs/`, `contracts/`, `schemas/`, `design/`은 읽기 전용이다.

## 준비물 및 경로

- 제2교시 실습을 마친 Windows 11, Docker Desktop, PowerShell, Hermes Agent 환경
- Docker Compose 경로: `C:\AI-Native\hermes-training-v2`
- 교육생 작업 공간: `C:\AI-Native\work-request-manager-v2` (컨테이너 `/workspace`)
- `lesson03.zip`: 배포 디렉터리 `C:\AI-Native\work-request-manager-distribution` 또는 `Downloads`
- Hermes Dashboard: <http://127.0.0.1:9120/>

> 기존 `AGENTS.md`, `progress.md`, `handoff.md` 및 제2교시 산출물을 삭제하거나 덮어쓰지 않는다. PowerShell 명령은 **각각의 `& {`부터 마지막 `}`까지 전체를 한 번에 복사해 실행**한다. 모든 `PASS`는 해당 검사 범위에 한정된다.

## 3-1. 제3교시 Starter와 기존 작업 상태 사전 점검

다음 명령은 읽기 전용이며 압축을 해제하지 않는다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $targetPath = 'C:\AI-Native\work-request-manager-v2'
    $distributionZip = 'C:\AI-Native\work-request-manager-distribution\lesson03.zip'
    $downloadZip = Join-Path $HOME 'Downloads\lesson03.zip'

    Write-Host '=== Lesson 03 Starter ==='
    if (Test-Path -LiteralPath $distributionZip -PathType Leaf) {
        $zipPath = $distributionZip
    }
    elseif (Test-Path -LiteralPath $downloadZip -PathType Leaf) {
        $zipPath = $downloadZip
    }
    else {
        throw 'lesson03.zip 파일을 찾을 수 없습니다.'
    }
    if (-not (Test-Path -LiteralPath $targetPath -PathType Container)) {
        throw "작업 공간이 없습니다: $targetPath"
    }
    Write-Host "ZIP: $zipPath"

    Write-Host '=== Previous Lesson Files ==='
    $required = @(
        'AGENTS.md',
        'docs/project-overview.md',
        'scripts/verify-handoff.py',
        'progress.md',
        'handoff.md'
    )
    foreach ($name in $required) {
        $exists = Test-Path -LiteralPath (Join-Path $targetPath $name) -PathType Leaf
        [PSCustomObject]@{ File = $name; Exists = $exists }
        if (-not $exists) { throw "이전 교시 필수 파일이 없습니다: $name" }
    }

    Write-Host '=== Lesson 03 ZIP Contents ==='
    Add-Type -AssemblyName System.IO.Compression
    $archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        $entries = @($archive.Entries | Where-Object { $_.Name })
        if ($entries.Count -eq 0) { throw 'Starter ZIP에 파일이 없습니다.' }
        $names = @($entries | ForEach-Object { $_.FullName.Replace('\', '/') })
        if (@($names | Select-Object -Unique).Count -ne $names.Count) {
            throw 'ZIP에 중복 파일 경로가 있습니다.'
        }
        foreach ($entry in $entries) {
            $relative = $entry.FullName.Replace('\', '/')
            if ($relative.StartsWith('/') -or
                $relative -match '(^|/)\.\.?(/|$)' -or
                $relative -match '^[A-Za-z]:') {
                throw "허용되지 않는 ZIP 경로: $relative"
            }
            [PSCustomObject]@{
                File = $relative
                Size = $entry.Length
                AlreadyExists = Test-Path -LiteralPath (Join-Path $targetPath $relative)
            }
        }
        Write-Host "ZIP File Count: $($entries.Count)"
    }
    finally { $archive.Dispose() }
    Write-Host 'Lesson 03 Precheck: PASS'
}
```

**정상 확인:** `ZIP File Count: 7`, `Lesson 03 Precheck: PASS`. 제2교시 파일 5개가 모두 존재해야 한다. ZIP의 신규 파일이 이미 존재하는 경우에는 다음 설치 단계를 그대로 반복하지 않는다.

## 3-2. 제3교시 Starter 누적 적용

`lesson03.zip`은 아래 **7개 고정 자산**을 제공한다.

```text
contracts/openapi.json
design/tokens.json
design/wireframes.md
docs/specification.md
schemas/request.schema.json
specs/acceptance-criteria.md
specs/requirements.md
```

다음은 **처음 추가하는 경우**의 명령이다. 같은 파일이 이미 있다면 덮어쓰지 않고 중단하므로, 재실습 시에는 3-1에서 상태를 확인하고 3-3으로 넘어간다. 일부만 있다면 강사에게 문의한다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $zipPath = 'C:\AI-Native\work-request-manager-distribution\lesson03.zip'
    if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) {
        $zipPath = Join-Path $HOME 'Downloads\lesson03.zip'
    }
    $targetPath = 'C:\AI-Native\work-request-manager-v2'
    $expected = @(
        'contracts/openapi.json',
        'design/tokens.json',
        'design/wireframes.md',
        'docs/specification.md',
        'schemas/request.schema.json',
        'specs/acceptance-criteria.md',
        'specs/requirements.md'
    )
    Write-Host '=== Lesson 03 ZIP Validation ==='
    if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) {
        throw "ZIP 파일이 없습니다: $zipPath"
    }
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
            throw '제3교시 ZIP 파일 구성이 예상과 다릅니다.'
        }
        Write-Host 'ZIP Validation: PASS'
        $existing = @($expected | Where-Object {
            Test-Path -LiteralPath (Join-Path $targetPath $_)
        })
        if ($existing.Count -ne 0) {
            throw "기존 파일과 충돌합니다: $($existing -join ', ')"
        }
    }
    finally { $archive.Dispose() }
    Write-Host '=== Extract Lesson 03 Starter ==='
    Expand-Archive -LiteralPath $zipPath -DestinationPath $targetPath -ErrorAction Stop
    Write-Host '=== Verify Files ==='
    foreach ($name in $expected) {
        $exists = Test-Path -LiteralPath (Join-Path $targetPath $name) -PathType Leaf
        [PSCustomObject]@{ File = $name; Exists = $exists }
        if (-not $exists) { throw "필수 파일이 없습니다: $name" }
    }
    Write-Host 'Lesson 03 Starter: PASS'
}
```

**정상 확인:** `ZIP Validation: PASS`, `Lesson 03 Starter: PASS`, 7개 파일 `Exists=True`.

## 3-3. 새로운 Hermes Agent Chat에서 인계 복원 및 명세 확인

Hermes Dashboard에서 **New Chat**을 연다. 모델은 `z-ai/glm-5.3-flash`, Reasoning은 `medium`을 사용한다. 다음은 **Hermes Agent Chat 입력 프롬프트**이다.

```text
AI Work Request Manager 2.0 프로젝트의 제3교시 작업을 시작한다.

작업 공간은 /workspace이다.
이전 Chat의 대화 내용을 기억한다고 가정하지 않는다.

실제 파일 읽기 도구로 다음 파일을 순서대로 읽어줘.
1. /workspace/AGENTS.md
2. /workspace/docs/project-overview.md
3. /workspace/progress.md
4. /workspace/handoff.md
5. /workspace/specs/requirements.md
6. /workspace/docs/specification.md
7. /workspace/specs/acceptance-criteria.md

수행할 작업:
- 인계 문서를 근거로 현재 프로젝트 단계와 완료·미완료 작업을 복원한다.
- 고정 요구사항과 상세 명세의 목적 및 범위를 요약한다.
- 요구사항 ID(REQ)와 인수 기준 ID(AC)가 실제 문서에서 어떻게 구성되어 있는지 확인한다.
- 요구사항과 인수 기준 사이에 명백한 누락 또는 모순이 있는지 확인한다.
- 읽지 않은 API 계약·스키마·UI 설계 문서는 아직 검토하지 않았다고 표시한다.
- 파일별 읽기 성공 여부와 분석 결과를 표로 보고한다.

제약 조건:
- 파일 생성·수정·삭제 금지
- Docker 명령 실행 금지
- /reference 접근 금지
- 요구사항이나 인수 기준을 임의로 추가·변경하지 않는다.
- 실제로 확인하지 않은 항목은 PASS로 보고하지 않는다.

분석 결과만 보고하고 다음 지시를 기다려줘.
```

**정상 확인:** 7개 파일 읽기, 이전 작업 단계 복원, `REQ-001`~`REQ-008`(8개)와 `AC-001`~`AC-014`(14개) 식별, 변경 작업 없음. 특정 AC가 여러 REQ에 대응할 수 있다. 인수 기준으로 직접 표현되지 않은 세부 명세는 누락 여부를 근거와 함께 구분한다.

## 3-4. API 계약·데이터 스키마·UI 설계 분석

같은 Hermes Agent Chat에 다음 프롬프트를 입력한다.

```text
AI Work Request Manager 2.0의 고정 API·데이터·UI 계약을 분석해줘.

실제 파일 읽기 도구를 사용해 다음 파일을 순서대로 읽는다.
1. /workspace/contracts/openapi.json
2. /workspace/schemas/request.schema.json
3. /workspace/design/wireframes.md
4. /workspace/design/tokens.json

이미 읽은 specs/requirements.md, docs/specification.md, specs/acceptance-criteria.md의 내용과 비교하되, 필요한 경우 해당 파일을 다시 읽어서 근거를 확인한다.

수행할 작업:
1. API 엔드포인트, HTTP 메서드, 요청·응답 구조, 오류 코드와 상태 코드를 표로 정리한다.
2. 데이터 스키마의 필수 필드, 자료형, 허용값, 길이 제한을 정리한다.
3. 화면 구성과 화면별 사용자 동작을 정리한다.
4. 디자인 토큰의 색상·간격·글꼴 등 실제 정의된 항목을 정리한다.
5. 요구사항·상세 명세·인수 기준과 API·스키마·UI 계약 사이의 일치 여부를 확인한다.
6. 차이가 발견되면 파일 경로와 해당 규칙을 근거로 충돌, 누락, 추가 확인 필요 중 하나로 분류한다.
7. 앞서 보고한 인수 기준의 직접 검증 미대응 항목이 이번 계약 문서에서 어떻게 정의되어 있는지 확인한다.

제약 조건:
- API, 스키마, UI 설계는 고정 Baseline이므로 수정하지 않는다.
- 파일 생성·수정·삭제 금지.
- 애플리케이션 구현 금지.
- Docker 명령 실행 및 /reference 접근 금지.
- 파일에 없는 API·필드·UI 요소를 추측해서 추가하지 않는다.
- 불일치가 있으면 임의로 해결하지 말고 근거와 함께 보고한다.

마지막에 문서별 읽기 결과와 정합성 판정을 PASS/FAIL/추가 확인 필요로 구분해서 보고하고 다음 지시를 기다려줘.
```

**정상 확인:** API의 등록·목록·상세·수정·상태 변경, 요청 데이터 필드, 화면 3개(WF-01~03), 디자인 토큰 정의를 근거와 함께 제시한다. 확인이 필요한 해석은 임의로 확정하지 않는다.

## 3-5. 고정 JSON 계약 구조 자동 검사

이 단계는 **PowerShell에서 실행**한다. Windows에 Python을 설치하지 않고 Hermes 컨테이너의 Python을 사용한다. 다음 코드는 **JSON 파싱과 핵심 구조**를 확인하며, 전체 OpenAPI/JSON Schema 규격 검증이나 실제 서버 테스트는 아니다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    Write-Host '=== Lesson 03 JSON Contract Validation ==='

    $pythonCode = @'
import json
import sys
from pathlib import Path

root = Path("/workspace")
files = {
    "OpenAPI": root / "contracts/openapi.json",
    "Request Schema": root / "schemas/request.schema.json",
    "Design Tokens": root / "design/tokens.json",
}
data = {}
try:
    for name, path in files.items():
        if not path.is_file():
            raise AssertionError(f"Missing file: {path}")
        with path.open("r", encoding="utf-8-sig") as f:
            data[name] = json.load(f)
        print(f"{name} JSON: PASS")

    api = data["OpenAPI"]
    schema = data["Request Schema"]
    tokens = data["Design Tokens"]
    assert str(api.get("openapi", "")).startswith("3.1."), "Expected OpenAPI 3.1"
    paths = api.get("paths", {})
    expected_operations = {
        "/api/requests": {"get", "post"},
        "/api/requests/{id}": {"get", "patch"},
        "/api/requests/{id}/status": {"patch"},
    }
    for path, methods in expected_operations.items():
        assert path in paths, f"Missing API path: {path}"
        for method in methods:
            assert method in paths[path], f"Missing operation: {method.upper()} {path}"
    print("OpenAPI Operations: PASS")

    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    expected_fields = {
        "id", "title", "description", "requester", "assignee",
        "priority", "status", "createdAt", "updatedAt",
    }
    assert expected_fields.issubset(properties), \
        f"Missing fields: {expected_fields - set(properties)}"
    assert expected_fields.issubset(required), \
        f"Missing required fields: {expected_fields - required}"
    assert schema.get("additionalProperties") is False, \
        "Unexpected additionalProperties setting"
    print("Request Schema Structure: PASS")

    assert isinstance(tokens, dict), "Design tokens must be an object"
    for key in ("color", "spacing", "radius", "typography"):
        assert key in tokens, f"Missing token group: {key}"
    print("Design Tokens Structure: PASS")
    print("Lesson 03 JSON Validation: PASS")
except (OSError, ValueError, AssertionError, TypeError) as exc:
    print(f"Lesson 03 JSON Validation: FAIL - {exc}", file=sys.stderr)
    sys.exit(1)
'@

    $pythonCode | docker compose exec -T hermes python3 -
    $exitCode = $LASTEXITCODE
    Write-Host "Validation Exit Code: $exitCode"
    if ($exitCode -ne 0) { throw "JSON 계약 검증 실패: 종료 코드 $exitCode" }
    Write-Host 'Lesson 03 Contract Check: PASS'
}
```

**정상 확인:** `OpenAPI JSON: PASS`, `Request Schema JSON: PASS`, `Design Tokens JSON: PASS`, `OpenAPI Operations: PASS`, `Request Schema Structure: PASS`, `Design Tokens Structure: PASS`, `Lesson 03 Contract Check: PASS`, 종료 코드 `0`.

## 3-6. 요구사항·인수 기준·계약 정합성 종합 점검

같은 Hermes Agent Chat에 아래 프롬프트를 입력한다.

```text
AI Work Request Manager 2.0의 제3교시 Baseline 분석 결과를 종합해줘.

작업 공간: /workspace
앞서 읽은 요구사항, 상세 명세, 인수 기준, API 계약, JSON Schema, 와이어프레임, 디자인 토큰을 근거로 한다. 필요한 경우 실제 파일을 다시 읽어 확인한다.

다음 내용을 보고해줘.
1. REQ-001~REQ-008 각각에 대해 기능 목적, 관련 AC ID, 관련 API 또는 UI 요소를 연결한 추적 표를 작성한다.
2. 구현 시 반드시 준수해야 할 데이터 규칙, 상태 전이, 오류 처리, 저장 방식, 접근성 규칙을 요약한다.
3. 앞선 분석에서 발견된 불명확한 사항을 재검토한다.
   - 잘못된 UUID 형식의 요청 ID 처리
   - 목록 응답 total의 의미
   - 포커스 표시용 전용 디자인 토큰 부재
   - 목록 정렬 규칙의 API 계약 미표기
4. 각 항목을 실제 문서 근거에 따라 '명확함', '해석 필요', '승인 필요'로 분류한다. 문서에서 확인되지 않은 결론을 임의로 확정하지 않는다.
5. 다음 단계인 Planning에서 다뤄야 할 작업을 제안하되, 지금 계획 파일을 작성하거나 구현하지 않는다.
6. 방금 PowerShell에서 확인된 JSON 계약 검사의 결과는 사용자 제공 실행 로그에 근거한 PASS로 구분한다. Hermes Agent가 직접 실행했다고 기록하지 않는다.

제약:
- 모든 고정 Baseline 파일 수정 금지
- progress.md, handoff.md를 포함한 파일 생성·수정·삭제 금지
- 구현 코드 작성 금지
- Docker 명령 실행 금지
- /reference 접근 금지
- 근거가 불확실한 내용은 추가 확인 필요로 보고

최종적으로 REQ–AC 연결 결과, 정합성 판정, 미해결 사항, Planning 준비 상태를 표로 보고하고 다음 지시를 기다려줘.
```

**정상 확인:** REQ 8개 모두 대응 AC를 갖고, 명세에서 확인된 규칙과 해석이 필요한 항목을 구분한다. 한 예로 `total`의 의미, 포커스 표시 방식, 잘못된 UUID 형식 처리 등은 근거가 부족하면 미해결로 남긴다. 구현이나 파일 변경은 수행하지 않는다.

## 3-7. 진행 상태 및 Chat 인계 문서 갱신

같은 Hermes Agent Chat에 아래 프롬프트를 입력한다.

```text
AI Work Request Manager 2.0의 제3교시 작업을 마무리하고 다음 Chat으로 인계할 상태를 기록해줘.

작업 공간: /workspace
먼저 /workspace/progress.md와 /workspace/handoff.md를 실제로 다시 읽는다.
기존 기록을 보존하면서 두 파일만 갱신한다.

progress.md에 반영할 사항:
1. 현재 단계: Specification Baseline 분석 완료, Planning 착수 전
2. 제1·2교시 기록 유지 및 제3교시 고정 자산 7개 읽기·분석 추가
3. 요구사항 REQ-001~008과 인수 기준 AC-001~014의 대응 관계 확인
4. OpenAPI·JSON Schema·디자인 토큰 JSON 구조 검사 PASS (사용자 제공 PowerShell 결과)
5. API·스키마·와이어프레임·토큰 사이 명백한 모순 없음
6. 해석 필요 항목: total 의미, 포커스 표시 방식, 잘못된 UUID 형식 처리
7. 애플리케이션 구현 및 테스트는 미착수
8. 다음 작업: Planning에서 해석 필요 사항 검토, 구현 작업 분해, 검증 계획 수립

handoff.md에 반영할 사항:
1. 프로젝트 단계 및 제1~3교시 완료 작업
2. 고정 Baseline 9개(AGENTS.md, 프로젝트 개요, 제3교시 자산 7개)의 경로와 역할
3. REQ 8개·AC 14개 대응 관계 및 주요 구현 규칙
4. 사용자 제공 실행 로그에 근거한 JSON 계약 구조 검사 PASS
5. 해석 필요 3건을 미해결로 기록하고 임의 확정하지 않음
6. Planning에서 작성할 계획과 검증 범위
7. 다음 Chat에서 읽을 AGENTS.md, 프로젝트 개요, 요구사항, 상세 명세, progress.md, handoff.md 경로

기록 원칙:
- 제1·2교시 완료 기록을 삭제하지 않는다.
- 완료한 작업과 앞으로 할 작업을 구분한다.
- 사용자 PowerShell 검증을 Hermes가 직접 실행했다고 기록하지 않는다.
- 해석 필요 항목을 해결 완료로 기록하지 않는다.
- 두 파일 외 생성·수정·삭제 금지
- 고정 Baseline 변경 금지
- 애플리케이션 구현 금지
- Docker 명령 및 /reference 접근 금지

작업 후 두 파일을 다시 읽어 필수 제목, 문서 중복, 문장 병합 오류, 갱신 내용을 확인한다. 변경한 파일 목록과 다음 단계 준비 상태를 보고하고 기다려줘.
```

**정상 확인:** 수정된 파일은 `progress.md`, `handoff.md` 두 개뿐이다. 기존 기록이 보존되고 3개 해석 필요 항목은 미해결로 남는다. Agent의 작성 완료 보고만으로 문서 전체의 무결성을 확정하지 않는다.

## 3-8. Chat 인계 문서 구조 검증

제2교시에 제공한 고정 스크립트를 Docker 컨테이너의 Python으로 실행한다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    Write-Host '=== Lesson 03 Handoff Validation ==='
    $script = 'C:\AI-Native\work-request-manager-v2\scripts\verify-handoff.py'
    if (-not (Test-Path -LiteralPath $script -PathType Leaf)) {
        throw "검증 스크립트가 없습니다: $script"
    }
    Get-Content -Raw -Encoding UTF8 -LiteralPath $script |
        docker compose exec -T hermes python3 - --root /workspace
    $exitCode = $LASTEXITCODE
    Write-Host "Validation Exit Code: $exitCode"
    if ($exitCode -ne 0) { throw 'Chat 인계 문서 구조 검증 실패' }
    Write-Host 'Lesson 03 Handoff Check: PASS'
}
```

**정상 확인:**

```text
Handoff structure: PASS
Validation Exit Code: 0
Lesson 03 Handoff Check: PASS
```

## 문제 해결

| 증상 | 확인 및 처리 |
|---|---|
| `lesson03.zip 파일을 찾을 수 없습니다` | 배포 경로 또는 `Downloads`에 파일이 있는지 확인한다. 임의의 다른 ZIP으로 대체하지 않는다. |
| 기존 파일과 충돌 | 이미 제3교시 Starter를 배치했다면 **3-2를 재실행하지 않는다**. 3-1의 파일 목록과 내용 확인 후 다음 단계로 진행한다. 부분 배치는 강사에게 확인한다. |
| `/workspace`에서 파일을 못 읽음 | PowerShell에서 `docker compose ps`와 마운트를 확인한다. Windows에서 지정한 작업 공간과 컨테이너 `/workspace`의 연결을 확인한다. |
| JSON 계약 검사 실패 | 출력된 파일명·검사 항목을 확인한다. 고정 JSON을 임의 수정하지 않는다. |
| Hermes Agent가 요구사항 수정을 제안함 | 고정 Baseline 변경은 중단하고 충돌 사항을 보고한다. |
| 인계 문서에 중복 문장이나 잘못 이어진 문장이 있음 | `progress.md`, `handoff.md`만 다시 읽고 문제가 있는 부분만 고친다. 제1·2교시 내용과 고정 자산은 보존한다. |
| `Handoff structure: FAIL` | 문서 필수 제목을 확인하고 두 인계 문서만 수정한다. 고정 스크립트를 고쳐서 통과시키지 않는다. |

## 완료 확인

- [ ] 7개 고정 자산이 작업 공간에 존재한다.
- [ ] 새로운 Chat에서 인계 문서와 요구사항을 읽었다.
- [ ] REQ–AC–API/UI 연결 관계를 확인했다.
- [ ] API·스키마·와이어프레임·디자인 토큰을 분석했다.
- [ ] JSON 계약 구조 검사가 `PASS`를 반환했다.
- [ ] 미해결 해석 항목을 다음 작업으로 인계했다.
- [ ] `progress.md`와 `handoff.md`의 기존 내용을 보존하면서 갱신했다.
- [ ] 인계 문서 구조 검사가 `Handoff structure: PASS`를 반환했다.
- [ ] 고정 Baseline과 애플리케이션 구현 코드를 변경하지 않았다.

다음 작업에서는 갱신된 인계 문서를 읽어 **Planning: 구현 작업 분해와 검증 계획 수립**을 진행한다.

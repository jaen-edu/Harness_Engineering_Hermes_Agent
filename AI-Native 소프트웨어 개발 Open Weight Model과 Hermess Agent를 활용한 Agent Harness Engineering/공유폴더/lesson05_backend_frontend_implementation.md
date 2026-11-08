# 제5교시. Hermes Agent 기반 업무 요청 등록·목록·상세 기능 구현

**과정명:** Open Weight Model과 Hermes Agent를 활용한 Agent Harness Engineering  
**실습 프로젝트:** AI Work Request Manager 2.0

## 학습 목표

- 제4교시의 구현·검증 계획과 Chat 인계 내용을 복원한다.
- 고정된 API 테스트를 읽고 **수정하지 않은 채** Backend 등록·목록·상세 기능을 구현한다.
- React/TypeScript로 목록(WF-01), 등록(WF-02), 읽기 전용 상세(WF-03) 화면을 구현한다.
- API·정적 검사·빌드·Chromium 기능 테스트를 구분해 실행하고, 결과를 다음 Chat에 인계한다.

> 이번 실습의 완료 범위는 **REQ-001~003과 이에 필요한 공통 Backend 및 기본 UI**이다. `PATCH` 수정·상태 변경은 다음 교시에서 구현한다. 고정 `tests/api.test.js`에는 다음 교시의 기능 테스트도 포함되므로, 이번 교시에 전체 11개 테스트의 PASS를 완료 조건으로 삼지 않는다.

## 준비물 및 실행 규칙

- Hermes Dashboard: <http://127.0.0.1:9120/>, 모델 `z-ai/glm-5.3-flash`, Reasoning `medium`
- Docker Compose: `C:\AI-Native\hermes-training-v2`
- 프로젝트 디렉터리: `C:\AI-Native\work-request-manager-v2` = Hermes 내부 `/workspace`
- Starter: `lesson05.zip` (배포 폴더 또는 `Downloads`)
- 기존 `AGENTS.md`, 계약·명세·테스트·계획 문서는 보존한다.
- **PowerShell은 각 `& {` 블록 전체를 한 번에 복사해 실행한다.** Hermes Agent 프롬프트는 별도 텍스트 블록으로 입력한다.
- 표시된 PASS는 그 단계의 검증 범위만 뜻하며, 자동 수정은 최초 검증 이후 최대 3회로 제한한다.

## 5-1. 이전 작업 및 Starter 사전 확인

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $root = 'C:\AI-Native\work-request-manager-v2'
    $distributionZip = 'C:\AI-Native\work-request-manager-distribution\lesson05.zip'
    $downloadZip = Join-Path $HOME 'Downloads\lesson05.zip'

    if (Test-Path -LiteralPath $distributionZip -PathType Leaf) { $zipPath = $distributionZip }
    elseif (Test-Path -LiteralPath $downloadZip -PathType Leaf) { $zipPath = $downloadZip }
    else { throw 'lesson05.zip 파일을 찾을 수 없습니다.' }
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { throw "작업 공간 없음: $root" }

    $required = @(
        'AGENTS.md', 'docs/project-overview.md', 'specs/requirements.md',
        'docs/specification.md', 'specs/acceptance-criteria.md',
        'contracts/openapi.json', 'schemas/request.schema.json',
        'design/wireframes.md', 'design/tokens.json',
        'package.json', 'package-lock.json',
        'plans/implementation-plan.md', 'plans/verification-plan.md',
        'progress.md', 'handoff.md', 'scripts/verify-handoff.py'
    )
    foreach ($name in $required) {
        if (-not (Test-Path -LiteralPath (Join-Path $root $name) -PathType Leaf)) {
            throw "이전 교시 필수 파일 없음: $name"
        }
    }
    Write-Host "Previous Lesson Files: PASS ($($required.Count) files)"
    Add-Type -AssemblyName System.IO.Compression
    $archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        $names = @($archive.Entries | Where-Object { $_.Name } | ForEach-Object { $_.FullName.Replace('\', '/') })
        if ($names.Count -ne 1 -or $names[0] -ne 'tests/api.test.js') {
            throw "ZIP 구성 불일치: $($names -join ', ')"
        }
        Write-Host "Starter File: $($names[0])"
        Write-Host "Already Exists: $(Test-Path -LiteralPath (Join-Path $root $names[0]))"
    } finally { $archive.Dispose() }
    Write-Host 'Lesson 05 Precheck: PASS'
}
```

**정상 확인:** `Previous Lesson Files: PASS (16 files)`, `Starter File: tests/api.test.js`, `Lesson 05 Precheck: PASS`.

## 5-2. Starter 최초 적용 또는 안전한 재개

ZIP 파일은 **고정 API 테스트 1개**를 포함한다. 기존 파일이 있으면 ZIP 내부 내용과 SHA-256을 비교하여 동일할 때만 재개한다. 다른 내용은 덮어쓰지 않는다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $root = 'C:\AI-Native\work-request-manager-v2'
    $distributionZip = 'C:\AI-Native\work-request-manager-distribution\lesson05.zip'
    $downloadZip = Join-Path $HOME 'Downloads\lesson05.zip'
    if (Test-Path -LiteralPath $distributionZip -PathType Leaf) { $zipPath = $distributionZip }
    elseif (Test-Path -LiteralPath $downloadZip -PathType Leaf) { $zipPath = $downloadZip }
    else { throw 'lesson05.zip 파일을 찾을 수 없습니다.' }
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { throw '프로젝트 디렉터리가 없습니다.' }

    Add-Type -AssemblyName System.IO.Compression
    $archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        $entries = @($archive.Entries | Where-Object { $_.Name })
        if ($entries.Count -ne 1 -or $entries[0].FullName.Replace('\','/') -ne 'tests/api.test.js') {
            throw '제5교시 ZIP 구성은 tests/api.test.js 1개여야 합니다.'
        }
        Write-Host 'ZIP Validation: PASS'
        $local = Join-Path $root 'tests/api.test.js'
        if (-not (Test-Path -LiteralPath $local)) { $mode = 'INSTALL' }
        else {
            if (-not (Test-Path -LiteralPath $local -PathType Leaf)) { throw '기존 테스트 경로가 파일이 아닙니다.' }
            $localHash = (Get-FileHash -LiteralPath $local -Algorithm SHA256).Hash
            $stream = $entries[0].Open()
            try {
                $sha = [System.Security.Cryptography.SHA256]::Create()
                try { $zipHash = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','') }
                finally { $sha.Dispose() }
            } finally { $stream.Dispose() }
            if ($localHash -ne $zipHash) { throw '기존 고정 테스트와 배포본이 다릅니다. 덮어쓰지 않습니다.' }
            $mode = 'RESUME'
        }
    } finally { $archive.Dispose() }

    switch ($mode) {
        'INSTALL' {
            Expand-Archive -LiteralPath $zipPath -DestinationPath $root -ErrorAction Stop
            Write-Host 'Starter Mode: INSTALL'
            break
        }
        'RESUME' { Write-Host 'Starter Mode: RESUME (압축 해제 생략)'; break }
        default { throw "알 수 없는 모드: $mode" }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $root 'tests/api.test.js') -PathType Leaf)) {
        throw '고정 API 테스트 파일이 없습니다.'
    }
    Write-Host 'Lesson 05 Starter: PASS'
}
```

**정상 확인:** `ZIP Validation: PASS`, `Starter Mode: INSTALL` 또는 `RESUME`, `Lesson 05 Starter: PASS`.

## 5-3. 새 Hermes Agent Chat 및 고정 테스트 분석

Hermes Dashboard에서 **New Chat**을 만든 후 다음을 입력한다. 이 단계는 읽기 전용이다.

```text
AI Work Request Manager 2.0의 제5교시 구현 준비를 시작한다.
작업 공간은 /workspace이다. 이전 Chat의 내용을 기억한다고 가정하지 않는다.

실제 파일 읽기 도구로 다음을 순서대로 읽어라.
AGENTS.md, docs/project-overview.md, progress.md, handoff.md,
specs/requirements.md, docs/specification.md, specs/acceptance-criteria.md,
contracts/openapi.json, schemas/request.schema.json,
design/wireframes.md, design/tokens.json,
plans/implementation-plan.md, plans/verification-plan.md,
tests/api.test.js, package.json, index.html, tsconfig.json, vite.config.js.

1. Specification과 Planning의 완료 상태, 이번 교시 구현 범위를 복원한다.
2. 승인된 구현 기준 A(total=필터된 items.length), B(primary 포커스),
   C(형식 오류 UUID 400 / 유효하지만 미존재 UUID 404)를 확인한다.
3. tests/api.test.js의 실제 import 계약, 테스트 11개와 각 기대값을 분석한다.
4. server/app.js가 ESM named export createApp({dataFile})을 제공해야 한다는
   테스트 계약을 확인한다.
5. 등록·목록·상세만 이번 교시 구현 대상으로 구분한다.
   PATCH 및 상태 변경은 다음 교시 대상으로 남긴다.
6. 고정 테스트와 승인 기준 A·C 사이 충돌 여부를 보고한다.

이번 요청에서는 파일 생성·수정·삭제와 테스트 실행을 하지 않는다.
Docker 명령, /reference 접근, Baseline 변경을 하지 않는다.
읽기 결과, 구현 준비 사항과 미확인 항목만 보고하고 기다려라.
```

**정상 확인:** 고정 테스트에서 `createApp({dataFile})` import를 확인하고, 등록·목록·상세에 대한 테스트 기대값과 PATCH 테스트를 구분한다. **고정 테스트를 수정해서 통과시키지 않는다.**

## 5-4. Backend 최초 통합 구현 — Hermes Agent 프롬프트 하나

다음 프롬프트는 **저장 경로 누락, ESM 오류, 디렉터리 생성 실패, 동시 등록 데이터 유실**을 방지할 요구조건을 처음부터 포함한다. 별도의 사후 보완 프롬프트를 순서상 필수로 두지 않는다.

```text
AI Work Request Manager 2.0의 제5교시 Backend를 구현한다.
작업 공간: /workspace.

먼저 AGENTS.md, 두 plans/ 계획, package.json, tests/api.test.js,
requirements.md, specification.md, acceptance-criteria.md,
contracts/openapi.json과 schemas/request.schema.json을 실제로 읽어라.
고정 테스트는 읽기 전용이며 기대값을 수정하지 않는다.

1. 모듈·테스트 인터페이스
- package.json의 "type": "module"에 맞춰 Node ESM import/export만 사용한다.
- server/app.js에서 named export `createApp(options = {})`를 제공한다.
- `createApp({dataFile})`로 Supertest가 포트 없이 앱을 검사할 수 있어야 한다.
- server/index.js는 createApp을 호출해 기본 포트 3001에서 실행한다.
- package.json, package-lock.json, index.html, Vite·TS 설정을 변경하지 않는다.

2. 이번에 구현할 API
- POST /api/requests: title, requester, assignee, priority 필수;
  description 선택 및 생략 시 빈 문자열. 공백 trim과 Unicode 코드 포인트 기준
  길이 검증, enum 검사, 알 수 없는 필드 거부. 생성 시 UUID v4, UTC ISO 8601,
  status=received를 서버에서 설정하고 HTTP 201을 반환한다.
- GET /api/requests: status·priority 선택 필터를 AND로 적용하며 enum 오류는
  400 처리한다. 생성 시각 내림차순, 동률이면 ID 오름차순. 응답 {items,total};
  total은 필터 적용 후 items.length(승인 기준 A).
- GET /api/requests/:id: UUID v4 형식 오류는 400 VALIDATION_ERROR,
  정상 형식이지만 없는 ID는 404 NOT_FOUND(승인 기준 C).
- 오류 응답 형식은 {error:{code,message}}; 서버 내부 경로·스택은 노출하지 않는다.
- PATCH /api/requests/:id와 PATCH /api/requests/:id/status는 이번 교시에
  추가하지 않는다. 두 API는 다음 교시 범위이다.

3. JSON 저장소 — 처음부터 모두 충족
- createApp에 dataFile 옵션이 전달되면 이를 사용한다. 그렇지 않으면
  ./data/requests.json을 작업 디렉터리 기준으로 사용한다.
  server/index.js는 DATA_FILE 환경변수가 설정되어 있으면 우선 전달한다.
- 파일이 없으면 빈 배열부터 시작한다. 처음 저장할 때 상위 디렉터리를
  안전하게 생성한다.
- 손상된 기존 JSON은 빈 배열로 덮지 않고 HTTP 500 INTERNAL_ERROR를 반환한다.
- 같은 디렉터리의 고유한 임시 파일에 쓰고 rename으로 원자적 교체한다.
- 동시 POST의 읽기→수정→쓰기 전체를 직렬화한다. 쓰기만 직렬화해서는 안 된다.
  예: 순차 작업 큐에서 load→mutate→save를 수행한다.
- 차후 PATCH 라우트도 동일 저장소의 안전한 변경 연산을 재사용할 수 있도록 한다.

4. 코드 파일
- server/app.js, server/index.js
- 필요에 따라 server/errors.js, validate.js, store.js, routes.js
- import 경로의 .js 확장자 및 함수 export 명을 서로 일치시킨다.

5. 범위·절차
- server/ 파일만 생성·수정한다. client/는 이번 요청에서 건드리지 않는다.
- AGENTS.md, docs/, specs/, contracts/, schemas/, design/, tests/, e2e/,
  scripts/, plans/, 루트 설정 파일은 수정하지 않는다.
- 의존성을 설치하지 말고 Docker 명령이나 /reference 접근도 수행하지 않는다.
- 실제 파일 확인 → 구현 → 파일 재읽기 → import/export·저장소 동작의
  코드 점검 순으로 작업한다.
- 이 요청에서는 테스트 실행·자동 수정 루프는 시작하지 않는다.
- 구현 파일과 현재 지원 API, 다음 교시 미구현 기능을 구분해 보고한다.
```

**정상 확인:** `server/` 파일이 생성되며 `createApp({dataFile})`과 세 API가 구현되었다고 보고한다. 이때 **테스트 PASS를 아직 주장하지 않는다.**

## 5-5. 프로젝트 의존성 설치 및 실행 확인

Hermes 컨테이너에는 Node.js와 npm이 있으나 `/workspace/node_modules`가 없을 수 있다. `npm ci`는 lockfile 기준으로 설치한다. Vitest를 `import('vitest')`로 확인하지 않는다. Vitest는 **CLI로 실행 가능 여부**를 확인한다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    Write-Host '=== Lesson 05 Dependencies ==='
    docker compose exec -T hermes sh -lc '
        set -eu
        cd /workspace
        test -f package.json && test -f package-lock.json
        if test ! -d node_modules; then
            npm ci --no-audit --no-fund
        else
            echo "node_modules: EXISTS (설치 생략)"
        fi
        node --input-type=module -e "await import(\"express\"); await import(\"supertest\"); console.log(\"Express and Supertest: PASS\")"
        ./node_modules/.bin/vitest --version
        echo "Vitest CLI: PASS"
        node --input-type=module -e "import * as esbuild from \"esbuild\"; const r=await esbuild.transform(\"const answer = 42\",{loader:\"js\"}); if(!r.code.includes(\"answer\")) throw Error(\"transform failed\"); console.log(\"esbuild Runtime: PASS\")"
        echo "Lesson 05 Dependencies: PASS"
    '
    $exitCode = $LASTEXITCODE
    Write-Host "Validation Exit Code: $exitCode"
    if ($exitCode -ne 0) { throw "의존성 준비 실패: $exitCode" }
}
```

**정상 확인:** `Express and Supertest: PASS`, `Vitest CLI: PASS`, `esbuild Runtime: PASS`, 종료 코드 0. `esbuild` 실행 스크립트 차단 경고가 있더라도 실제 변환이 통과했는지를 기준으로 판단한다. 기존 `node_modules`가 불완전하여 실패하면 설치 상태를 확인한 후 동일 lockfile로 `npm ci`를 다시 실행한다. 고정 설정 파일을 수정하지 않는다.

## 5-6. Backend API 독립 기능 검증

이 검증은 **고정 테스트 파일을 변경하지 않는다.** 임시 디렉터리에 데이터를 생성한 후 삭제한다. 등록·목록·상세와 동시 등록·손상 파일 보존만 검사하며 PATCH는 제외한다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    Write-Host '=== Lesson 05 Backend API Verification ==='
    $nodeCode = @'
import { createApp } from './server/app.js';
import request from 'supertest';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';

const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'lesson05-api-'));
const file = path.join(dir, 'nested', 'requests.json');
const app = createApp({ dataFile: file });
let passed = 0;
function check(ok, label) {
    if (!ok) throw new Error(`FAIL: ${label}`);
    console.log(`PASS: ${label}`); passed++;
}
const payload = (title, priority = 'high') => ({
    title, requester: '교육생', assignee: '담당자', priority
});
try {
    const created = await request(app).post('/api/requests').send(payload('첫 번째 요청'));
    check(created.status === 201 && created.body.status === 'received' &&
          /^[0-9a-f-]{36}$/.test(created.body.id), 'POST registration');
    check(created.body.description === '' && Boolean(created.body.createdAt), 'Default fields');
    const listed = await request(app).get('/api/requests');
    check(listed.status === 200 && listed.body.total === 1 && listed.body.items.length === 1, 'GET list');
    const filtered = await request(app).get('/api/requests?status=received&priority=high');
    check(filtered.status === 200 && filtered.body.total === 1, 'AND filtering');
    const empty = await request(app).get('/api/requests?priority=low');
    check(empty.status === 200 && empty.body.total === 0, 'Filtered total');
    const detail = await request(app).get(`/api/requests/${created.body.id}`);
    check(detail.status === 200 && detail.body.title === '첫 번째 요청', 'GET detail');
    const invalid = await request(app).post('/api/requests').send(payload('   '));
    check(invalid.status === 400 && invalid.body.error?.code === 'VALIDATION_ERROR', 'Input validation');
    const invalidId = await request(app).get('/api/requests/not-a-uuid');
    check(invalidId.status === 400 && invalidId.body.error?.code === 'VALIDATION_ERROR', 'Invalid UUID');
    const unknownId = await request(app).get(`/api/requests/${crypto.randomUUID()}`);
    check(unknownId.status === 404 && unknownId.body.error?.code === 'NOT_FOUND', 'Missing UUID');
    const concurrent = await Promise.all(Array.from({length:5}, (_,i) =>
        request(app).post('/api/requests').send(payload(`동시 요청 ${i+1}`))));
    const after = await request(app).get('/api/requests');
    check(concurrent.every(r => r.status === 201) && after.status === 200 &&
          after.body.total === 6, 'Concurrent registration');
    const corrupt = path.join(dir, 'corrupt.json');
    await fs.writeFile(corrupt, '{broken', 'utf8');
    const corruptResponse = await request(createApp({dataFile: corrupt})).get('/api/requests');
    const preserved = await fs.readFile(corrupt, 'utf8');
    check(corruptResponse.status === 500 &&
          corruptResponse.body.error?.code === 'INTERNAL_ERROR' &&
          preserved === '{broken', 'Corrupt file preservation');
    console.log(`Lesson 05 Backend API: PASS (${passed} checks)`);
} catch (e) {
    console.error(e); process.exitCode = 1;
} finally {
    await fs.rm(dir, {recursive:true, force:true});
}
'@
    $nodeCode | docker compose exec -T -w /workspace hermes node --input-type=module -
    $exitCode = $LASTEXITCODE
    Write-Host "Validation Exit Code: $exitCode"
    if ($exitCode -ne 0) { throw 'Backend API 검증 실패' }
    Write-Host 'Lesson 05 Backend Check: PASS'
}
```

**정상 확인:** `Lesson 05 Backend API: PASS (11 checks)`와 종료 코드 0. 이 결과는 기능별 독립 검사 통과이며 고정 `tests/api.test.js` 전체 통과가 아니다.

## 5-7. Frontend 최초 통합 구현 — Hermes Agent 프롬프트 하나

**현재 제5교시 Hermes Agent Chat을 그대로 사용한다.** 다음 UI 계약은 이번 프로젝트의 등록 화면 구현 기준이다. 우선순위는 **라디오 버튼 3개**, 각각 `name="priority"`, 값 `low`, `medium`, `high`로 고정한다. 테스트는 선택자의 우연한 모양보다 접근 가능한 이름·동작을 우선 검사한다.

```text
AI Work Request Manager 2.0의 제5교시 Frontend를 구현한다.
작업 공간: /workspace.

반드시 다음 실제 파일을 먼저 읽어라.
AGENTS.md, docs/project-overview.md, docs/specification.md,
specs/requirements.md, specs/acceptance-criteria.md, design/wireframes.md,
design/tokens.json, contracts/openapi.json, schemas/request.schema.json,
plans/implementation-plan.md, plans/verification-plan.md,
package.json, index.html, tsconfig.json, vite.config.js,
server/app.js, server/routes.js.

목표: React 18 + TypeScript(strict) + Vite 6으로 세 화면을 구현한다.
새 의존성 또는 라우터 라이브러리를 추가하지 않는다.
기존 index.html이 참조하는 client/src/main.tsx를 사용한다.
API 요청은 기존 Vite 프록시를 사용하는 /api 상대 경로로 보낸다.

WF-01 목록 화면
- GET /api/requests, 상태·우선순위 필터 동시 적용, total=필터 후 개수.
- 제목·상태·우선순위·담당자 및 와이어프레임의 정보 표시.
- 로딩·빈 목록·오류·재시도를 구분한다.
- 버튼의 접근 가능한 이름은 '요청 등록'을 포함하게 한다.
- 제목을 눌러 상세로 이동한다.
- 모바일에서도 동일 정보/조작을 제공한다.

WF-02 요청 등록 화면
- 제목: input id=f-title, name=title.
- 설명: textarea id=f-description, name=description.
- 요청자: input id=f-requester, name=requester.
- 담당자: input id=f-assignee, name=assignee.
- 우선순위: low/medium/high 값을 가진 radio input 3개,
  모두 name=priority로 묶고 각 항목에 접근 가능한 한국어 라벨을 제공한다.
- form의 제출 버튼은 type=submit, 접근 가능한 이름에 '등록'을 포함한다.
- 필수·문자 길이·공백 입력을 계약대로 검증하고 오류를 필드에 연결한다.
- 제출 중 재클릭·Enter 중복 제출을 막는다. 오류 시 입력을 보존한다.
- POST /api/requests 성공(201) 시 '요청 상세' 화면으로 이동한다.

WF-03 상세 화면
- GET /api/requests/{id}를 사용하고 제목·설명·요청자·담당자·우선순위·
  상태·생성/수정 시각을 표시한다.
- 제목 heading의 접근 가능한 이름은 '요청 상세'로 한다.
- 로딩·404·네트워크 오류를 구분하고 목록으로 돌아가는 버튼을 제공한다.
- PATCH 수정과 상태 변경은 다음 교시이므로 실제로 작동하는 것처럼 표현하지 않는다.

공통 UI
- design/tokens.json의 색상·간격·타이포그래피·레이아웃 값을 사용하되
  토큰 파일 자체는 변경하지 않는다.
- 상태 received/in_progress/completed는 접수/진행 중/완료,
  우선순위 low/medium/high는 낮음/보통/높음으로 표시한다.
- 명시적인 label, 오류 연결, :focus-visible을 통한 포커스 표시를 제공한다.
- 브라우저 기본 키보드 동작을 유지하고 기존 primary 색상을 사용한다.
- 가능한 한 type-safe한 React 컴포넌트와 API 타입을 작성한다.

구현 파일 예시:
client/src/main.tsx, App.tsx, api.ts, types.ts, labels.ts, styles.css,
client/src/components/RequestList.tsx, RequestForm.tsx, RequestDetail.tsx.
필요하면 client/ 내부에서만 파일을 추가·분리한다.

작업 범위:
- client/만 생성·수정한다. server/, plans/, AGENTS.md,
  docs/, specs/, contracts/, schemas/, design/, tests/, e2e/, scripts/,
  package.json, package-lock.json, index.html, 설정 파일은 변경하지 않는다.
- 의존성 설치, Docker 명령, /reference 접근은 하지 않는다.
- 파일 생성 후 다시 읽어 import/export·API 경로·화면 간 이동을 확인한다.
- 이번 요청에서는 자동 테스트·자동 수정 루프를 수행하지 않는다.
- 생성 파일·구현 기능·다음 교시 미구현 기능을 보고한 뒤 기다려라.
- 삭제·검색·로그인·정렬 변경은 이 프로젝트의 제외 기능이며
  다음 교시의 미구현 과제로 보고하지 않는다.
```

**정상 확인:** `client/src/`에 React 진입점·세 화면과 API 클라이언트가 생성된다. 코드 작성만으로 UI 통합 PASS를 선언하지 않는다.

## 5-8. TypeScript 정적 검사 및 프로덕션 빌드

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    Write-Host '=== Lesson 05 Frontend Verification ==='
    docker compose exec -T hermes sh -lc '
        set -eu
        cd /workspace
        ./node_modules/.bin/tsc --noEmit
        echo "TypeScript Check: PASS"
        npm run build
        echo "Frontend Build: PASS"
        test -f dist/index.html || { echo "dist/index.html missing"; exit 1; }
        echo "Lesson 05 Frontend Verification: PASS"
    '
    $exitCode = $LASTEXITCODE
    Write-Host "Validation Exit Code: $exitCode"
    if ($exitCode -ne 0) { throw 'Frontend 정적 검사 또는 빌드 실패' }
    Write-Host 'Lesson 05 Frontend Check: PASS'
}
```

**정상 확인:** `TypeScript Check: PASS`, `Frontend Build: PASS`, 종료 코드 0. 실패할 경우 고정 계약이 아닌 `client/` 구현 파일만 분석·수정한다.

## 5-9. Backend·Frontend 실행 및 HTTP 연결 확인

아래 블록은 아직 서버가 없다면 기동하고, 이미 실행 중이라면 그대로 사용한다. 잠깐의 초기 기동 지연을 고려하되, 단순히 Vite의 `ready` 메시지만으로 정상 판정하지 않는다. **`hermes` 호스트 허용은 실행 환경변수로 지정**한다. 고정 `vite.config.js`는 수정하지 않는다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    Write-Host '=== Lesson 05 HTTP Startup ==='
    docker compose exec -T hermes sh -lc '
        set -eu
        cd /workspace
        if curl --noproxy "*" -fsS --max-time 3 http://127.0.0.1:3001/api/requests >/dev/null 2>&1; then
            echo "Backend: ALREADY RUNNING"
        else
            nohup node server/index.js >/tmp/lesson05-backend.log 2>&1 </dev/null &
            echo $! >/tmp/lesson05-backend.pid
            echo "Backend: START REQUESTED"
        fi

        # 이전 실습에서 실행한 Vite가 있다면 우선 기존 서버의 hermes 허용 여부를 확인한다.
        vite_ok=0
        if curl --noproxy "*" -fsS --max-time 5 -H "Host: hermes:5173" \
            http://127.0.0.1:5173/ -o /dev/null 2>/dev/null; then
            vite_ok=1
            echo "Frontend: ALREADY RUNNING (hermes allowed)"
        else
            # 기존 Vite가 허용 호스트를 차단하면 소유한 PID로만 종료한다.
            if test -f /tmp/lesson05-frontend.pid; then
                oldpid=$(cat /tmp/lesson05-frontend.pid)
                case "$oldpid" in *[!0-9]*|"") echo "Invalid Vite PID"; exit 1;; esac
                if kill -0 "$oldpid" 2>/dev/null; then
                    cmd=$(ps -p "$oldpid" -o args=)
                    case "$cmd" in
                        *node_modules/.bin/vite*) kill "$oldpid"; echo "Previous Vite process stopped";;
                        *) echo "Unrecognized process: refusing to stop"; exit 1;;
                    esac
                fi
            fi
            export __VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS=hermes
            nohup ./node_modules/.bin/vite --host 0.0.0.0 --port 5173 --strictPort \
                >/tmp/lesson05-frontend.log 2>&1 </dev/null &
            echo $! >/tmp/lesson05-frontend.pid
            echo "Frontend: START REQUESTED"
        fi

        backend_ok=0
        for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
            if curl --noproxy "*" -fsS --max-time 5 http://127.0.0.1:3001/api/requests >/dev/null 2>&1; then
                backend_ok=1; break
            fi
            sleep 1
        done
        if test "$backend_ok" -ne 1; then
            echo "Backend HTTP: FAIL"; tail -n 30 /tmp/lesson05-backend.log 2>/dev/null || true; exit 1
        fi
        echo "Backend HTTP: PASS"

        frontend_ok=0
        for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
            if curl --noproxy "*" -fsS --max-time 10 -H "Host: hermes:5173" \
                http://127.0.0.1:5173/ -o /dev/null 2>/dev/null; then
                frontend_ok=1; break
            fi
            sleep 1
        done
        if test "$frontend_ok" -ne 1; then
            echo "Frontend HTTP: FAIL"; tail -n 40 /tmp/lesson05-frontend.log 2>/dev/null || true; exit 1
        fi
        echo "Frontend HTTP: PASS"
        curl --noproxy "*" -fsS --max-time 10 -H "Host: hermes:5173" \
            http://127.0.0.1:5173/api/requests
        echo
        echo "Vite API Proxy: PASS"
        echo "Lesson 05 HTTP: PASS"
    '
    $exitCode = $LASTEXITCODE
    Write-Host "Validation Exit Code: $exitCode"
    if ($exitCode -ne 0) { throw '애플리케이션 HTTP 연결 실패' }
}
```

**정상 확인:** `Backend HTTP: PASS`, `Frontend HTTP: PASS`, `Vite API Proxy: PASS`. **주의:** 5173 포트가 Windows 호스트에 게시되지 않았으므로 Windows의 `localhost:5173` 브라우저 접속을 전제하지 않는다. Playwright 컨테이너에서 Docker DNS `hermes:5173`을 사용한다.

## 5-10. Chromium 목록·등록 화면 확인

기존 Playwright Runner는 시작 시 `/runner` 파일을 **`/opt/playwright-runtime`**으로 복사한 뒤 npm 의존성을 설치한다. 따라서 `/runner`가 아니라 `/opt/playwright-runtime`에서 브라우저를 실행한다. Runner의 `browser-smoke`는 환경 점검용이며 이 실습의 애플리케이션 E2E가 아니다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    Write-Host '=== Lesson 05 Chromium UI ==='
    $js = @'
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1365,height:900},locale:'ko-KR'});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const response = await page.goto('http://hermes:5173/', {waitUntil:'networkidle',timeout:30000});
    if (!response || response.status() !== 200) throw Error(`Frontend HTTP ${response?.status()}`);
    console.log('Frontend HTTP: PASS');
    await page.getByRole('heading', {name:'AI Work Request Manager 2.0'}).waitFor();
    console.log('List Screen: PASS');
    const r = await page.evaluate(async () => {
      const response = await fetch('/api/requests');
      return {status:response.status,body:await response.json()};
    });
    if (r.status !== 200 || !Array.isArray(r.body.items)) throw Error('API list invalid');
    console.log('Browser API Request: PASS');
    await page.getByRole('button',{name:/요청 등록/}).click();
    await page.getByRole('heading',{name:'새 업무 요청'}).waitFor();
    console.log('Registration Screen: PASS');
    for (const id of ['f-title','f-description','f-requester','f-assignee']) {
      if (await page.locator('#'+id).count() !== 1) throw Error(`Missing field: ${id}`);
    }
    if (await page.locator('input[name="priority"]').count() !== 3)
      throw Error('Expected three priority radio buttons');
    console.log('Registration Fields: PASS');
    if (errors.length) throw Error(errors.join('; '));
    console.log('Browser JavaScript Errors: NONE');
    console.log('Lesson 05 Browser UI: PASS');
  } finally { await browser.close(); }
})().catch(e => { console.error('Lesson 05 Browser UI: FAIL',e); process.exitCode=1; });
'@
    $js | docker compose exec -T -w /opt/playwright-runtime playwright node -
    $exitCode = $LASTEXITCODE
    Write-Host "Validation Exit Code: $exitCode"
    if ($exitCode -ne 0) { throw 'Chromium 화면 검사 실패' }
    Write-Host 'Lesson 05 Chromium Check: PASS'
}
```

**정상 확인:** `List Screen: PASS`, `Registration Screen: PASS`, `Registration Fields: PASS`, `Lesson 05 Chromium Check: PASS`.

## 5-11. Chromium 등록 → 상세 → 목록 복귀 통합 검증

> 이 단계는 **실행 중인 애플리케이션의 로컬 JSON 저장소에 요청 1건을 실제 추가**한다. 삭제 기능은 제외 범위이므로 테스트 후 자동 삭제하지 않는다. 같은 검사를 다시 실행하면 새 요청이 추가된다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    Write-Host '=== Lesson 05 Browser Integration ==='
    $js = @'
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1365,height:900},locale:'ko-KR'});
    const errors = []; page.on('pageerror',e=>errors.push(e.message));
    const title = `브라우저 검증 요청 ${Date.now()}`;
    await page.goto('http://hermes:5173/', {waitUntil:'networkidle',timeout:30000});
    await page.getByRole('button',{name:/요청 등록/}).click();
    await page.getByRole('heading',{name:'새 업무 요청'}).waitFor();
    console.log('Registration Screen: PASS');
    await page.locator('#f-title').fill(title);
    await page.locator('#f-description').fill('제5교시 Chromium 통합 검사');
    await page.locator('#f-requester').fill('교육생');
    await page.locator('#f-assignee').fill('담당자');
    await page.locator('input[name="priority"][value="high"]').check();
    console.log('Form Input: PASS');
    const [response] = await Promise.all([
      page.waitForResponse(r=>r.url().includes('/api/requests') && r.request().method()==='POST'),
      page.locator('form button[type="submit"]').click()
    ]);
    if (response.status()!==201) throw Error(`POST HTTP ${response.status()}`);
    const created = await response.json();
    if (created.title!==title || created.status!=='received') throw Error('Created request mismatch');
    console.log('POST Registration: PASS');
    await page.getByRole('heading',{name:'요청 상세'}).waitFor();
    await page.getByText(title,{exact:true}).waitFor();
    console.log('Detail Screen: PASS');
    await page.getByRole('button',{name:/목록으로/}).first().click();
    await page.getByRole('heading',{name:'AI Work Request Manager 2.0'}).waitFor();
    await page.getByRole('button',{name:title,exact:true}).waitFor();
    console.log('Return to List: PASS');
    if (errors.length) throw Error(errors.join('; '));
    console.log('Browser JavaScript Errors: NONE');
    console.log(`Created Request ID: ${created.id}`);
    console.log('Lesson 05 Browser Integration: PASS');
  } finally { await browser.close(); }
})().catch(e=>{ console.error('Lesson 05 Browser Integration: FAIL',e); process.exitCode=1; });
'@
    $js | docker compose exec -T -w /opt/playwright-runtime playwright node -
    $exitCode = $LASTEXITCODE
    Write-Host "Validation Exit Code: $exitCode"
    if ($exitCode -ne 0) { throw 'Chromium 통합 기능 검사 실패' }
    Write-Host 'Lesson 05 Browser Integration Check: PASS'
}
```

**정상 확인:** `POST Registration: PASS`, `Detail Screen: PASS`, `Return to List: PASS`, `Lesson 05 Browser Integration: PASS`, 종료 코드 0.

## 5-12. 검증 실패 시 제한된 Closed-loop

테스트 실패 시에는 **실제 오류 로그와 실패한 검사만** Hermes Agent에 제공한다. 고정 파일을 수정해서 PASS로 만드는 행위는 허용하지 않는다.

```text
제5교시 구현 검증에서 다음 실패가 발생했다.
[여기에 실행한 명령, 종료 코드, 실제 오류 로그를 붙여 넣는다]

작업 공간: /workspace.
AGENTS.md §2·§3·§6과 두 plans/ 문서를 먼저 읽어라.
1. 실패가 구현 결함인지 실행 환경·검증 도구 문제인지 근거를 구분하라.
2. 고정 명세·테스트와 충돌하는 요청은 임의 수정하지 말고 보고하라.
3. 구현 결함일 때만 현재 승인된 범위의 client/ 또는 server/ 파일을 수정하라.
4. 처음 실패 이후 자동 수정·동일 검증 재실행은 최대 3회로 제한하라.
5. 테스트·계약·스키마·와이어프레임·토큰·AGENTS.md·설정 파일은 수정 금지.
6. 매 반복의 오류 원인, 변경한 구현 파일, 실행한 정확한 테스트, 종료 코드와
   PASS/FAIL을 기록하라. 해결되지 않으면 즉시 중단하고 남은 문제를 보고하라.

Docker·포트 노출 등 인프라 변경은 직접 하지 말고 사용자에게 보고하라.
```

자동 루프를 실행하는 경우에는 Agent가 도구로 해당 테스트를 **실제로 실행할 수 있는 범위**인지 먼저 확인한다. PowerShell에서만 실행 가능한 명령을 Agent가 실행했다고 가장해서는 안 된다.

## 5-13. 제5교시 결과를 다음 Chat에 인계

현재 Hermes Agent Chat에서 아래 프롬프트를 입력한다. `progress.md`, `handoff.md`만 갱신한다.

```text
AI Work Request Manager 2.0 제5교시 구현 및 검증 결과를 다음 Chat에 인계해라.

먼저 AGENTS.md, plans/implementation-plan.md,
plans/verification-plan.md, progress.md, handoff.md를 실제로 읽어라.
기존 이력을 삭제하지 말고 progress.md와 handoff.md 두 파일만 갱신한다.

완료 기록:
- lesson05.zip의 tests/api.test.js를 읽고 createApp({dataFile}) 계약 확인.
- ESM Backend: POST 등록, GET 목록·필터, GET 상세 및 공통 입력 검증·오류·JSON 저장.
- 기본 ./data/requests.json, 상위 디렉터리 생성, rename 원자적 교체,
  손상 파일 보존, 읽기→수정→쓰기 전체 직렬화.
- React/TypeScript UI: WF-01 목록, WF-02 등록, WF-03 읽기 전용 상세.
- 승인된 구현 기준 A·B·C를 유지하며 고정 Baseline은 변경하지 않음.

검증 기록(사용자가 제공한 PowerShell 결과를 근거로 한 것임을 명시):
- Backend API 11/11 PASS, 종료 코드 0.
- TypeScript 정적 검사 PASS, Vite 프로덕션 빌드 PASS.
- Backend·Frontend·API 프록시 HTTP 200.
- Chromium 목록·등록 화면 PASS.
- Chromium 등록 → POST 201 → 상세 → 목록 복귀 PASS, 종료 코드 0.
- 고정 tests/api.test.js 전체는 실행하지 않았음. PASS로 기록 금지.
- 위 검증은 Hermes Agent가 직접 실행한 결과가 아님.

남은 작업:
- 제6교시 REQ-004 상태 변경 PATCH, REQ-005 담당자·우선순위 수정 PATCH,
  상세 화면 수정·상태 변경 UI.
- 고정 API 전체 테스트·영속성 테스트·후속 E2E 검증.
- 로그인·삭제·검색 등 제외 범위는 구현 대상 아님.

다음 Chat 읽기 목록에 AGENTS.md, 요구사항·명세·AC, 두 계획 문서,
progress.md, handoff.md, tests/api.test.js, 현재 client/·server/를 포함하라.
Closed-loop 최대 3회와 고정 테스트 수정 금지 원칙을 인계하라.
두 파일 이외의 생성·수정·삭제는 하지 않는다. /reference·Docker 명령 금지.
갱신한 두 파일을 실제로 다시 읽어 필수 제목과 제5교시 기록을 확인한 뒤 보고하라.
```

## 5-14. 인계 문서 자동 검사

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    $root = 'C:\AI-Native\work-request-manager-v2'
    $script = Join-Path $root 'scripts\verify-handoff.py'
    if (-not (Test-Path -LiteralPath $script -PathType Leaf)) { throw '인계 검사 스크립트 없음' }
    Write-Host '=== Handoff Structure ==='
    Get-Content -Raw -Encoding UTF8 -LiteralPath $script |
        docker compose exec -T hermes python3 - --root /workspace
    if ($LASTEXITCODE -ne 0) { throw '인계 문서 구조 검사 실패' }

    $code = @'
from pathlib import Path
import sys
root=Path('/workspace')
checks={
 'progress.md':['# 프로젝트 진행 상태','제5교시','제6교시','11/11','PATCH'],
 'handoff.md':['# Chat 인계 문서','제5교시','제6교시','implementation-plan.md','verification-plan.md','PATCH']
}
try:
 for name, terms in checks.items():
  s=(root/name).read_text(encoding='utf-8-sig')
  missing=[x for x in terms if x not in s]
  if missing: raise ValueError(f'{name}: missing {missing}')
  h1=[x for x in s.splitlines() if x.startswith('# ')]
  if len(h1)!=1: raise ValueError(f'{name}: expected one H1, found {len(h1)}')
  print(f'{name}: PASS')
 print('Lesson 05 Handoff Content: PASS')
except (OSError,ValueError) as e:
 print(f'Lesson 05 Handoff Content: FAIL - {e}',file=sys.stderr);sys.exit(1)
'@
    $code | docker compose exec -T -w /workspace hermes python3 -
    $exitCode = $LASTEXITCODE
    Write-Host "Validation Exit Code: $exitCode"
    if ($exitCode -ne 0) { throw '제5교시 인계 문서 검증 실패' }
    Write-Host 'Lesson 05 Handoff Check: PASS'
}
```

**정상 확인:** `Handoff structure: PASS`, `progress.md: PASS`, `handoff.md: PASS`, `Lesson 05 Handoff Check: PASS`, 종료 코드 0. 이는 제목과 필수 기록의 존재 여부 검사이며 중복 문장·의미적 모순 전체를 자동 판정하지는 않는다.

## 문제 해결

| 증상 | 확인 및 조치 |
|---|---|
| Starter 설치 시 파일 충돌 | 기존 파일과 ZIP의 SHA-256을 비교한다. 다르면 중단하며 `-Force` 덮어쓰기를 하지 않는다. |
| Node 의존성이 없음 | `/workspace`에서 `npm ci --no-audit --no-fund`로 lockfile 기준 설치. 설치 후 CLI·변환 검사 실시. |
| `Vitest failed to access its internal state` | 일반 `import('vitest')` 검사를 하지 않고 `./node_modules/.bin/vitest --version`으로 실행 가능 여부를 확인한다. |
| `esbuild` 설치 스크립트 경고 | 실제 `esbuild.transform` 실행 검사를 우선 확인한다. 실패 시 환경 문제로 분리한다. |
| `createApp` import 오류 | `package.json`의 `type: module`과 `server/app.js` named export 및 ESM import 경로를 확인한다. |
| 등록 중 ENOENT | 기본 DATA_FILE 경로, 상위 디렉터리 자동 생성, 컨테이너의 쓰기 권한을 확인한다. |
| 동시 등록 후 데이터 수 감소 | `store.mutate()`가 읽기→수정→쓰기 전체를 직렬화하는지 확인한다. |
| 처음 Vite 접속만 시간 초과 | 재시도 후 실제 HTTP 200을 확인한다. `ready` 로그만으로 PASS 처리하지 않는다. |
| Playwright 컨테이너에서 Vite HTTP 403 | `hermes` 호스트 허용 실행 환경변수와 Host 헤더를 확인한다. 고정 Vite 설정 파일은 수정하지 않는다. |
| `/runner`에서 Playwright 모듈을 못 찾음 | 실제 런타임 `/opt/playwright-runtime`에서 Node 실행. 새 설치 전 Runner `start.sh` 확인. |
| `tests/api.test.js` 전체 FAIL | 해당 파일에는 제6교시 PATCH 테스트도 들어 있다. 이번 교시 범위의 독립 검증 결과와 구분한다. 테스트를 수정하지 않는다. |
| Chat 인계 문서 중복 | `verify-handoff.py`는 구조만 검사한다. `progress.md`, `handoff.md`의 최신 상태와 오래된 이력이 모순되지 않는지 별도 읽기 점검한다. |

## 완료 확인

- [ ] 제4교시 산출물과 `lesson05.zip` 고정 테스트가 보존되어 있다.
- [ ] 새로운 Hermes Agent Chat에서 작업 상태 및 고정 테스트 기대값을 복원했다.
- [ ] `server/app.js`의 ESM `createApp({dataFile})`와 등록·목록·상세 API를 구현했다.
- [ ] 임시 데이터 기반 Backend API 독립 검사 11개가 통과했다.
- [ ] WF-01 목록, WF-02 등록, WF-03 읽기 전용 상세 화면을 구현했다.
- [ ] TypeScript 정적 검사와 Vite 프로덕션 빌드가 통과했다.
- [ ] Chromium에서 목록·등록 화면과 등록→상세→목록 흐름을 확인했다.
- [ ] `progress.md`, `handoff.md` 인계 검사가 통과했다.
- [ ] PATCH/상태 변경·전체 고정 API 테스트·후속 E2E는 아직 완료되지 않았다고 기록했다.

**다음 작업:** 기존 작업 공간과 계획·인계 문서를 유지한 채, 다음 교시에서 담당자·우선순위 수정과 상태 변경 기능을 구현한다.

# 제6교시. 요청 수정과 상태 전이 구현

**과정:** Open Weight Model과 Hermes Agent를 활용한 Agent Harness Engineering  
**프로젝트:** AI Work Request Manager 2.0  
**실습 환경:** Windows 11 · PowerShell · Docker Compose · Hermes Agent · OpenRouter GLM-5.3-Flash

## 학습 목표

제5교시의 요청 등록·목록·필터·상세 조회 기능을 유지하면서 담당자·우선순위 수정과 상태 변경·재개 기능을 완성한다. 상세 화면의 라디오 버튼이 가로로 표시되고, Windows 브라우저에서 실제 동작을 확인한다.

| 구성 | 위치 |
|---|---|
| Hermes Compose | `C:\AI-Native\hermes-training-v2` |
| 프로젝트 | `C:\AI-Native\work-request-manager-v2` |
| Starter ZIP | `C:\AI-Native\work-request-manager-distribution\lesson06.zip` |
| Hermes 작업 공간 | `/workspace` |
| Hermes Dashboard | `http://127.0.0.1:9120/` |
| 완성 앱(브라우저) | `http://127.0.0.1:5173/` |

> **변경 통제** — `AGENTS.md`, `docs/`, `specs/`, `contracts/`, `schemas/`, `design/`, `tests/`, `e2e/`, `scripts/`는 수정하지 않는다. 이 교시의 구현은 `server/`, `client/`에서만, 인계 기록은 `progress.md`·`handoff.md`에서만 수행한다. `compose.browser.yaml`은 사용자 관리 Docker 운영 파일로 따로 설치한다. 이미 존재하는 파일은 덮어쓰지 않는다.

> **진행 방식** — 각 단계의 출력과 상태를 확인한 후 다음으로 진행한다. 실행하지 않은 검사는 PASS로 적지 않는다. 실패 시 고정 테스트는 변경하지 않으며, 최초 검증 이후 Hermes Agent 자동 수정·재검증은 최대 세 차례다.

---


## 6-1. Starter 설치 및 기존 기능 확인

### 6-1-1. 경로·서비스·Starter 내용 확인

PowerShell에서 다음 블록 전체를 실행한다. 확인만 수행하며 파일을 변경하지 않는다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $composeDir = 'C:\AI-Native\hermes-training-v2'
    $projectDir = 'C:\AI-Native\work-request-manager-v2'
    $zipPath = Join-Path $HOME 'Downloads\lesson06.zip'
    foreach ($p in @($composeDir, $projectDir, $zipPath)) {
        if (-not (Test-Path -LiteralPath $p)) { throw "경로가 없습니다: $p" }
        Write-Host "[PASS] $p"
    }
    Add-Type -AssemblyName System.IO.Compression
    $archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        $names = @($archive.Entries | Where-Object { $_.Name } | ForEach-Object { $_.FullName.Replace('\','/') })
        $names | ForEach-Object { Write-Host "ZIP: $_" }
        if ($names.Count -ne 1 -or $names[0] -ne 'tests/api-contract.test.js') {
            throw 'Starter 파일 구성이 예상과 다릅니다.'
        }
    } finally { $archive.Dispose() }
    Set-Location -LiteralPath $composeDir
    docker compose ps
    if ($LASTEXITCODE -ne 0) { throw 'Compose 상태 확인 실패' }
}
```

**정상 확인:** `lesson06.zip`에는 `tests/api-contract.test.js`가 하나 포함되어 있으며, `hermes`와 `playwright` 서비스가 실행 중이다.

### 6-1-2. INSTALL / RESUME — 기존 파일 덮어쓰기 방지

ZIP 안의 파일을 신규 설치한다. 기존 파일이 동일하면 그대로 유지하며, 다르면 중단한다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $projectDir = 'C:\AI-Native\work-request-manager-v2'
    $zipPath = Join-Path $HOME 'Downloads\lesson06.zip'
    $target = Join-Path $projectDir 'tests\api-contract.test.js'
    Add-Type -AssemblyName System.IO.Compression
    $zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        $files = @($zip.Entries | Where-Object { $_.Name })
        if ($files.Count -ne 1 -or $files[0].FullName.Replace('\','/') -ne 'tests/api-contract.test.js') {
            throw 'ZIP에 예상하지 않은 항목이 있습니다.'
        }
        $stream = $files[0].Open()
        $memory = [System.IO.MemoryStream]::new()
        try { $stream.CopyTo($memory); $bytes = $memory.ToArray() }
        finally { $stream.Dispose(); $memory.Dispose() }
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try { $expected = [Convert]::ToHexString($sha.ComputeHash($bytes)) }
        finally { $sha.Dispose() }
        if (Test-Path -LiteralPath $target) {
            if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { throw '대상 경로가 일반 파일이 아닙니다.' }
            $actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
            if ($actual -ne $expected) { throw "[CONFLICT] 기존 파일이 달라 중단: $target" }
            Write-Host '[RESUME] 기존 Starter와 동일하므로 유지'
        } else {
            $parent = Split-Path -Parent $target
            if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw 'tests 폴더가 없습니다.' }
            $output = [System.IO.File]::Open($target, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
            try { $output.Write($bytes, 0, $bytes.Length) }
            finally { $output.Dispose() }
            Write-Host '[INSTALL] 고정 계약 테스트 추가'
        }
        if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $expected) { throw '설치 파일 해시 불일치' }
        Write-Host '[PASS] tests/api-contract.test.js SHA-256 검증'
    } finally { $zip.Dispose() }
}
```

### 6-1-3. 기존 API 계약 기준 확인

새로 배포된 테스트는 AC-001, AC-002, AC-004, AC-006, AC-008, AC-013의 6개 사례를 포함한다. 먼저 기존 기능 3개만 확인한다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    docker compose exec -T -w /workspace hermes `
        npm exec -- vitest run tests/api-contract.test.js -t 'AC-001|AC-002|AC-004'
    if ($LASTEXITCODE -ne 0) { throw '기존 API 계약 테스트 실패' }
    Write-Host '[PASS] 기존 계약 테스트 3개'
}
```

**정상 확인:** `3 passed | 3 skipped`.

---

---

## 6-2. Hermes Agent 상태 복원 및 구현

Hermes Dashboard에서 새 Chat을 생성한다.

### 프롬프트 ① — Harness와 인계 문서 복원

```text
AI Work Request Manager 2.0의 제6교시 작업을 시작합니다.
작업 공간: /workspace

이번 요청은 읽기 및 상태 복원만 수행합니다. 코드를 수정하거나 테스트를 실행하지 마세요.

AGENTS.md §4의 읽기 순서를 준수하여 다음 파일을 실제로 읽으세요.
- AGENTS.md, docs/project-overview.md
- specs/requirements.md, docs/specification.md, specs/acceptance-criteria.md
- contracts/openapi.json, schemas/request.schema.json
- design/wireframes.md, design/tokens.json
- plans/implementation-plan.md, plans/verification-plan.md
- progress.md, handoff.md
- tests/api.test.js, tests/api-contract.test.js
- server/의 모든 구현 파일
- client/src/의 모든 구현 파일(styles.css 포함)

보고 내용:
1. 실제 읽은 파일과 읽지 못한 파일
2. 수정 허용·금지 영역과 Closed-loop 최대 3회 규칙
3. 기존 POST/GET, WF-01~03 구현 상태
4. 제6교시 PATCH 2종과 상세 수정 UI 구현 대상 및 순서
5. 상태 전이표, 400/404/409, 동일 값 updatedAt 규칙
6. 해석 충돌 및 확인이 필요한 사항

사용자 승인 기준:
A. 목록 total = 필터 후 items.length
B. 기존 primary 토큰과 기본 키보드 포커스 사용
C. 잘못된 UUID는 400, 형식이 유효하지만 미존재하면 404

현재 테스트 기록: 기존 Backend 독립 검증 11/11, TS·빌드·Chromium 통합 PASS;
새 계약 테스트의 기존 기능 3 PASS / 3 SKIPPED; tests/api.test.js 전체 미실행.
실제 읽거나 실행하지 않은 내용을 확인했다고 보고하지 말고, 상태 복원 보고 후 다음 지시를 기다리세요.
```

**정상 확인:** 에이전트가 변경 금지 영역, 기존 구현, PATCH 범위와 파일별 계획을 보고한다.

### 프롬프트 ② — PATCH API·UI 완성형 구현

상태 복원 보고를 확인한 후 같은 Chat에 입력한다.

```text
AI Work Request Manager 2.0 제6교시 Implementation을 수행하세요.
작업 공간은 /workspace입니다.
앞서 실제 읽은 AGENTS.md, Specification, API 계약, acceptance criteria,
implementation-plan.md, verification-plan.md, progress.md, handoff.md를 기준으로 합니다.

[사전 확인]
- server/store.js의 mutate 인터페이스와 직렬화 큐를 재확인하세요.
- server/routes.js·validate.js·errors.js와 client/src/api.ts의 기존 구현을 재확인하세요.
- client/src/styles.css를 실제 읽고 기존 토큰·반응형 스타일을 따르세요.
- 기존 POST/GET 3개 API, 등록·목록·필터·상세 조회를 보존하세요.

[PATCH /api/requests/:id]
- assignee, priority 중 1개 이상만 받습니다. 빈 본문, 미허용 필드(title 등),
  값·길이·enum 오류는 400 VALIDATION_ERROR입니다.
- 변경 대상 이외의 필드는 유지하고, 성공하면 전체 WorkRequest를 200으로 반환합니다.
- 입력값 정규화(trim) 후 실제 값이 바뀌지 않았다면 updatedAt 문자열을 유지하고
  저장 파일도 재기록하지 마세요.
- 실제 값이 바뀌면 updatedAt을 갱신하세요.
- 잘못된 UUID 형식은 400, 유효하지만 미존재 UUID는 404입니다.

[PATCH /api/requests/:id/status]
- 본문은 status 필드 하나만 허용합니다. 빈 본문, 미허용 필드, 잘못된 enum은 400입니다.
- 허용 전이: received→in_progress, in_progress→completed,
  completed→in_progress(재개).
- 동일 상태 요청은 200 + 기존 updatedAt 유지 + 저장 스킵입니다.
- 나머지 전이는 409 INVALID_TRANSITION이며 원본 파일을 변경하지 마세요.
- UUID 400/404 규칙과 전체 WorkRequest 200 응답을 일관 적용하세요.

[Backend 구현]
- server/validate.js, server/routes.js, 필요하면 server/errors.js를 수정하세요.
- 기존 store.mutate로 읽기→판정→수정→쓰기를 직렬화하세요.
- 기존 mutate가 '변경 없음'을 표현할 수 없다면 server/store.js에
  최소 변경으로 저장 스킵 경로를 추가할 수 있습니다.
- 원자적 저장(임시 파일 + rename), 손상 파일 보호, 오류 포맷을 유지하세요.

[Frontend 구현]
- client/src/types.ts: PATCH 입력 타입
- client/src/api.ts: updateRequest, updateRequestStatus
- client/src/components/RequestDetail.tsx: 제목·설명·요청자·시각 등 읽기 전용 필드,
  담당자 입력, 우선순위 라디오, 저장 버튼, 현재 상태 표시, 허용된 다음 상태 선택,
  상태 변경 버튼, 완료 후 재개.
- 실패 시 입력값 및 기존 상세 데이터 유지, 오류 안내, 중복 제출 방지,
  성공 시 서버 응답으로 화면 갱신.
- 기존 labels.ts의 한국어·enum 대응과 디자인 토큰(primary #2563EB),
  키보드 포커스, 모바일 반응형 구조를 유지하세요.
- **우선순위 라디오 가로 정렬을 최초 구현에서 완성하세요(추가 수정 단계로 미루지 말 것).**
  전역 `.field input { width:100% }`가 radio에도 적용되는 문제를 방지합니다.
  `RequestDetail.tsx`의 우선순위 `<div role="radiogroup">`에
  `className="priority-group"`을 지정하고 라벨 인라인 스타일은 사용하지 않습니다.
  `styles.css`에 다음과 같이 **상세 패널 범위로 한정된 규칙**을 적용하세요.
  `.detail-panel .priority-group { display:flex; flex-wrap:wrap; align-items:center; gap:var(--s-3); }`
  `.detail-panel .priority-group label { display:inline-flex; align-items:center; gap:var(--s-2); white-space:nowrap; flex-shrink:0; margin-right:0; font-weight:400; }`
  `.detail-panel .priority-group input[type="radio"] { width:auto; flex-shrink:0; margin:0; accent-color:var(--c-primary); }`
  라벨 텍스트(`낮음`, `보통`, `높음`)가 세로로 갈라지지 않아야 하며,
  좁은 화면에서는 라디오+문구 한 단위로 줄바꿈하고 Tab/방향키 조작을 유지하세요.
- 필요할 때만 client/src/styles.css를 수정하세요.
- 제6교시 구현 예정이라는 임시 안내 문구를 삭제하세요.

[변경 통제]
AGENTS.md와 docs/, specs/, contracts/, schemas/, design/, tests/, e2e/, scripts/는
수정 금지입니다. package.json, vite.config.js 등 허용되지 않은 경로도 변경하지 마세요.
명세 충돌이 있으면 임의 수정하지 말고 보고하세요.

[검증 통제]
이번 요청은 코드 구현과 정적 검토까지만 합니다.
npm test, Vitest, Playwright, 자동 수정·재검증 반복은 실행하지 마세요.
progress.md와 handoff.md는 아직 수정하지 마세요.

결과 보고: 변경한 파일, Backend/Frontend 구현, 무변경 저장 스킵 방식,
기존 기능 보존 방식, 아직 실행하지 않은 검증, 남은 위험과 충돌 여부.
```

**정상 확인:** 수정 범위는 주로 `server/errors.js`, `server/validate.js`, `server/store.js`, `server/routes.js`, `client/src/types.ts`, `client/src/api.ts`, `client/src/components/RequestDetail.tsx`, `client/src/styles.css`이다. 고정 테스트를 수정하거나 임의의 새 기능을 추가하지 않는다.

---

---

## 6-3. 소스 반영과 개발 서버 확인

Hermes Agent가 소스 수정을 마친 다음 **실행 중인 서버가 새 구현을 사용하도록 갱신**한다. Node.js Backend는 자동 재시작되지 않으며, Windows 바인드 마운트 환경에서는 Vite의 파일 변경 감지가 누락될 수 있다. Vite는 HMR을 지원하므로 무조건 재시작할 필요는 없다. 다음 명령은 응답을 확인해 필요한 서버만 갱신한다.

### 6-3-1. Backend/Vite 실제 응답 확인

아래 명령은 저장 데이터를 변경하지 않는다. 기존 백엔드에 새 PATCH 라우트가 로드되었는지 유효하지만 존재하지 않는 UUID로 확인한다. 응답의 **404 코드만** 보고 판단하지 말고, 새 라우트에서 정의한 본문 메시지를 함께 확인한다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    docker compose exec -T -w /workspace hermes node --input-type=module -e '
      const base = "http://127.0.0.1";
      const id = "00000000-0000-4000-8000-000000000000";
      const cases = [
        { name: "API list", url: `${base}:3001/api/requests`, method: "GET" },
        { name: "PATCH route", url: `${base}:3001/api/requests/${id}`, method: "PATCH", body: { assignee: "진단 담당자" } },
        { name: "PATCH status", url: `${base}:3001/api/requests/${id}/status`, method: "PATCH", body: { status: "in_progress" } },
        { name: "Vite", url: `${base}:5173/`, method: "GET" },
        { name: "Detail UI module", url: `${base}:5173/client/src/components/RequestDetail.tsx`, method: "GET" },
        { name: "UI CSS module", url: `${base}:5173/client/src/styles.css`, method: "GET" }
      ];
      let ready = true;
      for (const c of cases) {
        try {
          const r = await fetch(c.url, {
            method: c.method,
            ...(c.body ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(c.body) } : {})
          });
          const content = await r.text();
          const ok = c.name === "API list" || c.name === "Vite"
            ? r.status === 200
            : c.name === "PATCH route" || c.name === "PATCH status"
              ? r.status === 404 && JSON.parse(content).error?.message === "요청을 찾을 수 없습니다."
              : r.status === 200 && content.includes("priority-group");
          console.log(`[${ok ? "PASS" : "CHECK"}] ${c.name}: HTTP ${r.status}`);
          if (!ok) ready = false;
        } catch (error) {
          console.log(`[CHECK] ${c.name}: ${error.message}`);
          ready = false;
        }
      }
      if (!ready) process.exitCode = 1;
    '
    if ($LASTEXITCODE -eq 0) {
        Write-Host '[PASS] 현재 서버에서 최신 기능 제공' -ForegroundColor Green
    } else {
        Write-Host '[CHECK] 다음 재시작 절차에서 필요한 서버만 갱신하세요.' -ForegroundColor Yellow
    }
}
```

**결과 해석:** 모든 항목 PASS라면 다음 서버 재시작 단계는 건너뛴다. Backend PATCH 두 항목만 CHECK라면 6-3-2, Vite UI 모듈만 CHECK라면 6-3-3을 수행한다. API 연결 자체가 실패하면 프로세스 및 Compose 상태를 먼저 확인한다.

### 6-3-2. Backend 프로세스 안전 재시작 (필요한 경우)

기존 Backend를 **하나만 정확히 식별**한 후 종료하고 재실행한다. 종료되지 않으면 재실행하지 않는다. `data/requests.json`을 지우거나 초기화하지 않는다. `DATA_FILE` 환경변수로 별도 저장 경로를 사용하는 경우에는 그 설정을 먼저 확인한다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    $script = @'
const { execFileSync, spawn } = require("node:child_process");
const fs = require("node:fs");
const base = "http://127.0.0.1:3001";
const lines = execFileSync("ps", ["-eo", "pid=,args="], { encoding: "utf8" }).split("\n");
const pids = lines.map(line => line.trim().match(/^(\d+)\s+node server\/index\.js$/)).filter(Boolean).map(m => Number(m[1]));
(async () => {
  if (pids.length > 1) throw new Error(`Backend ${pids.length}개 발견: 수동 확인 필요`);
  if (pids.length === 1) {
    process.kill(pids[0], "SIGTERM");
    let stopped = false;
    for (let i = 0; i < 40; i++) {
      try { process.kill(pids[0], 0); }
      catch (e) { if (e.code === "ESRCH") { stopped = true; break; } throw e; }
      await new Promise(r => setTimeout(r, 100));
    }
    if (!stopped) throw new Error("기존 Backend 종료 미확인 — 중복 시작 금지");
    console.log("[PASS] 이전 Backend 종료");
  } else {
    console.log("[INFO] 기존 Backend 프로세스 없음");
  }
  const child = spawn(process.execPath, ["server/index.js"], { cwd: "/workspace", detached: true, stdio: "ignore" });
  child.unref();
  let ready = false;
  for (let i = 0; i < 30; i++) {
    try {
      const r = await fetch(`${base}/api/requests`);
      if (r.status === 200) { ready = true; break; }
    } catch {}
    await new Promise(r => setTimeout(r, 500));
  }
  if (!ready) throw new Error("Backend 재기동 후 HTTP 200 확인 실패");
  console.log("[PASS] Backend HTTP 200");
})().catch(e => { console.error("[FAIL]", e.message); process.exitCode = 1; });
'@
    $script | docker compose exec -T -w /workspace hermes `
        node -e 'let s="";process.stdin.setEncoding("utf8");process.stdin.on("data",c=>s+=c);process.stdin.on("end",()=>{require("vm").runInThisContext(s)})'
    if ($LASTEXITCODE -ne 0) { throw 'Backend 재시작 실패 — 다시 시작하지 말고 로그 확인' }
}
```

### 6-3-3. Vite 개발 서버 안전 재시작 (필요한 경우)

Vite는 일반적으로 HMR로 소스 변경을 반영한다. **모듈 제공 검사에서 최신 JSX/CSS가 보이지 않을 때만** 다음을 실행한다. 이미 실행 중인 Vite 프로세스를 먼저 종료하며 종료 확인 전 새 프로세스를 만들지 않는다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    $stopScript = @'
const { execFileSync } = require("node:child_process");
const output = execFileSync("ps", ["-eo", "pid=,args="], { encoding: "utf8" });
const pids = output.split("\n").map(line => line.trim().match(/^(\d+)\s+node (?:\.?\/)?(?:workspace\/)?node_modules\/\.bin\/vite --host 0\.0\.0\.0 --port 5173 --strictPort$/)).filter(Boolean).map(x => Number(x[1]));
(async () => {
  if (pids.length > 1) throw new Error(`Vite ${pids.length}개 확인: 중단`);
  if (pids.length === 1) {
    process.kill(pids[0], "SIGTERM");
    let stopped = false;
    for (let i = 0; i < 40; i++) {
      try { process.kill(pids[0], 0); }
      catch (e) { if (e.code === "ESRCH") { stopped = true; break; } throw e; }
      await new Promise(r => setTimeout(r, 100));
    }
    if (!stopped) throw new Error("Vite 종료 미확인 — 새 프로세스 시작 금지");
    console.log("[PASS] 기존 Vite 종료");
  } else console.log("[INFO] 기존 Vite 프로세스 없음");
})().catch(e => { console.error("[FAIL]", e.message); process.exitCode = 1; });
'@
    $stopScript | docker compose exec -T -w /workspace hermes `
        node -e 'let s="";process.stdin.setEncoding("utf8");process.stdin.on("data",c=>s+=c);process.stdin.on("end",()=>{require("vm").runInThisContext(s)})'
    if ($LASTEXITCODE -ne 0) { throw 'Vite 중단 실패' }

    docker compose exec -T -d -w /workspace hermes `
        npm run dev:client -- --port 5173 --strictPort
    if ($LASTEXITCODE -ne 0) { throw 'Vite 실행 실패' }

    docker compose exec -T -w /workspace hermes node --input-type=module -e '
      let ready = false;
      for (let i = 0; i < 20; i++) {
        try {
          const [js, css] = await Promise.all([
            fetch("http://127.0.0.1:5173/client/src/components/RequestDetail.tsx"),
            fetch("http://127.0.0.1:5173/client/src/styles.css")
          ]);
          const [j, c] = await Promise.all([js.text(), css.text()]);
          ready = js.ok && css.ok && j.includes("priority-group") && c.includes(".detail-panel .priority-group");
          if (ready) break;
        } catch {}
        await new Promise(r => setTimeout(r, 1000));
      }
      console.log(ready ? "[PASS] Vite 최신 UI 반영" : "[FAIL] Vite 최신 UI 미반영");
      if (!ready) process.exitCode = 1;
    '
    if ($LASTEXITCODE -ne 0) { throw 'Vite 최신 모듈 검사 실패' }
}
```

**안내:** 서버를 재시작해도 Docker Compose 서비스 전체를 재생성하지 않는다. 기존 Hermes Dashboard, Playwright 및 저장 데이터를 그대로 유지한다. Vite 실행 명령이나 프로세스 패턴이 다른 환경에서는 임의로 종료하지 말고 실행 프로세스를 확인한다.


---

## 6-4. 고정 API 및 정적 검사

### 6-4-1. 고정 API 테스트 전체

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    docker compose exec -T -w /workspace hermes npm test
    if ($LASTEXITCODE -ne 0) { throw '고정 API 테스트 실패' }
    Write-Host '[PASS] 고정 API 테스트 전체'
}
```

**정상 확인:** `tests/api.test.js` 11개, `tests/api-contract.test.js` 6개, 총 **17 passed**. 실패하면 테스트 파일을 수정하지 않고 구현 코드와 오류 로그를 비교한다. 최초 검증 이후 에이전트가 자동 수정·재검증하는 횟수는 최대 3회다.

### 6-4-2. TypeScript 검사와 Vite 프로덕션 빌드

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    docker compose exec -T -w /workspace hermes npm exec -- tsc --noEmit
    if ($LASTEXITCODE -ne 0) { throw 'TypeScript 검사 실패' }
    docker compose exec -T -w /workspace hermes npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Vite 빌드 실패' }
    Write-Host '[PASS] TypeScript + Vite Build'
}
```

**정상 확인:** TypeScript 오류가 없고 Vite가 `dist/` 산출물을 생성한다.

---

## 6-5. Windows 브라우저 접속 설정 및 확인

Hermes 컨테이너의 기본 포트 공개는 Dashboard `127.0.0.1:9120 → 9119`뿐이다. Windows의 `localhost:5173`으로 접속하려면 브라우저 프록시용 서비스가 필요하다. 기존 `compose.yaml`은 그대로 두고 `compose.browser.yaml`을 분리한다.

### 6-5-1. compose.browser.yaml INSTALL / RESUME

기존 파일이 있으면 본문을 비교한다. 내용이 같으면 유지하고 다르면 **중단**한다. 변경된 기존 파일을 덮어쓰지 않는다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    $path = Join-Path (Get-Location).Path 'compose.browser.yaml'
    $yaml = @'
services:
  app-preview:
    image: mcr.microsoft.com/playwright:v1.58.2-noble
    restart: "no"
    entrypoint:
      - node
      - -e
    command:
      - |
        const net = require('node:net');
        net.createServer(client => {
          const upstream = net.connect(5173, 'hermes');
          client.pipe(upstream);
          upstream.pipe(client);
          client.on('error', () => upstream.destroy());
          upstream.on('error', () => client.destroy());
        }).listen(5173, '0.0.0.0');
    ports:
      - "127.0.0.1:5173:5173"
    mem_limit: 128m
    cpus: 0.25
'@
    if (Test-Path -LiteralPath $path) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw '[CONFLICT] 대상이 파일이 아닙니다.' }
        $current = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        $normalizedCurrent = ($current -replace "`r`n", "`n").TrimEnd([char[]]@([char]13, [char]10))
        $normalizedExpected = ($yaml -replace "`r`n", "`n").TrimEnd([char[]]@([char]13, [char]10))
        if ($normalizedCurrent -cne $normalizedExpected) {
            throw '[CONFLICT] compose.browser.yaml 내용이 다릅니다. 덮어쓰지 않습니다.'
        }
        Write-Host '[RESUME] 기존 브라우저 Compose 파일 유지'
    } else {
        $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($yaml + "`n")
        $stream = [System.IO.File]::Open($path, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
        Write-Host '[INSTALL] compose.browser.yaml 생성'
    }
    docker compose -f compose.yaml -f compose.browser.yaml config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Compose 설정 검사 실패' }
    Write-Host '[PASS] Compose 설정 정상'
}
```

### 6-5-2. app-preview 서비스만 실행하고 Windows 연결 확인

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    docker compose -f compose.yaml -f compose.browser.yaml up -d --no-deps app-preview
    if ($LASTEXITCODE -ne 0) { throw 'app-preview 실행 실패' }
    docker compose -f compose.yaml -f compose.browser.yaml ps app-preview
    if ($LASTEXITCODE -ne 0) { throw 'app-preview 상태 확인 실패' }
    $response = Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -TimeoutSec 10
    if ($response.StatusCode -ne 200 -or $response.Content -notmatch 'AI Work Request Manager') {
        throw 'Windows 웹 접속 또는 HTML 제목 확인 실패'
    }
    Write-Host '[PASS] Windows Frontend HTTP 200'
}
```

브라우저에서 `http://127.0.0.1:5173/`을 연다. 목록 화면에서 새 요청 등록, 상세 화면의 담당자·우선순위 수정, 상태 변경, 완료 후 재개를 직접 확인한다. **브라우저에서 저장을 누르면 실제 프로젝트 저장 데이터가 변경**된다.

**주의:** `docker compose config`는 Dashboard 인증 비밀값을 출력할 수 있으므로 결과를 공유할 때에는 `config --quiet`를 사용한다. 서비스 확인은 비밀정보가 출력되지 않는 `docker compose ps`로 수행한다.


---

## 6-6. 브라우저 인터페이스 및 기능 검증

### 6-6-1. Chromium 상세 UI·키보드 회귀 검사

이 검사는 **실제 데이터를 저장하지 않는다.** 라디오 버튼의 브라우저 내부 선택 상태만 바꾸고 저장 버튼은 누르지 않는다. 기존 요청이 없으면 6-5에서 먼저 한 건을 등록한다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    $script = @'
const { chromium } = require("playwright");
const dns = require("node:dns").promises;
const assert = require("node:assert/strict");

(async () => {
  const addresses = await dns.lookup("hermes", { all: true });
  const ipv4 = addresses.find(a => a.family === 4);
  if (!ipv4) throw new Error("Hermes IPv4 not found");
  const baseURL = `http://${ipv4.address}:5173`;
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    const errors = [];
    page.on("pageerror", e => errors.push(e.message));
    const response = await page.request.get(`${baseURL}/api/requests`);
    assert.equal(response.status(), 200);
    const data = await response.json();
    assert.ok(Array.isArray(data.items) && data.items.length > 0, "검사할 요청이 없습니다");
    const item = data.items[0];
    const home = await page.goto(baseURL, { waitUntil: "networkidle", timeout: 30000 });
    assert.equal(home.status(), 200);
    await page.getByRole("button", { name: item.title, exact: true }).first().click();
    const group = page.locator(".detail-panel .priority-group");
    await group.waitFor({ state: "visible", timeout: 10000 });
    const labels = group.locator("label");
    const metrics = await labels.evaluateAll(nodes => nodes.map(node => {
      const rect = node.getBoundingClientRect();
      const radio = node.querySelector('input[type="radio"]');
      return {
        text: node.innerText.trim(), x: rect.x, y: rect.y,
        width: rect.width, height: rect.height,
        whiteSpace: getComputedStyle(node).whiteSpace,
        radioWidth: radio.getBoundingClientRect().width
      };
    }));
    console.log("Priority layout:", metrics);
    const checks = {
      threeLabels: metrics.length === 3,
      noLabelWrap: metrics.every(m => m.whiteSpace === "nowrap" && m.height < 40),
      horizontalLayout: metrics.every((m, i) => i === 0 || (Math.abs(m.y - metrics[0].y) < 3 && m.x > metrics[i - 1].x)),
      normalRadioWidth: metrics.every(m => m.radioWidth > 0 && m.radioWidth < 40),
      saveButton: await page.getByRole("button", { name: "저장", exact: true }).count() === 1,
      statusButton: await page.getByRole("button", { name: "상태 변경", exact: true }).count() === 1,
      noPageErrors: errors.length === 0
    };
    await group.locator('input[value="low"]').focus();
    await page.keyboard.press("ArrowRight");
    const checkedAfter = await group.locator('input[type="radio"]').evaluateAll(nodes => nodes.find(n => n.checked)?.value);
    checks.keyboardSelection = checkedAfter === "medium";
    for (const [key, ok] of Object.entries(checks)) console.log(`[${ok ? "PASS" : "FAIL"}] ${key}`);
    assert.ok(Object.values(checks).every(Boolean), "UI 회귀 검사 실패");
    console.log("[PASS] 8/8 UI checks");
  } finally { await browser.close(); }
})().catch(error => { console.error("[FAIL]", error.stack || error.message); process.exitCode = 1; });
'@
    $script | docker compose exec -T playwright `
        node -e 'let s="";process.stdin.setEncoding("utf8");process.stdin.on("data",c=>s+=c);process.stdin.on("end",()=>{require("vm").runInThisContext(s)})'
    if ($LASTEXITCODE -ne 0) { throw 'Chromium UI 회귀 검사 실패' }
}
```

**정상 확인:** 8/8 PASS. 폭이 작은 브라우저에서도 라디오 버튼과 한글 문구가 서로 분리되지 않는지 육안으로 확인한다.


### 6-6-2. Chromium 기능 통합 검사 — 수정부터 재개까지

이 명령은 **테스트용 요청을 실제 저장소에 1건 추가**한다. 기존 요청은 수정하거나 삭제하지 않는다. Playwright 컨테이너가 Vite에 접속할 때에는 Docker DNS로 `hermes`의 IP를 조회한다. 컨테이너 IP를 고정하지 않는다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    $script = @'
const { chromium } = require("playwright");
const dns = require("node:dns").promises;
const assert = require("node:assert/strict");

(async () => {
  const addresses = await dns.lookup("hermes", { all: true });
  const ipv4 = addresses.find(a => a.family === 4);
  if (!ipv4) throw new Error("Hermes IPv4 not found");
  const baseURL = `http://${ipv4.address}:5173`;
  const browser = await chromium.launch({ headless: true });
  let passed = 0;
  const pass = name => console.log(`[PASS ${++passed}] ${name}`);

  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    const pageErrors = [];
    page.on("pageerror", e => pageErrors.push(e.message));
    const title = `제6교시 E2E ${Date.now()}`;
    const createdResponse = await page.request.post(`${baseURL}/api/requests`, {
      data: {
        title, description: "제6교시 수정·상태 변경 검사",
        requester: "E2E 테스트", assignee: "기존 담당자", priority: "high"
      }
    });
    assert.equal(createdResponse.status(), 201);
    const created = await createdResponse.json();
    assert.equal(created.status, "received");
    pass("테스트 요청 생성");

    const home = await page.goto(baseURL, { waitUntil: "networkidle", timeout: 30000 });
    assert.equal(home.status(), 200);
    await page.getByRole("button", { name: title, exact: true }).first().click();
    await page.locator("#d-assignee").waitFor({ state: "visible", timeout: 10000 });
    assert.equal(await page.locator("#d-assignee").inputValue(), "기존 담당자");
    pass("상세 화면 진입");

    await page.locator("#d-assignee").fill("변경 담당자");
    await page.locator('input[name="detail-priority"][value="low"]').check();
    const savePromise = page.waitForResponse(r =>
      r.request().method() === "PATCH" &&
      new URL(r.url()).pathname === `/api/requests/${created.id}`
    );
    await page.getByRole("button", { name: "저장", exact: true }).click();
    const saveResponse = await savePromise;
    assert.equal(saveResponse.status(), 200);
    const saved = await saveResponse.json();
    assert.equal(saved.assignee, "변경 담당자");
    assert.equal(saved.priority, "low");
    assert.equal(saved.title, created.title);
    assert.equal(saved.createdAt, created.createdAt);
    await page.waitForFunction(() => {
      const input = document.querySelector("#d-assignee");
      const radio = document.querySelector('input[name="detail-priority"][value="low"]');
      return input?.value === "변경 담당자" && radio?.checked === true;
    }, null, { timeout: 10000 });
    pass("담당자·우선순위 UI 수정");

    async function detail() {
      const response = await page.request.get(`${baseURL}/api/requests/${created.id}`);
      assert.equal(response.status(), 200);
      return response.json();
    }
    const stored = await detail();
    assert.equal(stored.assignee, "변경 담당자");
    assert.equal(stored.priority, "low");
    assert.equal(stored.status, "received");
    pass("수정 결과 API 저장 확인");

    async function transition(status, name) {
      await page.locator("#d-next-status").selectOption(status);
      const button = page.getByRole("button", { name: "상태 변경", exact: true });
      assert.equal(await button.isEnabled(), true);
      const responsePromise = page.waitForResponse(r =>
        r.request().method() === "PATCH" &&
        new URL(r.url()).pathname === `/api/requests/${created.id}/status`
      );
      await button.click();
      const response = await responsePromise;
      assert.equal(response.status(), 200);
      assert.equal((await response.json()).status, status);
      await page.waitForFunction(expected => {
        const select = document.querySelector("#d-next-status");
        return select?.value === "" &&
          ![...select.options].some(o => o.value === expected);
      }, status, { timeout: 10000 });
      assert.equal((await detail()).status, status);
      pass(name);
    }
    await transition("in_progress", "접수 → 진행 중");
    await transition("completed", "진행 중 → 완료");
    await transition("in_progress", "완료 → 진행 중 재개");

    await page.getByRole("button", { name: /목록으로/ }).click();
    await page.getByRole("button", { name: title, exact: true }).first()
      .waitFor({ state: "visible", timeout: 10000 });
    const finalItem = await detail();
    assert.equal(finalItem.status, "in_progress");
    assert.equal(finalItem.assignee, "변경 담당자");
    assert.equal(finalItem.priority, "low");
    pass("목록 복귀와 최종 데이터 확인");
    assert.deepEqual(pageErrors, []);
    pass("브라우저 JavaScript 오류 없음");
    console.log("Final request ID:", finalItem.id);
    console.log(`[PASS] ${passed}/9 Chromium checks`);
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error("[FAIL]", error.stack || error.message);
  process.exitCode = 1;
});
'@
    $script | docker compose exec -T playwright `
        node -e 'let s="";process.stdin.setEncoding("utf8");process.stdin.on("data",c=>s+=c);process.stdin.on("end",()=>{require("vm").runInThisContext(s)})'
    if ($LASTEXITCODE -ne 0) { throw 'Chromium 통합 검사 실패' }
    Write-Host '[PASS] Chromium E2E'
}
```


```powershell 위 코드 에러시 요걸로 1
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'

    Write-Host "`n=== Lesson 6 Detail UI Diagnosis ===" -ForegroundColor Cyan

    docker compose exec -T -w /workspace hermes sh -lc '
        echo "=== RequestDetail source ==="
        grep -nE "d-assignee|d-next-status|detail-priority|RequestDetail|상태 변경" \
            client/src/components/RequestDetail.tsx || true

        echo "=== App source ==="
        grep -nE "RequestDetail|selected|detail|onSelect" \
            client/src/App.tsx || true
    '

    if ($LASTEXITCODE -ne 0) {
        throw 'Source inspection failed'
    }

    $js = @'
const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", e => errors.push(e.message));

    await page.goto("http://hermes:5173/", {
      waitUntil:"networkidle",
      timeout:30000
    });

    console.log("=== Page headings ===");
    console.log(await page.locator("h1,h2,h3").allTextContents());

    console.log("=== Buttons ===");
    console.log((await page.getByRole("button").allTextContents()).slice(0,20));

    console.log("=== Detail elements before click ===");
    console.log(await page.locator("#d-assignee").count());

    console.log("=== Request buttons ===");
    console.log((await page.getByRole("button").allTextContents()).slice(0,30));

    const requestButtons = page.getByRole("button", {
      name:/제6교시 E2E/
    });

    console.log("Matching requests:", await requestButtons.count());

    if (await requestButtons.count() > 0) {
      await requestButtons.first().click();
      await page.waitForTimeout(1000);

      console.log("=== After click ===");
      console.log("Headings:", await page.locator("h1,h2,h3").allTextContents());
      console.log("Inputs:", await page.locator("input").evaluateAll(
        els => els.map(e => ({
          id:e.id,
          name:e.name,
          type:e.type
        }))
      ));
      console.log("Detail field count:", await page.locator("#d-assignee").count());
      console.log("Alerts:", await page.getByRole("alert").allTextContents());
    }

    console.log("Page errors:", errors);
  } finally {
    await browser.close();
  }
})().catch(e => {
  console.error(e.stack || e.message);
  process.exitCode=1;
});
'@

    $js | docker compose exec -T -w /opt/playwright-runtime playwright `
        node -e 'let s="";process.stdin.setEncoding("utf8");process.stdin.on("data",c=>s+=c);process.stdin.on("end",()=>{require("vm").runInThisContext(s)})'

    if ($LASTEXITCODE -ne 0) {
        throw 'Detail UI diagnosis failed'
    }

    Write-Host "`n[PASS] Detail UI diagnosis completed" -ForegroundColor Green
}
```

``` html 확인하기
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'

    Write-Host "`n=== Lesson 6 UI Selector Check ===" -ForegroundColor Cyan

    docker compose exec -T -w /workspace hermes sh -lc '
        echo "=== Assignee ==="
        grep -n -C 3 "detail-assignee" client/src/components/RequestDetail.tsx

        echo "=== Status Select ==="
        grep -n -C 5 "<select" client/src/components/RequestDetail.tsx

        echo "=== Status Buttons ==="
        grep -n -C 3 "상태 변경" client/src/components/RequestDetail.tsx | tail -n 25

        echo "=== Navigation ==="
        grep -n -C 3 "목록으로" client/src/components/RequestDetail.tsx
    '

    if ($LASTEXITCODE -ne 0) {
        throw 'Selector inspection failed'
    }

    Write-Host "`n[PASS] UI selector inspection" -ForegroundColor Green
}
```

``` 수정하는 코드
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'

    Write-Host "`n=== Lesson 6 Chromium E2E ===" -ForegroundColor Cyan

    $script = @'
const { chromium } = require("playwright");
const assert = require("node:assert/strict");

(async () => {
  const browser = await chromium.launch({ headless: true });
  let passed = 0;
  const pass = name => console.log(`[PASS ${++passed}] ${name}`);

  try {
    const page = await browser.newPage({
      viewport: { width: 1280, height: 800 }
    });

    const errors = [];
    page.on("pageerror", e => errors.push(e.message));

    const baseURL = "http://hermes:5173";
    const title = `제6교시 E2E ${Date.now()}`;

    const response = await page.request.post(`${baseURL}/api/requests`, {
      data: {
        title,
        description: "제6교시 수정 및 상태 전이 검증",
        requester: "E2E 테스트",
        assignee: "기존 담당자",
        priority: "high"
      }
    });

    assert.equal(response.status(), 201);
    const created = await response.json();
    assert.equal(created.status, "received");
    pass("테스트 요청 생성");

    await page.goto(baseURL, {
      waitUntil: "networkidle",
      timeout: 30000
    });

    await page.getByRole("button", {
      name: title,
      exact: true
    }).click();

    await page.locator("#detail-assignee").waitFor();
    pass("상세 화면 진입");

    await page.locator("#detail-assignee").fill("변경 담당자");

    await page.locator(
      'input[name="detail-priority"][value="low"]'
    ).check();

    const saveResponse = page.waitForResponse(r =>
      r.request().method() === "PATCH" &&
      new URL(r.url()).pathname === `/api/requests/${created.id}`
    );

    await page.getByRole("button", {
      name: "저장",
      exact: true
    }).click();

    const saved = await saveResponse;
    assert.equal(saved.status(), 200);

    const updated = await saved.json();
    assert.equal(updated.assignee, "변경 담당자");
    assert.equal(updated.priority, "low");
    pass("담당자 및 우선순위 수정");

    async function getDetail() {
      const r = await page.request.get(
        `baseURL/api/requests/{created.id}`
      );
      assert.equal(r.status(), 200);
      return r.json();
    }

    let detail = await getDetail();
    assert.equal(detail.assignee, "변경 담당자");
    assert.equal(detail.priority, "low");
    pass("수정 결과 저장 확인");

    async function transition(status, name) {
      await page.locator("#detail-status").selectOption(status);

      const responsePromise = page.waitForResponse(r =>
        r.request().method() === "PATCH" &&
        new URL(r.url()).pathname ===
          `/api/requests/${created.id}/status`
      );

      await page.getByRole("button", {
        name: "상태 변경",
        exact: true
      }).click();

      const r = await responsePromise;
      assert.equal(r.status(), 200);

      const result = await r.json();
      assert.equal(result.status, status);

      await page.waitForFunction(expected => {
        const select = document.querySelector("#detail-status");
        return select && select.value !== expected;
      }, status);

      detail = await getDetail();
      assert.equal(detail.status, status);
      pass(name);
    }

    await transition("in_progress", "접수 → 진행 중");
    await transition("completed", "진행 중 → 완료");
    await transition("in_progress", "완료 → 진행 중 재개");

    await page.getByRole("button", {
      name: "목록으로"
    }).click();

    await page.getByRole("button", {
      name: title,
      exact: true
    }).waitFor();

    detail = await getDetail();
    assert.equal(detail.status, "in_progress");
    assert.equal(detail.assignee, "변경 담당자");
    assert.equal(detail.priority, "low");
    pass("목록 복귀 및 최종 데이터");

    assert.deepEqual(errors, []);
    pass("JavaScript 오류 없음");

    console.log(`Final request ID: ${created.id}`);
    console.log(`[PASS] ${passed}/9 Chromium checks`);

  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error("[FAIL]", error.stack || error.message);
  process.exitCode = 1;
});
'@

    $script | docker compose exec -T -w /opt/playwright-runtime playwright `
        node -e 'let s="";process.stdin.setEncoding("utf8");process.stdin.on("data",c=>s+=c);process.stdin.on("end",()=>{require("vm").runInThisContext(s)})'

    if ($LASTEXITCODE -ne 0) {
        throw 'Lesson 6 Chromium E2E failed'
    }

    Write-Host "`n[PASS] Lesson 6 Chromium E2E" -ForegroundColor Green
}
```

**정상 확인:** 9개 항목 전부 PASS. 새로 생성된 요청의 ID는 다음 영속성 검증에서 사용할 수 있다.

---

## 6-7. 데이터 영속성과 손상 파일 보호

**운영 파일 백업 및 저장 경로를 확인한다.** `DATA_FILE`을 지정한 경우 검증 명령의 기본 경로 가정을 반드시 확인한다.

### 6-7-1. 서버 재시작 후 데이터 유지 (AC-009)

다음 명령은 **Backend 프로세스만 재시작**한다. 다른 프로세스와 데이터 파일은 유지한다. 재시작 전에 API 목록과 저장 파일 해시를 보관하고, 재시작 후 비교한다. 실습 중 다른 사람이 동시에 데이터를 변경하지 않는 환경에서 실행한다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    $script = @'
const fs = require("node:fs");
const crypto = require("node:crypto");
const { execFileSync, spawn } = require("node:child_process");
const base = "http://127.0.0.1:3001";
const file = "/workspace/data/requests.json";
const hash = () => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
async function list() {
  const r = await fetch(`${base}/api/requests`);
  if (!r.ok) throw new Error(`API HTTP ${r.status}`);
  return r.json();
}
(async () => {
  const before = await list();
  const hashBefore = hash();
  const processes = execFileSync("ps", ["-eo", "pid=,args="], { encoding: "utf8" })
    .split("\n").map(x => x.trim().match(/^(\d+)\s+node server\/index\.js$/)).filter(Boolean);
  if (processes.length !== 1) throw new Error(`Backend 프로세스 ${processes.length}개: 중단`);
  const pid = Number(processes[0][1]);
  process.kill(pid, "SIGTERM");
  let stopped = false;
  for (let i = 0; i < 30; i++) {
    try { process.kill(pid, 0); }
    catch (e) { if (e.code === "ESRCH") { stopped = true; break; } throw e; }
    await new Promise(r => setTimeout(r, 100));
  }
  if (!stopped) throw new Error("이전 Backend 종료 미확인: 중복 시작 금지");
  const child = spawn(process.execPath, ["server/index.js"], {
    cwd: "/workspace", detached: true, stdio: "ignore"
  });
  child.unref();
  let after;
  for (let i = 0; i < 30; i++) {
    try { after = await list(); break; }
    catch { await new Promise(r => setTimeout(r, 500)); }
  }
  if (!after) throw new Error("Backend 재시작 후 API 확인 실패");
  const checks = {
    listEqual: JSON.stringify(before) === JSON.stringify(after),
    hashEqual: hashBefore === hash()
  };
  for (const [key, ok] of Object.entries(checks)) console.log(`[${ok ? "PASS" : "FAIL"}] ${key}`);
  if (Object.values(checks).some(ok => !ok)) process.exitCode = 1;
  else console.log("[PASS] AC-009 restart persistence");
})().catch(e => { console.error("[FAIL]", e.message); process.exitCode = 1; });
'@
    $script | docker compose exec -T -w /workspace hermes `
        node -e 'let s="";process.stdin.setEncoding("utf8");process.stdin.on("data",c=>s+=c);process.stdin.on("end",()=>{require("vm").runInThisContext(s)})'
    if ($LASTEXITCODE -ne 0) { throw '재시작 영속성 검사 실패' }
    Write-Host '[PASS] AC-009'
}
```

수정
```수정1
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'

    Write-Host "`n=== AC-009 Backend Process Diagnosis ===" -ForegroundColor Cyan

    docker compose exec -T -w /workspace hermes sh -lc '
        echo "=== Backend HTTP ==="

        if curl --noproxy "*" -fsS --max-time 5 \
            http://127.0.0.1:3001/api/requests >/dev/null; then
            echo "[PASS] Backend HTTP"
        else
            echo "[FAIL] Backend HTTP"
        fi

        echo
        echo "=== Node Processes ==="
        ps -eo pid,ppid,args | grep -E "node|PID" | grep -v grep || true

        echo
        echo "=== Port 3001 ==="
        if command -v ss >/dev/null 2>&1; then
            ss -ltnp | grep -E "3001|State" || true
        else
            echo "ss command unavailable"
        fi

        echo
        echo "=== Data File ==="
        if test -f /workspace/data/requests.json; then
            ls -l /workspace/data/requests.json
            sha256sum /workspace/data/requests.json
        else
            echo "[CHECK] requests.json not found"
        fi
    '

    if ($LASTEXITCODE -ne 0) {
        throw 'Backend diagnosis failed'
    }

    Write-Host "`n[PASS] Backend diagnosis completed" -ForegroundColor Green
}
```
```수정2
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'

    $script = @'
const fs = require("node:fs");
const crypto = require("node:crypto");
const { execFileSync, spawn } = require("node:child_process");

const base = "http://127.0.0.1:3001";
const file = "/workspace/data/requests.json";

const hash = () =>
  crypto.createHash("sha256")
    .update(fs.readFileSync(file))
    .digest("hex");

async function list() {
  const r = await fetch(`${base}/api/requests`);
  if (!r.ok) throw new Error(`API HTTP ${r.status}`);
  return r.json();
}

function backendProcesses() {
  return execFileSync("ps", ["-eo", "pid=,stat=,args="], {
    encoding: "utf8"
  })
    .split("\n")
    .map(line => line.trim().match(
      /^(\d+)\s+(\S+)\s+(?:\S+\/)?node\s+server\/index\.js$/
    ))
    .filter(Boolean)
    .filter(match => !match[2].startsWith("Z"))
    .map(match => Number(match[1]));
}

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

(async () => {
  const before = await list();
  const hashBefore = hash();

  const processes = backendProcesses();
  if (processes.length !== 1) {
    throw new Error(`Backend 프로세스 ${processes.length}개: 중단`);
  }

  const oldPid = processes[0];
  console.log(`[INFO] Existing Backend PID: ${oldPid}`);

  process.kill(oldPid, "SIGTERM");

  let stopped = false;

  for (let i = 0; i < 30; i++) {
    if (!backendProcesses().includes(oldPid)) {
      stopped = true;
      break;
    }
    await sleep(100);
  }

  if (!stopped) {
    throw new Error("이전 Backend 종료 미확인: 중복 시작 금지");
  }

  console.log("[PASS] Previous Backend stopped");

  const child = spawn(process.execPath, ["server/index.js"], {
    cwd: "/workspace",
    detached: true,
    stdio: "ignore"
  });
  child.unref();

  let after;

  for (let i = 0; i < 30; i++) {
    try {
      after = await list();
      break;
    } catch {
      await sleep(500);
    }
  }

  if (!after) {
    throw new Error("Backend 재시작 후 API 확인 실패");
  }

  console.log("[PASS] Backend restarted");

  const checks = {
    listEqual: JSON.stringify(before) === JSON.stringify(after),
    hashEqual: hashBefore === hash()
  };

  for (const [name, ok] of Object.entries(checks)) {
    console.log(`[${ok ? "PASS" : "FAIL"}] ${name}`);
  }

  if (Object.values(checks).some(ok => !ok)) {
    process.exitCode = 1;
  } else {
    console.log("[PASS] AC-009 restart persistence");
  }

})().catch(error => {
  console.error("[FAIL]", error.message);
  process.exitCode = 1;
});
'@

    $script | docker compose exec -T -w /workspace hermes `
        node -e 'let s="";process.stdin.setEncoding("utf8");process.stdin.on("data",c=>s+=c);process.stdin.on("end",()=>{require("vm").runInThisContext(s)})'

    if ($LASTEXITCODE -ne 0) {
        throw 'AC-009 restart persistence failed'
    }

    Write-Host "`n[PASS] AC-009" -ForegroundColor Green
}

```

**정상 확인:** 재시작 전후 API 목록과 저장 파일 SHA-256이 동일하다.

### 6-7-2. 손상 JSON 원본 보존 (AC-010)

**운영 데이터 파일을 손상시키지 않는다.** 별도의 임시 JSON 파일과 `createApp({dataFile})`를 사용한다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    $script = @'
import assert from "node:assert/strict";
import crypto from "node:crypto";
import os from "node:os";
import path from "node:path";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import request from "supertest";
import { createApp } from "./server/app.js";
const hash = b => crypto.createHash("sha256").update(b).digest("hex");
const productionFile = path.resolve("data/requests.json");
let directory;
try {
  const prodBefore = await readFile(productionFile);
  directory = await mkdtemp(path.join(os.tmpdir(), "wrm-ac010-"));
  const dataFile = path.join(directory, "requests.json");
  await writeFile(dataFile, '{"requests":[ INVALID JSON }', "utf8");
  const before = await readFile(dataFile);
  const response = await request(createApp({ dataFile })).get("/api/requests");
  const after = await readFile(dataFile);
  const prodAfter = await readFile(productionFile);
  const checks = {
    http500: response.status === 500,
    internalError: response.body?.error?.code === "INTERNAL_ERROR",
    errorFormat: typeof response.body?.error?.message === "string",
    noStackExposure: !JSON.stringify(response.body).includes(dataFile) && !JSON.stringify(response.body).includes("at "),
    corruptedFilePreserved: before.equals(after) && hash(before) === hash(after),
    productionDataPreserved: prodBefore.equals(prodAfter) && hash(prodBefore) === hash(prodAfter)
  };
  for (const [key, ok] of Object.entries(checks)) console.log(`[${ok ? "PASS" : "FAIL"}] ${key}`);
  assert.ok(Object.values(checks).every(Boolean), "AC-010 검증 실패");
  console.log("[PASS] 6/6 AC-010 checks");
} catch (e) {
  console.error("[FAIL]", e.stack || e.message);
  process.exitCode = 1;
} finally {
  if (directory) await rm(directory, { recursive: true, force: true });
}
'@
    $script | docker compose exec -T -w /workspace hermes node --input-type=module
    if ($LASTEXITCODE -ne 0) { throw '손상 JSON 보호 검사 실패' }
    Write-Host '[PASS] AC-010'
}
```

**정상 확인:** HTTP 500, `INTERNAL_ERROR`, 원본 보존, 운영 파일 보존 등의 6개 검사 모두 PASS.

---

---

## 6-8. 진행 기록과 다음 Chat 인계

### 프롬프트 ③ — progress.md / handoff.md 갱신

같은 Hermes Chat에 입력한다. **실제 실행한 결과만** 입력하고, 실행하지 않은 검증을 PASS로 적지 않는다.

```text
AI Work Request Manager 2.0 제6교시 구현 및 검증 결과를
/workspace/progress.md와 /workspace/handoff.md에 추가하세요.
위 두 파일 외에는 수정하지 마세요. 기존 제1~5교시 기록을 보존하세요.

제6교시 구현:
- PATCH /api/requests/:id 담당자·우선순위 수정, 동일 값 updatedAt 유지
- PATCH /api/requests/:id/status 상태 변경·재개, 불허 전이 409 INVALID_TRANSITION
- UUID 잘못된 형식 400 / 유효·미존재 404
- mutate의 변경 없는 요청 저장 생략, 직렬화·원자적 저장 보존
- 상세 UI의 담당자·우선순위 수정, 상태 변경, 오류 안내 및 중복 제출 방지
- 우선순위 라디오: .detail-panel .priority-group의 flex/nowrap/width:auto 적용,
  JSX의 priority-group 클래스, 파란색 선택 표시와 키보드 방향키 지원
- Windows 브라우저 연결: 사용자 관리 compose.browser.yaml의 app-preview,
  127.0.0.1:5173 접속, 기존 Dashboard 127.0.0.1:9120 유지

확인된 출력에 근거해 다음 검증만 기록하세요.
- 고정 API 테스트 17/17, TypeScript 검사, Vite 프로덕션 빌드
- Chromium UI 8/8 및 Chromium 기능 E2E 9/9 (각각 실제 실행한 경우)
- AC-009 재시작 전후 데이터·해시 보존 / AC-010 손상 JSON 원본 보존
- Windows 브라우저 목록·상세 및 수정 UI 확인
- 자동 수정·재검증 사용 횟수(최대 3회)

환경 주의:
- Backend 소스 변경 후 Node 프로세스를 재시작해야 최신 라우트가 반영됨
- Vite는 HMR을 지원하지만 Windows 바인드 마운트에서 변경 감지 누락 시
  실제 모듈 내용을 확인하고 Vite만 재시작
- Playwright에서 hermes:5173이 403이면 Docker DNS에서 IPv4 주소를 조회해 사용
- PID·IP·요청 ID는 고정 문자열로 쓰지 않음
- compose.browser.yaml은 사용자 관리이며 Hermes가 임의 수정하지 않음
- 고정 Baseline·tests/는 수정 금지

구현과 검증을 구분하고, 사용자 제공 로그에 기반한 검증 결과와
Hermes가 직접 실행한 검사를 구분하세요. 두 문서를 재독한 뒤 변경 내용을 보고하세요.
```

### 6-8-1. 인계 문서 구조 확인

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $root = 'C:\AI-Native\work-request-manager-v2'
    $rules = @{
        'progress.md' = @('제6교시','17/17','9/9','AC-009','AC-010','제7교시','priority-group')
        'handoff.md' = @('제6교시','PATCH','INVALID_TRANSITION','updatedAt','17/17','Playwright','app-preview','priority-group')
    }
    $failed = 0
    foreach ($name in $rules.Keys) {
        $path = Join-Path $root $name
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            Write-Host "[FAIL] $name 없음"; $failed++; continue
        }
        $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $path
        foreach ($word in $rules[$name]) {
            if ($content.Contains($word)) { Write-Host "[PASS] $name : $word" }
            else { Write-Host "[FAIL] $name : $word"; $failed++ }
        }
        Write-Host "$name SHA256: $((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash)"
    }
    if ($failed) { throw "인계 문서 항목 누락 $failed 건" }
    Write-Host '[PASS] Handoff 구조 확인'
}
```

**정상 확인:** 진행·인계 문서 모두 수정 사항과 실제 검증 내용을 포함하고, 제1~5교시 기록이 유지된다.


---

## 완료 기준

| 영역 | 확인 기준 |
|---|---|
| 고정 API | `tests/api.test.js` 11개 + `tests/api-contract.test.js` 6개 = 17 PASS |
| PATCH | 수정 허용 필드만 반영, 동일 값 `updatedAt` 유지, 불허 전이 409 |
| 서버 최신 반영 | Backend의 두 PATCH 라우트 확인, Vite 최신 JSX·CSS 제공 |
| UI | 우선순위 `낮음·보통·높음` 한 줄 배치, 키보드 방향키 동작 |
| 빌드 | TypeScript 검사와 Vite 프로덕션 빌드 성공 |
| Windows 브라우저 | `127.0.0.1:5173`의 목록·상세·수정·상태 변경 표시 |
| Chromium | UI 회귀 8항목, 기능 E2E 9항목 |
| AC-009 | 서버 재시작 후 데이터 보존 |
| AC-010 | 손상 JSON에서 500/INTERNAL_ERROR, 원본·운영 파일 보존 |
| Handoff | 기존 기록 유지, 제6교시 완료 내용·검증 내역·환경 주의 사항 기록 |

**문제 해결:** Vite나 Backend의 구버전 모듈이 실행 중이면 6-3에서 **해당 프로세스만** 갱신한다. Playwright에서 `hermes:5173`이 403이면 6-6의 동적 Docker IPv4 접속 방식을 따른다. Windows에서 5173 연결이 거부되면 6-5의 `app-preview` 상태를 확인한다. `compose.yaml`, `vite.config.js`, 고정 테스트를 임의 수정하지 않는다.


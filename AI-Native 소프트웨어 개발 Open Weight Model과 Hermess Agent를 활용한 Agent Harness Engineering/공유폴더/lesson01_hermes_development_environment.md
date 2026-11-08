# 제1교시. Hermes Agent 기반 AI 개발 환경 구축과 검증

**과정명:** Open Weight Model과 Hermes Agent를 활용한 Agent Harness Engineering  

**프로젝트:** AI Work Request Manager 2.0  
**운영 환경:** Windows 11 · Docker Desktop(Linux 컨테이너) · Hermes Agent · OpenRouter · Playwright  
**실습 방식:** PowerShell로 인프라 구성, Hermes Agent Chat으로 실행·검증  
**목표:** Hermes Agent Chat에서 Playwright 브라우저 테스트를 요청하고, 실행 결과를 파일과 HTTP API로 확인한다.

> **사전 준비:** Docker Desktop 설치 및 실행, OpenRouter 계정과 API 키. 명령은 **PowerShell 7**을 기준으로 작성한다. 명령 블록을 순서대로 실행하고 각 단계의 정상 확인 후 다음 단계로 진행한다. 이 실습은 기존 작업물을 초기화하거나 삭제하지 않는다.

## 1. 실습 디렉터리 생성

```powershell
New-Item -ItemType Directory -Force -Path 'C:\AI-Native' | Out-Null
New-Item -ItemType Directory -Force -Path 'C:\AI-Native\hermes-training-v2' | Out-Null
New-Item -ItemType Directory -Force -Path 'C:\AI-Native\work-request-manager-v2' | Out-Null
Set-Location 'C:\AI-Native\hermes-training-v2'
Get-Item 'C:\AI-Native\hermes-training-v2','C:\AI-Native\work-request-manager-v2' |
  Select-Object FullName,Exists
```

**정상 확인:** 두 경로의 `Exists`가 모두 `True`.

## 2. Docker 환경 확인

```powershell
docker version --format 'Client: {{.Client.Version}} / Server: {{.Server.Version}}'
docker compose version
docker info --format 'OSType: {{.OSType}} / Architecture: {{.Architecture}}'
```

**정상 확인:** Client/Server 버전, Compose 버전이 표시되고 `OSType: linux`가 출력된다.

## 3. Hermes 인증 설정

Dashboard 비밀번호와 인증 Secret은 `.env`에 저장한다. API 키는 이 파일에 넣지 않는다.

```powershell
Set-Location 'C:\AI-Native\hermes-training-v2'
$securePassword = Read-Host 'Dashboard password' -AsSecureString
$password = [System.Net.NetworkCredential]::new('', $securePassword).Password
if ($password -match '[\r\n]' -or [string]::IsNullOrWhiteSpace($password)) { throw '비밀번호는 비어 있거나 줄바꿈을 포함할 수 없습니다.' }
$bytes = [byte[]]::new(32)
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$secret = [Convert]::ToHexString($bytes)
# Compose .env에서 안전하게 처리할 수 있도록 달러 기호를 이스케이프한다.
$passwordForEnv = $password.Replace('$','$$')
[System.IO.File]::WriteAllLines(
  (Join-Path (Get-Location) '.env'),
  @("DASHBOARD_PASSWORD=$passwordForEnv", "DASHBOARD_SECRET=$secret"),
  [System.Text.UTF8Encoding]::new($false)
)
Remove-Variable securePassword,password,passwordForEnv,bytes,secret
Write-Host '.env created'
```

**정상 확인:** `.env created`가 출력된다. `.env` 파일 내용은 화면이나 채팅에 공개하지 않는다. 비밀번호에 `#`, 따옴표, 역슬래시 등 특수문자가 포함되면 Compose 해석에 주의가 필요하므로, 아래 `docker compose config --quiet`로 반드시 검증한다.

## 4. Playwright Runner 파일 준비

Runner는 **허용 목록에 등록된 테스트만** 실행한다. HTTP API는 Docker 내부 네트워크에서만 접근 가능하며 호스트 포트를 공개하지 않는다. 테스트 결과는 웹 애플리케이션 작업 공간에 저장한다.

```powershell
New-Item -ItemType Directory -Force -Path '.\playwright-service' | Out-Null
New-Item -ItemType Directory -Force -Path 'C:\AI-Native\work-request-manager-v2\e2e' | Out-Null
New-Item -ItemType Directory -Force -Path 'C:\AI-Native\work-request-manager-v2\test-results' | Out-Null
```

### 4-1. package.json

```powershell
@'
{
  "name": "hermes-playwright-runner",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "playwright": "1.58.2"
  }
}
'@ | Set-Content -Encoding UTF8 '.\playwright-service\package.json'
```

### 4-2. 브라우저 Smoke Test

```powershell
@'
const { chromium } = require('playwright');
const started = Date.now();
const mark = (name) => console.error(`[DIAG] ${Date.now() - started}ms ${name}`);
(async () => {
  let browser;
  try {
    mark('TEST_STARTED');
    mark('CHROMIUM_LAUNCH_START');
    browser = await chromium.launch({ headless: true });
    mark('CHROMIUM_LAUNCH_COMPLETE');
    const page = await browser.newPage();
    mark('PAGE_CREATE_COMPLETE');
    await page.goto('about:blank');
    mark('NAVIGATION_COMPLETE');
    if (page.url() !== 'about:blank') throw new Error('Unexpected URL');
    const version = browser.version();
    const url = page.url();
    mark('BROWSER_CLOSE_START');
    await browser.close();
    browser = null;
    mark('BROWSER_CLOSE_COMPLETE');
    console.log(JSON.stringify({status:'PASS',test:'browser-smoke',browser:version,url}));
    mark('TEST_COMPLETE');
  } catch (err) {
    console.error(err.stack || String(err));
    process.exitCode = 1;
    if (browser) await browser.close().catch(() => {});
  }
})();
'@ | Set-Content -Encoding UTF8 '.\playwright-service\browser-smoke.js'
```

### 4-3. HTTP 테스트 실행 서버

서버는 `GET /health`, `POST /run`, `GET /results`를 제공한다. 동시 실행은 한 건으로 제한하고, 실행 시간은 30초로 제한한다. 테스트의 실제 결과와 종료 코드를 함께 검증한다.

```powershell
@'
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const ROOT = '/opt/playwright-runtime';
const RESULTS = '/workspace/test-results';
const TESTS = Object.freeze({'browser-smoke': path.join(ROOT, 'browser-smoke.js')});
let running = false;
let lastResult = null;
fs.mkdirSync(RESULTS, {recursive:true});
const reply = (res, code, data) => {
  res.writeHead(code, {'content-type':'application/json; charset=utf-8','cache-control':'no-store'});
  res.end(JSON.stringify(data));
};
function execute(name) {
  return new Promise(resolve => {
    const child = spawn(process.execPath, [TESTS[name]], {cwd:ROOT, shell:false, stdio:['ignore','pipe','pipe']});
    let stdout = '', stderr = '', timedOut = false, settled = false;
    const cap = (s, chunk) => (s + chunk.toString()).slice(-65536);
    child.stdout.on('data', b => { stdout = cap(stdout,b); });
    child.stderr.on('data', b => { stderr = cap(stderr,b); });
    const timer = setTimeout(() => { timedOut = true; child.kill('SIGKILL'); }, 30000);
    const finish = (code, signal, error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      let reportedPass = false;
      try { reportedPass = JSON.parse(stdout.trim()).status === 'PASS'; } catch {}
      const result = {
        test:name,
        status:code === 0 && !timedOut && reportedPass && !error ? 'PASS' : 'FAIL',
        exitCode:code, signal, timedOut,
        stdout:stdout.trim(), stderr:stderr.trim(),
        ...(error ? {error:String(error)} : {}),
        timestamp:new Date().toISOString()
      };
      try {
        fs.writeFileSync(path.join(RESULTS,'latest.json'),JSON.stringify(result,null,2));
      } catch(e) { result.status = 'FAIL'; result.storageError = e.message; }
      lastResult = result;
      resolve(result);
    };
    child.once('error', err => finish(null,null,err));
    child.once('close', (code,signal) => finish(code,signal));
  });
}
http.createServer(async (req,res) => {
  if (req.method === 'GET' && req.url === '/health')
    return reply(res,200,{status:'ok',service:'playwright-runner',running});
  if (req.method === 'GET' && req.url === '/results')
    return reply(res,200,lastResult || {status:'NO_RESULTS'});
  if (req.method !== 'POST' || req.url !== '/run')
    return reply(res,404,{error:'Not Found'});
  if (running) return reply(res,409,{error:'Test already running'});
  running = true;
  try {
    let body = '';
    for await (const chunk of req) {
      body += chunk.toString();
      if (Buffer.byteLength(body) > 4096) return reply(res,413,{error:'Request too large'});
    }
    let input;
    try { input = JSON.parse(body); } catch { return reply(res,400,{error:'Invalid JSON'}); }
    if (!input || typeof input !== 'object' || !Object.hasOwn(TESTS,input.test))
      return reply(res,400,{error:'Unknown test'});
    const result = await execute(input.test);
    return reply(res,result.status === 'PASS' ? 200 : 500,result);
  } catch(err) {
    return reply(res,500,{status:'FAIL',error:String(err)});
  } finally { running = false; }
}).listen(3000,'0.0.0.0',() => console.log('Playwright Runner listening on port 3000'));
'@ | Set-Content -Encoding UTF8 '.\playwright-service\server.js'
```

### 4-4. Runtime 자동 초기화 스크립트

`/runner`는 Windows 공유 경로이며 **실행하지 않는다**. 실행 시 필요한 파일을 Linux `ext4` 볼륨으로 복사한 뒤, 그 볼륨에서 `npm ci`와 Node.js를 실행한다. 볼륨이 비어 있거나 컨테이너를 재생성해도 같은 절차로 시작한다.

```powershell
@'
#!/bin/sh
set -eu
ROOT=/opt/playwright-runtime
mkdir -p "$ROOT"
cp /runner/package.json "$ROOT/package.json"
cp /runner/server.js "$ROOT/server.js"
cp /runner/browser-smoke.js "$ROOT/browser-smoke.js"
cd "$ROOT"
# 고정 버전의 lockfile이 없다면 Linux 볼륨에서 처음 생성한다.
if [ ! -f package-lock.json ]; then
  npm install --package-lock-only --ignore-scripts --no-audit --no-fund
fi
npm ci --ignore-scripts --no-audit --no-fund
node --check server.js
node --check browser-smoke.js
exec node server.js
'@ | Set-Content -Encoding UTF8 '.\playwright-service\start.sh'
# Windows에서 생성한 셸 스크립트의 줄바꿈을 Linux LF로 통일
$scriptPath = (Resolve-Path '.\playwright-service\start.sh').Path
$scriptText = [System.IO.File]::ReadAllText($scriptPath).Replace("`r`n","`n")
[System.IO.File]::WriteAllText($scriptPath,$scriptText,[System.Text.UTF8Encoding]::new($false))
```

> **운영 참고:** 위 초기화는 재시작 시에도 의존성을 재설치한다. 교육 환경의 재현성과 시작 속도를 높이려면 최초 실행 후 생성된 `package-lock.json`을 교육 자료에 함께 포함하고, 이후 `npm ci`를 lockfile 기반으로 유지한다. 실제 운영 서비스에서는 빌드 단계에서 의존성을 설치한 별도 이미지를 사용하는 것이 더 적절하다.

## 5. Docker Compose 파일 생성

```powershell
@'
name: hermes-training-v2

services:
  hermes:
    image: nousresearch/hermes-agent:latest
    restart: "no"
    command: gateway run
    ports:
      - "127.0.0.1:9120:9119"
    volumes:
      - hermes-data:/opt/data
      - type: bind
        source: C:/AI-Native/work-request-manager-v2
        target: /workspace
    environment:
      HERMES_DASHBOARD: "1"
      HERMES_WRITE_SAFE_ROOT: "/opt/data:/workspace"
      HERMES_DASHBOARD_BASIC_AUTH_USERNAME: "student"
      HERMES_DASHBOARD_BASIC_AUTH_PASSWORD: "${DASHBOARD_PASSWORD:?Password required}"
      HERMES_DASHBOARD_BASIC_AUTH_SECRET: "${DASHBOARD_SECRET:?Secret required}"
    mem_limit: 4g
    cpus: 2.0

  playwright:
    image: mcr.microsoft.com/playwright:v1.58.2-noble
    restart: "no"
    init: true
    working_dir: /opt/playwright-runtime
    command: ["sh", "/runner/start.sh"]
    volumes:
      - playwright-runtime:/opt/playwright-runtime
      - type: bind
        source: C:/AI-Native/hermes-training-v2/playwright-service
        target: /runner
        read_only: true
      - type: bind
        source: C:/AI-Native/work-request-manager-v2
        target: /workspace
    expose:
      - "3000"
    mem_limit: 2g
    cpus: 1.0

volumes:
  hermes-data:
  playwright-runtime:
'@ | Set-Content -Encoding UTF8 '.\compose.yaml'

docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose 구성 오류' }
docker compose config --services
```

**정상 확인:** `hermes`, `playwright` 두 서비스가 표시되고 구성 오류가 없다. **Docker 소켓은 마운트하지 않는다.**

## 6. 이미지 다운로드 및 서비스 실행

```powershell
docker compose pull
docker compose up -d
docker compose ps
docker compose logs --tail 30 playwright
docker compose logs --tail 30 hermes
```

**정상 확인:** 두 서비스가 `Up`; Playwright 로그에 `Playwright Runner listening on port 3000`; Hermes 로그에 `HERMES_DASHBOARD_READY port=9119`가 표시된다. 초기 Playwright 패키지 설치는 네트워크 상황에 따라 시간이 걸릴 수 있다.

## 7. Dashboard 및 OpenRouter 연결

1. 브라우저에서 `http://127.0.0.1:9120` 접속.
2. 사용자 이름 `student`, 비밀번호는 3단계에서 설정한 값으로 로그인.
3. PowerShell에서 다음 명령 실행:

```powershell
docker compose exec hermes hermes model
```

4. 화면 안내에 따라 OpenRouter API 키를 **컨테이너 내부 입력창에만** 등록한다. 채팅이나 가이드북에 API 키를 기록하지 않는다.
5. 기본 모델로 교육에서 지정한 GLM 모델을 선택한다. 모델 목록은 제공자의 실제 지원 상황에 따라 달라질 수 있다.
6. Hermes Agent Chat에서 다음 프롬프트 실행:

```text
현재 모델과 추론 제공자를 알려주고, 아래 문장을 정확히 출력해줘.
Hermes Agent Chat 연결 테스트 성공
파일 수정과 도구 실행은 하지 마.
```

**정상 확인:** 모델 응답이 생성되고 지정 문장이 출력된다. 모델이 답한 제공자 정보는 참고용이며 실제 모델 설정과 호출 성공 여부를 함께 확인한다.

## 8. 작업 공간 쓰기·읽기·삭제 확인

Hermes Agent Chat에 입력:

```text
다음 작업을 /workspace 디렉터리에서 실제 Terminal 도구로 순서대로 수행해줘.
1. /workspace/.hermes-write-test.txt 생성
2. 내용: Hermes Agent workspace write test OK
3. 파일을 다시 읽어 정확히 일치하는지 확인
4. 테스트 파일 삭제
5. 실행 결과와 오류를 보고
제약: /workspace 외부 파일 변경 금지, 실패 시 자동 재시도 금지.
```

PowerShell에서 독립 확인:

```powershell
Test-Path 'C:\AI-Native\work-request-manager-v2\.hermes-write-test.txt'
```

**정상 확인:** Agent가 실제 도구 실행을 보고하고 PowerShell 결과가 `False`.

## 9. Playwright HTTP 통신 및 브라우저 실행 검증

```powershell
# Hermes 컨테이너에서 Runner 상태 확인
docker compose exec -T hermes curl --silent --show-error --max-time 10 http://playwright:3000/health

# 허용된 브라우저 테스트 실행 (한 번)
docker compose exec -T hermes curl --silent --show-error --max-time 40 `
  -H 'Content-Type: application/json' `
  -d '{"test":"browser-smoke"}' http://playwright:3000/run

# Windows에서 결과 파일 확인
Get-Content -Raw -Encoding UTF8 'C:\AI-Native\work-request-manager-v2\test-results\latest.json'
```

**정상 확인:** 응답 JSON의 `status: PASS`, `exitCode: 0`, `timedOut: false`; `stderr`에 `BROWSER_CLOSE_COMPLETE`, `TEST_COMPLETE`; 결과 파일 존재. `curl`의 종료 코드만으로 테스트 성공을 판단하지 않는다.

## 10. Hermes Agent Chat에서 E2E 검증

다음 프롬프트를 Chat에 입력:

```text
Playwright Runner를 이용해 Browser Smoke Test를 정확히 1회 실행해줘.
1. GET http://playwright:3000/health 상태 확인
2. 정상이라면 POST http://playwright:3000/run, JSON {"test":"browser-smoke"} 실행
3. status, exitCode, timedOut, stdout, stderr 확인
4. /workspace/test-results/latest.json 직접 읽기
5. GET http://playwright:3000/results 조회 후 파일과 timestamp 비교
6. 근거를 포함해 PASS 또는 FAIL 보고
제약: 실제 Terminal 도구 사용, Docker 명령 금지, 직접 파일 수정 금지,
자동 재실행·자동 수정 금지, 실행하지 않은 작업을 PASS로 보고하지 말 것.
```

**최종 정상 확인:** `status=PASS`, `exitCode=0`, `timedOut=false`, 브라우저 종료 로그 존재, 파일과 API의 `timestamp` 일치.

## 11. 문제 해결

| 증상 | 확인 및 조치 |
|---|---|
| Docker Server 연결 실패 | Docker Desktop을 실행하고 Linux 컨테이너 모드를 확인한다. |
| Compose 검증 실패 | `.env` 인증 변수와 `compose.yaml` 들여쓰기를 확인한다. 비밀번호 값은 출력하지 않는다. |
| Dashboard 접속 실패 | `docker compose ps`, `docker compose logs --tail 50 hermes` 확인. |
| OpenRouter 모델 호출 실패 | API 키, 모델 선택, OpenRouter 사용 가능 잔액을 확인한다. |
| Playwright Runner가 시작되지 않음 | `docker compose logs --tail 80 playwright`에서 `npm ci` 오류와 서버 구문 오류 확인. |
| Runner HTTP 연결 실패 | 두 서비스가 `Up`인지 확인하고, 컨테이너 내부 주소 `http://playwright:3000`을 사용한다. |
| 테스트 `FAIL` 또는 `timedOut=true` | `latest.json`의 `stderr`와 `[DIAG]` 마지막 단계를 확인한다. 실패를 PASS로 처리하지 않는다. |
| 컨테이너 재생성 후 오류 | Runtime 초기화 로그 확인. 소스 수정 후 `docker compose up -d --no-deps --force-recreate playwright`로 재적용한다. |

## 12. 실습 종료 및 다음 수업 준비

```powershell
# 서비스 상태 확인
docker compose ps

# 실습을 종료할 때만 실행 (컨테이너 및 데이터 보존)
docker compose stop

# 다음 실습에서 다시 시작
docker compose up -d
```

**주의:** 데이터 보존을 위해 `docker compose down -v`, `docker volume prune`, `docker system prune`은 사용하지 않는다. `.env`와 API 키는 Git 저장소에 포함하지 않는다.

### 제1교시 완료 기준

- Docker Compose에서 Hermes Agent와 Playwright Runner가 정상 실행된다.
- Dashboard에 로그인하고 OpenRouter 모델 응답을 확인한다.
- Hermes Agent가 `/workspace`의 파일을 생성·읽기·삭제할 수 있다.
- Linux Runtime 볼륨에서 Playwright 1.58.2와 Chromium이 실행된다.
- Hermes Agent Chat이 HTTP API로 브라우저 테스트를 실행한다.
- 테스트 결과 파일과 API 응답을 비교하여 PASS/FAIL을 판정한다.

> **범위:** 이 교시의 테스트는 `about:blank`를 사용하는 브라우저 Smoke Test이다. 실제 업무 요청 관리 웹 애플리케이션의 기능별 E2E 테스트는 이후 교시에서 추가한다.

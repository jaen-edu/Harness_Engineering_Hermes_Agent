# 제2일차 실습 환경 복구 가이드

**과정:** Open Weight Model과 Hermes Agent를 활용한 Agent Harness Engineering  
**프로젝트:** AI Work Request Manager 2.0  
**목표:** 제5교시 완료 소스로 환경을 맞춘 후 제6교시 실습 시작

## 시작 전 확인

- Windows 11, PowerShell, Docker Desktop이 준비되어 있고 Docker Desktop이 실행 중이어야 합니다.
- 제1일차에 생성한 `C:\AI-Native\hermes-training-v2` 및 `C:\AI-Native\work-request-manager-v2` 폴더가 있어야 합니다.
- `C:\AI-Native\hermes-training-v2\.env` 파일이 있어야 합니다.
- 제1일차에 직접 수정한 파일 중 보관할 자료는 **복구 실행 전에 별도로 복사**하세요. 복구 프로그램은 기존 두 프로젝트 폴더를 백업한 뒤 소스를 교체합니다.
- 강사가 배포한 `day2-recovery-v2.zip`을 다운로드 폴더(`$HOME\Downloads`)에 저장합니다.

## 1단계. ZIP 압축 해제

PowerShell에 다음 블록 전체를 붙여넣어 실행합니다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $zip = Join-Path $HOME 'Downloads\day2-recovery-v2.zip'
    $dest = Join-Path $HOME 'Downloads\day2-recovery-v2'
    if (-not (Test-Path -LiteralPath $zip -PathType Leaf)) { throw "ZIP 파일이 없습니다: $zip" }
    if (Test-Path -LiteralPath $dest) { throw "압축 해제 폴더가 이미 있습니다: $dest" }
    Expand-Archive -LiteralPath $zip -DestinationPath $dest
    foreach ($name in @('restore.ps1','verify.ps1','verify-http.sh','verify-browser.cjs')) {
        if (-not (Test-Path -LiteralPath (Join-Path $dest $name) -PathType Leaf)) { throw "누락: $name" }
    }
    Write-Host '[PASS] 압축 해제 완료' -ForegroundColor Green
}
```

## 2단계. 복구 사전 검사

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $restore = Join-Path $HOME 'Downloads\day2-recovery-v2\restore.ps1'
    & $restore -WhatIf
    if (-not $?) { throw '사전 검사 실패' }
    Write-Host '[PASS] 복구 사전 검사 완료' -ForegroundColor Green
}
```

`[PASS] Package precheck`와 `[PASS] Dry run: no changes made`를 확인합니다. 오류가 나면 다음 단계로 넘어가지 말고 강사에게 화면을 보여주세요.

## 3단계. 프로젝트 복구

**주의:** 기존 프로젝트 폴더를 백업한 뒤 배포 소스로 교체합니다. Docker 서비스가 중지될 수 있습니다. 실행 중인 편집기와 프로젝트 작업을 정리한 뒤 실행하세요.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $restore = Join-Path $HOME 'Downloads\day2-recovery-v2\restore.ps1'
    & $restore
    if (-not $?) { throw '프로젝트 복구 실패' }
    Write-Host '[PASS] 복구 완료' -ForegroundColor Green
}
```

`[PASS] Day 2 Recovery`를 확인합니다. 출력되는 `Backup:` 경로는 기존 프로젝트 백업 위치이므로 보관하세요. **복구 오류가 발생하면 재실행하지 말고 강사에게 문의하세요.**

## 4단계. Docker 컨테이너 재생성 및 자동 검증

다음 블록은 컨테이너를 새 소스 경로에 맞춰 재생성한 후 Docker, 빌드, HTTP, Chromium 화면을 검사합니다. **Docker Volume은 삭제하지 않습니다.** 첫 실행에는 시간이 걸릴 수 있습니다.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\AI-Native\hermes-training-v2'
    docker compose up -d --force-recreate
    if ($LASTEXITCODE -ne 0) { throw 'Docker 컨테이너 재생성 실패' }
    $verify = Join-Path $HOME 'Downloads\day2-recovery-v2\verify.ps1'
    & $verify
    if (-not $?) { throw '자동 검증 실패' }
    Write-Host '[PASS] 제6교시 준비 완료' -ForegroundColor Green
}
```

## 완료 확인

다음 출력이 확인되면 제6교시 실습을 시작합니다.

- `[PASS] Required files`
- `[PASS] Compose configuration`
- `[PASS] Docker services`
- `[PASS] Backend ESM`, `[PASS] TypeScript`, `[PASS] Frontend Build`
- `[PASS] Backend HTTP`, `[PASS] Frontend HTTP`, `[PASS] Vite API Proxy`
- `[PASS] List Screen`, `[PASS] Browser API`, `[PASS] Registration Screen`
- `[PASS] Chromium UI Verification`
- **`[PASS] 제6교시 준비 완료`**

## 문제가 생기면

- ZIP이 없다는 오류: 파일명과 `$HOME\Downloads` 저장 위치를 확인합니다.
- `.env`가 없다는 오류: 제1일차에 만든 설정 파일이 있는지 확인하고 강사에게 문의합니다. 다른 사람의 `.env`를 복사하지 않습니다.
- Docker 관련 오류: Docker Desktop 실행 여부를 확인하고 강사에게 오류 화면을 보여주세요.
- 검증 FAIL: 오류 메시지를 그대로 강사에게 전달합니다. 프로젝트 폴더, Docker Volume, 백업 폴더를 임의로 삭제하지 않습니다.

**이 패키지는 신규 설치용이 아니라 제1일차 환경을 복구하기 위한 자료입니다.**

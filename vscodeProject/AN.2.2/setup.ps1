# setup.ps1
# AI-Native 개발 실습 환경 자동화 설정 스크립트
# 사용법: PowerShell에서 .\setup.ps1 실행

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n===== $Message =====" -ForegroundColor Cyan
}

function Assert-Success {
    if ($LASTEXITCODE -ne 0) {
        Write-Host "오류가 발생했습니다. 위 메시지를 확인하세요." -ForegroundColor Red
        exit 1
    }
}

# ─────────────────────────────────────────
# 1. uv 설치 (이미 설치된 경우 건너뜀)
# ─────────────────────────────────────────
Write-Step "1/5  uv 패키지 매니저 설치"
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "uv 이미 설치됨: $(uv --version)" -ForegroundColor Green
} else {
    Write-Host "uv 설치 중..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    Assert-Success
    # PATH 갱신 (현재 세션 반영)
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH
    Write-Host "uv 설치 완료: $(uv --version)" -ForegroundColor Green
}

# ─────────────────────────────────────────
# 2. Python 3.12 설치
# ─────────────────────────────────────────
Write-Step "2/5  Python 3.12 설치"
uv python install 3.12  --force
Assert-Success
Write-Host "Python 3.12 설치 완료" -ForegroundColor Green

# ─────────────────────────────────────────
# 3. 가상환경 생성
# ─────────────────────────────────────────
Write-Step "3/5  가상환경(.venv) 생성"
if (Test-Path ".venv") {
    Write-Host ".venv 이미 존재합니다. 재사용합니다." -ForegroundColor Yellow
} else {
    uv venv --python 3.12
    Assert-Success
    Write-Host "가상환경 생성 완료" -ForegroundColor Green
}

# ─────────────────────────────────────────
# 4. 가상환경 활성화
# ─────────────────────────────────────────
Write-Step "4/5  가상환경 활성화"
$activateScript = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    & $activateScript
    Write-Host "가상환경 활성화 완료 (프롬프트에 (.venv) 표시 확인)" -ForegroundColor Green
} else {
    Write-Host "활성화 스크립트를 찾을 수 없습니다: $activateScript" -ForegroundColor Red
    exit 1
}

# ─────────────────────────────────────────
# 5. 의존성 설치
# ─────────────────────────────────────────
Write-Step "5/5  requirements.txt 설치"
uv pip install -r requirements.txt
Assert-Success
Write-Host "의존성 설치 완료" -ForegroundColor Green

# ─────────────────────────────────────────
# 완료 안내
# ─────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Green
Write-Host " 환경 설정 완료!" -ForegroundColor Green
Write-Host " Python: $(python --version)" -ForegroundColor Green
Write-Host " pytest: $(pytest --version)" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "`n※ 새 터미널을 열 때마다 가상환경을 활성화해야 합니다:" -ForegroundColor Yellow
Write-Host "   .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow

@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title 불량 분석 앱

echo ==================================================
echo   불량 분석 및 원인제거 방안 제안 웹앱
echo ==================================================

rem ── 1. Python 3.11 이상 찾기 (없으면 winget으로 설치) ──
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [1/4] Python 3.11 이상이 없습니다. winget으로 Python 3.12를 설치합니다...
    winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo.
        echo [오류] Python 자동 설치에 실패했습니다.
        echo        https://www.python.org/downloads/ 에서 Python 3.11 이상을 설치한 뒤 다시 실행하세요.
        pause
        exit /b 1
    )
    echo.
    echo Python 설치가 끝났습니다. 이 창을 닫고 실행.bat을 다시 더블클릭하세요.
    pause
    exit /b 0
)
echo [1/4] Python 확인 완료 (%PY%)

rem ── 2. 가상환경 생성 ──
if not exist ".venv\Scripts\python.exe" (
    echo [2/4] 가상환경을 만듭니다...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo [오류] 가상환경 생성에 실패했습니다.
        pause
        exit /b 1
    )
) else (
    echo [2/4] 가상환경 확인 완료
)
set "VPY=.venv\Scripts\python.exe"

rem ── 3. 패키지 설치 (빠진 것이 있을 때만) ──
"%VPY%" -c "import streamlit, pandas, openpyxl, plotly, matplotlib, docx, anthropic, dotenv" >nul 2>&1
if errorlevel 1 (
    echo [3/4] 필요한 패키지를 설치합니다. 처음 한 번은 몇 분 걸립니다...
    "%VPY%" -m pip install --upgrade pip --disable-pip-version-check -q
    "%VPY%" -m pip install -r requirements.txt --disable-pip-version-check
    if errorlevel 1 (
        echo [오류] 패키지 설치에 실패했습니다. 인터넷 연결을 확인하세요.
        pause
        exit /b 1
    )
) else (
    echo [3/4] 패키지 확인 완료
)

rem ── 4. .env 확인 (없으면 견본 복사 후 메모장으로 열기) ──
if not exist ".env" (
    copy /y ".env.example" ".env" >nul
    echo.
    echo [안내] .env 파일을 만들었습니다. 메모장에서 ANTHROPIC_API_KEY 값을 넣고 저장하세요.
    echo        키가 없어도 집계·분석·내보내기는 사용할 수 있습니다. 키를 넣은 뒤에는 앱을 다시 실행하세요.
    start "" notepad ".env"
)

rem ── 빈 포트 찾기 (8510부터, 다른 Streamlit 앱과 충돌 방지) ──
set "PORT=8510"
for /f %%p in ('powershell -NoProfile -Command "$p=8510; while (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) { $p++ }; $p"') do set "PORT=%%p"

echo [4/4] 앱을 시작합니다. 잠시 후 브라우저가 열립니다: http://localhost:%PORT%
echo       종료하려면 이 창을 닫거나 Ctrl+C 를 누르세요.
echo.
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 4; Start-Process 'http://localhost:%PORT%'"
"%VPY%" -m streamlit run app.py --server.port %PORT%
if errorlevel 1 (
    echo.
    echo [오류] 앱 실행 중 문제가 발생했습니다. 위 메시지를 확인하세요.
    pause
)
endlocal

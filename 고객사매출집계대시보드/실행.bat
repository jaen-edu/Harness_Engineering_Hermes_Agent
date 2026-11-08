@echo off
chcp 949 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title 고객사별 매출 집계 대시보드

set "VPY=%~dp0.venv\Scripts\python.exe"
set "MARK=%~dp0.venv\설치완료.txt"

if exist "%MARK%" if exist "%VPY%" goto run

echo ============================================================
echo  처음 실행 준비: 필요한 프로그램을 설치합니다 (1~2분, 인터넷 필요)
echo ============================================================
echo.

rem ---- 1. Python 3.11 이상 찾기 ----
set "PY="
call :try_python py -3
if not defined PY call :try_python python
if not defined PY call :try_python "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" -3
if defined PY goto make_venv

echo [1/3] Python 3.11 이상이 없어 설치를 시도합니다...
where winget >nul 2>nul
if errorlevel 1 goto no_python
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
call :try_python "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" -3
if not defined PY call :try_python "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY goto no_python

:make_venv
echo [1/3] Python 확인 완료
echo [2/3] 앱 전용 환경을 만드는 중...
if not exist "%VPY%" %PY% -m venv "%~dp0.venv"
if not exist "%VPY%" goto fail

echo [3/3] 라이브러리 설치 중 (streamlit, pandas, openpyxl, plotly)...
"%VPY%" -m pip install --disable-pip-version-check -q --upgrade pip
"%VPY%" -m pip install --disable-pip-version-check -q -r "%~dp0requirements.txt"
if errorlevel 1 goto fail
echo 설치 완료 > "%MARK%"
echo.
echo 설치가 끝났습니다.
echo.

:run
rem Streamlit 첫 실행 때 묻는 이메일 질문 건너뛰기
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
  if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
  > "%USERPROFILE%\.streamlit\credentials.toml" echo [general]
  >> "%USERPROFILE%\.streamlit\credentials.toml" echo email = ""
)

echo ============================================================
echo  대시보드를 실행합니다. 잠시 뒤 브라우저가 자동으로 열립니다.
echo  사용을 마치면 이 검은 창을 닫으세요.
echo ============================================================
"%VPY%" -m streamlit run "%~dp0app.py"
if errorlevel 1 goto fail
goto :eof

:try_python
%* -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 set PY=%*
goto :eof

:no_python
echo.
echo [오류] Python을 찾거나 설치하지 못했습니다.
echo  1) https://www.python.org/downloads/ 에서 Python을 내려받아 설치하세요.
echo  2) 설치 첫 화면에서 'Add Python to PATH'를 꼭 체크하세요.
echo  3) 설치 후 실행.bat을 다시 더블클릭하세요.
pause
exit /b 1

:fail
echo.
echo [오류] 실행 중 문제가 생겼습니다. 위 메시지를 확인하세요.
echo  설치를 처음부터 다시 하려면 이 폴더의 .venv 폴더를 지운 뒤 실행.bat을 다시 실행하세요.
pause
exit /b 1

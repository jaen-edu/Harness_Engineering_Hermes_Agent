@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title 외주명세서 대사

echo ==============================================
echo   외주명세서 대사 웹앱
echo ==============================================

rem ---- 1) 가상환경과 패키지 (최초 1회만 설치)
if exist ".venv\.installed" goto run

set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
  python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo [안내] 파이썬이 없어 설치를 시도합니다. 잠시 기다려 주세요...
  winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
  if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe""
)
if not defined PY (
  echo [오류] 파이썬을 찾지 못했습니다. https://www.python.org 에서 설치한 뒤 다시 실행해 주세요.
  pause
  exit /b 1
)

echo [최초 1회] 실행 환경을 준비합니다. 몇 분 걸릴 수 있습니다...
if not exist ".venv\Scripts\python.exe" (
  %PY% -m venv .venv
  if errorlevel 1 goto fail
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q --upgrade pip
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto fail
echo ok> ".venv\.installed"

:run
if not exist ".env" copy ".env.example" ".env" >nul

rem ---- 2) 앱 실행 (빈 포트를 골라 띄우고 브라우저를 엽니다)
echo.
echo 앱을 시작합니다. 잠시 후 브라우저가 열립니다...
".venv\Scripts\python.exe" launcher.py %*
if errorlevel 1 (
  echo.
  echo [오류] 앱이 비정상 종료했습니다. 위 메시지를 확인해 주세요.
  pause
)
exit /b 0

:fail
echo.
echo [오류] 패키지 설치에 실패했습니다. 인터넷 연결을 확인하고 다시 실행해 주세요.
if exist ".venv\.installed" del ".venv\.installed"
pause
exit /b 1

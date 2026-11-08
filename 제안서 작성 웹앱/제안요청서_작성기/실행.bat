@echo off
chcp 65001 > nul
cd /d "%~dp0"
title 제안요청서 작성기

where python > nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo https://www.python.org/downloads/ 에서 설치하고, 설치 화면에서 "Add Python to PATH"를 꼭 체크해 주세요.
    pause
    exit /b 1
)

echo 필요한 프로그램을 확인하는 중입니다...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo [오류] 필요한 프로그램 설치에 실패했습니다. 인터넷 연결을 확인해 주세요.
    pause
    exit /b 1
)

rem Streamlit 첫 실행 때 나오는 이메일 입력 질문을 건너뛴다
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
    > "%USERPROFILE%\.streamlit\credentials.toml" echo [general]
    >> "%USERPROFILE%\.streamlit\credentials.toml" echo email = ""
)

echo.
echo 제안요청서 작성기를 시작합니다. 브라우저가 자동으로 열립니다.
echo 이 검은 창을 닫으면 프로그램이 종료됩니다.
echo.
python -m streamlit run app.py
pause

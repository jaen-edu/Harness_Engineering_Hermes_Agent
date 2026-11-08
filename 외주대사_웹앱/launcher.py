"""실행.bat 이 부르는 실행기: 빈 포트를 찾아 Streamlit 을 띄우고, 준비되면 브라우저를 연다.

다른 Streamlit 앱이 8501 을 쓰고 있어도 충돌하지 않도록 8517 부터 빈 포트를 고른다.
"""
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent


def free_port(start=8517, tries=50):
    for port in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("사용할 수 있는 포트를 찾지 못했습니다")


def main():
    no_browser = "--no-browser" in sys.argv
    port = free_port()
    url = f"http://localhost:{port}"
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(APP_DIR / "app.py"),
                             "--server.port", str(port)], cwd=APP_DIR)
    for _ in range(120):
        if proc.poll() is not None:
            sys.exit(proc.returncode or 1)
        try:
            with urllib.request.urlopen(f"{url}/_stcore/health", timeout=1) as r:
                if r.status == 200:
                    break
        except OSError:
            time.sleep(0.5)
    print(f"\n  준비 완료: {url}\n  (브라우저가 열리지 않으면 위 주소를 직접 여세요. 사용을 마치면 이 창을 닫으세요.)\n", flush=True)
    if not no_browser:
        webbrowser.open(url)
    try:
        sys.exit(proc.wait())
    except KeyboardInterrupt:
        proc.terminate()


if __name__ == "__main__":
    main()

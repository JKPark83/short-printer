"""전용 Chrome(sp chrome으로 한 번 로그인). Flow 자동과 YouTube 스튜디오 업로드가 CDP로 같이 붙는다."""
import json
import subprocess
import time
from urllib.request import Request, urlopen

from .. import config

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE = config.SECRETS_DIR / "flow-chrome"   # Chrome 136+는 기본 프로필에 디버그 포트를 안 연다
PORT = 9333
FLOW = "https://flow.google.com/"


def _up() -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=2):
            return True
    except OSError:
        return False


def open_chrome() -> None:
    """전용 Chrome을 디버그 포트로 띄운다. 이미 떠 있으면 그대로 둔다. 서버와 따로 산다."""
    if _up():
        # 맥은 창을 다 닫아도 프로세스가 남는데, 창이 없으면 CDP로 붙지 못한다
        with urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=2) as r:
            if not any(t["type"] == "page" for t in json.load(r)):
                urlopen(Request(f"http://127.0.0.1:{PORT}/json/new?{FLOW}", method="PUT"), timeout=5).close()
        return
    PROFILE.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([CHROME, f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}", "--lang=ko",
                      "--no-first-run", "--no-default-browser-check", FLOW],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(30):
        if _up():
            return
        time.sleep(0.5)
    raise RuntimeError("Flow용 Chrome을 띄우지 못했어요")

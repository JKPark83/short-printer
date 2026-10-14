"""sp web: 화면 띄우기 / sp run "주제": 화면 없이 한 편 만들기 / sp trends [키워드]: 주제 찾기 / sp youtube-login: 업로드 권한 받기 / sp chrome: Flow 자동용 Chrome 띄우기."""
import argparse
import sys

from . import flow_auto, pipeline, trends, voice, youtube
from .jobs import Job, read_json


def main() -> None:
    p = argparse.ArgumentParser(prog="sp")
    sub = p.add_subparsers(dest="cmd", required=True)
    web = sub.add_parser("web", help="웹 화면을 띄운다")
    web.add_argument("--port", type=int, default=8765)
    run = sub.add_parser("run", help="주제 하나로 쇼츠 한 편을 만든다")
    run.add_argument("topic")
    run.add_argument("--voice", default=next(iter(voice.choices())), choices=voice.choices())
    tr = sub.add_parser("trends", help="인기 쇼츠를 분석해 주제를 추천한다")
    tr.add_argument("keyword", nargs="?", default="")
    tr.add_argument("--period", default=trends.DEFAULT_PERIOD, choices=trends.PERIODS)
    sub.add_parser("youtube-login", help="YouTube 업로드 권한을 받는다")
    sub.add_parser("chrome", help="Flow 자동(SP_VIDEO=flow-auto)용 Chrome을 띄운다. 처음 한 번 여기서 Google 로그인")
    a = p.parse_args()

    if a.cmd == "trends":
        t = trends.Trend.create(a.keyword, a.period)
        print(f"분석 폴더: {t.dir}")
        try:
            trends.run(t)
        except Exception:  # noqa: BLE001 — 키를 가린 오류만 보여 준다
            err = t.data["error"]
            sys.exit(f"실패({err['step']}): {err['message']}")
        for i, pk in enumerate(read_json(t.dir / "picks.json")["picks"], 1):
            print(f"{i}. [{pk['total']}점] {pk['topic']}\n   {pk['angle']}")
        return

    if a.cmd == "youtube-login":
        try:
            youtube.login()
        except RuntimeError as e:
            sys.exit(str(e))
        print("YouTube 연결 완료. 작업 화면에서 [승인하고 YouTube에 올리기]를 누르면 비공개로 올라가요.")
        return

    if a.cmd == "chrome":
        flow_auto.open_chrome()
        print(f"Flow용 Chrome을 띄웠어요(프로필 {flow_auto.PROFILE}). 처음이면 그 창에서 Google 로그인 후 Flow가 열리는지 확인하세요. 창은 켜 둬도 되고 닫아도 작업 때 다시 뜹니다.")
        return

    if a.cmd == "web":
        import uvicorn
        uvicorn.run("shorts_printer.web.app:app", host="127.0.0.1", port=a.port)
        return
    job = Job.create(a.topic, a.voice)
    print(f"작업 폴더: {job.dir}")
    try:
        pipeline.run(job)
    except Exception:  # noqa: BLE001 — 키를 가린 오류만 보여 준다
        err = job.data["error"]
        sys.exit(f"실패({err['step']}): {err['message']}")
    if job.data["status"] == "waiting":
        print(f"장면 클립을 기다려요. uv run sp web을 켜고 /jobs/{job.id}에서 클립을 올리면 이어서 만들어요.")
        return
    print(f"완성: {job.dir / 'final.mp4'}")

"""sp web: 화면 띄우기 / sp run "주제": 화면 없이 한 편 만들기 / sp trends [키워드]: 주제 찾기 /
sp youtube-login: 업로드 권한 받기 / sp chrome: Flow 자동용 Chrome 띄우기 / sp channels: 채널 목록 /
sp migrate: 예전 폴더(json·log.txt)를 DB로."""
import argparse
import sys

from . import registry
from .adapters import chrome  # 로그인·Chrome 명령만 adapters를 직접 부른다
from .core import channel, pipeline, trends
from .core.channel import Channel
from .core.pipeline import Job
from .infra.store import migrate


def _channel(cid: str | None) -> Channel:
    """--channel 값. 채널이 하나뿐이면 빼도 된다."""
    ids = channel.ids()
    if cid is None:
        if len(ids) != 1:
            sys.exit(f"--channel로 채널을 골라 주세요: {', '.join(ids) or '(채널이 없어요)'}")
        cid = ids[0]
    try:
        return channel.load(cid)
    except (KeyError, ValueError) as e:
        sys.exit(f"{e.args[0] if e.args else e} (가능: {', '.join(ids)})")


def main() -> None:
    p = argparse.ArgumentParser(prog="sp")
    sub = p.add_subparsers(dest="cmd", required=True)
    web = sub.add_parser("web", help="웹 화면을 띄운다")
    web.add_argument("--port", type=int, default=8765)
    run = sub.add_parser("run", help="주제 하나로 쇼츠 한 편을 만든다")
    run.add_argument("topic")
    run.add_argument("--voice", help="채널 channel.toml [tts.voices]의 키. 비우면 채널 기본 목소리")
    tr = sub.add_parser("trends", help="인기 쇼츠를 분석해 주제를 추천한다")
    tr.add_argument("keyword", nargs="?", default="")
    tr.add_argument("--period", default=trends.DEFAULT_PERIOD, choices=trends.PERIODS)
    login = sub.add_parser("youtube-login", help="채널 업로드 권한을 받는다")
    for sp in (run, tr, login):
        sp.add_argument("--channel", help="채널 id(channels/ 폴더 이름). 채널이 하나뿐이면 빼도 된다")
    sub.add_parser("chrome", help="Flow 자동(video.provider = flow-auto)용 Chrome을 띄운다. 처음 한 번 Google 로그인")
    sub.add_parser("channels", help="채널 목록을 보여 준다")
    sub.add_parser("migrate", help="예전 폴더의 json·log.txt를 DB로 옮긴다(이미 옮긴 것은 건너뛴다, 원본은 남는다)")
    a = p.parse_args()

    if a.cmd == "channels":
        for ch in channel.load_all():
            print(f"{ch.id}\t{ch.name}\t{ch.language}\tllm={ch.llm} tts={ch.tts.provider} "
                  f"video={ch.video.provider} publish={ch.publish.provider}")
        return

    if a.cmd == "migrate":
        n = migrate()
        print(f"DB({registry.STORE.path})로 옮김: 작업 {n['job']}개, 주제 찾기 {n['trend']}개, "
              f"스케줄 {n['schedule']}개")
        return

    if a.cmd == "trends":
        ch = _channel(a.channel)
        sv = registry.services(ch.id)
        t = trends.Trend.create(ch.id, a.keyword, a.period)
        print(f"분석 폴더: {t.dir}")
        try:
            trends.run(t, sv)
        except Exception:  # noqa: BLE001 — 키를 가린 오류만 보여 준다
            err = t.data["error"]
            sys.exit(f"실패({err['step']}): {err['message']}")
        for i, pk in enumerate(t.doc("picks.json")["picks"], 1):
            print(f"{i}. [{pk['total']}점] {pk['topic']}\n   {pk['angle']}")
        return

    if a.cmd == "youtube-login":
        ch = _channel(a.channel)
        try:
            registry.publisher(ch).login()
        except RuntimeError as e:
            sys.exit(str(e))
        print(f"{ch.name} 연결 완료. 작업 화면에서 [승인하고 YouTube에 올리기]를 누르면 비공개로 올라가요.")
        return

    if a.cmd == "chrome":
        chrome.open_chrome()
        print(f"Flow용 Chrome을 띄웠어요(프로필 {chrome.PROFILE}). 처음이면 그 창에서 Google 로그인 후 Flow가 열리는지 "
              "확인하세요. 창은 켜 둬도 되고 닫아도 작업 때 다시 뜹니다.")
        return

    if a.cmd == "web":
        import uvicorn
        uvicorn.run("shorts_printer.web.app:app", host="127.0.0.1", port=a.port)
        return
    ch = _channel(a.channel)
    voice = a.voice or ch.tts.default
    if voice not in ch.tts.voices:
        sys.exit(f"모르는 목소리예요: {voice} (가능: {', '.join(ch.tts.voices)})")
    sv = registry.services(ch.id)
    job = Job.create(ch.id, a.topic, voice)
    print(f"작업 폴더: {job.dir}")
    try:
        pipeline.run(job, sv)
    except Exception:  # noqa: BLE001 — 키를 가린 오류만 보여 준다
        err = job.data["error"]
        sys.exit(f"실패({err['step']}): {err['message']}")
    if job.data["status"] == "waiting":
        print(f"장면 클립을 기다려요. uv run sp web을 켜고 /jobs/{job.id}에서 클립을 올리면 이어서 만들어요.")
        return
    print(f"완성: {job.dir / 'final.mp4'}")

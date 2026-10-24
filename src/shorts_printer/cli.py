"""sp web: 화면 띄우기 / sp run "주제": 화면 없이 한 편 만들기 / sp trends ["추가 요청"]: 주제 찾기 /
sp youtube-login·instagram-login: 업로드 권한 받기 / sp chrome: Flow 자동용 Chrome 띄우기 / sp channels: 채널 목록 /
sp migrate: 예전 폴더(json·log.txt)를 DB로 / sp approve <작업> script|draft: 롱폼 대본·초안 승인 후 이어 만들기 /
sp upload <작업>: 완성 작업을 채널 업로드 공급자로 올리기(롱폼은 이게 사람의 최종 승인)."""
import argparse
import sys

from . import registry
from .adapters import chrome  # 로그인·Chrome 명령만 adapters를 직접 부른다
from .core import channel, longform, pipeline, trends
from .core.channel import Channel
from .core.pipeline import Job, upload_of
from .core.services import Services
from .infra.store import migrate
from .infra.worker import LocalQueue


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


def _services(cid: str) -> Services:
    """작업을 만들거나 돌리기 전에 고른다: 공급자 이름이 틀렸으면 작업을 남기지 않고 바로 알린다."""
    try:
        return registry.services(cid)
    except (KeyError, ValueError, RuntimeError) as e:
        sys.exit(str(e.args[0] if e.args else e))


def _go(job: Job, sv: Services) -> None:
    """작업을 돌리고 멈춘 까닭을 알려 준다."""
    print(f"작업 폴더: {job.dir}")
    try:
        pipeline.run(job, sv)
    except Exception:  # noqa: BLE001 — 키를 가린 오류만 보여 준다
        err = job.data["error"]
        sys.exit(f"실패({err['step']}): {err['message']}")
    if job.data["status"] == "done":
        print(f"완성: {job.dir / 'final.mp4'}")
    elif job.data["status"] != "waiting":
        sys.exit(f"취소돼 멈췄어요. 이어 만들려면 uv run sp web을 켜고 /jobs/{job.id}에서 [다시 시도]를 눌러 주세요")
    elif job.data.get("format") != "long":
        print(f"장면 클립을 기다려요. uv run sp web을 켜고 /jobs/{job.id}에서 클립을 올리면 이어서 만들어요.")
    else:
        step = next(k for k in longform.STEPS_LONG if job.data["steps"][k]["status"] != "done")
        if what := {"voice": "script", "render": "draft"}.get(step):
            print(f"{longform.LABELS_LONG[step]} 전에 기다려요. 확인한 뒤 uv run sp approve {job.id} {what}")
        else:   # 장면 클립: 승인한 대본을 다시 승인하면 이어서 돈다
            print(f"장면 클립을 기다려요. {job.dir / 'clips'}에 clipN.mp4를 넣고 uv run sp approve {job.id} script")


def main() -> None:
    p = argparse.ArgumentParser(prog="sp")
    sub = p.add_subparsers(dest="cmd", required=True)
    web = sub.add_parser("web", help="웹 화면을 띄운다")
    web.add_argument("--port", type=int, default=8765)
    run = sub.add_parser("run", help="주제 하나로 영상 한 편을 만든다(채널 format이 long이면 롱폼)")
    run.add_argument("topic")
    run.add_argument("--voice", help="채널 channel.toml [tts.voices]의 키. 비우면 채널 기본 목소리")
    tr = sub.add_parser("trends", help="채널 기본 추천 기준(+추가 요청)으로 주제를 추천한다")
    tr.add_argument("keyword", nargs="?", default="", help="기본 기준에 더해 따를 추가 요청(선택)")
    login = sub.add_parser("youtube-login", help="채널 업로드 권한을 받는다")
    ig = sub.add_parser("instagram-login", help="채널 Instagram(페이스북 페이지) 업로드 권한을 받는다")
    for sp in (run, tr, login, ig):
        sp.add_argument("--channel", help="채널 id(channels/ 폴더 이름). 채널이 하나뿐이면 빼도 된다")
    sub.add_parser("chrome", help="Flow 자동(video.provider = flow-auto)용 Chrome을 띄운다. 처음 한 번 Google 로그인")
    sub.add_parser("channels", help="채널 목록을 보여 준다")
    sub.add_parser("migrate", help="예전 폴더의 json·log.txt를 DB로 옮긴다(이미 옮긴 것은 건너뛴다, 원본은 남는다)")
    ap = sub.add_parser("approve", help="롱폼 작업의 대본(script)·초안(draft)을 승인하고 이어서 만든다")
    ap.add_argument("job_id")
    ap.add_argument("what", choices=("script", "draft"))
    sub.add_parser("upload", help="완성 작업을 채널 업로드 공급자로 올린다(YouTube는 비공개)").add_argument("job_id")
    a = p.parse_args()

    if a.cmd == "upload":
        try:
            job = Job.load(a.job_id)
        except FileNotFoundError as e:
            sys.exit(str(e))
        pub = _services(job.data["channel"]).publisher
        if not pub.ready():
            sys.exit(f"{pub.label} 연결이 안 돼 있어요. {pub.hint}")
        q = LocalQueue(registry.services, registry.notify)   # 화면 업로드와 같은 길: 막기·상태·스케줄 알림
        if not q.enqueue_upload(job.id):
            data = job.data
            sys.exit("완성된 영상만 올릴 수 있어요" if data["status"] != "done"
                     else "이미 올렸어요" if upload_of(data).get("status") == "done" else "이미 올리는 중이에요")
        q.run_one(job.id, "upload")
        up = upload_of(job.data)
        if up.get("status") != "done":
            sys.exit(f"업로드 실패: {up.get('error')}")
        print(f"업로드 완료: {up.get('url') or up['video_id']}" + (f"\n{up['note']}" if up.get("note") else ""))
        return

    if a.cmd == "approve":
        try:
            job = Job.load(a.job_id)
        except FileNotFoundError as e:
            sys.exit(str(e))
        if job.data["status"] in ("running", "queued"):
            sys.exit("이미 돌고 있는 작업이에요. 끝난 뒤에 승인해 주세요")
        sv = _services(job.data["channel"])
        job.update(cancel=None, **{f"{a.what}_ok": True})   # 화면에서 취소한 작업도 승인하면 다시 돈다
        _go(job, sv)
        return

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
        t = trends.Trend.create(ch.id, a.keyword)
        print(f"추천 기록: {t.id}")
        try:
            trends.run(t, sv)
        except Exception:  # noqa: BLE001 — 키를 가린 오류만 보여 준다
            err = t.data["error"]
            sys.exit(f"실패({err['step']}): {err['message']}")
        for i, pk in enumerate(t.doc("picks.json")["picks"], 1):
            print(f"{i}. [{pk['total']}점] {pk['topic']}\n   {pk['angle']}")
            if pk.get("content"):
                print(f"   {pk['content']}")
        return

    if a.cmd == "youtube-login":
        ch = _channel(a.channel)
        try:
            registry.publisher(ch).login()
        except RuntimeError as e:
            sys.exit(str(e))
        print(f"{ch.name} 연결 완료. 작업 화면에서 [승인하고 YouTube에 올리기]를 누르면 비공개로 올라가요.")
        return

    if a.cmd == "instagram-login":
        ch = _channel(a.channel)
        try:
            user = registry.publisher(ch, "instagram").login()
        except RuntimeError as e:
            sys.exit(str(e))
        print(f"{ch.name} ↔ @{user} 연결 완료. 작업 화면에서 [승인하고 Instagram에 올리기]를 누르면 "
              "바로 공개로 올라가요.")
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
    sv = _services(ch.id)
    _go(Job.create(ch.id, a.topic, voice), sv)

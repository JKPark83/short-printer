# 여러 채널 운영 구조 설계

브랜치 `feature/multi-channel`. 채널 수에 제한 없이, 채널마다 대본·음성 언어·영상·썸네일 스타일을 다르게 두고 같은 6단계(대본 → 음성 → 자막 → 영상 소스 → 썸네일 → 렌더)와 업로드를 돈다.

## 확정한 결정

| 주제 | 결정 |
|---|---|
| 채널 설정 | `channels/<id>/` 폴더 하나 = 채널 하나. `channel.toml`(값) + `script.md`·`video_style.md`·`thumbnail.md`·`trends.md`(글) |
| 채널 만들기 | Claude Code 스킬 `.claude/skills/channel-create/`. 인터뷰 → 이름·설명·스타일 제안 → 폴더 생성 |
| YouTube | 한 Google 계정의 브랜드 채널들. 채널마다 OAuth 토큰(`.secrets/channels/<id>/youtube_token.json`), 클라이언트 JSON은 하나, 전용 Chrome 프로필도 하나 |
| 인터페이스(포트) | LLM, TTS, 영상 공급자, 업로드(Publisher), 자막 나누기(Splitter), 작업 큐(Queue). 트렌드 수집은 YouTube 쇼츠를 분석하는 기능 자체라 포트로 만들지 않는다 |
| 공급자 고르기 | 채널마다 `channel.toml`에서. `SP_VIDEO`·`SP_CHANNEL`은 없앤다 |
| 구현 범위 | 지금 쓰는 것만 옮긴다: Claude, ElevenLabs, Flow·Flow 자동, YouTube API + 스튜디오 대체. 가짜·새 공급자는 만들지 않는다 |
| 단계 | 6단계 고정. 구현과 스타일만 채널마다 다르다 |
| 화면 배치 | 공통(1080×1920, 위아래 검은 띠). 글꼴·강조색·배경색만 채널 값 |
| 언어 | ko·en·ja 정식 지원, 그 밖의 언어는 띄어쓰기 기본 규칙. ko=Kiwi, en=띄어쓰기+폭, ja=문장부호·조사 위치(새 의존성 없음). 글꼴은 언어별 기본값, 채널에서 덮어쓰기 |
| 대본 | 공통 뼈대(코드) + 채널 `script.md`·`video_style.md`. 장면 수·문장 길이(글자/단어)·영상 스타일 머리말은 `channel.toml` |
| 썸네일 | 채널 `thumbnail.md`(지금 `shorts-thumbnail` 스킬 본문은 첫 채널로 옮긴다). 줄 길이·강조색은 `channel.toml` |
| 목소리 | 채널마다 목소리 목록·기본값·미리 듣기 문장. 새 작업 화면엔 그 채널 목소리만 |
| 추천 | 채널마다 따로 수집. 지역·언어·검색어·제작 방식·가중치는 채널 값, 코드는 공통. 이미 만든 주제·최근 제목은 같은 채널 안에서만 본다 |
| 저장 | `jobs/`·`trends/`는 그대로 평평하게. `job.json`·`trend.json`에 `channel` 필드. 예전 기록은 `ko-40sec-facts` |
| 동시 실행 | 전역 큐 하나·작업 스레드 하나 그대로. 큐는 포트 뒤로 |
| 웹 | 상단바 채널 고르기(`?channel=<id>`, 쿠키 `sp_channel`로 기억) + "전체" 보기(채널 배지). 대시보드·추천·새 작업·하루 목표가 고른 채널을 따른다 |
| 첫 채널 | `ko-40sec-facts` |
| 공통 지시문 | 코드에 적힌 LLM 지시문(대본 뼈대·고쳐 쓰기·썸네일 뼈대·쇼츠 분석·주제 고르기)은 `prompts/<이름>.md`로 뺀다. 채널 값은 `$scenes`처럼 `string.Template`로 채운다(본문의 `{}`와 안 부딪힌다). 부를 때마다 읽어 고치면 바로 반영된다. 출력 모양의 짧은 필드 설명(pydantic `Field`)은 구조라서 코드에 둔다 |
| 규칙 | ruff(PEP 8, 줄 120, import 정렬) + `.claude/rules/*.md`를 `CLAUDE.md`에서 가리킨다. `core`가 `adapters`·`registry`를 import하지 않는지 테스트로 막는다 |

따로 묻지 않고 정한 기본값:
- 장면 영상 프롬프트는 모든 채널에서 영어(생성 서비스가 영어에 가장 잘 맞는다).
- 운영 화면·로그·오류 문구는 한국어.
- 하루 목표(`daily_goal`)와 민감 주제 확인(`sensitive_gate`)은 채널 값.
- 업로드 로그인은 `sp youtube-login --channel <id>`.

## 패키지 구조(포트와 어댑터)

```
src/shorts_printer/
  config.py            .env·경로·외부 도구 경로만
  (저장소 맨 위) prompts/*.md   공통 LLM 지시문. core/prompts.py가 읽어 ${이름}을 채운다
  registry.py          조립 지점: 이름 → 구현. 채널 하나에 쓸 Services를 만든다. 유일하게 adapters를 아는 곳(web·cli 빼고)
  cli.py
  ports/               인터페이스(typing.Protocol)만. 구현·외부 import 없음
    llm.py  tts.py  video.py  publisher.py  splitter.py  queue.py
  core/                업무 규칙. ports·infra·config만 import
    channel.py         Channel 모델·읽기
    services.py        Services(채널 + 포트 구현 묶음)
    script.py  voice.py  subtitles.py  scenes.py  thumbnail.py  render.py  trends.py
    pipeline.py        Job·STEPS·단계·run_steps·publish
  adapters/            포트 구현. ports·infra·config만 import(core 금지)
    claude.py  elevenlabs.py  flow.py  flow_auto.py  chrome.py  youtube.py  youtube_studio.py
    splitters/ko.py  ja.py  whitespace.py
  infra/
    store.py           Record·원자적 저장·redact 등(예전 jobs.py)
    ffmpeg.py
    worker.py          LocalQueue(Queue 구현). Services는 생성자로 받은 resolve 함수로 얻는다
  web/
```

의존 방향: `web·cli → registry → adapters → ports/infra`, `web·cli·registry → core → ports/infra`. `infra/worker.py`는 `core.pipeline`·`core.trends`를 부르지만 `registry`는 모른다.

## 포트

```python
# ports/llm.py
class LLM(Protocol):
    label: str; model: str; hint: str
    def ready(self) -> bool: ...
    def ask(self, system: str, text: str, schema: type[T], *, refusal: str, what: str,
            images: Sequence[bytes | str] = ()) -> tuple[T, dict]: ...   # images: JPEG 바이트 또는 URL
    def cost(self, input_tokens: int, output_tokens: int) -> float | None: ...
def add_usage(a: dict | None, b: dict | None) -> dict | None   # 사용량 dict 규약과 합치기

# ports/tts.py
class TTS(Protocol):
    label: str; hint: str
    def ready(self) -> bool: ...
    def speak(self, voice: str, text: str, out: Path) -> tuple[Path, list[dict] | None]: ...

# ports/video.py  (지금 VideoProvider 그대로)
class VideoProvider(Protocol):
    label: str; hint: str
    def ready(self) -> bool: ...
    def make(self, scenes: list[dict], out: Path, log) -> Iterable[dict]: ...

# ports/publisher.py
class Publisher(Protocol):
    label: str; hint: str
    def ready(self) -> bool: ...
    def upload(self, path: Path, meta: dict, log) -> str: ...   # meta = {"title", "description", "tags"}
    def set_thumbnail(self, video_id: str, path: Path) -> None: ...

# ports/splitter.py
class Splitter(Protocol):
    limit: int                                   # 자막 한 덩어리 기본 길이
    def chunks(self, text: str, limit: int) -> list[str]: ...
    def width(self, text: str) -> float: ...     # 글자 크기 1일 때 대략 폭

# ports/queue.py
class Queue(Protocol):
    lock: RLock
    def start(self) -> None: ...
    def enqueue(self, job_id: str) -> bool: ...
    def enqueue_upload(self, job_id: str) -> bool: ...
    def redo(self, job_id: str, steps=..., files=None, **fields) -> bool: ...
    def enqueue_trend(self, trend_id: str) -> bool: ...
```

## core 함수 모양

| 모듈 | 함수 |
|---|---|
| script | `write(llm, ch, topic, brief=None, recent=()) -> (Script, usage)`, `revise(llm, ch, s, note) -> (dict, usage)`, `system(ch) -> str` |
| voice | `synth(tts, ch, sentences, voice, job_dir, log) -> str`, `sample(tts, ch, voice) -> Path` |
| subtitles | `cues(timing, splitter, limit) -> list[dict]`, `header(font) -> str`, `write_ass(path, cues, font)`, `ts`, `escape` |
| scenes | `scenes(script, timing) -> list[dict]`, `set_clip(job_dir, meta)` |
| thumbnail | `make(llm, ch, job_dir, script, topic, log, note="") -> dict` |
| render | `render(job_dir, clips, voice_sec, ch, splitter, title=None, starts=None) -> float`, `thumbnail(job_dir, lines, accent, position, ch, splitter, clip=None) -> str`, `frames`, `TAIL` |
| trends | `Trend.create(channel, keyword="", period=...)`, `run(trend, sv)`, `brief(trend_dir, pick)`, `ready()` |
| pipeline | `Job.create(channel, topic, voice, brief=None, source=None)`, `run(job, sv)`, `publish(job, sv)`, `run_steps(rec, steps, labels, run, done_msg)`, `missing_clips`, `Wait`, `STEPS`, `LABELS` |

`run_steps`의 `run`은 `{단계: rec -> str}`. 서비스가 필요한 단계는 `run(job, sv)`이 묶어서 넘긴다.

## channel.toml

```toml
name = "40초 상식"                 # 채널 이름(YouTube)
description = "..."               # 채널 설명(YouTube)
concept = "사람들에게 실제로 도움이 되는 상식"   # 대본·추천이 이 분야 안에서 돈다
language = "ko"                   # 대본·음성·자막 언어
daily_goal = 3
sensitive_gate = true             # 민감 분야 대본은 사람이 확인해야 장면을 만든다
llm = "claude"

[script]
scenes = 7
sentence = [48, 55]
unit = "chars"                    # chars | words
duration = "40~50초"

[tts]
provider = "elevenlabs"
default = "LKOcTG4J4tYTPR9DnLeM"  # 없으면 voices 맨 앞
sample = "안녕하세요. ..."
[tts.voices]
LKOcTG4J4tYTPR9DnLeM = "미스터킴"

[video]
provider = "flow"                 # flow | flow-auto. 쓸 수 없으면 flow
style = "Stylized 3D ..."         # 모든 장면 프롬프트 앞 머리말(영어)

[style]                           # 화면 값. 배치는 공통
font = ""                         # 비우면 언어 기본 글꼴
accent = "#FFE500"
background = ["#0f172a", "#14532d"]
subtitle_limit = 0                # 0이면 언어 기본

[thumbnail]
max_line = 9
max_total = 16

[publish]
provider = "youtube"
category = "22"
channel_id = ""                   # UC… 스튜디오 화면으로 올릴 때 이 채널로 간다. 비우면 Chrome에서 고른 채널

[trends]
region = "KR"
language = ""                     # 비우면 채널 language
keywords = []                     # 키워드 없이 찾을 때 OR로 묶어 검색
production = "..."                # 우리 제작 방식 한 단락(분석·선정 지시문에 들어간다)
weights = { trend = 35, fit = 35, fresh = 15, safe = 15 }
```

## 옮기기

- 기존 `jobs/*/job.json`, `trends/*/trend.json`에 `"channel": "ko-40sec-facts"`를 넣는다.
- `.secrets/youtube_token.json`을 `.secrets/channels/ko-40sec-facts/youtube_token.json`으로 복사한다(내용은 읽지 않는다. 원본은 main 브랜치용으로 둔다).
- `.claude/skills/shorts-thumbnail/SKILL.md` 본문은 `channels/ko-40sec-facts/thumbnail.md`로 옮기고 스킬은 지운다.
- 목소리 미리 듣기 캐시는 `.cache/voices/<channel>/<voice>-<문장 해시>.mp3`.

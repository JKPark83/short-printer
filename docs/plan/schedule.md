# 스케줄 업로드와 알림 (2026-10-15 확정)

정해진 시각(또는 N시간마다)에 채널 하나의 영상을 자동으로 만들어 비공개로 올리고, 끝나면 Discord·Telegram으로 알린다.

## 사용자가 정한 것

| 항목 | 결정 |
|---|---|
| 주제 출처 | 스케줄마다 고른다. `trend`(추천) = 그 시각에 주제 찾기를 **매번 새로** 돌려 추천 1위(이미 만든 주제는 건너뜀)로 만든다. `list`(주제 목록) = 넣어 둔 주제를 위에서부터 하나씩 쓴다 |
| 시각 | 스케줄마다 고른다. `times` = 정해진 시각 여러 개 + 요일. `every` = 시작~끝 시각 안에서 N시간마다 + 요일 |
| 시각의 뜻 | 그 시각에 제작 시작 → 완성되면 바로 업로드 |
| 공개 상태 | 늘 비공개(지금과 같다). 사용자가 스튜디오에서 바꾼다 |
| 알림 | Discord 웹훅·Telegram 봇 둘 다. `.env`에 켜진 것 모두로 보낸다 |
| 알림 시점 | 스케줄 작업의 업로드 완료, 실패(주제 찾기·제작·업로드·목록 빔), 민감 분야 확인 대기. 손으로 올린 업로드는 알리지 않는다 |
| 민감 대본 | 지금 규칙대로 멈추고 알린다. [확인하고 계속]을 누르면 제작·업로드까지 이어진다 |
| 놓친 시각 | 건너뛴다(서버가 꺼졌거나 잠들었던 동안). 기록에 "놓침"만 남긴다 |
| 목소리 | 스케줄마다 하나(기본값은 채널 기본 목소리) |
| 겹침 | 같은 스케줄의 이전 회차가 아직 안 끝났으면(주제 찾기 중·제작 중·대기·업로드 중) 이번 회차는 건너뛴다 |

## 저장

`schedules/<id>/schedule.json` + `log.txt`. `infra.store.Record`를 그대로 쓴다(`FILE = "schedule.json"`, `WHAT = "스케줄"`, 단계 없음).
`config.SCHEDULES_DIR = ROOT / "schedules"`(테스트 conftest가 tmp로 돌린다). `.gitignore`에 `schedules/`.

schedule.json 필드(Record 기본 필드 외):

```json
{
  "channel": "ko-40sec-facts", "name": "아침 상식", "enabled": true,
  "source": "trend", "keyword": "", "period": "3d", "topics": [],
  "voice": "LKOcTG4J4tYTPR9DnLeM",
  "when": {"kind": "times", "times": ["09:00", "18:00"], "days": [0,1,2,3,4,5,6], "every": 6, "start": "09:00", "end": "23:00"},
  "last_slot": "2026-10-15T09:00:00+09:00",
  "runs": [{"at": "...", "slot": "...", "result": "started|skipped|missed|failed", "job": null, "trend": null, "topic": null, "note": null}]
}
```

- `days`: 월요일 0 … 일요일 6. 비면 오류.
- `last_slot`: 마지막으로 처리(실행·건너뜀·놓침)한 예정 시각. 만들 때·켤 때·시각을 고칠 때 지금으로 둬서 지난 시각이 바로 돌지 않게 한다.
- `runs`: 최근 50개만 남긴다. 작업 상태는 job.json에서 그때그때 읽는다.
- `topics`: 남은 주제. 쓰면 맨 앞에서 뺀다(쓴 주제는 runs[].topic에 남는다).

## core/schedule.py (업무 규칙, 순수 함수 + Queue·notify를 인자로 받음)

```python
GRACE = timedelta(minutes=5)   # 이보다 늦게 알아챈 시각은 놓친 것으로 본다(사용자 결정: 건너뛰기)
MAX_RUNS = 50
BUSY_JOB = ("draft", "queued", "running", "waiting")

class When(BaseModel):   # 시각 규칙. 검증 실패는 ValueError(pydantic) → 화면 400
    kind: Literal["times", "every"]
    times: list[str] = []          # "HH:MM", 정렬·중복 제거. kind=times면 1~12개
    every: int = 6                 # 1~24시간
    start: str = "09:00"; end: str = "23:00"   # every 창(start <= end)
    days: list[int] = [0..6]

class Schedule(Record):
    @classmethod
    def create(cls, channel, name, source, voice, when: When, keyword="", period=DEFAULT_PERIOD, topics=()) -> "Schedule"

def slots(when: When, day: date, tz) -> list[datetime]          # 그날의 예정 시각들
def next_runs(when: When, after: datetime, n: int = 5) -> list[datetime]   # after 다음 n개(최대 8일 앞까지 찾음)
def summary(when: When) -> str     # "매일 09:00 · 18:00" / "월·수·금 09:00~23:00 6시간마다"
def due(data: dict, now: datetime) -> tuple[datetime | None, bool]   # (last_slot 뒤 now까지 마지막 예정 시각, 놓쳤나)
def busy(data: dict) -> bool       # 마지막 started 회차의 trend·job·upload가 아직 진행 중인가
def fire(s: Schedule, q: Queue, notify, at: datetime, slot: datetime | None = None) -> dict   # 한 회차 시작. 돌려준 run을 기록
def tick(q: Queue, notify, now: datetime) -> None   # 켜진 스케줄 모두: due → fire 또는 missed 기록. q.lock 안에서
def after_trend(trend: Trend, q: Queue, notify) -> None   # 스케줄 주제 찾기가 끝나면: 추천 1위로 Job 만들고 enqueue / 실패면 알림
def after_job(job: Job, kind: str, q: Queue, notify) -> None   # 스케줄 작업: 완성→enqueue_upload, 실패·민감 대기·업로드 완료/실패→알림
```

- 스케줄 작업 표시: `Job.create(..., source={"schedule": sid})`, 추천이면 `{"trend": tid, "pick": i, "schedule": sid}`. 주제 찾기는 `trend.update(schedule=sid)`.
- 추천 고르기: picks.json 순서(총점 순)에서 같은 채널 작업 주제와 글자가 같지 않은 첫 추천. 다 겹치면 1위. brief는 `trends.brief()`.
- 주제 목록이 비어 있으면: 실패 회차 기록 + 알림 + 스케줄을 끈다(`enabled=False`).
- 수동 [지금 실행]도 `fire()`를 쓴다(겹침 검사 같음, slot=None).
- 알림 문구는 core가 만든다(채널 이름·스케줄 이름·제목·링크). 작업 링크는 `config.URL`(`.env` `SP_URL`, 기본 `http://127.0.0.1:8765`), 업로드 완료는 `https://studio.youtube.com/video/<id>/edit`도.

## 알림 공급자 (ports/notifier.py + adapters)

```python
class Notifier(Protocol):
    label: str; hint: str
    def ready(self) -> bool: ...
    def send(self, text: str) -> None: ...   # 실패하면 한국어 RuntimeError. 키·URL을 메시지에 넣지 않는다
```

- `adapters/discord.py` `Discord`: `.env` `DISCORD_WEBHOOK_URL`. JSON `{"content": text[:2000]}` POST, User-Agent 지정, timeout 10초.
- `adapters/telegram.py` `Telegram`: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`. `sendMessage` `{"chat_id", "text": text[:4096], "disable_web_page_preview": true}`.
- `registry.NOTIFIERS = {"discord": Discord(), "telegram": Telegram()}`, `registry.notify(text) -> list[tuple[str, str | None]]`: 준비된 공급자 모두에 보내고 (label, 오류 또는 None)을 돌려준다. 예외는 삼키고 로그(redact)만 — 알림 실패로 작업이 실패하지 않는다.
- `infra.store.redact()`는 이름이 `_API_KEY`·`_TOKEN`·`_WEBHOOK_URL`로 끝나는 값을 가린다.
- 알림은 채널 설정이 아니라 전역(.env)이다. 고르는 곳은 registry.

## 작업 큐(infra/worker.py)

- `LocalQueue(resolve, notify=lambda text: None)`. `registry.queue()`가 `LocalQueue(services, notify)`.
- `run_one` 끝(성공·실패 모두)에 `trend`면 `schedule.after_trend`, `run`·`upload`면 `schedule.after_job`. 이 훅의 예외는 잡아서 로그만.
- `start()`가 작업 스레드와 함께 스케줄 스레드(`sp-scheduler`, 30초마다 `schedule.tick(self, self.notify, datetime.now().astimezone())`)를 띄운다.

## 웹

- 상단 메뉴에 "스케줄"(`/schedules`). 고른 채널의 스케줄 목록(전체 채널이면 모두).
- 스케줄 카드: 이름, 채널, 켜기/끄기, 주제 출처(추천: 키워드·기간 / 목록: 남은 개수), 시각 요약, 다음 실행(상대 시각), 최근 회차 결과(작업 링크·상태), [지금 실행]·[고치기]·[지우기].
- 만들기·고치기 폼: 이름, 주제 출처(추천: 키워드·기간 / 목록: 줄마다 주제 하나), 목소리, 시각 방식(정해진 시각: 시각 칩 더하기·빼기 / N시간마다: 간격·시작·끝), 요일 칩, 다음 실행 5개 미리 보기(`POST /api/schedules/preview`).
- 알림 패널: Discord·Telegram 준비 여부, [테스트 알림 보내기](`POST /api/notify/test`).
- 환경 점검에 "알림" 한 줄(하나라도 준비되면 ok, 없으면 warn).
- 라우트: `GET /schedules`, `GET /schedules/new`, `GET /schedules/{id}`, `POST /schedules`(만들기), `POST /api/schedules/{id}`(고치기), `POST /api/schedules/{id}/toggle`, `POST /api/schedules/{id}/run`, `POST /api/schedules/{id}/delete`, `POST /api/schedules/preview`, `POST /api/notify/test`.

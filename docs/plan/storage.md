# 저장소를 DB로 (2026-10-15 확정)

작업·주제 찾기·스케줄의 상태, 로그, JSON 결과물을 SQLite에 둔다. 다른 DB로 바꿀 수 있게 저장소 포트 뒤에 둔다.

## 사용자가 정한 것

| 항목 | 결정 |
|---|---|
| 옮길 범위 | 상태(job·trend·schedule json) + 로그(log.txt) + JSON 결과물(script·timing·cues·clips·thumb·picks·videos·analyses 등). 미디어(mp4·mp3·wav·jpg·png)와 ffmpeg가 읽는 subs.ass 같은 렌더용 파일은 폴더에 남는다 |
| 추상화 | `ports/store.py` Protocol + 표준 라이브러리 `sqlite3` 구현 하나. 새 의존성 없음. 다른 DB는 구현 파일 하나 + registry 한 줄 |
| 기존 데이터 | 켤 때 자동으로 DB에 가져온다(이미 있는 id는 건너뜀, 여러 번 돌려도 같다). 원본 json·log.txt는 지우지 않고 백업으로 남긴다. `sp migrate`로도 돌릴 수 있다 |
| 설정 파일 | channel.toml·채널 규칙 md·prompts/*.md·.secrets 토큰은 파일 그대로 |

## 포트 (ports/store.py)

```python
class Store(Protocol):
    """종류(kind: job|trend|schedule)와 id로 찾는 문서 저장소. 값은 JSON으로 바꿀 수 있는 것."""
    def get(self, kind: str, rec_id: str, name: str = "", default=None): ...   # name ""= 상태 문서
    def put(self, kind: str, rec_id: str, value, name: str = "") -> None: ...
    def edit(self, kind: str, rec_id: str, fn, name: str = ""): ...   # 읽고 fn으로 고쳐 쓰기를 한 트랜잭션으로
    def ids(self, kind: str) -> list[str]: ...          # id 오름차순(= 만든 시각 순)
    def delete(self, kind: str, rec_id: str) -> None: ...   # 상태·결과물·로그 모두
    def log(self, kind: str, rec_id: str, line: str) -> None: ...
    def tail(self, kind: str, rec_id: str, n: int = 200) -> list[str]: ...
```

- `edit`은 구현하며 더했다: `Record.update()`·`step()`의 읽고-고쳐-쓰기가 작업 스레드·웹 스레드·`sp run` 프로세스 사이에서 값을 잃지 않게 한다. SQLite는 잠금 + `BEGIN IMMEDIATE`.

## 구현 (infra/sqlite.py)

- `infra`가 저장 층이라 여기 둔다(infra는 adapters를 import하지 못하고, Record가 infra에 있다).
- 표 세 개. 열이 일반적이라 Postgres(JSONB)로 그대로 옮길 수 있다.

```sql
CREATE TABLE IF NOT EXISTS docs (kind TEXT, id TEXT, name TEXT, data TEXT NOT NULL, PRIMARY KEY (kind, id, name));
CREATE TABLE IF NOT EXISTS logs (seq INTEGER PRIMARY KEY, kind TEXT, id TEXT, line TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS logs_rec ON logs (kind, id, seq);
```

- 연결은 처음 쓸 때 연다(registry를 import만 해도 `shorts.db`가 생기지 않게. 테스트는 conftest가 tmp DB를 건다).
- 연결 하나 + `threading.Lock`, `check_same_thread=False`, autocommit(`isolation_level=None`), `PRAGMA journal_mode=WAL`, `busy_timeout`. 작업 스레드·스케줄 스레드·웹 스레드와 다른 프로세스(`sp run`)가 같이 쓴다.
- DB 파일은 `config.DB`(`ROOT / "shorts.db"`), `.gitignore`에 `shorts.db*`.

## 고르는 곳

- `registry.py`: `STORE = SQLiteStore(config.DB)` 를 만들고 `infra.store.use(STORE)`로 건다. web·cli는 registry를 import하므로 켤 때 걸린다.
- `infra.store`는 걸린 저장소를 쓰고, 안 걸렸으면 한국어 RuntimeError. 테스트 conftest는 테스트마다 tmp DB를 건다.

## Record (infra/store.py)

- `KIND` 클래스 값(job·trend·schedule). 상태는 `data`·`update()`·`step()`이 저장소의 상태 문서를 쓴다.
- 결과물: `rec.doc(name, default=None)` / `rec.put(name, value)` (`name`은 "script.json" 같은 예전 파일 이름 그대로, 옮긴 데이터와 맞춘다).
- 로그: `rec.log(msg)`(redact·시각 붙이기 그대로) / `rec.tail(n)`.
- `all()`·`load()`는 저장소 id로. `rec.dir`는 미디어 폴더로 남는다(필요할 때 만든다).
- `rec.delete()`: 저장소 행 + 미디어 폴더.
- `rec.dir`는 상태 문서가 있을 때만 처음 쓸 때 만든다(스케줄은 폴더가 생기지 않고, 지운 기록은 다시 생기지 않는다).
- 예전 파일의 모양 고치기(`Job`의 썸네일 단계 채우기)는 `_fix(d)`를 덮어써서 읽을 때·고칠 때 모두 적용한다.
- core 함수가 `job_dir`에 json을 쓰던 곳(`voice.synth`의 timing.json, `scenes.set_clip`의 clips.json, `thumbnail`의 thumb.json 읽기 등)은 값을 돌려주거나 Record를 받게 바꾼다. `read_json`·`atomic_write_json`은 미디어 아닌 데이터에는 더 쓰지 않는다(`.secrets` 토큰·설정만).

## 옮기기 (infra/store.migrate)

- `migrate(roots)`: `jobs/*/job.json`, `trends/*/trend.json`, `schedules/*/schedule.json`과 같은 폴더의 다른 `*.json`, `log.txt`를 저장소에 넣는다. 상태 문서가 이미 있는 id는 통째로 건너뛴다.
- 웹 lifespan(`recover()` 앞)과 `sp migrate`가 부른다. 몇 개 옮겼는지 로그에 남긴다.

### 어떤 json을 옮기나 (2026-10-15, 실제 폴더를 보고 정함)

| 파일 | 어디로 | 왜 |
|---|---|---|
| `job.json`·`trend.json`·`schedule.json` | 상태 문서(name "") | |
| 작업 `script.json`·`timing.json`·`cues.json`·`clips.json`·`thumb.json` | 결과물 문서(같은 이름) | 파이썬 코드만 읽는다. 화면은 app.py가 값으로 넘기고 `/files/`로는 wav·mp4·jpg만 연다 |
| 주제 찾기 `videos.json`·`analyses.json`·`picks.json` | 결과물 문서 | 같은 이유 |
| `log.txt` | logs 표(줄마다 한 행, 시각 그대로) | |
| `subs.ass`·`thumb.ass`·`title.ass`, wav·mp3·mp4·jpg, `clips/clip{i}.task` | 폴더에 남는다 | ffmpeg·브라우저가 파일로 읽거나, 공급자가 재시작 때 보는 작업 표시 |
| 하위 폴더 json(`before-chunks/cues.json` 등) | 옮기지 않는다 | 손으로 남긴 백업. 코드가 읽지 않는다 |
| `jobs/.cache/pixabay-*.json` | 옮기지 않는다 | 상태 파일이 없는 폴더(예전 공급자 캐시)라 기록이 아니다 |

- 옮기는 순서: 반쯤 옮긴 흔적을 지우고(`delete`) → 결과물 → 로그 → 상태 문서를 맨 뒤에. 상태 문서가 있으면 다 옮긴 것이라 다음엔 건너뛴다.
- 반환값은 종류마다 옮긴 기록 수(`{"job": n, "trend": n, "schedule": n}`).

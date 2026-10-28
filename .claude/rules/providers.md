# 공급자 더하기(TTS·영상·LLM·업로드·자막 나누기·알림)

목적: 새 공급자를 core를 건드리지 않고 파일 하나 + 등록 한 줄로 붙인다.

## 순서

1. `src/shorts_printer/ports/`에서 맞는 Protocol을 읽는다: `llm.LLM`, `tts.TTS`, `video.VideoProvider`, `publisher.Publisher`, `splitter.Splitter`, `notifier.Notifier`. docstring의 약속(반환 모양, 원자적 쓰기, 재시도·오류 규칙)을 그대로 지킨다.
2. `adapters/<name>.py`(자막 나누기는 `adapters/splitters/<lang>.py`)에 클래스 하나를 둔다. 상속하지 않는다(Protocol은 모양만 맞추면 된다).
   - `label`: 화면 이름. `hint`: 환경 점검 한 줄(준비 안 됐을 때 할 일, 한국어).
   - `ready()`: 키·도구가 있는지 빠르게만 본다(네트워크 호출 금지).
   - 오류는 한국어 `RuntimeError`. 키 값은 메시지·로그에 넣지 않는다.
3. `registry.py`에 한 줄 등록한다: `LLMS`·`TTSES`·`VIDEOS`·`SPLITTERS`·`NOTIFIERS`, 업로드는 채널을 받아 만드는 함수를 `PUBLISHERS`에(주 공급자는 `publish.provider`, 더 올리는 곳은 `publish.also`). import 한 줄.
4. 키가 필요하면 `.env.example`에 이름만 한 줄. 이름이 `_API_KEY`·`_TOKEN`·`_WEBHOOK_URL`·`_SECRET`으로 끝나면 `redact()`가 로그에서 가린다. 키는 `config.secret(name)`으로 읽는다.
5. 알림은 채널 설정이 아니라 전역이다: `.env`에 켜진(`ready()`) 것 모두로 `registry.notify(text)`가 보낸다. 채널에서 쓰려면 `channel.toml`의 `llm`·`tts.provider`·`video.provider`·`publish.provider`에 등록 이름을 적는다. 자막 나누기는 `language`로 고른다.
6. 테스트: `tests/test_<name>.py`에서 HTTP·SDK를 monkeypatch한 가짜로 돌린다. 실제 호출은 `@pytest.mark.live`만.

## 하지 않는 것

- core·web 코드에 공급자 이름(`"elevenlabs"`, `Claude` 등)을 적지 않는다. 고르는 건 registry, 값은 channel.toml.
- 공급자마다 분기(`if provider == ...`)를 core에 넣지 않는다. 차이는 adapter 안에서 흡수한다.
- 쓰지 않는 공급자·가짜 공급자를 미리 만들어 두지 않는다.
- 비동기 영상 생성은 작업 ID를 `out / f"clip{i}.task"`에 적어 재시작 때 다시 요청하지 않는다(두 번 과금 방지). 유료 공급자면 `job_cost`에 비용을 더한다.

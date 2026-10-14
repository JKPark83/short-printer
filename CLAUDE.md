# shorts-printer

## 서버 재시작

코드·템플릿·정적 파일을 바꿔서 서버를 다시 켜야 반영되는 경우, 사용자에게 미루지 말고 항상 직접 재시작한다.

- 대상: `sp web --port 8765` (127.0.0.1:8765)
- 먼저 `jobs/*/job.json`에서 `running`·`queued`·`uploading` 작업을 확인한다. 돌고 있으면 끝난 뒤에 재시작하고, 기다릴 수 없으면 사용자에게 알린다.
- 재시작: `pkill -f "sp web --port 8765"; nohup .venv/bin/sp web --port 8765 > /tmp/sp-web.log 2>&1 &`
- 재시작 후 `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/` 로 200을 확인한다.

## 코드 규칙

코드를 읽거나 고치기 전에 아래 규칙을 읽고 항상 따른다. 결정·패키지 구조·함수 모양은 `docs/plan/multi-channel.md`가 기준이다.

- `.claude/rules/architecture.md`: 층(ports·core·adapters·infra·registry)과 의존 방향. `tests/test_architecture.py`가 막는다
- `.claude/rules/providers.md`: TTS·영상·LLM·업로드·자막 나누기 공급자 더하기
- `.claude/rules/channels.md`: 채널 더하기, `channel.toml` 키 설명(새 채널은 `channel-create` 스킬)
- `.claude/rules/conventions.md`: ruff(줄 120)·import 순서·타입 힌트·한국어 주석과 오류·LLM 지시문은 `prompts/*.md`·원자적 쓰기·비밀 가리기·테스트

마치기 전에 `uv run pytest -q`와 `uv run ruff check`를 돌린다.

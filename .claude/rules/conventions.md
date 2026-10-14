# 코드 규칙

목적: 누가 고쳐도 같은 모양의 짧고 안전한 코드가 남게 한다.

## 모양

- PEP 8, 줄 120자. `uv run ruff check`(E·F·W·I·B·UP)가 통과해야 한다. 설정은 `pyproject.toml`.
- import 순서: 표준 라이브러리 → 외부 라이브러리 → 패키지 안(상대 import `from ..ports.llm import LLM`). 묶음 사이 빈 줄 하나(ruff `I`가 정렬).
- 공개 함수(밑줄로 시작하지 않는 것)에는 타입 힌트를 단다. Python 3.12 문법(`list[str]`, `X | None`).
- 짧고 관용적인 코드. 한 번 쓰는 추상화·설정값을 만들지 않는다.

## 주석과 문구

- 주석·docstring은 짧은 한국어, 기존 말투(해요체 아닌 평서형 "~한다", 명사형 끝맺음)에 맞춘다. 무엇보다 왜를 적는다.
- 사용자에게 보이는 오류·로그·화면 문구는 한국어. 오류는 `RuntimeError("…요")`로 던져 화면에 그대로 뜨게 한다.
- 일부러 남긴 한계는 `# ponytail:` 주석에 한계와 고칠 길을 적는다.

## LLM 지시문

- 지시문(system 프롬프트)은 코드에 쓰지 않는다. 모든 채널 공통은 `prompts/<이름>.md`, 채널마다 다른 규칙은 `channels/<id>/*.md`.
- 코드는 `core.prompts.render("<이름>", 값=…)`로 읽어 `${이름}` 자리를 채운다(`string.Template`). 빠진 값은 KeyError로 바로 드러난다. 글자 `$`는 `$$`로 쓴다.
- 파일 맨 앞 `--- … ---` 머리말에 무엇에 쓰는지와 채우는 값을 적는다(LLM에는 안 간다).
- 코드에 남는 건 출력 모양의 짧은 필드 설명(pydantic `Field`)과, 요청마다 바뀌는 사용자 메시지 조립(주제·참고·최근 제목 등)뿐이다.
- 지시문을 바꾸면 `tests/test_prompts.py`가 모든 파일이 실제 채널로 채워지는지 본다.

## 의존성과 저장

- 표준 라이브러리를 먼저 쓴다. 새 의존성은 더하지 않는다(꼭 필요하면 사용자에게 먼저 묻는다).
- 파일은 원자적으로 쓴다: `infra.store.atomic_write_text`·`atomic_write_json`, 바이너리는 tmp에 쓴 뒤 `os.replace`.
- 로그·오류에 비밀을 남기지 않는다: `infra.store.redact()`를 거친다. 키는 `config.secret(name)`으로 읽고 값을 출력하지 않는다.
- `.env` 값, `.secrets/` 아래 파일, `client_secret_*.json`, `AuthKey_*.p8`는 읽거나 출력하지 않는다. 설정 여부만 `grep -c '^KEY=..*' .env`로 본다.

## 테스트

- 로직을 바꾸면 그걸 잡는 테스트를 하나 남긴다(`tests/test_<모듈>.py`). 외부 API는 monkeypatch한 가짜로, 실제 호출은 `@pytest.mark.live`.
- 마치기 전에 `uv run pytest -q`와 `uv run ruff check`를 돌린다.
- 구조 규칙은 `tests/test_architecture.py`가 막는다(`architecture.md`).

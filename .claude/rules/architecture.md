# 구조와 의존 방향

목적: 업무 규칙(core)이 공급자(Claude·ElevenLabs·Flow·YouTube)를 몰라서, 채널·공급자를 늘려도 core를 고치지 않게 한다.

## 층

| 경로 | 하는 일 | import해도 되는 것 |
|---|---|---|
| `ports/` | 인터페이스(`typing.Protocol`)만: LLM(+`add_usage`)·TTS·VideoProvider·Publisher·Splitter·Queue | 표준 라이브러리, pydantic, 다른 `ports` |
| `core/` | 업무 규칙: 채널·대본·음성·자막·장면·썸네일·렌더·추천·파이프라인 | `ports`·`infra`·`config`·다른 `core`, 외부 SDK가 아닌 라이브러리 |
| `adapters/` | 포트 구현(공급자마다 파일 하나) | `ports`·`infra`·`config`·다른 `adapters` |
| `infra/` | 저장(`store`)·ffmpeg·작업 큐(`worker.LocalQueue`) | `ports`·`config`·`core`·다른 `infra` |
| `registry.py` | 조립 지점: 이름 → 구현, 채널 하나의 `Services`를 만든다 | 전부 |
| `web/`·`cli.py` | 화면과 명령 | 전부(구현은 되도록 registry를 거친다) |

방향: `web·cli → registry → adapters → ports/infra`, `web·cli·registry → core → ports/infra`.

## 규칙

- core는 `adapters`·`registry`·`web`·`cli`를 import하지 않는다. `anthropic`·`kiwipiepy`·`playwright`도 직접 부르지 않는다. 예외는 `core/trends.py`의 `yt_dlp` 하나(쇼츠를 내려받아 분석하는 기능 자체라서).
- core 함수는 필요한 구현을 인자로 받는다: `Services`(`channel`·`llm`·`tts`·`video`·`publisher`·`splitter`) 또는 그중 하나. 전역 등록부를 찾아가지 않는다.
- 구현을 고르는 곳은 `registry.py` 하나뿐이다(web·cli의 로그인·Chrome 명령만 예외). 채널 값(`channel.toml`)으로 고르고 환경 변수로 고르지 않는다.
- `infra/worker.py`는 `core.pipeline`·`core.trends`를 부르지만 registry는 모른다. `Services`는 생성자로 받은 `resolve(channel_id)`로 얻는다.
- ports는 구현을 담지 않는다(`add_usage`처럼 규약을 지키는 작은 함수만).
- 함수 모양과 결정은 `docs/plan/multi-channel.md`가 기준이다.

## 왜

- 공급자를 바꾸거나 더할 때 adapters 파일 하나 + registry 한 줄로 끝나고 core 테스트는 그대로 돈다.
- core 테스트는 가짜 구현(fake)만 넘기면 돼서 키·네트워크 없이 돈다.
- 위 규칙은 `tests/test_architecture.py`가 막는다. 깨지면 import를 고치지, 테스트를 고치지 않는다.

# 100초 쇼츠 출처 기반 제작: 코드에 넣는 자리

## 1. 자료 조사는 어디에 들어가는가

### Takeaway
(c) 가볍게 둘 다로 간다. 주제 찾기(`trend pick/idea`)에는 지금 들어간 `web=True` 확인을 점수용으로만 남긴다. 출처를 남기는 진짜 조사는 파이프라인 맨 앞의 새 단계 `research`로 둔다. 사람 확인은 지금처럼 `step_footage` 앞 한 번뿐이고, 그 화면에 사실·출처·근거 없는 문장을 같이 보여 준다.

### Cited Findings
- 단계 순서는 `STEPS = ("script", "voice", "subtitles", "footage", "thumbnail", "render")`이고 `RUN` 사전으로 돌린다 (`src/shorts_printer/core/pipeline.py:11`, `:160`).
- 사람 확인 지점은 `step_footage` 첫 줄이다: `if job.data.get("review") and not job.data.get("confirmed"): raise Wait("대본 확정")`. 주석은 "영상 크레딧이 가장 비싸 먼저 확정받는다"이다 (`core/pipeline.py:94-95`). 아직 커밋 안 된 작업 트리 상태다.
- `run_steps`는 `Wait`가 나면 상태를 `waiting`으로, 그 단계를 `pending`으로 돌린다 (`core/pipeline.py:164`).
- 예전 작업 보정은 `Job._fix`의 `d["steps"].setdefault("thumbnail", …)`가 한다 (`core/pipeline.py:20-22`).
- 화면의 단계 묶음은 `PHASES = (("대본", ("script", "voice", "subtitles")), ("영상", ("footage",)), …)`이다 (`web/app.py:46`). 확인 문구는 `job.html:70` 근처의 `{% elif review and script %}` 배너다.
- 주제 찾기는 이미 `web=True`로 검색한다: `search_words`, `pick_ideas`, `step_pick` (`core/trends.py`, 작업 트리). 다만 `adapters/claude.py:87-92`는 `resp.parsed_output`만 돌려줘 URL은 작업에 닿지 않는다.
- 스케줄 작업은 `Job.create(d["channel"], topic, d["voice"], source={"schedule": s.id})`로 만들어 `review`가 없다 (`core/schedule.py:257`, `:312`). 그래서 끝까지 돌고 `after_job`이 바로 업로드를 넣는다 (`core/schedule.py:344-347`).

### Inferences
- **단계 추가.** `STEPS = ("research", "script", "voice", "subtitles", "footage", "thumbnail", "render")`, `LABELS["research"] = "자료 조사"`, `RUN["research"] = step_research`로 한다.
  - `Job._fix`에 `d["steps"].setdefault("research", {"status": "done" if d["steps"]["script"]["status"] == "done" else "pending", …})` 한 줄을 넣는다. 예전 작업이 조사 없이 그대로 열리게 하려는 것이다.
- **왜 trend 안이 아니라 단계인가.**
  - 화면·CLI·스케줄 어느 길로 만든 작업이든 지나가는 곳이 파이프라인뿐이다.
  - 주제를 손으로 넣은 작업에도 출처가 붙는다.
  - 실패하면 `failed` → 다시 시도로 그 단계만 다시 돈다.
  - trend에서 이미 조사해 두면 주제 후보 수만큼 비용이 든다. 고르지 않을 후보까지 조사하는 낭비다.
- **확인 문.** 새 문을 만들지 않는다. `research` → `script` → `voice` → `subtitles`가 돈 뒤 `step_footage`의 기존 `Wait("대본 확정")`에서 한 번 멈춘다. `PHASES` 첫 묶음을 `("대본", ("research", "script", "voice", "subtitles"))`로 바꾼다.
- **확인 화면(`web/templates/job.html`)에 더할 것** (30분 안에 끝내는 데 필요한 것만):
  1. 사실 목록 카드: 번호, 사실 한 줄, 사이트·날짜 칩, 링크(`target=_blank`).
  2. 문장마다 근거 번호 칩(`[2][5]`). `fact_ids`가 빈 문장은 강조하고 맨 위에 "근거 없는 문장 n개"를 띄운다.
  3. 업로드될 설명 미리보기: 설명, 출처 머리말과 URL, footer 순서로 실제 `publish`와 같은 함수로 만든 글이다.
- **스케줄 작업에도 확인을 건다.** `Job.create(..., review=True)` 두 곳(`fire`, `after_trend`)이다.
  - `after_job`의 `_sensitive_wait` 분기 옆에 확인 대기 알림 한 갈래를 더한다: `status == "waiting"`이고 `review`인데 `confirmed`가 아니면 "검수 필요"와 링크를 보낸다.
  - 확인한 뒤 `done`이 되면 기존 `d.get("upload") is None` 분기가 그대로 업로드를 넣는다.

### Gaps
- `docs/plan/multi-channel.md`가 작업 트리에 없다(`docs/` 폴더 자체가 없다). CLAUDE.md가 기준이라고 한 문서와 맞는지 대조하지 못했다.
- 스케줄 작업에 확인 문을 걸면 "하루 한 편 자동 업로드"가 사람 손을 기다린다. 사람이 그날 안 보면 그날 영상이 안 나간다. 이걸 받아들일지(시간 넘기면 비공개 업로드만 하는 길 등)는 정해지지 않았다.

## 2. 포트 모양: `Searcher` 대 `LLM.ask(web=True)`

### Takeaway
새 포트 `ports/research.py`의 `Researcher`(조사 한 번에 사실 목록을 돌려준다)와 어댑터 `adapters/claude_research.py`를 둔다. `LLM.ask`에 출처를 얹지 않는다. 구조화 출력과 인용은 같이 못 쓰기 때문이다. 일반 `Searcher.search/fetch` 포트는 사실 뽑기를 core에 끌고 와 더 무겁다.

### Cited Findings
- Claude API 문서는 구조화 출력이 "Incompatible with: Citations (returns 400 error), message prefilling"이라고 적는다 (claude-api 스킬 `shared/tool-use-concepts.md:510`).
- 지금 `LLM.ask`는 `output_format`(구조화 출력)을 쓰고 `parsed_output`을 돌려준다 (`adapters/claude.py:87-92`). 그래서 같은 호출에 citations를 켤 수 없다.
- `web_search_20260209`와 `web_fetch_20260209`는 동적 필터링을 지원하고, 별도 code_execution 선언이 필요 없다 (`shared/tool-use-concepts.md:180-200`).
- `allowed_domains`/`blocked_domains`는 Messages API 웹 도구에 있고, Messages API 쪽에는 `max_uses`, `citations`도 있다 (`shared/managed-agents-tools.md:236`).
- 웹 검색 값은 1,000번에 10달러다(직전 조사의 `shared/managed-agents-core.md` 확인). 코드도 `SEARCH_USD = 0.01`로 같다 (`adapters/claude.py:11`).
- `adapters/claude.py`는 이미 `pause_turn`이면 최대 4번 이어 부르고 `server_tool_use.web_search_requests`를 센다 (`:58-70`).
- `add_usage(a, b)`는 토큰을 더하고 한쪽 값이 `None`이면 비용도 `None`이다 (`ports/llm.py`).
- `job_cost`는 `usage`, `thumb_usage`, `ko_usage` 셋만 더한다 (`web/app.py:208-210`).
- 구조 테스트는 core가 `anthropic`을 부르면 막는다 (`tests/test_architecture.py:14`의 `VENDORS`).

### Inferences
- **포트** (`src/shorts_printer/ports/research.py`):
  ```python
  class Researcher(Protocol):
      label: str
      hint: str
      def ready(self) -> bool: ...
      def gather(self, system: str, topic: str, brief: str | None, *, lang: str, domains: list[str], queries: int,
                 max_sources: int, freshness_days: int) -> tuple[list[dict], dict]:
          """사실 목록(id 없이 text·url·title·site·published)과 usage(model·토큰·cost_usd)."""
  ```
  왜: core가 받는 것은 "사실과 URL"뿐이어야 공급자를 바꿔도 `step_research`가 그대로다.
- **어댑터** (`src/shorts_printer/adapters/claude_research.py`, 클래스 `ClaudeResearch`):
  - `messages.create`를 구조화 출력 없이 부른다. `tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": queries, "allowed_domains": domains or 생략}, {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": max_sources}]`.
  - 시스템 지시문은 `prompts/research.md`에 둔다(사실을 한 줄씩, 숫자·날짜는 원문 그대로, 오래된 자료 피하기). 렌더는 어댑터가 `core.prompts.render`로 하지 않고 core에서 렌더해 문자열로 넘긴다. adapters가 core를 import하면 안 되기 때문이다(`architecture.md` 표). 그래서 `gather`의 첫 인자가 렌더된 `system`이다.
  - 응답의 text 블록마다 붙은 `citations`(url·title·cited_text)를 모아 사실 하나로 만든다.
  - `pause_turn` 반복과 검색 횟수 세기는 `adapters/claude.py`와 같은 모양이다. 두 파일이 쓰는 작은 함수(가격표 `PRICES`, 비용 계산)는 `adapters/claude.py`에서 import한다(adapters끼리 import는 허용).
  - `published`는 citation에 없을 수 있다. 그럴 땐 `None`으로 둔다.
- **registry**: `RESEARCHERS = {"claude": ClaudeResearch()}`. `Services`에 `research: Researcher` 필드를 하나 더하고 `services()`에서 `_pick(RESEARCHERS, ch.research.provider, "자료 조사")`로 고른다.
- **비용**: `step_research`가 `job.update(research_usage=add_usage(job.data.get("research_usage"), usage))`를 한다. `job_cost`의 튜플에 `j.get("research_usage")`를 더한다. 상한은 `max_uses`(검색 수)로 잡는다. 13장면 기준 검색 5~8번이면 0.05~0.08달러에 토큰값이 붙는다.
- **버린 길.**
  - B안(`LLM.ask`가 citations를 돌려주게): 구조화 출력과 400으로 부딪히고 LLM 포트 약속(`schema` → `T`)이 흐려진다.
  - 일반 `Searcher.search/fetch`: 쪽 본문에서 사실을 뽑는 LLM 호출이 core에 따로 생겨 호출이 두 번이 된다.

### Gaps
- citation 블록이 Python SDK에서 어떤 객체 모양(`web_search_result_location`의 필드 이름)으로 오는지 이 저장소에서 확인한 예가 없다. 어댑터 첫 구현 때 실제 응답 한 번을 찍어 맞춰야 한다(`@pytest.mark.live` 하나).
- `web_fetch`의 별도 과금(토큰 외) 여부는 이번에 확인하지 못했다.
- `allowed_domains`를 비우면 어떤 사이트든 나온다. 사이트 등급(`tier`)을 어댑터에서 매길지 core에서 매길지는 정하지 않았다(아래 3에서 core 쪽을 권한다).

## 3. `facts` 문서, `fact_ids`, 근거 확인, 설명란 출처

### Takeaway
`facts.json` 문서 하나, `Scene.fact_ids: list[int]`, 순수 함수 `script.unverified()`, `publish`의 출처 붙이기로 끝낸다. 출처 머리말은 `[publish] sources_heading` 키 하나다.

### Cited Findings
- 결과물은 `Record.put`/`doc`으로 저장소에 쓴다(`conventions.md` "의존성과 저장"). 대본은 `job.put("script.json", s.flat())`이다 (`core/pipeline.py` `step_script`, `:50` 이후).
- `Scene(sentence, prompt)`, `Script(title, description, tags, scenes, sensitive)`이고 `.flat()`가 문장·프롬프트 목록으로 펼친다 (`core/script.py`).
- `revise`와 `save_edit`는 장면 수를 바꾸지 않는다 (`core/script.py` `Revision`/`Draft`, `web/app.py:557`의 문장 수·길이 검사).
- `publish`는 `meta = {k: s[k] for k in ("title", "description", "tags")}` 뒤에 `footer`를 빈 줄 하나 두고 붙인다 (`core/pipeline.py:198-207`). 스튜디오 대체 업로드도 같은 `meta`를 쓴다.
- YouTube 어댑터는 설명을 `_clean`(꺾쇠 제거) 뒤 5000바이트로 자른다 (`adapters/youtube.py:127-144`).
- 지시문은 `prompts/*.md`에 두고 `${이름}`을 채운다. 요청마다 바뀌는 사용자 메시지 조립은 코드에 둬도 된다(`conventions.md` "LLM 지시문").

### Inferences
- **문서 모양** `facts.json`:
  ```json
  {"queries": ["…"], "facts": [{"id": 1, "text": "…", "url": "https://…", "title": "…", "site": "kma.go.kr",
    "published": "2026-09-30", "retrieved_at": "2026-10-16T09:00:00+09:00", "tier": 1}]}
  ```
  - `id`는 core가 1부터 매긴다.
  - `retrieved_at`은 `step_research`가 넣는다.
  - `tier`는 core가 `[research] domains`에 든 사이트면 1, 아니면 2로 매긴다. 표 하나로 끝내고 따로 등급 설정을 만들지 않는다.
- **새 core 함수** (`src/shorts_printer/core/research.py`):
  - `gather(rs: Researcher, ch: Channel, topic: str, brief: str | None) -> tuple[dict, dict]`: 지시문 렌더, 호출, id·tier·retrieved_at 붙이기, URL 같은 것 합치기를 한다.
  - 사실이 0개면 `RuntimeError("자료를 찾지 못했어요. 주제를 바꾸거나 다시 시도해 주세요")`를 던진다.
  - `pipeline.step_research(job, sv) -> str`: `job.put("facts.json", f)`와 `research_usage`를 남기고 `f"사실 {n}개"`를 돌려준다.
- **대본** (`core/script.py`):
  - `Scene`에 `fact_ids: list[int] = Field(default_factory=list, description="이 문장의 근거 사실 번호")`를 더한다.
  - `write(llm, ch, topic, brief=None, recent=(), facts: list[dict] = ())`에서 사실은 사용자 메시지에 `[1] 사실 (사이트, 날짜)` 줄로 붙인다(요청마다 바뀌므로 코드 쪽).
  - `prompts/script.md`에 규칙 한 줄을 더한다: "숫자·고유명사·날짜가 든 문장은 아래 사실 번호를 `fact_ids`에 적고, 사실에 없는 숫자는 쓰지 않는다."
  - `flat()`이 `fact_ids`를 목록의 목록으로 펼친다.
  - `revise`/`Revision`/`Draft`도 `fact_ids`를 받아 그대로 이어 간다.
- **근거 확인**: `script.unverified(s: dict) -> list[int]`는 `fact_ids`가 빈 장면 번호를 돌려준다. 순수 함수 한 줄이다. `step_script` 끝에서 `job.update(unverified=…)`로 남기고 화면이 그 값을 쓴다. 근거 없는 문장이 있다고 멈추지는 않는다. 어차피 사람이 확인 문에서 보기 때문이다.
- **설명란**: `pipeline.description(job, ch) -> str` 하나로 뽑는다. 설명, `sources_heading`, 실제 쓰인 `fact_ids`의 URL(중복 없이, 등장 순), footer 순서다.
  - `publish`와 확인 화면 미리보기가 같이 쓴다.
  - 5000바이트를 넘으면 URL을 뒤에서부터 뺀다(YouTube 어댑터의 일괄 자르기에 맡기면 footer가 잘린다).
- **설정**: `PublishCfg.sources_heading: str = ""`. 비우면 출처를 붙이지 않는다. ko는 `"출처"`, ja는 `"出典"`이다.

### Gaps
- `published`를 citation에서 못 얻으면 `freshness_days` 걸러 내기를 지킬 수 없다. LLM이 본문에서 날짜를 적게 하는 것 말고 확실한 길은 찾지 못했다.
- 사람이 문장을 고치면(`save_edit`) `fact_ids`가 실제 내용과 어긋날 수 있다. 문장이 바뀐 장면만 `fact_ids`를 비우고 `unverified`로 다시 띄우는 것이 가장 짧은 길로 보인다.

## 4. 채널별 `[research]` 표

### Takeaway
`core/channel.py`에 `ResearchCfg`를 두고 `Channel.research: ResearchCfg = ResearchCfg()`로 기본값을 준다. 기존 채널 파일은 고치지 않아도 읽힌다. `channels.md` 표에 다섯 줄을 더한다.

### Cited Findings
- 채널 설정은 pydantic 모델 묶음이다: `ScriptCfg`, `TTSCfg`, `VideoCfg`, `StyleCfg`, `ThumbCfg`, `PublishCfg`, `TrendsCfg`, `Channel` (`core/channel.py:22-93`).
- `TrendsCfg`는 `weights`의 합이 100인지 검사하는 검사기를 갖는다 (`core/channel.py:72`).
- `channels.md`는 "값이 모자라면 channel.toml 키를 더하는 걸 먼저 제안한다(`core/channel.py`와 이 표를 같이 고친다)"라고 적는다.

### Inferences
```python
class ResearchCfg(BaseModel):
    provider: str = "claude"
    domains: list[str] = []                 # 먼저 볼 사이트(비우면 제한 없음). 여기 든 사이트는 tier 1
    queries_per_topic: int = Field(5, ge=1, le=10)
    languages: list[str] = []               # 검색 언어. 비우면 채널 language
    max_pages: int = Field(8, ge=1, le=20)
    freshness_days: int = Field(0, ge=0)    # 0이면 날짜 제한 없음
```
- 도메인은 `field_validator`로 `https://`와 경로를 떼고 소문자로 맞춘다. `web_fetch`가 경로 붙은 도메인을 거부하기 때문이다 (`shared/managed-agents-tools.md:225`).
- 위 상한(`le`)이 곧 비용 상한이다.
- `channels.md` 표에 더할 줄:
  - `[research]` `provider`: registry `RESEARCHERS` 이름(`claude`).
  - `[research]` `domains`: 먼저 볼 사이트. 여기 든 사이트의 사실은 1등급.
  - `[research]` `queries_per_topic` / `max_pages`: 한 편에 쓸 검색 수 / 읽을 쪽 수 상한(비용 상한).
  - `[research]` `languages`: 검색 언어(비우면 `language`). ja 채널이 한국 정보를 한국어 자료로 찾을 때 `["ko", "ja"]`.
  - `[research]` `freshness_days`: 이 날수보다 오래된 자료는 버린다(0 = 제한 없음).
  - `[publish]` `sources_heading`: 설명란 출처 머리말(`출처`, `出典`). 비우면 출처를 붙이지 않는다.

### Gaps
- `languages`가 여럿일 때 검색을 언어마다 나눌지, 지시문에 "두 언어로 찾아라"라고만 쓸지는 실제 결과를 보고 정해야 한다. 첫 구현은 지시문 한 줄로 충분하다.

## 5. 길이 105초, 하루 한 편

### Takeaway
코드에는 7장면·60초 가정이 거의 없다. 바꾸는 것은 `channel.toml` 두 개, `channels/ko-40sec-facts/script.md`의 위치 고정 규칙, 깨지는 테스트 세 군데다.

### Cited Findings
- `ScriptCfg.scenes`는 `Field(7, ge=1, le=20)`이라 13이 들어간다 (`core/channel.py:23`).
- `prompts/script.md:10`은 `${scenes}`, `${lo}~${hi}`, `${duration}`으로 채우고 "장면 클립이 8초라 한 문장이 ${hi}${unit}를 넘지 않게"라고 적는다. 장면당 8초 상한은 그대로 지켜진다.
- ko는 `scenes = 7`, `sentence = [62, 68]`, `duration = "52~56초"`, `daily_goal = 3`이다. 설명은 "생활에 바로 써먹는 상식을 40초 안에 알려 드려요."이다 (`channels/ko-40sec-facts/channel.toml:2-6`).
- ja는 `daily_goal = 2`, `duration = "50~56초"`이고 설명에 "毎日2本更新"과 "1分のミニチュアガイド"가 있다. `trends.production`에도 "50~56초"가 들어 있다 (`channels/ja-korea-trip/channel.toml:3-58`).
- ko `script.md:8`은 "4번째 문장을 여기까진 다들 아시죠? 로 시작"이라는 7장면 전제의 고정 위치 규칙이다.
- `flow_auto`는 장면을 하나씩 만들고 "7장면 약 15분"이라 적혀 있다. `GEN_TIMEOUT = 360`이다 (`adapters/flow_auto.py:12`, `:89`).
- ffmpeg는 `timeout=600`으로 돈다 (`infra/ffmpeg.py:10`).
- `voice`, `subtitles`, `scenes`, `render`, `thumbnail`에는 장면 수·길이 상한이 없다(`core/*.py` 읽음).
- 대시보드 목표는 `ch.daily_goal`의 합이다 (`web/app.py:420`).
- 테스트가 toml 글자에 묶여 있다:
  - `tests/test_script.py:55`: "52~56초", "정확히 7개", "62~68자".
  - `tests/test_script.py:213`: `6 <= len(s.scenes) <= 7`, live.
  - `tests/test_web.py:47`, `:448`: "daily_goal = 3", "daily_goal = 2"를 글자로 바꾼다.

### Inferences
- **ko**: `scenes = 13`, `sentence = [62, 68]`, `duration = "1분 40초~1분 50초"`, `daily_goal = 1`, `description`에서 "40초"를 뺀다.
  - 13 × 약 7.4초에 문장 사이 0.2초(`GAP`)와 끝 0.6초(`TAIL`)를 더하면 약 100~105초다.
  - `name = "40초 상식"`은 YouTube 채널 이름이라 바꿀지 사람이 정한다.
- **ja**: `scenes = 13`, `sentence = [50, 56]`(초당 약 7.2자 그대로) 또는 보고서대로 `[46, 52]`. `duration = "1分40秒~1分50秒"`에 해당하는 한국어 표기 "1분 40초~1분 50초"로 쓴다. 지시문 언어가 한국어이기 때문이다. `daily_goal = 1`이다.
  - `description`의 "毎日2本"과 "1分", 그리고 `trends.production`의 "50~56초"를 고친다.
- **ko `script.md`**: "4번째 문장" 대신 비율로 쓴다. "전체의 40% 지점(13장면이면 5~6번째)". 마지막 두 문장 규칙은 그대로 둔다.
- **테스트**:
  - `test_script.py:55`는 값 글자 대신 `ch.script`에서 만든 문자열로 검사하게 고친다(예: `f"정확히 {ch.script.scenes}개"`).
  - `:213`은 `ch.script.scenes - 1 <= len(...) <= ch.script.scenes`로 고친다.
  - `test_web.py:47`, `:448`의 글자 치환은 새 값(`daily_goal = 1`)에 맞춘다.
- **영상 시간·크레딧**: 13장면이면 `flow_auto`로 약 28분, 장면당 6크레딧이라 78크레딧(지금 42)이다. `flow_auto.py:89` 주석의 "7장면 약 15분"을 고친다.

### Gaps
- 렌더가 13클립·105초에서 600초 안에 끝나는지 재 보지 않았다. 지금 7클립 렌더 시간의 약 2배로 보지만 실측이 필요하다.
- ja를 105초로 늘리는 근거는 이 저장소 안에 없다. 보고서는 ja를 60초로 두자고 했다(아래 9).

## 6. 워커·큐

### Takeaway
워커는 고치지 않는다. 단계는 `pipeline.STEPS`/`RUN`에만 더한다. 재시도는 기존 실패 후 다시 시도, 시간 상한은 SDK 기본 시간 제한과 `max_uses`, 비용 상한은 `[research]` 상한값이 맡는다.

### Cited Findings
- `infra/worker.py`의 `LocalQueue(resolve, notify)`는 스레드 하나로 돌고 `run_one`이 trend·run·upload로 나눠 보낸다. 단계 이름을 모른다(작업 트리 `infra/worker.py`).
- 단계별 시간 제한은 없다. TTS는 `urlopen` 시간 제한 60초, Flow는 `GEN_TIMEOUT = 360`이다.
- `BUSY_JOB`에 "waiting"이 들어 있어 확인을 기다리는 작업이 있으면 스케줄이 다음 작업을 만들지 않는다 (`core/schedule.py`).

### Inferences
- `step_research`는 한 번 호출, 내부 `pause_turn` 최대 4번이라 길어야 수 분이다. 단일 스레드 큐에서 다른 작업을 오래 막지 않는다.
- 하루 한 편이고 확인 대기가 `BUSY_JOB`에 걸리므로, 사람이 확인하지 않으면 다음 회차가 건너뛰어진다. 의도에 맞는 동작이지만 알림(1에서 말한 "검수 필요")이 꼭 있어야 한다.
- 비용 상한을 따로 두지 않는다. `queries_per_topic ≤ 10`, `max_pages ≤ 20`이 곧 상한이다.

### Gaps
- 확인을 안 해서 회차를 놓쳤을 때 `missed`로 남길지 `skipped`로 남길지는 `fire()` 쪽 규칙을 다시 봐야 한다.

## 7. 테스트

### Takeaway
새 파일은 `tests/test_research.py` 하나다. 나머지는 기존 테스트에 몇 개씩 더하고 고친다. 가짜는 `FakeResearcher`(고정 사실 목록)와 monkeypatch한 anthropic 응답 둘이다.

### Cited Findings
- `test_pipeline.py`는 `services(**kw)` 도우미와 `pipeline.RUN`을 바꾸는 `stub_steps`를 쓴다. 실제 채널 `ko-40sec-facts`를 읽는다.
- `test_prompts.py:16-23`은 모든 지시문이 실제 채널로 채워지는지 본다.
- `conftest.py`는 임시 jobs·trends·schedules 폴더, 임시 `SQLiteStore`, 알림 끄기를 자동으로 건다.
- `test_architecture.py`는 `ALLOWED`와 `VENDORS`로 층을 막는다.

### Inferences
- `tests/test_research.py`:
  - `core.research.gather`가 id 1부터, tier(도메인 표 기준), `retrieved_at`, URL 중복 합치기, 0개면 `RuntimeError`를 하는지.
  - `ClaudeResearch` 어댑터가 가짜 응답(text 블록에 citations 둘, `pause_turn` 한 번)에서 사실 2개와 검색 횟수 비용을 뽑는지.
  - live 테스트 하나.
- `test_pipeline.py`:
  - `STEPS[0] == "research"`.
  - 예전 작업 `_fix`에서 `research`가 done/pending으로 채워지는지.
  - `description()`이 출처 머리말, 쓰인 URL만, footer 순서인지, 5000바이트를 넘으면 URL을 덜어 내는지.
- `test_script.py`: `fact_ids`가 `flat()`과 `revise`를 거쳐 살아남는지, `unverified()`, 55·213줄 고치기.
- `test_channel.py`(또는 해당 테스트): `[research]` 없는 채널이 기본값으로 읽히는지, `domains` 정규화, 상한 넘으면 pydantic 오류.
- `test_prompts.py`: `prompts.render("research", …)`를 목록에 더한다.
- `test_web.py`: `job_cost`가 `research_usage`를 더하는지, 확인 화면에 사실 카드와 "근거 없는 문장" 표시가 뜨는지, `daily_goal` 글자 치환을 고친다.
- `test_schedule.py`: 스케줄 작업이 `review=True`로 만들어지고 확인 대기 때 "검수 필요" 알림이 가는지, 확인 뒤 done이면 업로드가 들어가는지.
- `test_architecture.py`는 그대로 통과해야 한다(새 포트는 표준 라이브러리만, 어댑터만 anthropic).

### Gaps
- 없음.

## 8. 크기와 순서

### Takeaway
전체로는 M~L이다. 설정과 테스트 글자부터 바꾸고, 포트·어댑터, 단계, 대본, 화면, 업로드 설명, 스케줄 순으로 간다. 채널 값(13장면·하루 한 편) 전환은 맨 마지막에 한다.

### Cited Findings
- 위 1~7의 파일·줄 근거와 같다.

### Inferences
| 순서 | 일 | 파일 | 크기 |
|---|---|---|---|
| 1 | `ResearchCfg`, `PublishCfg.sources_heading`, `channels.md` 표 | `core/channel.py`, `.claude/rules/channels.md` | S |
| 2 | `Researcher` 포트, `ClaudeResearch` 어댑터, `RESEARCHERS`, `Services.research`, `prompts/research.md` | `ports/research.py`, `adapters/claude_research.py`, `registry.py` | M |
| 3 | `core/research.gather`, `step_research`, `STEPS`·`LABELS`·`RUN`·`_fix`, `research_usage`, `job_cost`, `PHASES` | `core/research.py`, `core/pipeline.py`, `web/app.py` | M |
| 4 | `Scene.fact_ids`, `write(facts=…)`, `unverified`, 지시문 한 줄 | `core/script.py`, `prompts/script.md` | M |
| 5 | 확인 화면: 사실 카드, 근거 칩, 설명 미리보기 | `web/templates/job.html`, `web/app.py` `job_page` | M |
| 6 | `pipeline.description()`, `publish`가 그걸 쓰게 | `core/pipeline.py` | S |
| 7 | 스케줄 `review=True`, "검수 필요" 알림 | `core/schedule.py` | S |
| 8 | 두 채널 toml·ko `script.md`·테스트 글자, `flow_auto` 주석 | `channels/*`, `tests/test_script.py`, `tests/test_web.py` | S |
| 9 | 테스트 묶음(7) | `tests/*` | M |

### Gaps
- 시간 추정은 하지 않았다.

## 9. `reports/2분 쇼츠 퀄리티 전략.md` 6절(실행 계획)과 겹치는 것

### Takeaway
2단계(ko 15장면·2분)와 3단계(ja 7장면 유지)는 이번 결정이 대신한다. 0·1단계(지시문·`IdeaOut` 구조 필드)는 그대로 살린다. 4단계 `Scene(lines)`는 `fact_ids`와 모양이 겹치므로 같이 설계해야 한다.

### Cited Findings
- 보고서 6절 2단계: ko `scenes = 15`, `duration = "1분 55초~2분 5초"`, `daily_goal = 1`, `sentence = [62, 68]` (`reports/2분 쇼츠 퀄리티 전략.md:181`).
- 3단계: ja는 "기본은 `scenes = 7` 그대로", `daily_goal`은 결과 보고 정함, `subtitle_limit = 13`, 2분 편은 장면당 46~52자 (`:191`).
- 이야기 구조 절은 50초·90초 근처 재훅 두 개와 "여기까진 다들 아시죠?"를 약 40% 위치로 옮기자고 한다 (`:27`, `:90` 이후).
- 4단계는 `Scene(lines: list[str])`와 Flow 참조 이미지다 (6절, `:153-203`).

### Inferences
- **대신하는 것**:
  - ko: 15장면 → 13장면, 2분 → 약 105초.
  - ja: 7장면·60초 유지 → 13장면·105초, 하루 한 편.
  - 자동 업로드 → 30분 사람 확인 뒤 업로드(스케줄 작업에도 `review=True`).
- **고쳐 쓰는 것**: 재훅 위치를 105초에 맞춰 약 45%(≈47초, 6번째 문장)와 약 85%(≈90초, 11~12번째 문장)로 옮긴다. "여기까진 다들 아시죠?"는 40%(5~6번째 문장)로, 보고서와 같다.
- **그대로 살리는 것**: 0단계 지시문·스타일 고치기, 1단계 `IdeaOut`의 `question`, `beats`, `twist`, `payoff`와 brief 이름표 고치기, `subtitle_limit = 13`. 구조 필드(`beats`)는 조사 단계의 검색 질의를 만드는 재료로도 쓸 수 있다.
- **새로 생기는 것**: `research` 단계, `facts.json`, `fact_ids`, 설명란 출처. 보고서에는 없다.
- **부딪히는 것**: 4단계에서 장면이 여러 줄(`lines`)이 되면 근거를 장면 단위로 둘지 줄 단위로 둘지 정해야 한다. 지금은 장면 = 문장이라 `fact_ids`를 장면에 두는 게 맞다. `lines`로 갈 때 줄 단위로 옮기기는 어렵지 않다.

### Gaps
- 보고서 6절의 검증 지표(`:204` 이후)를 105초·하루 한 편 기준으로 다시 잡을지는 다루지 않았다.
- `research_notes/2분 쇼츠 퀄리티 전략/` 아래 이전 노트들은 읽지 않았다.

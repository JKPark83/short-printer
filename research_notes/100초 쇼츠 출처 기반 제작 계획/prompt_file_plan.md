# 100~110초 출처 기반 쇼츠로 바꿀 때의 지시문 파일 계획

대상: 13장면 × 8초(약 104초). 첫 2초 안에 훅을 두고, 5번째와 9번째 장면에서 물음을 다시 연다. 사실은 번호 붙은 사실 시트에서만 가져온다.
범위: `prompts/*.md`, `channels/{ko-40sec-facts,ja-korea-trip}/*.md`, `channel.toml` 키.
근거: 저장소 코드·테스트·DB(`shorts.db`, 읽기 전용) 실측, 이전 조사(`research_notes/2분 쇼츠 퀄리티 전략/current_prompt_audit.md`, `reports/2분 쇼츠 퀄리티 전략.md` 4절), 같은 폴더의 `search_grounding.md`(사실 시트 설계), 웹 자료.
기준일: 2026-10-16. 저장소와 DB는 바꾸지 않았다.

---

## 1. 지시문 자리표시자: test_prompts·core/prompts가 요구하는 것

### Takeaway
제목(`##`)을 요구하는 테스트는 없다. 자리표시자는 코드가 넘기는 이름과 정확히 같아야 하며, 빠지면 KeyError가 난다. 그래서 새 자리표시자를 만들지 않고 사실 시트는 user 메시지로 보내는 편이 가장 작다.
다만 `tests/test_script.py`, `tests/test_trends.py`, `tests/test_thumbnail.py`는 ko 채널 지시문에 들어 있는 **문구 자체**를 검사한다. 13장면으로 바꾸면 그 문구 목록도 같이 고쳐야 한다(아래 목록).

### Cited Findings
- `render(name, **values)`는 `Template(body(...)).substitute(values)`를 쓴다. 값이 빠지면 KeyError가 나고, 남는 값은 무시한다. `body()`는 맨 앞의 `--- … ---` 머리말을 뺀다. — [core/prompts.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/core/prompts.py)
- `test_every_prompt_file_renders_for_a_real_channel`은 `ko-40sec-facts`로 지시문을 하나씩 채운다. 채우는 지시문은 script, script_revise, script_revise_draft, thumbnail, trend_video, trend_pick, trend_idea, translate, trend_keywords이다. 채운 결과가 비어 있지 않은지, `${`가 남지 않았는지, 첫 줄이 `---`가 아닌지만 본다. 제목 검사는 없다. — [tests/test_prompts.py](/Users/jkpark/my-toy/shorts-printer/tests/test_prompts.py)
- 파일마다 쓰는 자리표시자(지금):

| 파일 | 자리표시자 | 채우는 곳 |
|---|---|---|
| `script.md` | lang, duration, scenes, lo, hi, unit, total_lo, total_hi, channel_script, channel_video | `script.system(ch)` |
| `thumbnail.md` | channel_rules, lang, max_line, max_total | `thumbnail.system(ch)` |
| `trend_pick.md` | lang, concept, production, channel_rules | `trends.system_pick` (trends.py:407) |
| `trend_idea.md` | lang, concept, production, channel_rules, idea_rules, n | `trends.system_idea` (trends.py:451) |
| `trend_keywords.md` | lang, concept, channel_rules | 새 키워드 단계(커밋 전) |
| `trend_video.md` | region, lang, production | trends.py:234 |
| `translate.md` | lang | `script.translate` |
| `script_revise*.md` | 없음 | `script.revise`가 script.md 뒤에 붙인다 |

- 문구를 고정한 테스트:
  - `test_ko_system_keeps_every_old_rule`은 다음 문구를 본다: "52~56초", "정확히 7개", "62~68자", "68자를 넘지", "이모지·해시태그·괄호", "60~90단어", "photoreal", "주인공·장소·시대·옷차림", "앞 5초", "No on-screen text, no numbers, no logos.", "실존 인물의 얼굴", "No dialogue, no voices, no music.", "훅", "존댓말", "널리 확인된", "여기까진 다들 아시죠?", "오늘도 상식 하나 챙기셨네요?", "질문형", "3D 애니메이션", "단면도", "한국어". — [tests/test_script.py:54-60](/Users/jkpark/my-toy/shorts-printer/tests/test_script.py)
  - `test_words_unit_english_system`은 `"## 채널 대본 규칙\nscript.md 본문"`과 `"## 채널 장면 영상 규칙\nvideo_style.md 본문"`을 본다. 이 두 제목은 바꾸면 안 된다. — 같은 파일 63-67행
  - 실호출 테스트는 `6 <= len(s.scenes) <= 7`을 본다(`@pytest.mark.live`). — 같은 파일 213행
  - trend_pick은 "뻔한 절약 요령", "장마철 빨래", "인기 이유(포맷·훅·소재)", "search_terms만 영어", "웹 검색", "재미 규칙", "거짓 낚시"를 본다. trend_idea는 "알아보기 귀찮았던", "난방비", "비어 있으면 채널 분야 안에서"를 본다. — [tests/test_trends.py:252-255, 448-452](/Users/jkpark/my-toy/shorts-printer/tests/test_trends.py)
  - thumbnail은 "한눈에"와 "문구는 한국어로 1~2줄, 줄마다 12자 이내, 합쳐 22자 이내."를 본다. — [tests/test_thumbnail.py:27-28](/Users/jkpark/my-toy/shorts-printer/tests/test_thumbnail.py)
  - 채널 이름 "40초 상식"은 test_schedule(125, 192행), test_web_trends(120, 191행), test_web(45행)에 박혀 있다.

### Inferences
- 사실 시트를 `${facts}`로 지시문에 넣는 안(`search_grounding.md` 5절 4번)도 된다. 그 경우 `script.system(ch)`에 인자가 생기고 `test_prompts`·`revise()`도 사실 시트를 넘겨야 한다.
- 이 노트는 **user 메시지로 보내는 안**을 고른다. 사실 시트는 주제마다 다르고, `write()`가 이미 주제·참고·최근 제목을 user 메시지로 조립한다. 지시문은 "user 메시지의 사실 시트만 쓴다"는 규칙만 갖는다. 이러면 지시문 파일은 자리표시자가 바뀌지 않고 `test_prompts`도 그대로 통과한다. 두 노트 중 하나로 맞춰야 한다.
- 아래 초안대로 고치면 `test_ko_system_keeps_every_old_rule`의 다음 문구를 바꿔야 한다. 의도한 동작 변경이므로 테스트를 고치는 것이 맞다(architecture 테스트가 아니다).

  | 지금 문구 | 바뀐 뒤 문구 |
  |---|---|
  | "52~56초" | "100~110초" |
  | "정확히 7개" | "정확히 13개" |
  | "62~68자" | "52~58자" |
  | "68자를 넘지" | "58자를 넘지" |
  | "60~90단어" | "80~110단어" |
  | "널리 확인된" | "사실 시트" |

  나머지 문구는 초안에 그대로 남긴다.
- 채널 이름을 바꾸면 테스트 4곳을 고쳐야 한다. 이름은 YouTube 채널 이름이기도 하다(아래 5절).

### Gaps
- ja 채널 지시문은 어떤 테스트도 채워 보지 않는다(`test_prompts`는 ko만 본다). ja 파일에 `$`를 실수로 넣어도 테스트가 잡지 못한다.

---

## 2. 13장면 전환은 설정만으로 되는가

### Takeaway
된다. `scenes`·`sentence`·`duration`은 지시문에 들어가는 값일 뿐이고, 렌더 길이는 음성 길이로 정해진다. 정할 것은 문장 길이다. 지금 ko 값(62~68자)은 실제 목소리(크리스)로 읽으면 장면당 8.6~9.6초가 나와 8초 클립을 넘는다.

권장 값:

| 채널 | sentence | 13장면 예상 길이 |
|---|---|---|
| ko | [52, 58] | 약 94~106초 |
| ja | [50, 56] 그대로 | 약 93~104초 |

`duration`은 두 채널 모두 "100~110초"로 둔다.

### Cited Findings
- `ScriptCfg`의 정의:
  - `scenes`는 `Field(7, ge=1, le=20)`이라 13을 받을 수 있다.
  - `sentence`는 (최소, 최대) 짝이고, `duration`은 문자열이다.
  - 출처: [core/channel.py:22-26](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/core/channel.py)
- 값을 쓰는 곳:
  - `script.system()`이 지시문에 `scenes`, `lo`, `hi`, `unit`, `total_lo = lo*scenes`, `total_hi = hi*scenes`, `duration`을 넣는다. — [core/script.py:38-39](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/core/script.py)
  - 그 밖에는 문장 손수정 한도(`sentence[1] * 2`)에만 쓰인다. — [web/app.py:557](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/web/app.py), [job.html:108](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/web/templates/job.html)
  - 장면 수가 맞는지 코드가 확인하는 곳은 없다(`write()`는 장면이 비었는지만 본다).
- 렌더:
  - 전체 길이는 음성 길이 + `TAIL` 0.6초이다.
  - 장면 경계는 문장 시작 시각이다.
  - 문장이 8초보다 길면 클립 마지막 프레임이 멈춘다(`tpad stop_mode=clone`).
  - 출처: [core/render.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/core/render.py) (이전 대화에서 확인)
- `subtitle_limit`은 `pipeline.py:122`의 `sv.channel.style.subtitle_limit or sv.splitter.limit`에만 쓰인다. 기본값은 ko 16자([splitters/ko.py:85](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/adapters/splitters/ko.py)), ja 10자([splitters/ja.py:40](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/adapters/splitters/ja.py))이다.
- 낭독 속도 실측(`shorts.db`의 `timing.json`):

  | 목소리 | 초당 글자 | 지금 설정으로 나온 결과 |
  |---|---|---|
  | 크리스(ko 기본) | 약 7.1~7.2 | 62~68자 문장이 8.0~9.8초, 7장면 합계 63.5초("52~56초" 목표) |
  | 미스터킴 | 약 8.1~8.8 | (channel.toml 주석의 기준 목소리) |
  | 미나미(ja) | 약 7.0 | 50~56자 문장이 6.6~8.2초, 합계 약 53초 |

  측정 대상은 Job 20261016-062150-fb52, 20261015-235528-59f3, 20261015-195423-e9bc, 20261016-054604-c25e 등이다.
- 장면 클립 비용: Omni 1.1 Flash는 360p에서 장면당 6크레딧이다(사용자 메모리·이전 조사). 7장면 42크레딧이 13장면이면 **78크레딧**이 된다.

### Inferences
- 장면당 목표를 7.3~8.0초로 잡는다(문장 사이 쉼 포함). 그러면 글자 수는 이렇다.
  - 크리스: 52~58자. 계산은 7.1자/초 × 7.3~8.2초이다.
  - 미스터킴: 63~68자. 지금 값은 이 목소리에 맞춘 것이다.
  - 미나미: 50~56자(지금 그대로).
- 목소리 속도가 다른데 문장 길이는 채널 설정 하나라서, 목소리를 바꾸면 길이가 틀어진다. ko 기본 목소리가 크리스이므로 [52, 58]을 권한다.
  - `# ponytail:` 같은 한계로 남기고, 실측이 쌓이면 목소리별 초당 글자 수로 바꾸는 길이 있다.
  - 지금은 channel.toml 주석에 기준 목소리를 적어 둔다.
- 이전 보고서는 ja 피로를 줄이려고 46~52자를 제안했다. 그러면 13장면이 약 86~97초가 되어 100초에 못 미친다. 100초가 우선이면 50~56자, 듣기 편한 쪽이 우선이면 46~52자에 14장면을 쓴다(84크레딧). 사용자가 고를 문제이다.
- `subtitle_limit`은 바꾸지 않는다. ja 10자는 Netflix 일본어 기준(가로 한 줄 13자)보다 짧아 이미 안전하고, 길이가 늘어도 자막 한 줄 길이와는 상관없다.
- 13장면 문장 수가 정확한지 코드로 확인하지 않는다. LLM이 12개나 14개를 내도 그대로 진행된다. 지금도 같은 한계이고, 장면이 늘수록 틀릴 확률이 커진다. `write()`에서 `len(scenes) != ch.script.scenes`면 다시 요청하는 한 줄을 더할지는 사용자가 정한다.

### Gaps
- 크리스·미나미 속도는 각 3~4편 실측이다. 문장 사이 쉼과 ElevenLabs 앞쪽 무음이 길이에 얼마나 들어가는지는 따로 재지 않았다.
- 첫 문장 2초 훅이 실제로 2초 안에 들리는지는 TTS 시작 지연에 달려 있다. 시험 1편으로 확인해야 한다.

---

## 3. core/script.py가 LLM에게 받는 출력과 출처 묶기에 필요한 코드 변경

### Takeaway
지금 출력은 `Script(title, description, tags, scenes[sentence, prompt], sensitive)`이다. 출처 묶기와 검토용 한국어 한 줄을 위해 `Scene`에 `fact_ids: list[str]`과 `prompt_ko: str`을 더하고, `write()`가 사실 시트를 user 메시지에 붙인다. 지시문 파일만으로는 사실 시트를 넘길 수 없으므로 이 부분은 코드 변경이다.

### Cited Findings
- 지금 모델([core/script.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/core/script.py)):
  - `Scene.sentence`: "내레이션 한 문장"
  - `Scene.prompt`: "이 문장 동안 보일 한 장면의 영어 영상 생성 프롬프트, 스타일 머리말 없이"
  - `Script.title`: "쇼츠 제목. 40자 이내, 해시태그 없이"
  - `Script.description`: "영상 설명 2~3문장, 끝에 해시태그 3개"
  - `Script.tags`: "검색 태그 5~10개, # 없이"
  - `Script.sensitive`: 민감 분야 이름 또는 빈 문자열
  - `flat()`은 `sentences`·`prompts` 배열로 펴서 `script.json`에 넣는다.
- `write()`의 user 메시지 순서:
  1. `주제: …`
  2. brief가 있으면 `참고(최근 인기 쇼츠 분석). 훅·전개·속도는 따르되 문장을 베끼지 않는다:\n{brief}`
  3. `채널 분야: …`
  4. 최근 제목
  - 출처: [core/script.py:108-125](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/core/script.py)
- 스타일 머리말은 코드가 붙인다: `f"{style} {s.prompt}"`. 그래서 저장된 prompt는 머리말을 포함한다. — 같은 곳 122-124행
- `revise()`는 `Revision(title, description, tags, sentences)`를 받고, 확정 전에는 `Draft(+prompts)`를 받는다. 지시문은 `script.md` 뒤에 `script_revise*.md`를 붙인 것이다. 사실 시트는 넘기지 않는다. — 같은 파일 43-72행
- `script_revise.md`·`script_revise_draft.md`는 "위 규칙과 요청이 부딪히면 요청을 따른다"로 끝난다. — [prompts/script_revise.md](/Users/jkpark/my-toy/shorts-printer/prompts/script_revise.md)
- 아이디어 모드 주제의 `IdeaOut.content`는 "핵심 답과 사실 2~3문장. 300자 이내"이다. `brief()`는 아이디어 모드여도 "최근 인기 쇼츠 분석"이라는 꼬리표로 넘긴다. — [core/trends.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/core/trends.py), script.py:113

### Inferences
코드 변경 목록. 모두 core 안이고, 공급자 이름은 들어가지 않는다.
1. `Scene`에 두 필드를 더한다.
   - `fact_ids: list[str] = Field(description="이 문장이 기대는 사실 시트 번호(F1 등). 훅·연결·물음·고정 멘트 문장은 빈 목록")`
   - `prompt_ko: str = Field(description="prompt가 보여 줄 장면을 한국어 한 줄로. 40자 안팎, 검토용")`
   - `flat()`이 `fact_ids`·`prompts_ko` 배열도 낸다. `Draft`에는 `prompts_ko`를, `Revision`·`Draft`에는 `fact_ids`를 더한다.
2. `write(..., facts: str | None = None)`가 user 메시지에 사실 시트 블록을 붙인다.
   - 모양: `사실 시트(이것만 사실로 쓴다):\nF1. … (기준 2026-10, 출처 기관)`
   - URL은 빼서 토큰을 아낀다. URL은 저장소의 사실 시트 문서에 남기고 검토 화면이 번호로 잇는다(`search_grounding.md` 5절).
3. `revise()`도 같은 사실 시트를 user 메시지에 붙인다. `script_revise*.md`에 "사실 시트 규칙만은 요청보다 앞선다" 한 줄을 더한다(4절).
4. `brief()`의 꼬리표는 모드에 따라 고른다("참고(추천 주제 요약)"). 문구가 코드에 있지만 지시문이 아니라 사용자 메시지 조립이라 규칙 위반은 아니다.
5. `IdeaOut.content` 한도를 300자에서 500자로 늘리고, 설명을 "핵심 답 한 문장과 확인할 주장 3~5개"로 바꾼다. 105초 대본은 2~3문장 요지로는 모자라고, 이 주장들이 조사 단계의 질문이 된다.

### Gaps
- 구조화 출력에 필드가 둘 늘면 장면 13개의 출력 토큰이 늘어난다(장면당 약 30~50토큰). 비용은 재지 않았다.

---

## 4. 105초 출처 기반 형식과 부딪치는 지금 규칙

### Takeaway
부딪치는 규칙은 네 묶음이다.
1. 길이 숫자: 40초, 50초, 52~56초, 40~50초, "1分".
2. 사실 기준: "널리 확인된 것만"이 사실 시트 기준과 다르다.
3. 구조: 4번째 문장 고정 멘트, 3초 훅.
4. 제목 규칙과 머리말: 추천 단계 제목 규칙이 대본·썸네일과 어긋나고, 머리말에는 조명 충돌·무의미 문구가 있다.

화면 문구가 낡은 곳도 하나 있다(ko 썸네일의 "위 검은 띠에 제목").

### Cited Findings

| 파일 | 지금 문구 | 왜 부딪치나 |
|---|---|---|
| `channels/ko-40sec-facts/ideas.md` | "40초 안에 답이 딱 떨어지는 것" | 105초 형식은 물음을 두 번 다시 열 만큼 층이 있어야 한다 |
| `channels/ja-korea-trip/ideas.md` | "50초 안에 답이 딱 떨어지는 것" | 위와 같다 |
| ko `channel.toml` `[trends] production` | "40~50초" | 주제 고르기 지시문에 그대로 들어간다(trends.py:407, 451) |
| ja `channel.toml` `[trends] production` | "50~56초" | 위와 같다 |
| ko `channel.toml` `name`·`description` | "40초 상식", "…40초 안에 알려 드려요." | 채널 소개와 실제 길이가 다르다 |
| ja `channel.toml` `description` | "1分のミニチュアガイド", "毎日2本更新" | 길이가 다르고, 78크레딧 × 2편이면 하루 156크레딧이다 |
| ko `script.md` | "숫자와 사실은 널리 확인된 것만 쓴다" | 사실 시트 밖의 "널리 확인된" 사실을 허용한다 |
| ja `script.md` | "공식 자료(…)로 널리 확인된 것만" | 위와 같다 |
| ko `script.md` | 4번째 문장이 "여기까진 다들 아시죠?"로 시작 | 13장면이면 1/3 지점(5번째)이 맞다 |
| ko·ja `script.md` | "첫 문장은 3초 안에" | 목표는 2초이다 |
| `trend_pick.md`·`trend_idea.md` | "답을 제목에서 다 말하지 않는다" | 대본·썸네일은 "답·반전·결론과 그 단서를 넣지 않는다"로 더 엄격하다 |
| `trend_idea.md` | "content는 … 사실 2~3문장. 숫자는 널리 확인된 것만" | 105초에 모자라고, 사실 기준이 다르다 |
| ko `thumbnail.md` | "같은 문구가 영상 내내 위 검은 띠에 제목으로도 뜬다" | `layout = "clean"`이면 영상에 제목이 뜨지 않는다 |
| ko·ja `[video] style` | "soft even daylight", "same art style in every shot" | 밤·저녁 장면과 충돌하고, 뒤 문구는 효과가 없다 |
| ja `[video] style` | "a tabletop scale model of Seoul" | 실내(편의점·호텔 방) 장면에도 붙는다 |
| ja `video_style.md` | "… → 배경 → 분위기 순" | 분위기 자리에 머리말의 화풍 낱말이 다시 들어간다 |
| `script.md` | "prompt는 … 60~90단어" | 실제 출력 28장면 중 27개가 90단어를 넘는다(6절) |

- 출처:
  - 파일 문구는 각 파일 원문에서 가져왔다.
  - 머리말·분위기·실내 문제는 [current_prompt_audit.md](/Users/jkpark/my-toy/shorts-printer/research_notes/2분%20쇼츠%20퀄리티%20전략/current_prompt_audit.md) 3절에서 가져왔다.
  - 제목 규칙 불일치와 40/50초 기준은 [reports/2분 쇼츠 퀄리티 전략.md](/Users/jkpark/my-toy/shorts-printer/reports/2분%20쇼츠%20퀄리티%20전략.md) 4절에서 가져왔다.
  - 이전 보고서의 15장면 안은 이 노트에서 13장면으로 줄였다.

### Inferences
- 길이 숫자는 모두 "100~110초"로 맞춘다. 사용자에게 보이는 문구(ja 설명)는 "2分弱"으로 맞춘다.
- "널리 확인된"은 "사실 시트에 있는 것만"으로 바꾼다. 일반론("확실하지 않으면 일반론으로 말한다")도 지운다. 일반론은 출처 없이 사실처럼 들리는 문장을 만든다. 시트로 모자라면 같은 사실을 예시·비교로 풀게 한다.
- 제목 규칙은 세 곳에서 같은 문장을 쓴다: "답·반전·결론과 그 단서를 넣지 않는다". 세 곳은 추천 topic, 대본 title, 썸네일이다.

### Gaps
- 없음(모두 저장소 원문 대조).

---

## 5. 파일별 이전 → 이후 초안

### Takeaway
- 공통 지시문: `script.md`는 길이·흐름·사실·장면 prompt 네 덩어리로 다시 쓴다. `trend_pick.md`·`trend_idea.md`는 제목 규칙, 105초 주제 기준, 출처 확인 세 줄을 바꾼다. `thumbnail.md`·`translate.md`는 한 줄씩 더한다. `trend_keywords.md`는 그대로 둔다.
- 채널 파일: 고정 멘트 위치(4번째에서 5번째로), 9번째 다시 걸기, 마스코트 문장, 문화 물건 낱말 풀이, 길이 숫자를 바꾼다.
- 자리표시자는 모두 지금 것만 쓴다.

### Cited Findings
- 지시문은 코드에 쓰지 않는다. 공통은 `prompts/<이름>.md`, 채널마다 다른 규칙은 `channels/<id>/*.md`에 둔다. 글자 `$`는 `$$`로 쓴다. — [.claude/rules/conventions.md](/Users/jkpark/my-toy/shorts-printer/.claude/rules/conventions.md)
- 채널 글 파일은 부를 때마다 읽는다. — [.claude/rules/channels.md](/Users/jkpark/my-toy/shorts-printer/.claude/rules/channels.md)
- Veo 3.1 공식 프롬프트 요소: 장면, 피사체, 동작, 카메라, 조명, 소리. 소리는 대사·효과음(SFX)·배경음(ambient)으로 나눠 적으라고 권한다. — [Google Cloud, Ultimate prompting guide for Veo 3.1](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1), [DeepMind Veo prompt guide](https://deepmind.google/models/veo/prompt-guide/)
- Omni Flash는 기본으로 여러 샷을 만들 수 있다. 한 장면이 필요하면 "In a single unbroken scene"이나 "No scene cuts"로 쓰고, 원치 않는 것은 "No dialogue"처럼 직접 쓰라고 한다. — [Gemini API, Gemini Omni Flash](https://ai.google.dev/gemini-api/docs/omni)
- 고정 캐릭터는 참조 이미지로 이어 가는 것이 가장 안정적이라는 3자 정리가 있다. — [OpenArt, Gemini Omni Flash prompt guide](https://openart.ai/blog/gemini-omni-flash-prompt-guide/)

### Inferences

아래 "이후" 블록은 파일에 그대로 넣을 수 있는 전문이다. 머리말(`--- … ---`)의 설명은 LLM에 가지 않는다.

#### 5-1. `prompts/script.md`

- **남기는 것:**
  - 역할 첫 문단, 언어 규칙, 기호 금지, 8초 상한.
  - 머리말 중복 금지, 매번 다시 적기, 가운데·앞 5초, 카메라 하나.
  - "No on-screen text, no numbers, no logos.", 실존 인물·브랜드 금지, 대사·음악 빼기.
  - 두 채널 제목(`## 채널 대본 규칙`, `## 채널 장면 영상 규칙`). 테스트가 본다.
- **빼는 것:**
  - "릴스·틱톡"(쇼츠 길이 맞춤 형식이 되었다).
  - "60~90단어"(실제와 다르다).
  - "Audio: …" 한 줄 꼴. SFX와 Ambient로 나눈다. 코드는 "Audio:"를 읽지 않는다. `infra/ffmpeg.py:18`의 "Audio:"는 ffprobe 출력 검사라 상관없다.
- **더하는 것:**
  - `## 흐름`: 2초 훅, 1/3·2/3 지점 다시 걸기.
  - `## 사실`: 사실 시트만 쓰기, fact_ids, 강도 그대로.
  - `## 제목·설명`: 세 곳 공통 규칙.
  - prompt 변환 규칙: 6절 결과(그림 하나, 세기 금지, 글자 유도 물건 금지, 지명 대신 모습, 마스코트, 시간대 빛, 카메라와 장면 역할).
  - `prompt_ko`.

이후(전문):

```markdown
---
대본 쓰기 지시문(모든 채널 공통). 채널마다 다른 말투·화풍은 channels/<id>/script.md·video_style.md에 쓴다.
${이름} 자리는 앱이 채운다: lang 대본 언어, duration 목표 길이, scenes 장면 수, lo·hi 문장 길이,
unit 단위(자·단어), total_lo·total_hi 전체 길이, channel_script·channel_video 채널 글 파일 본문.
사실 시트는 주제마다 달라 지시문이 아니라 user 메시지로 온다(core/script.py write).
고치면 다음 대본부터 바로 반영된다(서버 재시작 필요 없음).
---
너는 유튜브 쇼츠용 ${lang} 내레이션 대본을 쓴다. 대본은 TTS가 그대로 읽고, 자막으로 화면에 뜬다. 장면 하나가 한 칸이고, 장면 영상은 prompt로 AI 영상 생성 서비스가 만든다.

## 길이
- 문장·제목·설명·태그는 ${lang}로 쓰고, prompt만 영어로 쓴다.
- 읽었을 때 ${duration} 길이. 장면은 정확히 ${scenes}개, 장면마다 ${lo}~${hi}${unit}(모두 합쳐 ${total_lo}~${total_hi}${unit}). 장면마다 생성 비용이 들어 장면 수를 늘리지 않고, 장면 클립이 8초라 한 장면이 ${hi}${unit}를 넘지 않게 한다.
- 한 장면 칸에 짧은 문장 두 개를 넣어도 된다. 길이는 두 문장을 합쳐 센다.
- TTS가 기호까지 읽으므로 문장에 이모지·해시태그·괄호·특수기호를 넣지 않는다.

## 흐름
긴 쇼츠는 중간에 넘기는 사람이 많아, 앞에서 연 물음을 끝까지 들고 가고 중간에 두 번 다시 건다.
- 첫 장면은 짧은 문장 두 개다. 첫 문장은 2초 안에 다 읽히게 아주 짧게 쓴다(한국어·일본어 15자 안팎, 영어 다섯 낱말 안팎). 질문이나 의외의 사실 하나만 던진다. 둘째 문장은 이 영상이 무엇에 답하는지 약속한다.
- 장면 수의 약 3분의 1 지점(13장면이면 5번째)에서 첫 번째로 다시 건다. 앞에서 말한 통념을 뒤집거나 덜 알려진 사실을 연다.
- 약 3분의 2 지점(13장면이면 9번째)에서 두 번째로 다시 건다. 아직 답하지 않은 물음 하나를 새로 열거나, 남은 장면에서 나올 것을 예고한다. 같은 영상 안에서 두 번 다 같은 말투로 열지 않는다.
- 다시 거는 문장 사이 장면은 원리·근거·예시를 한 장면에 하나씩 쌓는다. 같은 말을 되풀이해 길이를 채우지 않는다.
- 마지막 장면에서 첫 장면의 물음에 답이 끝나야 한다.

## 사실
- 사실은 user 메시지의 사실 시트(F1, F2 …)에서만 가져온다. 시트에 없는 숫자·연도·가격·고유명사·원인과 결과는 쓰지 않는다. 상식처럼 보여도 시트에 없으면 쓰지 않는다.
- 장면마다 그 문장이 기댄 사실 번호를 fact_ids에 적는다. 훅·연결·물음·고정 멘트만 있는 장면은 비워도 된다.
- 시트가 "연구에 따르면", "유력한 설명", "일부 지역"처럼 말하면 대본도 그 강도로 말한다. 가설을 정설처럼, 일부를 전부처럼 말하지 않는다.
- 시트에 기준 시점이 붙은 사실(요금, 제도, 운영 시간)은 문장에도 기준 시점을 넣는다.
- 시트로 장면을 다 채우기 모자라면 사실을 지어내지 말고, 시트의 사실을 생활 예시·비교·물음으로 풀어 쓴다.

## 제목·설명
- 제목은 시청자가 궁금했던 물음이다. 답·반전·결론과 그 단서를 넣지 않는다. 답은 영상 안에서만 나온다. 꼴은 채널 대본 규칙을 따른다.
- 설명은 영상에서 실제로 말한 내용만 쓴다. 영상에 없는 내용을 약속하지 않는다.

## 장면 prompt
- prompt는 그 장면을 읽는 약 8초 동안 보일 한 장면을 영어 한 단락(80~110단어)으로 쓴다. "Single continuous shot,"으로 시작한다.
- 문장의 핵심 그림 하나만 옮긴다. 문장에 나온 것을 다 그리지 않는다. 그림 하나는 첫 두 문장 안에 둔다.
- 생성 서비스는 앞 프롬프트를 기억하지 않으므로 주인공·장소·시대·옷차림·시간대를 매번 다시 적어 장면이 이어지게 한다.
- 사람이 필요하면 채널 장면 영상 규칙의 마스코트 문장을 글자 그대로 넣는다. 다른 주인공을 새로 만들지 않는다. 조연은 옷 색 하나로만 구분한다.
- 앱이 모든 prompt 앞에 같은 스타일 머리말을 붙이므로 prompt에 화풍·재질·분위기·품질 문구(photoreal, cinematic, clay texture, tilt-shift 등)를 쓰지 않는다. 빛은 그 장면의 시간대 한 구절만 쓴다(예: warm dusk light, night with soft window glow).
- 숫자·글자·기호는 그리지 않는다. 숫자는 크기·길이·높이·양의 차이로, 비율은 많은 무리와 적은 무리로 보여 주고 사람이나 물건을 세게 하지 않는다(ten people, two or three of them 같은 말 금지). 물음표·체크·X 아이콘, 그래프 막대, 달력, 시계, 가격표, 간판, 화면처럼 글자나 숫자가 들어갈 물건은 쓰지 않는다. 꼭 있어야 하면 plain and blank로 쓴다.
- 지명·가게 이름은 그림이 되지 않는다. 이름 대신 보이는 모습(낮은 붉은 벽돌 공장 골목, 가파른 비탈 상점가)을 쓴다. 한국 문화 물건은 채널 장면 영상 규칙의 낱말 풀이를 그대로 쓴다.
- 핵심 피사체와 동작은 화면 가운데, 앞 5초 안에 둔다. 영상의 양옆과 뒷부분은 잘릴 수 있다.
- 카메라 움직임은 하나만, 장면 역할에 맞춰 고른다. 훅과 다시 거는 장면은 보여 주며 바뀌는 움직임(reveal, pull-back), 설명 장면은 slow push-in이나 sideways truck, 마지막 장면은 pull-back. 같은 움직임을 세 장면 넘게 잇지 않는다.
- 실존 인물의 얼굴, 브랜드, 화면비 문구는 넣지 않는다.
- 생성 서비스가 소리도 만들고 앱이 효과음으로 깐다. 내레이션은 따로 입히므로 사람 목소리·음악은 넣지 않는다. prompt 끝은 다음 두 줄이다.
  SFX: <이 장면 동작의 소리 1~2개>. Ambient noise: <배경음 하나>. No dialogue, no voices, no music.
  No on-screen text, no numbers, no logos.
- prompt_ko에는 prompt가 보여 줄 장면을 한국어 한 줄(40자 안팎)로 적는다. 사람이 영어 prompt를 검토할 때 읽는다. prompt에 없는 것을 적지 않는다.

## 채널 대본 규칙
${channel_script}

## 채널 장면 영상 규칙
${channel_video}
```

- 테스트 문구 확인: "이모지·해시태그·괄호", "photoreal", "주인공·장소·시대·옷차림", "앞 5초", "No on-screen text, no numbers, no logos.", "실존 인물의 얼굴", "No dialogue, no voices, no music."은 남아 있다.
- 바꿔야 하는 테스트 문구: "60~90단어"는 "80~110단어"로, "널리 확인된"은 "사실 시트"로 바꾼다(1절 표).
- `script_revise.md`·`script_revise_draft.md` 끝 문장 "위 규칙과 요청이 부딪히면 요청을 따른다." 뒤에 한 문장을 더한다: "단, 사실 시트에 없는 숫자·사실을 더하라는 요청은 따르지 않고 그 문장을 그대로 둔다." 손으로 고치는 길(상세 화면 문장 편집)은 열려 있으므로 운영자가 직접 넣을 수 있다.

#### 5-2. `prompts/thumbnail.md`

- 남기는 것: 전부.
- 더하는 것: `## 길이 한도` 아래에 근거 한 줄을 둔다. 제목 규칙은 채널 파일이 갖고 있어 공통에는 숫자 규칙만 더한다.

이후(달라진 부분만):

```markdown
## 길이 한도
문구는 ${lang}로 1~2줄, 줄마다 ${max_line}자 이내, 합쳐 ${max_total}자 이내.
숫자를 넣으면 대본에 나온 숫자만 쓴다. 대본에 없는 숫자·사실을 문구로 약속하지 않는다.
```

- 테스트 문구 "문구는 한국어로 1~2줄, 줄마다 12자 이내, 합쳐 22자 이내."는 그대로 남는다.

#### 5-3. `prompts/translate.md`

- 남기는 것: 전부. 따로 불러 "실제로 적힌 글"을 보게 하는 설계가 출처 검토에도 맞다.
- 더하는 것: 숫자 보존 한 줄, notes에서 볼 것 한 가지.

이후(달라진 부분만):

```markdown
- 숫자·날짜·가격·단위는 원문 그대로 옮긴다. 환산하거나 반올림하지 않는다(사실 시트와 맞춰 보려고).
- notes에는 원문에서 어색한 표현, 사실이 틀렸거나 확인이 필요한 내용, 기준 시점 없이 바뀌기 쉬운 숫자(가격·운영 시간·제도), 시청자가 오해하거나 불쾌해할 수 있는 말을 한국어로 짧게 적는다. 없으면 빈 목록.
```

#### 5-4. `prompts/trend_keywords.md`

변경 없음. 검색어는 인기 쇼츠를 찾는 단계라 길이·출처와 관계가 없다. 105초 기준은 다음 단계(pick·idea)에서 거른다.

#### 5-5. `prompts/trend_pick.md`

- **남기는 것:** 역할, 채널 분야, production, channel_rules, 재미 규칙(테스트 문구 "재미 규칙", "거짓 낚시" 포함), 공통 규칙의 "인기 이유(포맷·훅·소재)", "웹 검색", "search_terms만 영어".
- **빼는 것:** "답을 제목에서 다 말하지 않는다."
- **더하는 것:** 세 곳 공통 제목 규칙, 105초 주제 기준 블록, 출처 확인 기준.

이후(달라진 부분만. 재미 규칙 셋째 줄과 그 아래 새 블록, 공통 규칙 첫 줄):

```markdown
- topic은 궁금증을 남기는 물음으로 쓴다. 답·반전·결론과 그 단서를 넣지 않는다(대본 제목·썸네일과 같은 규칙).

길이 규칙(우리 쇼츠는 약 1분 45초, 13장면):
- 반전 하나로 끝나는 주제보다 층이 있는 주제를 고른다: 시청자가 아는 것 → 뒤집히는 사실 → 그 원리나 근거 → 생활에서 써먹을 것. 이 네 단계를 채울 사실이 없으면 고르지 않는다.
- 중간에 물음을 한 번 더 열 거리(두 번째 의외의 사실, 흔한 실수)가 있는 주제를 먼저 고른다.

공통 규칙:
- 고르기 전에 웹 검색으로 지금 사람들이 궁금해하는 화제·계절 이슈를 찾아보고, 주제의 핵심 주장마다 공공기관·학술·공식 사이트 같은 1차 출처가 있는지 검색으로 확인한다. 1차 출처를 못 찾은 주장이 핵심이면 고르지 않고 excluded에 이유를 남긴다.
```

#### 5-6. `prompts/trend_idea.md`

- **남기는 것:** 역할, 주제 기준(`${idea_rules}`), "비어 있으면 채널 분야 안에서", 채널 추천 규칙, 재미 규칙, 민감 주제·중복·재추천 회피, 점수, 언어 규칙.
- **바꾸는 것:** 제목 규칙(5-5와 같은 줄), 길이 규칙 블록(5-5와 같은 블록), 아래 사실 세 줄.

이후(공통 규칙의 사실 관련 줄):

```markdown
- 고르기 전에 웹 검색으로 지금 사람들이 궁금해하는 화제·계절 이슈를 찾아보고, 주제의 핵심 주장마다 공공기관·학술·공식 사이트 같은 1차 출처가 있는지 확인한다. 1차 출처를 못 찾은 주제는 고르지 않는다.
- 연구 결과나 가설이면 content에 그렇게 밝힌다("연구에 따르면", "유력한 가설은" 등). 출처가 쓴 강도보다 세게 말하지 않는다.
- content는 핵심 답 한 문장과, 대본에 쓸 확인할 주장 3~5개다. 주장마다 숫자·날짜는 출처 표현 그대로 쓰고 끝에 출처 기관 이름을 붙인다. 다음 단계에서 이 주장들을 다시 출처로 확인해 사실 시트를 만든다.
```

- `IdeaOut.content` 300자 한도를 500자로 늘리는 코드 변경이 함께 필요하다(3절).
- "확실히 검증된 사실만 쓴다. 통설이 틀린 경우 바로잡는 각도가 좋다."는 둘째 문장만 남겨 재미 규칙 쪽으로 옮긴다. 첫 문장은 위 1차 출처 줄로 바뀐다.

#### 5-7. `channels/ko-40sec-facts/script.md`

- **남기는 것:** 존댓말, 문장 채우기 규칙, 마지막 고정 멘트와 좋은 예, 구독 요청 금지, 제목 질문형 규칙 전부.
- **빼는 것:** "3초 안에", "숫자와 사실은 널리 확인된 것만 … 일반론으로 말한다.", "4번째 문장을 여기까진 다들 아시죠?로 시작".
- **더하는 것:** 2초 훅 예, 고정 멘트를 5번째로, 9번째 다시 걸기 예, 사실 시트 강도 규칙의 채널 예.

이후(전문):

```markdown
# 대본 규칙

- 첫 장면의 첫 문장은 2초 안에 끝나는 훅이다. 15자 안팎의 질문이나 의외의 사실 하나로 시작하고, 둘째 문장에서 영상이 답할 물음을 분명히 한다.
  - 좋은 예: 바나나, 원래 곧았을까요? 우리가 먹는 바나나가 왜 휘어 있는지, 끝까지 보시면 남한테 설명할 수 있습니다.
- 말하듯 자연스러운 존댓말로 쓴다.
- 숫자와 사실은 사실 시트에 있는 것만, 시트가 말한 강도 그대로 쓴다. "연구마다 다르지만", "가장 유력한 설명은"처럼 시트가 단 단서를 빼지 않는다.
- 한 장면이 클립 8초를 거의 다 채울 만큼 길다. 같은 말을 되풀이하거나 꾸밈말로 늘리지 말고, 장면마다 이유·원리·비교·생활 속 예시 중 하나를 더 담아 내용으로 채운다.
- 채널 고정 멘트 두 개를 글자 하나 바꾸지 않고 매번 넣는다. 따옴표 없이 문장 안에 그대로 쓴다.
  - 중간: 5번째 장면을 여기까진 다들 아시죠? 로 시작하고, 같은 장면 안에서 바로 덜 알려진 사실이나 반전으로 넘어간다. 그래서 1~4번째 장면은 많이 아는 내용과 생활 속 장면으로, 6번째 장면부터는 의외의 내용과 그 근거로 짠다.
  - 마지막: 마지막 장면은 두 문장이다. 정보의 마무리나 반전을 마침표로 끝낸 뒤, 따로 떨어진 한 문장 오늘도 상식 하나 챙기셨네요? 로 끝낸다. 앞 문장에 이어 붙이지 않아야(예: ~해서 오늘도…, ~니까 오늘도…) 마무리 멘트로 바로 들린다. 구독·댓글 요청은 넣지 않는다.
    - 좋은 예: 바나나는 처진 게 아니라 해를 향해 고개를 든 겁니다. 오늘도 상식 하나 챙기셨네요?
  - 고정 멘트도 장면 길이에 들어가므로 나머지 부분을 그만큼 짧게 쓴다. 고정 멘트 앞뒤 문장은 매번 다르게 써서 같은 말이 반복되는 느낌을 줄인다.
- 9번째 장면은 두 번째로 다시 거는 자리다. 고정 멘트가 아니므로 매번 다르게 쓴다. 남은 물음 하나를 새로 열거나, 아직 말하지 않은 반전을 예고한다.
  - 예: 그런데 진짜 이상한 건, 같은 빛을 봐도 어떤 사람은 멀쩡하다는 겁니다. / 여기서 하나 더, 이걸 알면 내일 아침이 달라집니다.
  - 나쁜 예: 놀라운 사실이 하나 더 있습니다(무엇이 놀라운지 없음).
- 제목은 질문형으로 쓴다. 시청자가 평소 궁금했지만 찾아보지 않았던 물음을 시청자 말투 그대로 묻는다. 보자마자 어? 나도 저거 궁금했는데 하는 생각이 들어야 한다.
  - 좋은 예: 주유구 위치, 차에서 내리지 않고 확인할 수 있다? / 바나나는 왜 휘어져 있을까?
  - 나쁜 예: 바나나는 땅이 아니라 하늘을 향해 휩니다(답을 말함) / 주유구 방향, 계기판 화살표 하나로 끝(답을 말함)
  - 답·반전·결론과 그 단서를 제목에 넣지 않는다. 답은 영상 안에서만 나온다.
  - 최근 제목이 주어지면 물음의 끝맺음(~일까?, ~할 수 있다?, ~해도 될까?, ~의 정체는?)을 바꿔 같은 꼴이 이어지지 않게 한다.
```

- 테스트 문구 "훅", "존댓말", "여기까진 다들 아시죠?", "오늘도 상식 하나 챙기셨네요?", "질문형"은 남아 있다.
- 바나나 훅 예의 둘째 문장은 사실이 아니라 약속이라 fact_ids가 필요 없다.

#### 5-8. `channels/ko-40sec-facts/video_style.md`

- **남기는 것:** "3D 애니메이션", "단면도"(테스트 문구), 얼굴을 단순화한 캐릭터.
- **바꾸는 것:** 빨간 선을 coral 선 하나로 바꾼다(머리말 팔레트와 맞춘다).
- **더하는 것:** 마스코트 문장, 색 약속, 카메라 묶음, 그리기 약한 것, 낱말 풀이(생활 상식 채널이 자주 쓰는 물건만).

이후(전문):

```markdown
# 장면 영상 규칙

- 화풍은 실사가 아니라 건축·과학 해설 채널 같은 깔끔한 3D 애니메이션이다. 화풍은 앱이 머리말로 붙이므로 prompt에는 쓰지 않는다.
- 사람이 필요하면 아래 마스코트 문장을 글자 그대로 넣는다. 영상마다 새 주인공을 만들지 않는다. 다른 사람은 얼굴을 단순화한 3D 캐릭터로, 옷 색 하나만 정해 짧게 쓴다.
  - Dot, the channel's guide character: a small round-headed 3D figure with dot eyes, a mustard-yellow knit sweater and teal trousers.
- 눈에 안 보이는 원리나 수치는 숫자 대신 단면도(cutaway)와 선·화살표, 크기·길이·높이 차이로 보여 준다. 선과 화살표는 glowing coral 하나로 쓴다(흐름·원인). 비교는 같은 물건 두 개의 크기 차이로 보여 준다.
- 사람 무리·물건 개수로 비율을 보여 주지 않는다. "열 명 중 두세 명"은 많은 무리 가운데 몇몇만 빛나는 장면으로 쓰고, 몇 명인지 적지 않는다.
- 글자가 들어갈 물건(시계, 달력, 그래프, 간판, 화면, 물음표·X 아이콘)은 쓰지 않는다. 시간 흐름은 해의 위치나 그림자 길이로, 계산·데이터는 빛나는 작은 정육면체 흐름으로 보여 준다.
- 카메라는 이 넷 중 하나를 쓴다: slow push-in, sideways truck, top-down crane, slow pull-back. 훅과 5·9번째 장면은 pull-back이나 reveal로 화면이 바뀌게 한다.
- 한국 생활 물건은 이름 뒤에 생김새를 붙여 쓴다.
  - 온돌: a cutaway of a Korean ondol floor, warm air flowing through channels under flat stone slabs beneath a living room floor
  - 김치냉장고: a plain white chest-style kimchi refrigerator with a top lid
  - 교통카드: a plain blank card-sized transit pass tapped on a round reader at a subway gate
  - 김밥: gimbap, a seaweed-wrapped rice roll sliced into round pieces showing yellow, green, orange and egg fillings
```

- 마스코트 이름과 생김새는 이전 조사(audit 3절)의 안이다. 시험 생성으로 정한 것이 아니라서 처음 몇 편에서 모습이 이어지는지 확인해야 한다(Gaps).

#### 5-9. `channels/ko-40sec-facts/thumbnail.md`

- **바꾸는 것:** 맨 앞 문단의 낡은 문장, 1절 넷째 줄.
- **더하는 것:** 숫자 근거 한 줄.
- 나머지(2~4절)는 그대로 둔다. "한눈에"(테스트 문구)도 남긴다.

이후(달라진 부분만):

```markdown
썸네일은 1080×1920 세로 한 장이다. 휴대폰 피드에서 엄지손톱만 하게 보여도 0.5초 안에 읽혀야 한다. 문구는 썸네일 위 검은 띠에 들어간다(영상에는 제목 없이 자막만 뜬다).

- 쇼츠 화면은 위 10%(검색창)가 가려지므로 짧게 쓴다.
- 숫자를 넣으면 대본에 나온 숫자만 쓴다.
```

- 첫 문단은 ja 파일과 같은 문장으로 맞춘 것이다. "문구는 위 검은 띠(영상칸 위)에 들어간다."를 지우고 그 자리에 위 두 줄을 넣는다.

#### 5-10. `channels/ko-40sec-facts/trends.md`

이후(전문). 둘째 줄은 테스트 문구 "장마철 빨래"를 담고 있어 그대로 둔다.

```markdown
# 추천 주제 고르기 규칙

- 바로 써먹을 생활 정보도 좋지만 "몰랐는데 진짜?" 싶은 반전이나 원리가 있어야 한다. 뻔한 절약 요령 나열은 고르지 않는다.
- 오늘 날짜의 계절·시기에 맞는 주제를 우선한다(예: 겨울 난방비·결로, 여름 전기요금·제습, 장마철 빨래, 명절, 이사철).
- 핵심 사실을 정부·공공기관(질병관리청, 식품의약품안전처, 기상청, 국립국어원 등)이나 학술 자료로 확인할 수 있는 주제를 고른다. 블로그·커뮤니티에서만 도는 이야기는 고르지 않는다.
```

#### 5-11. `channels/ko-40sec-facts/ideas.md`

- **바꾸는 것:** 넷째 줄 "40초 안에 답이 딱 떨어지는 것"을 아래로 바꾼다.
- 나머지는 그대로 둔다. 테스트 문구 "알아보기 귀찮았던"도 남는다.

```markdown
- 1분 45초 동안 물음 → 반전 → 원리 → 생활에서 써먹을 것까지 갈 수 있는 것. 답이 한 줄로 끝나 반복으로 늘려야 하는 주제와 "사람마다 다르다"로 끝나는 주제는 고르지 않는다.
- 공식 자료나 연구로 답을 확인할 수 있는 것. 통설을 바로잡는 주제는 바로잡는 쪽의 출처가 있어야 한다.
```

#### 5-12. `channels/ja-korea-trip/script.md`

- **남기는 것:**
  - 시청자·소개 범위.
  - です・ます체, 가타카나 지명, 히라가나 읽기.
  - 문장 채우기, 마지막 고정 멘트, 역사 민감 규칙, 제목 규칙 전부, 해시태그.
- **바꾸는 것:**
  - "3초"를 "2초"로 바꾼다.
  - 사실 줄을 바꾼다.
- **더하는 것:**
  - 5·9번째 다시 걸기(고정 멘트 없이).
  - 기준 시점 표기.

바뀌는 줄만(나머지 줄은 지금 그대로):

```markdown
- 첫 장면의 첫 문장은 2초 안에 끝나는 훅이다. 15자 안팎의 질문이나 의외의 사실 하나로 시작하고, 둘째 문장에서 영상이 답할 물음을 분명히 한다. 例: 「ソンスのカフェ、どの出口？ 実は、出口ひとつで歩く距離が倍ちがいます。」
- 사실은 사실 시트에 있는 것만 쓴다. 시트는 한국관광공사·서울시·운영사 같은 공식 자료로 만든다. 가격·운영 시간·제도처럼 바뀌는 사실은 시트의 기준 시점을 문장에 넣는다(例: 2026年10月時点で). 시트에 없는 가게 이름·가격·출구 번호는 쓰지 않는다.
- 5번째 장면에서 한 번, 9번째 장면에서 한 번 다시 건다. 5번째는 일본 여행자가 흔히 하는 오해나 실수를 뒤집고, 9번째는 남은 꿀팁 하나를 예고하거나 새 물음을 연다. 매번 다르게 쓰고 같은 영상 안에서 같은 말투를 두 번 쓰지 않는다.
  - 例: 「でも、ここで多くの人が損をしています。」 / 「最後に、現地の人しか知らないコツがひとつあります。」
```

- 바뀌는 문장 가운데 "공식 자료(한국관광공사·궁능유적본부 등)로 널리 확인된 것만 쓴다. 연도·숫자·가격이 확실하지 않으면 일반론으로 말한다."는 위 사실 줄로 바뀐다.
- 첫 줄 훅 예의 "倍ちがいます"는 형식만 보여 주는 예이다. 실제 대본에서는 사실 시트가 있어야 쓸 수 있다.

#### 5-13. `channels/ja-korea-trip/video_style.md`

- **남기는 것:** 미니어처 디오라마, 실사 금지와 그 이유, 내려다보는 장면, 단면도, 간판·한글·로고 금지, 시대 제약 문장, 아주 느린 카메라.
- **빼는 것:**
  - "분위기" 자리(머리말 낱말이 반복되는 원인).
  - "빨간 선·화살표"(glossy coral clay path로 바꾼다).
  - "젊은 여성 여행자 인형(작은 캐리어·토트백)"(장면마다 소품이 바뀐 원인).
- **더하는 것:** 마스코트 문장, 실내 장면 규칙, 문화 물건 낱말 풀이, 순서.

이후(전문):

```markdown
# 장면 영상 규칙

- 화풍은 미니어처 디오라마 3D 해설 애니메이션 하나다. 지금의 서울 동네를 탁자 위 모형처럼 보여 준다. 누가 봐도 만든 영상이어야 한다. 실사·포토리얼은 쓰지 않는다(실존 장소를 사실처럼 그리면 AI 라벨 대상이 된다). 화풍·재질·흐림은 앱이 머리말로 붙이므로 prompt에 다시 쓰지 않는다.
- 주인공은 아래 마스코트 문장을 글자 그대로 넣는다. 소품(캐리어·토트백)과 옷을 장면마다 바꾸지 않는다. 다른 사람은 얼굴을 단순화한 작은 클레이 인형으로 쓰고, 실존 인물·연예인을 닮게 그리지 않는다.
  - Mina, the channel's clay traveler figure: round face with dot eyes, cream beret, sage-green coat, small coral suitcase.
- 거리 장면은 동네를 위에서 비스듬히 내려다보는 장면을 기본으로 쓴다. 카페가 모인 골목, 역에서 가는 길, 줄 서는 곳처럼 실제 영상으로는 한눈에 안 보이는 것을 모형 전체로 보여 준다.
- 실내 장면(가게 안, 숙소)은 지붕을 떼어 낸 방 모형(a tabletop model room with the roof removed)으로 쓴다. 동네 이름을 붙이지 않는다.
- 길·동선·순서는 숫자 대신 바닥에 그려지는 glossy coral clay path로 보여 준다. 비교(요금, 줄 길이)는 같은 물건 두 개의 높이·길이 차이로 보여 준다. 건물 안이나 원리는 단면도(cutaway)로 보여 준다.
- 간판·한글·로고·상품 상표·가격표·달력은 넣지 않는다. 가게는 업종만 알아보게 그린다. 진열대·포장은 plain pastel boxes with blank labels로 쓴다.
- 지명은 그림이 되지 않으므로 prompt에 동네 이름 대신 모습을 쓴다(성수: low red-brick former factories turned into cafés / 한남동: a steep hillside of small boutiques and narrow sloping alleys / 명동: a dense pedestrian shopping street with rows of street-food carts).
- 한국 물건은 이름 뒤에 생김새를 붙여 쓴다.
  - 김밥: gimbap, a seaweed-wrapped rice roll sliced into round pieces showing yellow, green, orange and egg fillings
  - 떡볶이: tteokbokki, short cylindrical rice cakes in glossy bright red sauce in a wide shallow pan
  - 한옥: a hanok, a traditional Korean wooden house with dark gray curved tile roofs, upturned eaves, white plaster walls and wooden lattice doors around a small courtyard
  - 한복: a hanbok, a high-waisted long full skirt with a short jacket tied with a long ribbon at the chest
  - 교통카드: a plain blank card-sized transit pass tapped on a round reader at a subway gate
  - 포장마차: a street-food tent with an orange tarp and a steaming counter
  - 화장품 가게: a bright health-and-beauty drugstore with rows of plain skincare bottles
- 옛 모습을 한 장면 보여 줄 때는 prompt 끝(마지막 두 줄 앞)에 시대 제약 문장을 붙인다. 조선 시대면 "Joseon era only: no modern buildings, no glass windows, no cars, no power lines, no tourists."
- 카메라 움직임은 아주 느린 것 하나만 쓴다: very slow push-in, very slow orbit, very slow pull-back, high three-quarter overhead 고정.
- prompt는 컷 → 카메라 → 마스코트 → 동작(시간 순) → 배경 → 시간대 빛 순으로 쓰고, 제약(시대, 소리, 텍스트 금지)은 끝에 둔다.
```

#### 5-14. `channels/ja-korea-trip/thumbnail.md`

거의 그대로 둔다. 1절 끝에 한 줄만 더한다.

```markdown
- 숫자를 넣으면 대본에 나온 숫자만 쓴다.
```

#### 5-15. `channels/ja-korea-trip/trends.md`

지금 줄은 모두 둔다. 끝에 두 줄을 더한다.

```markdown
- 1분 45초 동안 기본 정보 → 일본인이 흔히 하는 실수 → 실전 요령 → 하나 더 알면 좋은 것까지 이어질 수 있는 주제를 고른다. 가게 하나 소개로 끝나는 주제는 고르지 않는다.
- 핵심 정보를 한국관광공사·서울시·운영사(지하철, 공항, 결제 서비스) 같은 공식 자료로 확인할 수 있는 주제만 고른다. 일본 블로그·SNS는 관심도를 볼 때만 쓰고 사실의 출처로 쓰지 않는다.
```

#### 5-16. `channels/ja-korea-trip/ideas.md`

- **바꾸는 것:** "50초 안에 답이 딱 떨어지는 것. 가게 이름·가격처럼 금방 바뀌는 것보다 오래 쓸 수 있는 요령을 고른다." 줄을 아래로 바꾼다.

```markdown
- 1분 45초 동안 길 안내·고르는 법·주의할 점을 차례로 보여 줄 수 있는 것. 가게 이름·가격처럼 금방 바뀌는 것보다 오래 쓸 수 있는 요령을 고르고, 공식 자료로 확인되는 것만 고른다.
```

#### 5-17. `channel.toml` 키

| 키 | ko 지금 → 이후 | ja 지금 → 이후 |
|---|---|---|
| `[script] scenes` | 7 → **13** | 7 → **13** |
| `[script] sentence` | [62, 68] → **[52, 58]**, 주석 `# 크리스 기준 초당 약 7.1자: 한 장면이 7.3~8.2초` | [50, 56] 그대로, 주석 `# 미나미 기준 초당 약 7.0자: 13장면이 약 93~104초` |
| `[script] duration` | "52~56초" → **"100~110초"** | "50~56초" → **"100~110초"** |
| `[video] style` | 아래 ko 머리말 | 아래 ja 머리말 |
| `[style] subtitle_limit` | 0 그대로(16자) | 0 그대로(10자) |
| `[trends] production` | 아래 | 아래 |
| `description` | 아래 | 아래 |
| `name` | "40초 상식": 사용자 결정(아래) | 그대로 |

ko `[video] style`(이후). "soft even daylight"와 "same art style in every shot"을 빼고, 팔레트와 빈 간판을 넣는다.

```toml
style = "Stylized 3D animated explainer. Smooth matte materials, simple rounded shapes, limited palette of deep teal, cream, coral and mustard yellow, clean uncluttered sets, signs and screens plain and blank."
```

ja `[video] style`(이후). "of Seoul"을 빼서 실내 장면에 도시 모형이 붙지 않게 한다. 조명과 "same art style"도 뺀다.

```toml
style = "Stylized 3D animated miniature diorama: everything is a handmade tabletop model with soft clay-like matte materials and strong tilt-shift blur at the frame edges. Palette of cream, sage green, coral and warm wood. Signboards, packages and screens are plain and blank."
```

ko `[trends] production`(이후):

```toml
production = "Claude가 공식 자료로 만든 사실 시트로 한국어 대본을 쓰고, TTS가 읽고 번인 자막이 뜬다. 약 1분 45초(100~110초), 13장면. 배경은 장면마다 AI로 만든 3D 해설 애니메이션 클립(건축·과학 해설 채널 느낌)이고, 같은 마스코트가 나온다. 직접 촬영, 실존 인물·방송·게임 화면, 특정 브랜드는 못 쓴다. 공식·학술 자료로 핵심 사실을 확인할 수 없는 주제는 못 만든다."
```

ja `[trends] production`(이후):

```toml
production = "Claude가 공식 자료로 만든 사실 시트로 일본어 대본을 쓰고, 일본어 TTS가 읽고 일본어 번인 자막이 뜬다. 약 1분 45초(100~110초), 13장면. 화면은 9:16 전체를 장면 클립으로 채우고 자막만 뜬다(제목은 썸네일에만). 장면은 모두 AI로 만든 미니어처 디오라마 3D 해설 클립이다: 지금의 서울 동네를 탁자 위 모형처럼 내려다보고 길·동선은 바닥의 선으로 보여 주며, 같은 클레이 여행자 인형이 나온다. 직접 촬영·실사 영상, 남의 사진·영상, 실존 인물·연예인, 가게 간판·브랜드 로고·상품 화면은 못 쓴다. 한국관광공사·서울시·운영사 같은 공식 자료로 확인할 수 없는 정보는 못 쓴다."
```

ko `description`(이후):

```toml
description = "생활 속 \"왜 그렇지?\"에 근거를 갖고 2분 안에 답해 드려요. 영상에 쓴 자료는 설명란에 적어 둡니다."
```

ja `description`(이후). 첫 줄, "毎日2本更新" 줄, 출처 한 줄이 바뀐다.

```toml
description = """
韓国旅行・ソウル旅行の前に見たい、2分弱のミニチュアガイド。
聖水・漢南洞のカフェ街や明洞の屋台通りを、手のひらサイズのソウルで再現。
オリーブヤングと韓国美容、地下鉄の乗り方、両替のコツまで、行ってすぐ使える情報をお届けします。

情報は韓国観光公社・ソウル市などの公式資料で確かめ、出典は概要欄に載せています。
ソウル在住の韓国人が調べて作り、ナレーションはAI音声です。

※映像はAIで再現したイメージです。"""
```

- "毎日2本更新"을 지운 이유: 13장면이면 편당 78크레딧이라 하루 2편이 156크레딧이다. 지금 크레딧 한도로 가능한지 확인하지 못했다. 가능하면 다시 넣는다.
- 설명란 출처 블록은 `search_grounding.md` 6절대로 코드가 `footer` 앞에 붙인다는 전제다. 그 코드가 없으면 "出典は概要欄に" 문장을 빼야 한다.
- ko `name`: "40초 상식"은 YouTube 채널 이름이고, 테스트 4곳(1절)에 박혀 있다. 이름에서 길이를 빼는 안(예: "근거 있는 상식", "상식 한 입")은 사용자가 YouTube에서 이름을 바꿀 때 같이 바꾼다. 채널 id `ko-40sec-facts`는 기존 작업에 남아 있으므로 바꾸지 않는다(channels.md 규칙).

### Gaps
- 머리말·마스코트·낱말 풀이는 시험 생성 없이 쓴 초안이다. 마스코트가 장면 사이에 같은 모습으로 나오는지는 참조 이미지("소재" 모드) 없이는 보장되지 않는다. 처음 2~3편에서 확인해야 한다.
- 마스코트를 머리말에 넣지 않은 이유: 머리말은 사람이 없는 단면도 장면에도 붙기 때문이다. 그래서 video_style.md에 두고 "사람이 필요하면"으로 건다. 이 방식에서도 LLM이 마스코트를 빼먹는 비율은 재지 않았다.

---

## 6. 대본 문장 → 영상 프롬프트: 무엇이 남고 빠지고 지어지나

### Takeaway
실제 4편 28장면을 보면, LLM은 문장의 핵심 그림을 거의 매번 잘 옮긴다. 문제는 덧붙이는 쪽에서 생긴다.
- 숫자를 사람 수로 세게 한다.
- 글자를 부르는 물건을 넣는다(물음표 빛, X 아이콘, 색 표지, 달력, 에너지 막대).
- 매 장면 주인공을 끼워 넣는다.
- 머리말과 부딪치는 시간대 빛을 넣는다.
- ja는 화풍·분위기 낱말을 되풀이한다.
- 그림이 되지 않는 지명을 반복한다.
- 길이 규칙(60~90단어)은 27/28장면에서 지켜지지 않는다.

규칙은 5-1 `## 장면 prompt`와 5-8·5-13 채널 규칙에 넣었고, 사람 검토용 30초 점검표를 아래에 둔다.

### Cited Findings
대상은 `shorts.db` `script.json`이다(머리말을 뺀 본문).
- ko 20261016-062150-fb52 "AI 반도체"
- ko 20261015-235528-59f3 "햇빛 재채기"
- ja 20261016-054604-c25e "편의점 1+1"
- ja 20261015-225401-bbc6 "한남동"

장면 10개 대조:

| Job·장면 | 문장 요지 | prompt가 한 일 | 분류 |
|---|---|---|---|
| fb52 #1 | 질문 하나에 수십억 번 계산 | 노트북이 투명해지며 칩에서 "countless tiny red light streaks" | 숫자 → 추상적 많음으로 잘 바꿈. "at night"를 지음(머리말 daylight와 충돌) |
| fb52 #4 | 병목은 메모리에서 꺼내 오는 속도 | 좁은 길에 데이터 큐브가 정체, 남자가 "checking his wrist" | 핵심 그림을 잘 옮김. 손목시계(숫자 판)를 지음 |
| fb52 #5 | 옮기는 데 전기가 더 든다 | "a small red energy bar"와 굵게 부푸는 선 | 막대그래프(글자·눈금을 부름)를 지음 |
| fb52 #6 | 메모리를 아파트처럼 쌓은 것이 HBM | 얇은 칩이 층층이 쌓여 탑이 됨 | 고유명사(HBM)를 버리고 비유를 그림 — 좋음 |
| 59f3 #2 | 감기도 알레르기도 아니다 | "two crossed-out icons, a red thermometer and a pollen flower" | 부정을 X 아이콘으로 지음(기호) |
| 59f3 #3 | 열 명 중 두세 명꼴 | "A row of ten … two or three of them … sneeze" | 숫자를 사람 수로 그대로 셈 — 모델이 약한 연출 |
| 59f3 #4 | 과학자도 아직 모른다 | 실험실, 과학자 3명, "a faint question-shaped glow" | 물음표(글자)를 지음. 장소를 새로 만듦 |
| c25e #4 | 값표 위 색 표시로 구별 | "small blank colored tags glow above the price strips" | 문장의 표지를 옮겼지만 값표가 숫자를 부름 |
| c25e #5 | 대상 상품은 매달 바뀐다 | "a simple clay calendar page flips" | 달력(숫자)을 지음 |
| bbc6 #2 | 6호선 한강진역이 편하다 | 역 입구 + 빨간 선, "Hannam-dong in Seoul" | 노선 번호를 버림 — 좋음. 지명은 그림이 되지 않는 채 반복 |

28장면 전체 집계(직접 세었다):
- 핵심 그림 유지: 28/28. 모든 prompt가 문장의 주된 생각 하나를 그린다.
- 주인공 끼워 넣기:
  - fb52는 7/7장면에 "young man in a gray hoodie"가 나온다. 칩 단면도 같은 추상 장면 4개에서는 "watches from the left edge"처럼 구경꾼으로 들어간다.
  - ja 14/14장면에 여성 여행자 인형이 나온다. c25e는 소품이 suitcase와 tote bag 사이에서 바뀐다.
  - 59f3 #7은 가족(아버지·남동생)을 새로 만든다.
- 글자·숫자를 부르는 물건: 6장면(위 표의 fb52 #4·#5, 59f3 #2·#4, c25e #4·#5).
- 사람이나 물건을 세게 하는 묘사: 1장면(59f3 #3). c25e #2·#3의 병 2개·봉지 3개는 수가 작아 괜찮다.
- 시간대 빛이 머리말 "soft even daylight"와 부딪침: 3장면(fb52 #1 night, c25e #6 evening, c25e #7 early morning).
- 머리말 낱말 되풀이(ja): c25e는 7장면 모두 끝에 "… mood"가 붙고, #1·#6·#7에 "clay textures, tilt-shift depth"가 다시 나온다.
- 지명: bbc6는 7장면 중 6장면에 "Hannam-dong in Seoul"이 들어간다. 모습 묘사(hillside, sloping alleys)는 따로 있다.
- 카메라: push-in이 17/28장면이다. 59f3은 6/7장면이고, c25e는 5/7장면이다.
- 길이: 본문 87~110단어. 90단어 이하는 1장면(fb52 #1, 87단어)뿐이다. 머리말(ko 약 25단어, ja 약 35단어)을 더해도 공식 상한(1,024토큰) 안이다.
- 출처: 이 노트 작성 중 DB 실측. 이전 조사의 같은 관찰은 [current_prompt_audit.md](/Users/jkpark/my-toy/shorts-printer/research_notes/2분%20쇼츠%20퀄리티%20전략/current_prompt_audit.md) 3절에 있다.
- Omni Flash에서 한 장면을 원하면 "In a single unbroken scene"이나 "No scene cuts"를 쓰라고 한다. — [Gemini API, Gemini Omni Flash](https://ai.google.dev/gemini-api/docs/omni)
- Omni Flash는 글자를 요청하면 읽히게 그린다고 한다("prompt to include text … render in a way that is correct and readable"). 따라서 글자를 부르는 물건을 넣으면 실제로 글자가 나올 수 있다. — 같은 문서

### Inferences
변환 규칙(5-1에 반영):
1. **그림 하나:** 문장의 핵심 그림 하나만 첫 두 문장 안에 둔다. 지금도 잘 되는 부분이라 순서만 고정한다.
2. **숫자·글자·로고는 문자 그대로 그리지 않는다:**
   - 큰 수는 "countless/vast" 같은 양으로 쓴다(fb52 #1이 좋은 예).
   - 비율은 많은 무리 가운데 몇몇이 빛나는 장면으로 쓴다(59f3 #3을 고친다).
   - 가격은 같은 물건 두 개의 높이 차이로 쓴다.
   - 기간·시간은 해의 위치나 그림자로 쓴다(c25e #5의 달력을 고친다).
   - 부정은 그리지 않는다. "감기가 아니다"는 그냥 원인 장면으로 간다(59f3 #2를 고친다).
3. **지명·브랜드:** 이름 대신 모습을 쓴다. 한국 문화 물건은 채널 낱말 풀이를 글자 그대로 쓴다(5-8, 5-13). 모델이 "gimbap"을 몰라도 뒤의 생김새로 그리게 하려는 것이다.
4. **마스코트:** 채널 문장을 글자 그대로 쓴다. 사람이 필요 없는 단면도 장면에는 넣지 않는다(fb52 #2·#3·#5·#6 같은 구경꾼을 없앤다).
5. **빛:** 머리말에서 조명을 빼고, prompt가 시간대 한 구절을 갖는다.
6. **카메라:** 장면 역할에 묶는다. 훅·5·9번째는 reveal/pull-back으로 쓰고, 같은 움직임은 세 장면까지만 잇는다. 13장면에서 push-in만 이어지면 변화가 없다.
7. **소리:** "SFX:"와 "Ambient noise:"로 나눈다. Google 가이드의 소리 구분과 같다.
8. **길이:** 실제에 맞춰 80~110단어로 고친다. 지키지 않는 규칙을 남기는 것보다 낫다.

사람 검토 점검표(장면마다 30초). 상세 화면에서 prompt_ko 한 줄과 영어 prompt를 나란히 보고 확인한다.

| # | 볼 것 | 걸리면 |
|---|---|---|
| 1 | prompt_ko 한 줄이 문장의 핵심 그림과 같은가 | prompt를 고친다 |
| 2 | 영어 prompt에 숫자 낱말(ten, three, 6, percent)이나 세는 묘사가 있나 | 양·크기 묘사로 바꾼다 |
| 3 | 글자를 부르는 물건(sign, screen, calendar, clock, watch, price tag, label, icon, question mark, chart, bar)이 있나 | 빼거나 plain and blank를 붙인다 |
| 4 | 사람이 나오면 마스코트 문장이 글자 그대로인가, 새 주인공이 없는가 | 마스코트 문장으로 바꾼다 |
| 5 | 시간대 빛이 문장(밤·아침)과 맞는가 | 빛 구절을 고친다 |
| 6 | 지명·브랜드 이름만 있고 모습 묘사가 없지 않은가 | 모습을 더한다 |
| 7 | 카메라 움직임이 하나이고, 앞 두 장면과 같은 움직임이 세 번째로 이어지지 않는가 | 바꾼다 |
| 8 | 끝 두 줄(SFX·Ambient·No dialogue…, No on-screen text…)이 있는가 | 붙인다 |

- 1~3번이 가장 자주 걸린다(28장면 중 7장면). 4~8번은 지시문이 바뀌면 대부분 사라질 것으로 본다.
- 13장면 × 30초면 편당 약 6~7분이다.

### Gaps
- 규칙을 바꾼 prompt로 실제 생성해 본 적은 없다. 특히 "plain and blank"가 글자를 막는지, "no X"가 오히려 X를 부르는지는 Omni에서 A/B로 확인해야 한다(이전 조사 Gaps와 같다).
- 표본은 4편 28장면이다. 다른 주제(음식·건강)에서는 다른 덧붙이기가 나올 수 있다.

---

## 7. Flow·Veo·Omni는 한국어·일본어 프롬프트를 받는가, 영어를 유지할까

### Takeaway
**영어를 유지한다.**
- Google 문서는 Veo 3.1과 Gemini Omni Flash 모두 "영어만 완전 지원, 다른 언어는 평가하지 않았다"고 적는다.
- 2025년 크리에이터 글들도 한국어·일본어 프롬프트가 덜 안정적이라고 말한다. 다만 체계적 시험은 아니다.
- 한국어 운영자가 검토할 수 있게, 같은 대본 호출에서 장면마다 `prompt_ko` 한 줄(한국어 뜻)을 받아 `script.json`에 `prompts_ko`로 저장한다. 상세 화면에서 영어 prompt 옆에 보여 준다.

### Cited Findings
- Veo 3.1(Gemini API): "English (EN) is fully supported, but other languages have not been evaluated, so they may work but results can vary." — [Gemini API, Veo 3.1](https://ai.google.dev/gemini-api/docs/veo)
- Gemini Omni Flash(`gemini-omni-1.1-flash`)에도 같은 문장이 있다. 9:16, 360p~4K를 지원한다. — [Gemini API, Gemini Omni Flash](https://ai.google.dev/gemini-api/docs/omni)
- Vertex AI의 Veo 3.0 모델 페이지는 지원 프롬프트 언어를 English로 적는다(검색 요약으로 확인, 페이지 본문은 가져오지 못했다). — [Vertex AI, Veo 3.0 generate 001](https://cloud.google.com/vertex-ai/generative-ai/docs/models/veo/3-0-generate-001?hl=en)
- Flow 모델 안내 페이지는 Veo 3.1과 Omni Flash 1.1의 기능만 적고, 프롬프트 언어는 다루지 않는다. — [Flow Help, Learn about Flow models & supported features](https://support.google.com/flow/answer/16352836)
- Google 한국 블로그의 Omni 발표(I/O 2026)에도 언어 지원 언급은 없다. Flow와 YouTube Shorts에서 제공한다고만 적는다. — [Google 코리아 블로그, 제미나이 옴니 소개](https://blog.google/intl/ko-kr/company-news/technology/gemini-omni-kr/)
- 일본어 크리에이터 글(2025-12): 「最初は日本語だけでプロンプトを書き、10 回中 9 回失敗。英語の方が明らかに安定する」, 「純日本語プロンプトの成功率は英語の約 60%」. 시험 방법과 횟수는 밝히지 않았다. — [eastondev, Veo3 video quality tips(ja)](https://eastondev.com/blog/ja/posts/ai/20251207-veo3-video-quality-tips/)
- 한국어 입문서(위키독스 "한국어 프롬프트 vs 영어 프롬프트"): Veo 3는 한국어를 이해하지만 영어 프롬프트에서 더 정확하고, 섞어 쓰는 방식도 권한다. 페이지가 403을 돌려줘 **검색 요약으로만** 확인했다. — [wikidocs 337747](https://wikidocs.net/337747)
- Omni가 중국어·일본어·한국어 화면 글자를 프레임 사이에서 정확히 유지한다는 3자 비교가 있다. 시험 방법은 밝히지 않았다. 이것은 화면 글자 이야기이고 프롬프트 언어 이야기가 아니다. — [Opus Clip, Gemini Omni vs Sora 2 (2026-05-19)](https://www.opus.pro/blog/gemini-omni-vs-sora-2-ai-video-model-comparison)
- 대본 언어와 분리해 따로 부르는 지금의 "한국어 뜻" 설계는 이렇게 적혀 있다: "대본을 쓴 호출과 따로 불러, 쓰려던 뜻이 아니라 실제로 적힌 글을 보게 한다". — [prompts/translate.md](/Users/jkpark/my-toy/shorts-printer/prompts/translate.md)

### Inferences
- 영어를 유지하는 이유:
  1. 공식 문서가 영어만 평가했다고 명시한다.
  2. 실측 28장면에서 영어 prompt의 핵심 그림 전달은 이미 28/28이다.
  3. 한국어 prompt로 바꾸면 이점이 검토 편의 하나뿐이고, 품질 위험은 알 수 없다.
  4. 한국어·일본어 낱말(김밥, 한옥)을 넣으면 모델이 화면 글자로 그릴 위험도 있다. Omni는 글자를 잘 그리는 쪽으로 홍보된다.
- 검토 방법 두 안:
  - **A안(권장, 작다):** `Scene.prompt_ko`를 같은 호출에서 받는다. 지시문은 5-1 마지막 줄, 코드는 필드 하나와 `flat()`·`Draft` 한 줄씩, 상세 화면에서 영어 prompt 아래 회색 한 줄. 추가 호출이 없다.
    - 한계: 쓰려던 뜻을 적으므로 영어 prompt와 어긋날 수 있다(translate.md가 따로 부르는 이유). 점검표 1번(prompt_ko와 문장 비교)과 2·3번(영어 낱말 검사)을 함께 보면 어긋남 대부분을 잡는다.
    - `# ponytail:` 한계로 남기고, 어긋남이 잦으면 B안으로 간다.
  - **B안:** 확정 버튼 전에 `translate.md`처럼 따로 불러 실제 영어 prompt를 한국어로 옮긴다. 정확하지만 ko 채널에도 새 호출이 생기고, 손으로 prompt를 고칠 때마다 다시 불러야 한다.
- 일본어 채널도 prompt는 영어이다. 운영자가 한국인이므로 `prompt_ko`는 한국어로 쓴다(일본어 뜻은 필요 없다).

### Gaps
- Omni 1.1 Flash에서 한국어·일본어 prompt를 영어와 같은 장면으로 맞대어 본 2026년 시험 자료는 찾지 못했다. Veo 3 시기의 크리에이터 글 두 개뿐이고 둘 다 방법을 밝히지 않았다.
- 확인이 필요하면 같은 장면 3개를 영어/한국어로 각 2회 생성(약 72크레딧)해 비교하는 것이 가장 싸다.
- Flow UI가 입력 prompt를 내부에서 번역하거나 다시 쓰는지는 공개 자료로 확인하지 못했다.
```

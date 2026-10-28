# 현재 주제 고르기·대본·영상 지시문 점검 (2분 해설 쇼츠 기준)

조사일: 2026-10-16. 프로젝트 파일은 고치지 않고 읽기만 했다.
읽은 것: `prompts/{script,trend_pick,trend_idea,trend_keywords,trend_video,thumbnail,script_revise,script_revise_draft}.md`, 두 채널(`ko-40sec-facts`, `ja-korea-trip`)의 `channel.toml·script.md·video_style.md·thumbnail.md·trends.md·ideas.md`, `core/script.py`, `core/trends.py`(조립·스키마·점수), `adapters/flow_auto.py`(SETTINGS·제출 방식).
실제 출력: 저장소(shorts.db)에서 작업 32개의 주제 목록, 대본 4개(장면 문장+영상 프롬프트 전문), 추천 주제 기록 6회분을 꺼내 봤다.

중요한 전제: 영상 모델은 Veo 3.x가 아니다. `flow_auto.py`가 고르는 모델은 `MODEL = "Omni 1.1 Flash"`이고 설정은 `("동영상", "소재", "9:16", "360p", "8초", "x1")`이다. 지시문은 텍스트만 넣는다(참조 이미지 업로드 코드 없음, `_generate()`는 `insert_text(prompt)`뿐). 그래서 아래에서 Veo 3.1 공식 지침과 Gemini Omni Flash 지침을 함께 본다.

---

## 1. 주제 고르기: trend_pick·trend_idea가 "궁금증 빈칸 + 왜 지금 + 2분을 버틸 깊이"를 만드는가

### Takeaway
"어? 진짜?" 재미 규칙과 금지 목록은 잘 쓰여 있지만, ① 점수가 거의 다 같은 값으로 몰려(대부분 fit 5·fresh 4·safe 5 → 94점) 순위를 가르지 못하고, ② "40초/50초 안에 답이 딱 떨어지는 것"이 기준이라 2분을 채울 여러 단계 구조·중간 보상·깊이를 보는 항목이 없다. 2분용으로는 "비트 수·중간 보상·최종 반전"을 주제 단계에서 미리 받도록 출력 스키마와 기준을 바꿔야 한다.

### Cited Findings
- 잘된 점: 공통 재미 규칙이 구체적이다. `trend_pick.md`/`trend_idea.md`: "첫 문장을 듣자마자 "어? 진짜?" 하고 멈출 주제를 고른다: 상식이 뒤집히는 반전, 믿기 어려운 숫자·비교, 다들 잘못 알고 있는 통설…", "흔한 꿀팁 나열("~하는 5가지 방법", "~ 아끼는 법")은 고르지 않는다", "자극은 사실의 의외성에서 나와야 한다." — [prompts/trend_pick.md](/Users/jkpark/my-toy/shorts-printer/prompts/trend_pick.md), [prompts/trend_idea.md](/Users/jkpark/my-toy/shorts-printer/prompts/trend_idea.md)
- 잘된 점: 웹 검색 후 사실 확인, 연구·가설을 그렇게 밝히기, 고르지 않은 주제(avoid)와 비슷한 각도 피하기가 들어 있다. `IdeaOut`에 `content`(핵심 답과 사실 2~3문장)·`why_now` 필드가 있다 — [core/trends.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/core/trends.py) 433–440행
- 길이 기준이 2분과 정면으로 부딪힌다. ko `ideas.md`: "40초 안에 답이 딱 떨어지는 것. 설명이 길어지거나 "사람마다 다르다"로 끝나는 주제는 고르지 않는다." ja `ideas.md`: "50초 안에 답이 딱 떨어지는 것." ko `production`: "40~50초." — [channels/ko-40sec-facts/ideas.md](/Users/jkpark/my-toy/shorts-printer/channels/ko-40sec-facts/ideas.md), [channels/ja-korea-trip/ideas.md](/Users/jkpark/my-toy/shorts-printer/channels/ja-korea-trip/ideas.md), [channel.toml](/Users/jkpark/my-toy/shorts-printer/channels/ko-40sec-facts/channel.toml)
- 점수 기준이 한 줄짜리라 변별력이 없다. `CRITERIA`: fit "우리 제작 방식으로 만들 수 있나", fresh "이미 만든 주제·흔한 영상과 겹치지 않고 새 각도가 있나", safe "저작권·민감 주제 위험이 낮나" — [core/trends.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/core/trends.py) 41–46행
- 실제 기록에서 점수가 몰린다. 최근 ko 추천 3회(아이디어 모드 포함) 30개 중 약 20개가 정확히 94점(fit 5·fresh 4·safe 5)이고 나머지도 88/75점 몇 개뿐이다. ja 추천 10개 중 4개가 95점 동점. 예: "가을 하늘은 왜 더 높고 파래 보일까?"·"냉장실은 비우고 냉동실은 채워라"·"생밤 껍질, 칼집 내고…"가 모두 94점 — 저장소 `Trend.picks.json` 실측(로컬)
- 화제성(trend)은 수집한 영상 안의 시간당 조회수 백분위로만 매긴다(`percentile`, `1 + round(4 * …)`). 아이디어 모드는 trend를 빼고 fit·fresh·safe만 쓴다(`idea_weights`). 그래서 아이디어 모드에서 "왜 지금"은 글(`why_now`)로만 있고 점수에는 안 들어간다 — [core/trends.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/core/trends.py) 417–470행
- 중복 피하기는 최근 작업 30개의 `topic` 문자열을 LLM에 보여 주는 방식이다(`_made`: `[-30:]`). 실제 `topic`에는 사용자가 친 날말이 그대로 들어간다(예: "커피", "무기에 대한 재밌는 이야기", "흰빨래와 컬러있는 빨래할때위 차이점…"). 실제 영상 제목은 넘기지 않는다 — [core/trends.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/core/trends.py) 476–479행, 저장소 Job 목록 실측
- 제목 규칙이 단계마다 다르다. `trend_pick.md`는 "답을 제목에서 **다** 말하지 않는다"(일부 허용), ko `script.md`는 "답·반전·결론과 그 단서를 제목에 넣지 않는다." 실제 추천 topic에는 답이 들어 있다: "동전 테두리에 톱니가 있는 이유, 범죄 때문이었다", "녹음된 내 목소리가 남 같은 이유, 진짜는 녹음 쪽이다", "핫팩은 왜… 정체는 '녹스는 쇠'", ja "엔화 환전, 공항이냐 시내냐 정답은 이것" — 저장소 picks 실측
- 금지 규칙과 어긋나는 추천이 실제로 통과한다: "커튼 하나로 난방비 아끼기, 길이가 핵심이다", "냉장실은 비우고 냉동실은 채워라, 전기요금 아끼는 법"(재미 규칙의 "~ 아끼는 법" 금지에 해당), ja "서울 피부과, 예약 전에 꼭 알아 둘 4가지"(목록형, safe 2) — 저장소 picks 실측
- 민감 주제 거르기: 공통 규칙 + `sensitive_gate = true` + 대본 `sensitive` 필드가 있다. 하지만 사용자가 직접 넣은 주제("건강검진결과 읽는방법", "뇌는 정작 자기 아픔을 못 느낀다?")는 추천 단계를 거치지 않으므로 대본 단계 `sensitive` 필드와 게이트에만 기댄다 — 저장소 Job 목록, [core/script.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/core/script.py) `Script.sensitive`
- `trend_video.md`(인기 쇼츠 분석)는 hook·footage·자막·인기 이유·replicable을 뽑는다. 하지만 길이별 구조(몇 비트, 중간 재훅 위치, 끝 보상)는 뽑지 않는다(`VideoAnalysis` 필드) — [core/trends.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/core/trends.py) 219–229행
- Anthropic 문서: 한 줄 지시보다 원하는 수준을 구체적으로 적고, 이유(동기)를 함께 주면 더 정확하다("Providing context or motivation behind your instructions… can help Claude better understand your goals") — [Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- 2분 구조의 실무 꼴은 "훅 → 약속 → 비트 2~3개(각자 작은 보상) → 반전/최대 보상 → 즉시 끝"이며, 깊이 파기형은 중간 반전이 있어야 버틴다(옆 노트 정리) — [script_structure.md](/Users/jkpark/my-toy/shorts-printer/research_notes/2분%20쇼츠%20퀄리티%20전략/script_structure.md) 1·7절

### Inferences
- **점수가 장식이 되었다.** 1~5점 세 개를 LLM이 스스로 매기면 "고른 것"은 다 높게 준다(자기 선택을 정당화하는 쪽으로 쏠림). 변별을 만들려면 ① 기준마다 1·3·5점이 무엇인지 예시를 적은 루브릭, ② "이번 목록 안에서 상대 순위"를 매기게 하기, ③ 점수 대신 판정 근거 필드를 먼저 쓰게 하고 점수는 그 뒤에 매기기 중 하나가 필요하다.
- **2분용 주제 필드가 빠져 있다.** 지금 `content`는 "핵심 답과 사실 2~3문장"(300자)이라 50초 분량이다. 2분이면 최소 아래를 주제 단계에서 받아야 대본 작가가 깊이를 지어내지 않는다:
  - `question`: 시청자가 속으로 묻는 질문 한 줄(제목 후보, 답 없음)
  - `beats`: 3~4개. 각 비트 = 작은 질문 + 작은 답(사실·출처) + 화면에 보여 줄 것 한 줄
  - `twist`: 70초 안팎에 나올 반전(통설이 틀린 이유 등)
  - `payoff`: 마지막에 손에 쥐여 줄 한 문장(써먹을 행동·남에게 말할 한 줄)
  - `visual_fit`: 비트마다 "AI 3D/미니어처로 숫자·글자 없이 보여 줄 수 있나"
  - 주제 기준 문구도 "40초 안에 딱 떨어지는 것" → "질문 하나에 답이 있고, 그 답에 이르는 '왜'가 2~4단계로 나뉘는 것. 한 단계마다 '오, 그렇구나'가 하나씩 있는 것"으로 바꾼다.
- **2분을 못 버티는 주제를 걸러야 한다.** 실제 추천 중 "생밤 껍질, 칼집 내고 삶은 뒤 찬물에 넣어라", "전자레인지… 가장자리에 둬라" 같은 단일 요령은 답이 한 문장이라 2분에 맞지 않는다. 반대로 "얼음이 미끄러운 이유, 학교에서 배운 설명은 틀렸다", "귀뚜라미 울음소리로 기온 맞히기", "정체 파도(유령 정체)"는 통설→실험→원리→써먹기로 3~4비트가 나와 2분 후보다. 선정 지시문에 "답이 한 문장으로 끝나는 요령은 60초 미만용으로 표시하고 2분 추천에서 뺀다"를 넣으면 길이별로 갈라 쓸 수 있다.
- **제목 규칙을 한 곳으로 맞춘다.** trend_pick의 "다 말하지 않는다"를 script.md와 같은 "답·반전·결론과 그 단서를 넣지 않는다"로 고치고, topic(작업 이름)과 title(시청자용 질문)을 나눈다. 지금은 topic이 대본 user 메시지 첫 줄(`주제: …`)로 그대로 들어가 답이 미리 새어 나간 제목을 만들 여지가 있다.
- **중복 판단 재료를 늘린다.** `_made`에 topic 대신(또는 함께) 실제 업로드 제목을 넣으면 사용자가 대충 친 주제어보다 나은 비교가 된다.
- **"왜 지금"은 계절 말고 근거 하나를 요구한다.** 실제 why_now는 대부분 "~하는 시기다"뿐이다. "검색어·뉴스·인기 쇼츠 중 어느 근거로 지금인지 한 개를 적는다(없으면 '상시'로 적는다)"처럼 출처 종류를 요구하면 상시 주제와 시기 주제를 구분할 수 있다.

### Gaps
- 추천 점수와 실제 성과(조회·유지율)를 잇는 데이터가 저장소에 없어, 어떤 가중치가 맞는지는 판단할 수 없다. 업로드 뒤 Studio 숫자를 picks에 되돌려 붙여야 검증된다.
- 공식 출처 중 "LLM 자기 채점이 높게 몰린다"를 직접 다룬 Anthropic 문서는 찾지 못했다. 위 판단은 실측(저장소 기록)에 근거한 추론이다.

---

## 2. 대본 지시문: 훅·열린 고리·재훅·보상·마무리를 강제하는가, "한 문장 = 한 장면 = 8초"가 품질을 해치는가

### Takeaway
지금 지시문은 형식 제약(장면 수, 글자 수, TTS 기호, 영상 프롬프트 규칙)은 꼼꼼하지만, 이야기 구조는 "첫 문장은 훅"과 고정 멘트 두 개뿐이다. 열린 고리·재훅·비트별 보상·최종 반전은 공통 지시문에 한 줄도 없다. "문장 하나가 8초를 꽉 채우는 62~68자" 규칙은 훅을 8초짜리 긴 문장으로 만들고 모든 문장을 "~인데, ~해서" 꼴의 긴 복문으로 늘린다. 2분이면 "장면 = 8초 클립, 그 안에 짧은 문장 1~3개"로 문장과 장면을 떼어 내고, 구조를 비트 단위로 지시해야 한다.

### Cited Findings
- 공통 지시문 핵심 줄: "장면 하나가 문장 하나이고", "장면은 정확히 ${scenes}개, 문장마다 ${lo}~${hi}${unit}", "장면 클립이 8초라 한 문장이 ${hi}${unit}를 넘지 않게 한다." 구조 관련 지시는 없다 — [prompts/script.md](/Users/jkpark/my-toy/shorts-printer/prompts/script.md)
- 채널 설정: ko `scenes = 7`, `sentence = [62, 68]` "한 문장이 클립 8초를 거의 다 채운다", ja `sentence = [50, 56]` — [ko channel.toml](/Users/jkpark/my-toy/shorts-printer/channels/ko-40sec-facts/channel.toml), [ja channel.toml](/Users/jkpark/my-toy/shorts-printer/channels/ja-korea-trip/channel.toml)
- 잘된 점: 길이 채우기를 꾸밈말로 하지 말라는 규칙에 이유가 붙어 있다. ko `script.md`: "같은 말을 되풀이하거나 꾸밈말로 늘리지 말고, 문장마다 이유·원리·비교·생활 속 예시 중 하나를 더 담아 내용으로 채운다." TTS 규칙도 이유를 준다("TTS가 기호까지 읽으므로…"). Anthropic 문서가 권하는 꼴(이유를 함께 주면 일반화한다)과 같다 — [channels/ko-40sec-facts/script.md](/Users/jkpark/my-toy/shorts-printer/channels/ko-40sec-facts/script.md), [Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) ("Your response will be read aloud by a text-to-speech engine, so never use ellipses…")
- 고정 중간 멘트가 앞부분을 "아는 내용"으로 묶는다. ko `script.md`: "4번째 문장을 여기까진 다들 아시죠? 로 시작하고 … 그래서 1~3번째 문장은 많이 아는 내용으로, 5번째 문장부터는 의외의 내용으로 짠다." 즉 2~3번째 장면(약 8~24초)이 일부러 "새롭지 않은" 구간이 된다 — [channels/ko-40sec-facts/script.md](/Users/jkpark/my-toy/shorts-printer/channels/ko-40sec-facts/script.md)
- 실제 출력에서 훅 문장이 길다. "햇빛 재채기" 대본 1번: "터널을 빠져나오거나 햇살 쨍한 날 밖에 나서자마자 에취 하고 갑자기 재채기가 터진 적, 혹시 한 번쯤 있으신가요?"(약 60자 ≈ 7초에 걸쳐 질문이 완성된다). "도로 정체" 1번: "출퇴근길에 사고도 공사도 없는데 도로가 꽉 막혔다가, 한참 뒤 아무 일 없다는 듯 뻥 뚫린 경험 한 번쯤 있으시죠?" — 저장소 Job 20261015-235528-59f3, 20261015-195423-e9bc
- 실제 출력의 중간 문장이 늘이기용 복문이 된다: "신기한 건 이런 사람이 드물지 않다는 점인데, 연구마다 차이는 있지만 대략 열 명 중 두세 명꼴로 겪는다고 합니다." — 같은 Job
- 첫 1~3초에 볼지 넘길지가 갈리고, 재훅은 "아직 답하지 않은 질문을 다시 상기시키거나 새 질문을 여는 한 문장"이며 2분이면 약 40~50초마다 하나가 현실적이라는 정리 — [script_structure.md](/Users/jkpark/my-toy/shorts-printer/research_notes/2분%20쇼츠%20퀄리티%20전략/script_structure.md) 1·2절
- 전환 빈도: 8초 클립을 문장마다 하나씩 쓰는 구조는 영화 평균 샷(3~4초)보다 2배 느려, 클립 안에서 4초 안팎마다 무언가가 바뀌게 하는 편이 안전하다는 정리 — [script_structure.md](/Users/jkpark/my-toy/shorts-printer/research_notes/2분%20쇼츠%20퀄리티%20전략/script_structure.md) 4절
- 대본 user 메시지 조립: `주제: …` + (있으면) `참고(최근 인기 쇼츠 분석). 훅·전개·속도는 따르되 문장을 베끼지 않는다:` + brief + 채널 분야 + 최근 제목. 아이디어 모드 brief(내용·방향)도 같은 "최근 인기 쇼츠 분석" 꼬리표로 들어간다. 사용자가 직접 친 주제는 brief가 비어 주제어 한 줄만 간다(예: "왜 사고도 안났는데 도로가 막힐까?" Job의 brief는 빈 값) — [core/script.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/core/script.py) `write()`, 저장소 실측
- 출력 스키마: `Scene(sentence, prompt)` 목록 + title·description·tags·sensitive. 쓴 사실의 근거·확신도 필드는 없다 — [core/script.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/core/script.py)
- Anthropic: 예시는 출력 형식·말투·구조를 잡는 가장 확실한 방법이고, 3~5개를 서로 다르게 `<example>` 태그로 감싸라("Diverse: Cover edge cases and vary enough that Claude doesn't pick up unintended patterns"). 지시·맥락·예시·입력을 XML 태그로 나누면 오해가 준다 — [Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- 비용: Flow 설정은 장면 하나에 6크레딧(360p·8초·x1) — [adapters/flow_auto.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/adapters/flow_auto.py) 9–10행 주석. 2분을 8초 클립으로 채우면 15장면 = 90크레딧(지금 7장면 = 42크레딧의 약 2.1배).

### Inferences
- **"한 문장 = 한 장면 = 8초"는 2분에서 품질을 해친다.** 이유 셋: ① 훅이 8초짜리 한 문장이 된다(질문의 핵심어가 문장 끝에 온다). ② 모든 문장이 같은 길이·같은 리듬이라 2분 내내 단조롭다. ③ 짧고 센 문장("근데 틀렸습니다.")을 쓸 수 없다. 장면 수(비용)는 지키고 문장만 풀어 주면 된다:
  - 스키마를 `Scene(lines: list[str], prompt: str)`처럼 바꿔 "장면 하나 = 8초 클립 하나, 그 안에 짧은 문장 1~3개(합쳐 ${lo}~${hi}자)"로 둔다. 자막·TTS는 이미 문장 단위가 아니라 cue 단위로 잘리므로 렌더 쪽 영향은 작을 것으로 보인다(확인 필요).
  - 첫 장면만 예외 규칙: "첫 문장은 15자(ja 12자) 안쪽, 2초 안에 끝나는 질문이나 반전 한마디. 나머지 설명은 같은 장면의 두 번째 문장으로."
- **2분(15장면 안팎) 구조를 장면 번호로 지시한다.** 예(ko, 15장면):
  - 1: 훅(짧은 질문/반전) + 약속("끝까지 보면 ~를 알게 된다"를 노골적이지 않게)
  - 2–4: 비트 1 — 통설/모두가 아는 설명 + 첫 작은 보상
  - 5: 재훅 1 — "그런데 이 설명으로는 ~가 안 맞습니다" 꼴의 새 질문
  - 6–9: 비트 2 — 진짜 원리(단면도 장면), 끝에 작은 보상
  - 10: 재훅 2 — 남은 질문 상기
  - 11–13: 비트 3 / 반전(최대 보상)
  - 14: 써먹기(행동 한 가지)
  - 15: 한 문장 정리 + 고정 마무리 멘트
  - 고정 중간 멘트 "여기까진 다들 아시죠?"는 재훅 1 자리(5번)로 옮기고, 그 앞을 "아는 내용"으로 채우라는 규칙은 "아는 내용은 한 장면에 몰아 빠르게"로 바꾼다.
- **열린 고리 문구를 지시문에 직접 적는다.** 공통 script.md에 "규칙 + 이유" 꼴로: "앞에서 던진 질문의 답은 마지막 비트 전까지 다 주지 않는다. 시청자는 답을 기다리는 동안만 남기 때문이다." "비트마다 끝에 작은 '그렇구나'를 하나 준다. 2분 동안 보상이 없으면 넘긴다." 이런 줄이 지금은 없다.
- **brief가 비면 각도부터 정하게 한다.** 사용자 주제어 한 줄("커피", "자동차에 대한 비밀중 재밌는 이야기")만 받으면 LLM이 무난한 일반론을 쓴다. 지시문에 "주제가 넓으면 먼저 그 안에서 통설이 뒤집히는 질문 하나를 골라 그것만 다룬다"를 넣고, 출력에 `question`(다룰 질문)·`claims`(쓴 사실과 근거 한 줄씩)를 먼저 쓰게 하면 사실 확인과 집중도가 같이 오른다. 아이디어 모드 brief에 붙는 "참고(최근 인기 쇼츠 분석)" 꼬리표는 "참고(추천 주제 메모)"로 고치는 게 맞다.
- **예시 대본을 넣는다(Anthropic 권장).** 지금 공통 지시문에는 완성 대본 예시가 하나도 없다. 잘 된 실제 대본 2~3개를(주제·분야를 다르게) `<example>`로 넣으면 구조·리듬을 가장 빨리 고정한다. 단 예시를 베끼는 쏠림을 막으려 서로 다른 꼴(통설 뒤집기형, 실험형, 써먹기형)로 고른다.
- **채널 규칙은 지시문 본문과 태그로 나눈다.** 지금은 `## 채널 대본 규칙` 마크다운 제목 아래 붙인다. `<channel_script>`·`<channel_video>` 태그로 감싸면 공통 규칙과 채널 규칙이 부딪힐 때 우선순위("채널 규칙이 이긴다")를 한 줄로 정할 수 있다.

### Gaps
- 문장을 여러 개로 쪼개면 렌더(자막 cue·타이밍)가 어떻게 바뀌는지는 코드를 보지 않아 확인하지 못했다(`core/pipeline.py`·`subtitles`).
- 2분 쇼츠에서 재훅 간격과 유지율을 잇는 1차 데이터는 옆 노트도 못 찾았다. 위 장면 배치는 원칙 기반 제안이다.

---

## 3. 영상 프롬프트 규칙: Veo 3.1 / Gemini Omni Flash 지침과 맞는가, 장면 사이 일관성에 무엇이 빠졌나

### Takeaway
틀은 Google 지침과 대체로 맞다(피사체·동작·배경·카메라 하나·효과음 줄, 인물 묘사 반복). 하지만 ① 실제 모델(Omni Flash)은 기본으로 컷을 나누는데 "한 컷으로" 지시가 없고, ② 채널 머리말에 조명이 고정("soft even daylight")돼 저녁·밤 장면과 부딪히며, ③ "same art style in every shot"은 기억 없는 모델에 효과 없는 문구이고, ④ 일관성을 텍스트에만 맡겨 영상마다 주인공이 바뀌며, ⑤ 화살표·아이콘·"열 명 중 두세 명" 같은 도표·세기 연출은 모델이 약한 쪽이다. 참조 이미지(소재/ingredients)와 고정 캐릭터 문장, 장면별 조명, "single continuous shot", SFX/Ambient 분리 문법으로 바꾸는 것을 권한다.

### Cited Findings
- 공통 규칙 줄: "prompt는 … 영어 한 단락(60~90단어)", "prompt에 화풍·조명·카메라 품질 문구(photoreal, cinematic 등)를 쓰지 않는다", "주인공·장소·시대·옷차림을 매번 다시 적어", "카메라 움직임은 하나만", "항상 "No on-screen text, no numbers, no logos."로 끝낸다", "Audio: <구체적인 소리 2~3개>. No dialogue, no voices, no music." — [prompts/script.md](/Users/jkpark/my-toy/shorts-printer/prompts/script.md)
- 머리말은 코드가 모든 장면 앞에 붙인다("장마다 LLM이 화풍을 달리 쓰면 영상이 들쭉날쭉해서 채널 머리말을 코드로 붙인다") — [core/script.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/core/script.py) 121–124행
- ko 머리말: "Stylized 3D animated explainer, clean CGI visualization like an architecture documentary, smooth matte materials, soft even daylight, warm muted colors, same art style in every shot." ja 머리말: "…a tabletop scale model of Seoul with tilt-shift depth of field, soft clay-like matte materials, clean CGI visualization like an architecture documentary, soft even daylight, warm muted colors, same art style in every shot." — 두 channel.toml `[video] style`
- Veo 3.1 공식 5요소 공식: "[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]"; 오디오는 대사는 따옴표, "SFX: thunder cracks in the distance", "Ambient noise: the quiet hum of a starship bridge"; 일관성은 "Ingredients to Video"(캐릭터·장면·물건·스타일 참조 이미지); 8초 안에서 타임스탬프로 여러 샷 지시 가능("[00:00-00:02] …") — [Google Cloud, Ultimate prompting guide for Veo 3.1](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)
- 같은 글의 부정 지시 예: "a desolate landscape with no buildings or roads" 처럼 원하는 장면을 묘사하라("no man-made structures" 대신) — [Google Cloud, Veo 3.1 guide](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)
- Gemini API Veo 문서: 요소는 Subject·Action·Style·Camera positioning·Composition·Focus and lens effects·Ambiance("How the color and light contribute to the scene"); 입력 상한 1,024 토큰; 길이 4·6·8초; "Provide up to three asset images of a single person, character, or product. Veo preserves the subject's appearance" — [Gemini API, Veo](https://ai.google.dev/gemini-api/docs/veo)
- Google DeepMind Veo 가이드: "The more detail you add, the more control you'll have", 인물은 "A woman in her twenties with wavy brown hair and light freckles"처럼 구체적으로 — [Google DeepMind, Veo prompt guide](https://deepmind.google/models/veo/prompt-guide/)
- 실제 모델: Gemini Omni Flash는 Google I/O 2026에서 발표되어 Flow로 먼저 나왔고, 클립 최대 10초·음향 동시 생성, 텍스트+참조 이미지+영상+오디오를 함께 받는다. Google은 "Omni can keep the same characters, backgrounds, and movement consistent even after users make changes"라고 주장한다 — [Decrypt](https://decrypt.co/368393/google-unveils-gemini-omni-next-gen-ai-video-builder-simulate-world). 시연 예로 "claymation-style educational video explaining protein folding"이 나왔다(같은 기사)
- Omni Flash 프롬프트 요령(Google 팁을 옮긴 3자 정리): "Describe the whole scene: subject, action, setting, lighting, and camera", 기본으로 여러 샷을 만들므로 "When you need a single scene, say so directly: 'in a single continuous shot' or 'no scene cuts'", 오디오는 "'no dialogue'"처럼 직접 지시, "Add a reference image for a character, product, or style, and Omni Flash carries it across the clip", 화면 글자는 짧게 따옴표로 쓰면 깨끗하다("English is the most reliable") — [OpenArt, Gemini Omni Flash prompt guide](https://openart.ai/blog/gemini-omni-flash-prompt-guide/). "Omni 1.1 Flash"의 버전별 차이를 다룬 공식 자료는 찾지 못했다(Dreamina 글은 홍보물이라 근거로 쓰지 않는다 — [Dreamina](https://dreamina.capcut.com/ai-video/gemini-omni-1-1-flash-prompting-guide))
- 부정어("no text")가 오히려 그 대상을 부른다는 주장은 커뮤니티 글에 있고, API에는 별도 `negativePrompt` 필드가 있다고 한다 — [veo3ai.io negative prompts guide](https://www.veo3ai.io/blog/veo-3-negative-prompts-guide-2026) (3자 출처, 검증 안 됨). Google 공식 예시 자체도 "no buildings or roads"를 장면 묘사 안에 쓰므로, "no X"를 완전히 금지할 근거는 약하다(출처 충돌)
- 실제 출력: 프롬프트는 머리말(약 35단어) + 본문 70~100단어 ≈ 110~135단어로 1,024토큰 상한 안이다. 모든 장면이 같은 꼴("…in the center of the frame… Slow push-in… No on-screen text, no numbers, no logos. Audio: …")을 따른다 — 저장소 Job 4개 실측
- 실제 출력의 조명 충돌: "도로 정체" 1번 "a wide multi-lane city highway at evening rush hour" + 머리말 "soft even daylight"; ja 편의점 6번 "soft evening city lights behind" + 같은 머리말 — 저장소 Job 20261015-195423-e9bc, 20261016-054604-c25e
- 실제 출력의 머리말 중복: ja 프롬프트 본문에 "Clay textures, tilt-shift depth, playful curious mood"가 다시 들어간다(공통 규칙은 화풍 문구 금지, ja `video_style.md`는 "카메라 → 피사체 → 동작 → 배경 → 분위기 순"을 요구해 LLM이 분위기 자리에 화풍을 다시 씀) — 저장소 Job 20261016-054604-c25e, [ja video_style.md](/Users/jkpark/my-toy/shorts-printer/channels/ja-korea-trip/video_style.md)
- 실제 출력의 영상 사이 주인공 불일치: ko는 영상마다 새 인물("short black hair, mustard yellow knit sweater" / "commuter in a navy suit"), ja도 "beige coat and scarf" / 옷 묘사 없음 + "small suitcase" 또는 "tote bag"이 장면마다 바뀐다. 한 영상 안에서는 같은 문장을 반복해 대체로 유지한다 — 저장소 Job 4개 실측
- 실제 출력의 모델이 약할 법한 연출: "two crossed-out icons, a red thermometer and a pollen flower", "a faint question-shaped glow"(물음표 = 글자에 가까움), "A row of ten … two or three of them … sneeze"(개수 세기), "small blank colored tags glow above the price strips"(값표 = 글자 유도), "a stack of plain clay coins shrinks smoothly to show the lower cost" — 저장소 실측
- 머리말의 "tabletop scale model of Seoul"이 실내 장면(편의점 안, 호텔 방, 올리브영 진열대)에도 붙는다 — 저장소 ja Job 2개
- Flow 설정에 "소재" 라디오가 켜져 있지만(`SETTINGS`), 앱은 참조 이미지를 올리지 않는다 — [adapters/flow_auto.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/adapters/flow_auto.py)

### Inferences
- **맞는 것(유지):** 카메라 움직임 하나, 핵심 피사체를 가운데·앞 5초에, 인물·옷차림을 매번 다시 적기, 효과음 2~3개를 구체적으로, 대사·음악 빼기. Google 5요소 공식과 크게 다르지 않다.
- **바꿀 것:**
  1. 머리말에서 조명을 뺀다. "soft even daylight"를 "lighting as described in each scene"로 바꾸거나 아예 빼고, 공통 규칙의 "조명 문구를 쓰지 않는다"를 "조명·시간대는 장면마다 한 구절로 쓴다(예: warm amber dusk light)"로 고친다. 지금은 화풍 고정과 조명 고정이 한 줄에 묶여 있어 저녁 장면이 어정쩡해진다.
  2. "same art style in every shot", "like an architecture documentary"를 뺀다. 모델은 이전 장면을 모르므로 앞 문구는 효과가 없고, 뒤 문구는 모호한 비유다. 대신 재료·색·형태를 구체적으로: 예 "rounded low-poly-free smooth forms, matte pastel materials, limited palette of teal, cream, coral and mustard".
  3. ja 머리말의 "a tabletop scale model of Seoul"을 "everything is a handmade tabletop miniature diorama"로 일반화한다(실내 장면과 충돌 방지).
  4. 모든 프롬프트 맨 앞에 "Single continuous shot,"을 넣는다. Omni Flash는 기본으로 컷을 나눈다는 정리가 있으므로(OpenArt), 문장=장면 구조에서 원치 않는 컷이 나올 수 있다. 반대로 2분에서 "4초마다 변화"가 필요하면 8초 클립 안을 `[00:00-00:04] … [00:04-00:08] …` 타임스탬프 두 샷으로 나누는 선택지가 있다(Veo 3.1 공식 기법, Omni에서도 되는지는 확인 필요).
  5. 오디오 줄을 Google 문법으로: "Audio: a, b, c." → "SFX: … Ambient noise: … No dialogue, no music." 효과음과 배경음을 나누면 장면마다 같은 공간감(ambient)을 유지하기 쉽다.
  6. 글자 금지는 긍정 묘사로 먼저 막는다: "signs, labels and screens are plain and blank" + 끝에 짧게 "No on-screen text." 유지. 숫자·물음표·아이콘·값표처럼 글자를 부르는 소재는 video_style.md에서 금지 목록으로 명시한다("icons, symbols, question marks, price tags, charts").
  7. 개수 세기·도표 연출을 피한다. "열 명 중 두세 명"은 "a long line of people; only the few at the front, standing in bright sun, sneeze"처럼 비율을 상황으로 바꾼다.
- **영상 사이 일관성(채널 정체성):**
  - 채널 마스코트 한 줄을 channel.toml이나 video_style.md에 고정 문장으로 둔다. 예 ko: "Dot, the channel's guide character: a small round-headed 3D figure with dot eyes, a mustard-yellow knit sweater and teal trousers." ja: "Mina, the channel's clay traveler figure: round face with dot eyes, cream beret, sage-green coat, small coral suitcase." 지시문에 "사람이 필요하면 이 문장을 글자 그대로 넣는다"를 둔다. 지금은 영상마다 새 인물이 생겨 시리즈 인상이 약하다.
  - Flow "소재"(ingredients) 모드에 마스코트·화풍 참조 이미지를 고정으로 올리면 Google이 말하는 일관성 기능을 실제로 쓰게 된다. 단 이것은 flow_auto 자동화를 바꾸는 일이라 사용자 확인이 필요하다(지금은 텍스트만 넣는다).
  - 카메라 낱말을 채널마다 3~4개로 묶는다(ko: slow push-in, sideways truck, top-down crane; ja: very slow push-in, very slow orbit, high three-quarter overhead). 지금 ko는 규칙이 없어 orbit·crane·truck이 섞인다.
  - 고정 색 약속: 빨간 화살표 = 흐름/원인, 초록 = 좋은 쪽, 파랑 = 기준. 지금 video_style.md는 "빨간 선·화살표"만 있어 같은 영상 안에서 빨강이 원인·강조·나쁜 것에 다 쓰인다.

#### 다시 쓴 장면 프롬프트 예 (머리말을 아래처럼 바꾼다는 가정)

ko 새 머리말 예:
> Stylized 3D animated explainer. Smooth matte materials, simple rounded shapes, limited palette of deep teal, cream, coral and mustard yellow, clean uncluttered sets, signs and screens plain and blank.

ko 예 1 — "정체 파도는 차들과 반대로 움직인다"(실제 Job 20261015-195423-e9bc 4번 대체):
> Single continuous shot, high top-down aerial view with a slow push-in. A long straight four-lane highway runs vertically through the frame at dusk, and small rounded cream and teal cars drive upward. In the middle of the road, a tight cluster of stopped cars sits inside a translucent coral band of light. Over eight seconds the coral band slides steadily downward, against the traffic: cars enter it from below, stop, then leave it at the top and speed away. Dot, the channel's guide character (a small round-headed 3D figure with dot eyes and a mustard-yellow knit sweater), rides in a little red hatchback that passes through the band at the center. Warm amber dusk light, long soft shadows, deep teal sky. SFX: a ripple of brakes hissing, then engines revving away. Ambient noise: steady low highway hum. No dialogue, no music. No on-screen text.

ko 예 2 — "시신경 신호가 옆의 삼차신경으로 번진다"(실제 Job 20261015-235528-59f3 6번 대체):
> Single continuous shot, side-view medium close-up with a slow push-in. Dot's head in clean profile, centered against a soft deep-teal studio backdrop, the skin semi-transparent like frosted glass. Inside, a glowing blue cable runs from the eye back toward the brain, and right beside it a glowing coral cable branches down to the nose. A flash of white sunlight hits the eye; a pulse races along the blue cable, sparks leap across to the coral cable at the point where they touch, and the coral cable carries the glow down until the nose lights up and Dot scrunches into a small sneeze. Cool rim light, high contrast between the blue and coral lines. SFX: rising electric crackle, two sharp spark zaps, a short sneeze. Ambient noise: quiet soft room tone. No dialogue, no music. No on-screen text.

ja 새 머리말 예:
> Stylized 3D animated miniature diorama: everything is a handmade tabletop model with soft clay-like matte materials and strong tilt-shift blur at the frame edges. Palette of cream, sage green, coral and warm wood. Signboards, packages and screens are plain and blank.

ja 예 1 — "1+1은 하나 사면 하나 더"(실제 Job 20261016-054604-c25e 2번 대체):
> Single continuous shot, high three-quarter overhead view of a tabletop miniature convenience store with a very slow push-in. Mina, the channel's clay traveler figure (round face with dot eyes, cream beret, sage-green coat, small coral suitcase), stands at the checkout counter in the center holding one bottle of juice. A second identical bottle slides in beside hers from the right, a glossy coral clay arc grows from the first bottle over to the second, and both bottles bounce once together while Mina claps. Shelves of plain pastel snack boxes with blank labels fill the back wall. Bright morning light from a window on the left. SFX: a soft clay pop, two bottles clinking. Ambient noise: gentle refrigerator hum and a faint door chime. No dialogue, no music. No on-screen text.

ja 예 2 — "성수 카페 거리, 역에서 걷는 순서"(성수 주제 Job용 예시):
> Single continuous shot, 45-degree overhead view of a tabletop model of a Seoul neighborhood of low red-brick warehouses turned into cafés, with a very slow clockwise orbit. Mina, the channel's clay traveler figure (round face with dot eyes, cream beret, sage-green coat, small coral suitcase), steps out of a plain subway stairway at the lower left. A glossy coral clay path draws itself along the sidewalk from her feet, turns right past three café terraces with tiny cream umbrellas, and stops at a café with a large window at the upper right, where she arrives and waves. Tiny clay pedestrians stroll by; awnings and signboards are plain and blank. Crisp late-autumn afternoon light, long soft shadows, mustard-yellow ginkgo trees. SFX: tiny footsteps on clay pavement, a café door bell. Ambient noise: soft distant city murmur. No dialogue, no music. No on-screen text.

(네 예 모두 본문 약 100~120단어, 머리말 포함 약 140~150단어로 1,024토큰 안. 구조: 카메라/컷 → 고정 캐릭터 문장 → 동작(시간 순) → 배경 → 조명 → SFX → Ambient → 금지 한 줄.)

### Gaps
- Omni 1.1 Flash 전용 공식 프롬프트 가이드(Google 1차 문서)는 찾지 못했다. Omni 관련 요령은 3자 정리(OpenArt) 기준이다. Veo 3.1 지침이 Omni에 그대로 맞는지는 시험 생성으로 확인해야 한다.
- Flow UI의 "소재" 모드가 참조 이미지 몇 장까지, 어떤 형식으로 받는지, 크레딧이 달라지는지는 확인하지 못했다.
- "no X" 부정어가 Omni에서 실제로 역효과를 내는지에 대한 1차 근거는 없다(커뮤니티 주장과 Google 예시가 엇갈림). A/B 생성 몇 개로 확인하는 편이 낫다.
- Flow UI에 별도 negative prompt 칸이 있는지는 확인하지 못했다.

---

## 4. 썸네일 지시문

### Takeaway
충분히 잘 짜여 있다(길이 한도, 강조 낱말 하나, 답 금지, 좋은/나쁜 예, 정책 위반 이유까지). 2분 전환에서 고칠 것은 거의 없고, 제목·썸네일·주제 사이의 "답 금지" 규칙만 맞추면 된다.

### Cited Findings
- 공통 `thumbnail.md`는 채널 규칙 + 길이 한도 + 할 일 세 줄뿐이고, 실제 내용은 채널 `thumbnail.md`가 맡는다 — [prompts/thumbnail.md](/Users/jkpark/my-toy/shorts-printer/prompts/thumbnail.md)
- 채널 규칙: "핵심 낱말 하나만 강조색", "답·반전·결론과 그 단서를 넣지 않는다", 좋은 예/나쁜 예 각 2개와 이유, "영상에 없는 내용을 약속하면 낚시로 신고되고 YouTube 정책(오해 소지 메타데이터) 위반", 배경은 첫 장면 0.5초 화면 — [ko thumbnail.md](/Users/jkpark/my-toy/shorts-printer/channels/ko-40sec-facts/thumbnail.md), [ja thumbnail.md](/Users/jkpark/my-toy/shorts-printer/channels/ja-korea-trip/thumbnail.md)
- ko 규칙에 "같은 문구가 영상 내내 위 검은 띠에 제목으로도 뜬다"가 남아 있으나 ko `layout = "clean"`은 "영상은 띠·제목 없이"다(ja 규칙은 이미 "영상에는 제목 없이 자막만"으로 고쳐 있음) — [ko thumbnail.md](/Users/jkpark/my-toy/shorts-printer/channels/ko-40sec-facts/thumbnail.md), [ko channel.toml](/Users/jkpark/my-toy/shorts-printer/channels/ko-40sec-facts/channel.toml)

### Inferences
- ko `thumbnail.md`의 "영상 내내 위 검은 띠에 제목으로도 뜬다" 줄은 지금 배치(clean)와 맞지 않는 낡은 설명이다. 고치거나 지운다.
- 배경이 "첫 장면 클립 0.5초"라서 첫 장면 프롬프트가 썸네일 품질을 정한다. 2분 버전에서 첫 장면은 "한 장면에 피사체 하나, 가운데, 0.5초부터 이미 보이게"를 영상 규칙에 더하면 썸네일과 훅이 같이 좋아진다.

### Gaps
- 썸네일 결과물(`thumbnail.json` 등)은 저장소에서 찾지 못해 실제 문구는 확인하지 못했다.

---

## 5. 뻔한("AI slop") 출력을 부르는 문구와 서로 부딪히는 규칙

### Takeaway
가장 큰 원인은 (a) 내용 대신 길이를 채우게 만드는 고정 글자 수, (b) 모든 장면을 같은 꼴로 찍어 내게 만드는 고정 꼬리 문장과 고정 카메라, (c) 막연한 형용사·비유("clean", "warm muted", "like an architecture documentary", "playful curious mood"), (d) 예시 대본 없이 규칙만 나열한 지시문이다. 몇몇 규칙은 서로 부딪힌다.

### Cited Findings
- Anthropic: 모델은 지시가 없으면 "generic, 'on distribution' outputs"로 수렴하고, 원하는 수준을 구체적으로 적어야 한다("Be specific about desired behavior"). "Tell Claude what to do instead of what not to do" — [Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- Google: 구체적 묘사일수록 통제가 쉽다("The more detail you add, the more control you'll have"), 인물은 나이·머리·특징까지 — [Google DeepMind, Veo prompt guide](https://deepmind.google/models/veo/prompt-guide/)
- 서로 부딪히는 규칙(파일 인용):
  - 공통 `script.md` "prompt에 화풍·조명·카메라 품질 문구를 쓰지 않는다" ↔ ja `video_style.md` "prompt는 카메라 → 피사체 → 동작 → 배경 → **분위기** 순" → 실제로 "Clay textures, tilt-shift depth, playful curious mood"가 반복된다.
  - 머리말 "soft even daylight" ↔ 장면 "evening rush hour", "soft evening city lights", "early morning".
  - `trend_pick.md` "답을 제목에서 다 말하지 않는다" ↔ ko `script.md` "답·반전·결론과 그 단서를 제목에 넣지 않는다."
  - ko `ideas.md` "40초 안에 답이 딱 떨어지는 것" ↔ 2분 목표.
  - ko `thumbnail.md` "영상 내내 위 검은 띠에 제목" ↔ `layout = "clean"`.
  — 위 파일들 및 저장소 실측
- 실제 출력의 같은 꼴 반복: 대본 4개 28장면 모두 "…in the center (of the frame)… Slow/Very slow push-in…"이 거의 다 들어가고(28개 중 약 20개가 push-in), 모든 장면이 "No on-screen text, no numbers, no logos."와 "No dialogue, no voices, no music."으로 끝난다. ja 장면은 모두 "…mood." 형용사 꼬리("Helpful, discovering mood", "Calm, organized mood")를 단다 — 저장소 실측
- YouTube는 2025년 7월 "inauthentic content"로 이름을 바꾸며 템플릿·대량 생산·서로 바꿔 끼워도 되는 AI 콘텐츠 단속을 강화했다(옆 노트 정리) — [shorts_length_cadence.md](/Users/jkpark/my-toy/shorts-printer/research_notes/2분%20쇼츠%20퀄리티%20전략/shorts_length_cadence.md) Q4

### Inferences
- **꼬리 형용사("… mood")는 정보가 없다.** 장면마다 바꿀 것은 분위기 형용사가 아니라 조명·시간대·색 한 구절(예 "bright morning light from the left window")이다. ja `video_style.md`의 "분위기" 자리를 "조명·시간대"로 바꾼다.
- **카메라를 비트 역할에 묶는다.** 모든 장면이 push-in이면 2분 내내 같은 움직임이 15번 반복된다. 규칙 예: 훅·반전 = fast push-in 또는 top-down crane, 설명(단면도) = static 또는 slow push-in, 동선 = slow orbit/truck, 마무리 = slow pull-back. 이것은 단조로움과 "템플릿 같은 대량 생산" 인상을 함께 줄인다.
- **고정 멘트 두 개도 반복 신호다.** 매 영상 같은 4번째 문장 시작과 같은 끝 문장은 브랜드 장치이지만, 2분에서 재훅 자리를 차지한다. 끝 문장은 두고 중간 멘트는 재훅 문장으로 바꾸거나 매번 꼴을 달리하는 것을 권한다(사용자 결정 사항).
- **예시 > 규칙.** 지금 지시문은 금지 규칙(하지 않는다)이 많고 완성 예시가 없다. Anthropic 지침대로 "잘 된 대본 2~3개 + 잘 된 장면 프롬프트 3~4개"를 `<example>`로 넣고 금지 규칙 일부를 "이렇게 쓴다" 꼴로 바꾸면 무난한 평균 출력이 줄어들 것으로 본다.
- **지시문 구조 정리안(공통 script.md):** `<role>` 한 줄 → `<audience_and_goal>`(누가, 왜 끝까지 보나) → `<structure>`(장면 번호별 비트, 재훅, 보상) → `<sentence_rules>`(TTS·길이) → `<scene_prompt_rules>`(5요소 순서, single continuous shot, 마스코트 문장, 조명, SFX/Ambient, 금지 한 줄) → `<channel_script>` → `<channel_video>` → `<examples>`. 지금 내용을 거의 그대로 옮기고 구조 블록과 예시만 새로 쓰면 된다.

### Gaps
- 위 수정안이 실제 유지율을 올리는지는 측정 데이터가 없다. 같은 주제로 지금 지시문 vs 수정 지시문 대본을 몇 편 만들어 Studio 유지율 곡선을 비교해야 한다.
- 고정 멘트("여기까진 다들 아시죠?", "오늘도 상식 하나 챙기셨네요?")가 채널 인지에 주는 효과를 다룬 자료는 찾지 못했다.

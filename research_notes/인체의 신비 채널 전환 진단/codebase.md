# 코드베이스 진단: ko-40sec-facts를 "인체의 신비" 채널로 바꿀 때 고칠 곳

조사 범위: 로컬 저장소 `/Users/jkpark/my-toy/shorts-printer`만 읽었다(웹 검색 없음). 출처는 모두 `파일:줄`이다. 아무 파일도 고치지 않았다. `.env`·`.secrets/`는 읽지 않았다.
대상 시청자: 20~80대 전체. 일상에서 누구나 겪는 몸 현상의 원리만 설명하고 치료 조언은 하지 않는다(채널 주인이 정정한 방향. 시니어 전용 규칙은 제안하지 않는다).

## 1. 새 채널 폴더(새 id)로 만들까, ko-40sec-facts를 그 자리에서 고칠까?

### Takeaway
그 자리에서 고치기를 권한다. id는 바뀌지 않고 내용만 바뀐다. 그래서 YouTube 토큰, 지난 작업 28개, 주제 찾기 33개, 그리고 그 기록에 기대는 "같은 주제 피하기" 기능이 그대로 이어진다. 다만 지난 주제 대부분이 생활 상식이다. 그 기록은 몸 주제를 고를 때 제외 목록으로만 쓰이므로 해가 없다. 새 id가 필요한 경우는 YouTube 채널 자체를 새로 만들 때뿐이다.

### Cited Findings
- id는 만든 뒤 바꾸지 않는다. 기존 작업의 `channel` 필드에 남기 때문이다 — [.claude/rules/channels.md:9](.claude/rules/channels.md)
- 업로드 토큰 경로가 id에 묶여 있다: `.secrets/channels/<id>/youtube_token.json` — [src/shorts_printer/registry.py:50](src/shorts_printer/registry.py), [src/shorts_printer/config.py:30](src/shorts_printer/config.py)
- 저장소(shorts.db)에 있는 기록: job은 ko-40sec-facts 28개, ja-korea-trip 9개. trend는 ko 33개, ja 13개. schedule 레코드는 지금 없다(`sqlite3 shorts.db "select kind, json_extract(data,'$.channel'), count(*) from docs where name='' group by 1,2"` 결과) — [shorts.db](shorts.db)
- 주제 찾기는 같은 채널 id로 이미 만든 주제 최근 30개(`_made`)와 앞서 추천한 주제 최근 50개(`_shown`)를 제외 목록으로 보낸다 — [src/shorts_printer/core/trends.py:476-487](src/shorts_printer/core/trends.py)
- 대본은 같은 채널 최근 제목 15개를 "이 틀을 피한다"로 받는다 — [src/shorts_printer/core/pipeline.py:91-94](src/shorts_printer/core/pipeline.py), [src/shorts_printer/core/script.py:194-195](src/shorts_printer/core/script.py)
- 테스트가 채널 id `ko-40sec-facts`와 그 글 파일의 문구에 기댄다. 쓰는 곳은 tests/test_prompts.py, test_script.py, test_pipeline.py, test_web*.py, test_schedule.py, test_trends.py, test_research.py, test_thumbnail.py, test_voice_render.py, test_youtube.py다(`grep -rln ko-40sec-facts tests`) — [tests/test_prompts.py:18](tests/test_prompts.py)
- 채널 이름·설명은 이미 커밋하지 않은 변경이 있다("40초 상식" → "그러고 보니")(`git diff channels/`) — [channels/ko-40sec-facts/channel.toml:2-3](channels/ko-40sec-facts/channel.toml)

### Inferences
- 같은 id로 고치면 최근 제목 15개가 "틀을 피한다" 용도로 계속 들어간다. 생활 상식 제목이라도 질문형 끝맺음을 겹치지 않게 하는 데만 쓰이므로 문제없다.
- 새 id로 만들면 tests/test_script.py:55-64가 여전히 ko-40sec-facts의 문구를 확인한다. 그러면 옛 채널 폴더를 지울 수 없다.

### Gaps
- YouTube 쪽 채널 이름 변경 정책(이름을 바꿀 수 있는 횟수, 구독자 영향)은 코드 범위 밖이라 확인하지 않았다.

## 2. sensitive_gate는 무엇을 잡고 무엇을 하나? 몸 주제마다 걸릴까?

### Takeaway
게이트는 키워드 필터가 아니다. 대본을 쓰는 LLM이 `sensitive` 필드에 "건강·의료" 같은 분야 이름을 스스로 적으면 걸린다. 지금 채널의 몸 주제 8개 가운데 3개만 걸렸다. 판정이 들쭉날쭉하다는 뜻이다. 그런데 웹과 스케줄에서 만든 작업은 이미 모두 `review=True`라서, 장면 영상을 만들기 전에 사람이 대본을 확정해야 한다. 그래서 게이트가 따로 막는 경우는 CLI로 만든 작업뿐이다. 실제 영향은 배너와 알림 문구에 그친다. 몸 채널에서 게이트를 켜 둬도 막히지 않는다. 진짜 걸림돌은 주제 찾기 지시문이 건강 주제를 피하라고 하는 것이다(5번 질문).

### Cited Findings
- 판정 기준은 pydantic 필드 설명 하나다: `sensitive: str = Field(description="건강·의료, 법률, 금융·투자, 정치 주제면 그 분야 이름. 아니면 빈 문자열")`. 코드에 박혀 있어 채널별로 바꿀 수 없다 — [src/shorts_printer/core/script.py:29](src/shorts_printer/core/script.py)
- 채널 값은 켜고 끄는 bool 하나다(`sensitive_gate: bool = True`) — [src/shorts_printer/core/channel.py:113](src/shorts_printer/core/channel.py)
- 동작: 대본 단계는 로그만 남긴다 — [src/shorts_printer/core/pipeline.py:87-88](src/shorts_printer/core/pipeline.py). 장면 단계는 `sensitive_gate and area and not confirmed`이면 `Wait("민감 분야(..) 대본 확인")`로 멈춰 영상 크레딧을 쓰지 않는다 — [src/shorts_printer/core/pipeline.py:147-155](src/shorts_printer/core/pipeline.py)
- 그 바로 앞에서 `review and not confirmed`도 같은 자리에서 멈춘다 — [src/shorts_printer/core/pipeline.py:150-151](src/shorts_printer/core/pipeline.py)
- 웹 직접 주제 작업과 추천 주제 작업, 스케줄 작업은 모두 `review=True`로 만든다 — [src/shorts_printer/web/app.py:442-452](src/shorts_printer/web/app.py), [src/shorts_printer/core/schedule.py:257](src/shorts_printer/core/schedule.py), [src/shorts_printer/core/schedule.py:312-313](src/shorts_printer/core/schedule.py). CLI만 review 없이 만든다 — [src/shorts_printer/cli.py:100](src/shorts_printer/cli.py)
- 스케줄 알림은 "검수 확정이 민감 확인도 겸하므로 알림은 이것 하나"다. 민감 분야면 한 줄만 덧붙는다 — [src/shorts_printer/core/schedule.py:359-365](src/shorts_printer/core/schedule.py), [src/shorts_printer/core/schedule.py:320-326](src/shorts_printer/core/schedule.py)
- 화면 배너 문구가 고정돼 있다: "YouTube는 건강·법률·금융·정치를 AI가 전문가처럼 설명하는 영상을 수익화하지 않고…" — [src/shorts_printer/web/templates/job.html:73-77](src/shorts_printer/web/templates/job.html), 배지 [src/shorts_printer/web/app.py:802-804](src/shorts_printer/web/app.py)
- 실제 판정 기록(shorts.db의 ko 채널 script.json). 걸린 것: "햇빛만 보면 재채기…", "손 씻을 땐 꼭 따뜻한 물…", "면도하면 털이 굵어진다는 말…". 안 걸린 것: "하품은 왜 옮을까?", "뇌는 자기 아픔을 못 느낀다? 두통의 진짜 정체", "아침에 일어나기 힘든 진짜 이유", "진짜 웃음 vs 가짜 웃음…", "건강검진 결과지, 이것만 보면 됩니다" — [shorts.db](shorts.db)
- 채널 만들기 스킬은 "건강·법률·금융·정치를 다루면 켜 둔다"고 안내한다 — [.claude/skills/channel-create/SKILL.md:30](.claude/skills/channel-create/SKILL.md)

### Inferences
- 몸 채널에서도 `sensitive_gate = true`를 그대로 둬도 된다. 어차피 모든 작업이 검수에서 멈추므로 늘어나는 수고가 없다.
- 판정을 "생리 원리는 빼고 진단·치료·약·식품 효능을 말하면만"으로 좁히려면 script.py:29의 필드 설명을 고쳐야 한다. 이건 모든 채널에 걸리는 코드 변경이다. 채널별로 하려면 새 키가 필요하다(예: `sensitive_rule` 문자열을 필드 설명이나 지시문에 넣기). 지금 구조에서 가장 작은 변경은 필드 설명 한 줄을 고치는 것이다. 예: "진단·치료·약·식품 효능·투자·법률 조언·정치 주장이 들어가면 그 분야 이름. 몸의 원리 설명만이면 빈 문자열".
- 배너 문구("AI가 전문가처럼 설명하는 영상을 수익화하지 않고")가 YouTube 정책을 정확히 옮긴 것인지는 코드가 근거를 대지 않는다. 그대로 믿지 말아야 한다.

### Gaps
- `review` 확정 없이 CLI만으로 돌리는 운영을 실제로 하는지는 코드로 알 수 없다.

## 3. [research] 키와 지금 도메인 목록, 비었을 때의 동작

### Takeaway
키는 6개다: provider, domains, news, open, languages, queries_per_topic/max_pages. 지금 목록은 생활 전반(국립국어원·기상청·통계청·NASA·천문연 등)과 건강(질병관리청·식약처·PubMed·NIH·WHO)이 섞여 있다. 몸 채널은 건강 쪽을 남기고 해부·생리 출처를 더하는 게 맞다. domains와 news가 둘 다 비고 open이 false면 조사 단계가 오류로 멈춘다.

### Cited Findings
- 모델: `domains`, `languages`, `queries_per_topic`(1~10, 기본 5), `max_pages`(1~20, 기본 8), `news`, `open`(기본 false). 도메인은 scheme·경로·`www.`를 떼고 받는다 — [src/shorts_printer/core/channel.py:74-88](src/shorts_printer/core/channel.py)
- 지금 domains: kdca.go.kr, health.kdca.go.kr, mfds.go.kr, korean.go.kr, encykorea.aks.ac.kr, khs.go.kr, scent.kisti.re.kr, kasi.re.kr, weather.go.kr, kostat.go.kr, mods.go.kr, pubmed.ncbi.nlm.nih.gov, nih.gov, nasa.gov, noaa.gov, who.int. news는 방송·일간지 11개, health.chosun.com, bbc/nature/science/natgeo다. queries_per_topic와 max_pages는 적혀 있지 않아 기본 5/8을 쓴다 — [channels/ko-40sec-facts/channel.toml:46-52](channels/ko-40sec-facts/channel.toml)
- 둘 다 비고 open이 아니면 `RuntimeError("채널에 조사 사이트([research] domains)가 없어요…")`를 던진다 — [src/shorts_printer/core/research.py:42-45](src/shorts_printer/core/research.py). 사실이 0개여도 멈춘다 — [src/shorts_printer/core/pipeline.py:65-67](src/shorts_printer/core/pipeline.py)
- 허용 목록은 Claude web_search의 `allowed_domains`로 넘어간다(빈 목록이면 제한 없음) — [src/shorts_printer/adapters/claude_research.py:78-83](src/shorts_printer/adapters/claude_research.py). 하위 도메인도 허용된다(nih.gov면 ncbi.nlm.nih.gov도 된다) — [src/shorts_printer/core/research.py:32-36](src/shorts_printer/core/research.py)
- 사실 꼬리표: news 목록에서 온 사실은 kind="news", domains에서 온 것은 "official", 그 밖(open일 때)은 "web"이다. 사실 시트에는 " (보도)", " (웹)"이 붙는다 — [src/shorts_printer/core/research.py:32-36](src/shorts_printer/core/research.py), [src/shorts_printer/core/research.py:63-67](src/shorts_printer/core/research.py)
- 지시문의 건강 규칙: "건강·과학 주장은 기사만으로 쓰지 않는다. 기사가 인용한 기관 발표나 연구를 찾아 열고…"와 "상관을 원인으로, 동물 결과를 사람으로, 연구 결과를 조언으로 바꾸지 않는다" — [prompts/research.md:17](prompts/research.md), [prompts/research.md:22](prompts/research.md)
- 사실 수는 12개로 정해져 있다(`MAX_FACTS = 12`) — [src/shorts_printer/core/research.py:9](src/shorts_printer/core/research.py)
- 주제 찾기 검색도 같은 허용 사이트로 묶인다 — [src/shorts_printer/core/trends.py:494-496](src/shorts_printer/core/trends.py)
- 공통 지시문에 생활 상식 쪽으로 기운 문구가 있다: "주제의 답, 통념이 뒤집히는 사실, 그 원리나 근거, 생활에서 써먹을 것을 고루 찾는다", "첫 검색은 주제 전체를 넓게(운영사 이름 + 주제)" — [prompts/research.md:12](prompts/research.md), [prompts/research.md:24](prompts/research.md)

### Inferences
- 몸 채널 domains 제안. 남길 것: kdca.go.kr, health.kdca.go.kr, mfds.go.kr, pubmed.ncbi.nlm.nih.gov, nih.gov, who.int, encykorea.aks.ac.kr, korean.go.kr(용어). 뺄 것: kasi.re.kr, weather.go.kr, kostat.go.kr, mods.go.kr, khs.go.kr, nasa.gov, noaa.gov. 더할 후보는 이름만 적는다. 실제 도메인과 내용은 웹으로 확인해야 한다: 서울대병원 의학정보, 국가건강정보포털, MSD 매뉴얼 일반인용, Mayo Clinic, Cleveland Clinic, NHS, Britannica, OpenStax Anatomy & Physiology.
- "생활에서 써먹을 것"(research.md:24, trend_idea.md:27, trend_pick.md:22)은 몸 채널에서 "이렇게 하세요"식 조언을 끌어낸다. 채널 script.md:8의 "처방으로 끝내지 않는다"와 부딪힌다. 공통 지시문은 모든 채널에 걸리므로 손대기 어렵다. 그래서 채널 trends.md·ideas.md에 "써먹을 것 = 내 몸에서 알아차리는 법까지만, 치료·섭취 조언 아님"이라고 덮어써야 한다.
- 몸 주제는 공식 기관 자료만으로는 원리 설명 사실 12개가 모자랄 수 있다. queries_per_topic를 7~8로, max_pages를 10~12로 올리는 것을 검토할 만하다. ja 채널은 10/12다 — [channels/ja-korea-trip/channel.toml:61-62](channels/ja-korea-trip/channel.toml)

### Gaps
- 제안 도메인이 Claude web_fetch에서 열리는지(url_not_accessible 여부)는 실행해 봐야 안다.

## 4. 고정 멘트("여기까진 다들 아시죠?", "오늘도 상식 하나 챙기셨네요?")는 어디서 강제되나?

### Takeaway
코드 검사기는 없다. 채널 script.md 지시문에만 있고, LLM이 지킨다. 테스트 두 곳이 그 문구에 묶여 있다. 문구를 바꾸면 tests/test_script.py:61은 반드시 같이 고쳐야 한다. test_subtitles.py는 고정 데이터라 안 고쳐도 통과한다.

### Cited Findings
- 정의: [channels/ko-40sec-facts/script.md:10-14](channels/ko-40sec-facts/script.md)
- 테스트: `test_ko_system_keeps_every_old_rule`이 시스템 지시문 안에 "여기까진 다들 아시죠?", "오늘도 상식 하나 챙기셨네요?", "질문형", "3D 애니메이션", "단면도", "존댓말", "훅"이 있는지 본다 — [tests/test_script.py:55-64](tests/test_script.py)
- 자막 테스트가 문장 안에 그 멘트를 고정 데이터로 쓴다(채널 파일을 읽지 않음) — [tests/test_subtitles.py:17-18](tests/test_subtitles.py)
- 원어민 검수 지시문은 마지막 멘트를 "채널이 정해 둔 고정 문구라 상투적이어도 지적하지 않는다"로 봐준다. 한국어 채널은 검수를 건너뛴다 — [prompts/script_proofread.md:12](prompts/script_proofread.md), [src/shorts_printer/core/pipeline.py:101-103](src/shorts_printer/core/pipeline.py)
- 다시 거는 위치(13장면의 5번째·10번째)와 첫 문장 길이(한국어 15자 안팎, 2초)는 공통 지시문에도 박혀 있다 — [prompts/script.md:16-21](prompts/script.md)

### Inferences
- 멘트를 바꾸는 일은 script.md 수정 + test_script.py:61 문자열 교체로 끝난다. 코드 변경은 없다.

### Gaps
- 없음.

## 5. 대본 규칙(script.md)과 공통 지시문: 모든 연령 대상 몸 호기심 채널에 맞나, 무엇으로 바꾸나

### Takeaway
뼈대(훅 → 5번째 장면에서 반전 → 10번째 장면에서 다시 걸기 → 마무리, 사실 시트 강도 지키기, 존댓말)는 몸 채널에도 그대로 맞는다. 바꿀 것은 네 가지다. 훅 예시와 꼴을 "내 몸에서 일어나는 일 + 그 순간"으로, 마무리 멘트를 몸 주제로, 제목 예시를 몸 현상으로, 건강 규칙 한 줄을 채널의 중심 규칙으로 키운다. 주제 찾기 공통 지시문 두 곳은 건강 주제를 피하라고 한다. 이 지시문이 채널 규칙보다 세면 몸 채널이 돌지 않는다. 가장 큰 걸림돌이다.

### Cited Findings (규칙별)
- 훅: 지금은 "첫 문장은 2초 안에 끝나는 훅… 15자 안팎의 질문이나 의외의 사실"이고 예시는 바나나다 — [channels/ko-40sec-facts/script.md:3-4](channels/ko-40sec-facts/script.md). 공통 지시문도 같은 길이를 정한다 — [prompts/script.md:17](prompts/script.md)
- 존댓말: "말하듯 자연스러운 존댓말" — [channels/ko-40sec-facts/script.md:5](channels/ko-40sec-facts/script.md)
- 사실 강도: 쥐 실험·상관관계 단서를 지키라는 규칙이 있다 — [channels/ko-40sec-facts/script.md:6](channels/ko-40sec-facts/script.md)
- 건강 규칙: "건강 주제는 몸의 원리 설명까지만 쓴다. 진단·치료·식품 효능이나 '이렇게 하세요' 같은 처방으로 끝내지 않는다" — [channels/ko-40sec-facts/script.md:8](channels/ko-40sec-facts/script.md)
- 5번째 장면 고정 멘트: "여기까진 다들 아시죠?" — [channels/ko-40sec-facts/script.md:11](channels/ko-40sec-facts/script.md)
- 마지막 고정 멘트: "오늘도 상식 하나 챙기셨네요?" — [channels/ko-40sec-facts/script.md:12-13](channels/ko-40sec-facts/script.md)
- 10번째 장면: 매번 다르게 다시 건다. 예시는 "같은 빛을 봐도 어떤 사람은 멀쩡하다는 겁니다" — [channels/ko-40sec-facts/script.md:15-17](channels/ko-40sec-facts/script.md)
- 제목: "질문형으로 15~30자 한 줄… 소름·미친 같은 감탄어는 쓰지 않는다". 예시는 주유구와 바나나다 — [channels/ko-40sec-facts/script.md:18-22](channels/ko-40sec-facts/script.md)
- 대본 user 메시지에 `채널 분야: {ch.concept}. 이 분야를 즐겨 보는 시청자에게 맞는 각도로 쓴다.`가 들어간다 — [src/shorts_printer/core/script.py:193](src/shorts_printer/core/script.py)
- 주제 찾기 아이디어 모드 공통 지시문: "건강·법률·금융·정치처럼 민감한 주제는 피하고, 꼭 넣으면 safe를 낮게 매긴다" — [prompts/trend_idea.md:35](prompts/trend_idea.md)
- 주제 찾기 추천 모드 공통 지시문: "건강·법률·금융처럼 AI 해설로 수익화가 막히는 주제는 피하고 excluded에 이유를 남긴다" — [prompts/trend_pick.md:30](prompts/trend_pick.md)
- 아이디어 지시문에서 채널 trends.md는 "주제 기준과 부딪치면 주제 기준을 따른다". 그런데 공통 규칙(35줄)이 채널 글보다 뒤에 와서 무엇이 이기는지 정해져 있지 않다 — [prompts/trend_idea.md:13-17](prompts/trend_idea.md)
- safe 점수 기준은 "저작권·민감 주제 위험이 낮나"다. 몸 주제는 safe가 낮게 매겨져 총점이 깎인다(가중치 safe 15) — [src/shorts_printer/core/trends.py:41-46](src/shorts_printer/core/trends.py), [channels/ko-40sec-facts/channel.toml:58](channels/ko-40sec-facts/channel.toml)

### Inferences (규칙별 판정과 제안 문구)
- **훅(맞음, 예시와 꼴 교체)**: 15자 안팎 2초 훅은 공통 지시문이라 그대로 둔다. 채널 규칙은 "몸 부위 + 누구나 겪는 순간"으로 바꾼다. 제안: "첫 문장은 2초 안에 끝나는 훅이다. 누구나 겪어 본 몸의 순간 하나를 몸 부위 이름과 함께 묻는다. 둘째 문장에서 그때 몸 안에서 무슨 일이 일어나는지 답하겠다고 약속한다. 좋은 예: 하품, 왜 옮을까요? 남이 하품하면 따라 하게 되는 이유, 뇌 속에서 찾아보겠습니다." 이때 "몸 안에서 무슨 일이"라는 꼴이 채널 정체성이 된다.
- **존댓말(맞음)**: 20~80대 전체 대상이라 존댓말을 그대로 둔다.
- **건강 규칙(맞음, 위치와 범위 키우기)**: 지금은 한 줄이다. 몸 채널에서는 맨 위 원칙으로 올리고 하지 않는 말을 늘어놓는다. 제안: "이 채널은 몸이 왜 그렇게 움직이는지 원리만 설명한다. 병 이름으로 진단하지 않고, 치료법·약·영양제·음식 효능·운동법을 권하지 않는다. '~하면 좋다', '~하세요', '병원에 가 보세요'로 끝내지 않는다. 증상이 질병의 신호일 수 있는 주제는 '대부분은 정상 반응' 같은 안심이나 경고도 시트에 있는 말만 쓴다."
- **5번째 멘트 "여기까진 다들 아시죠?"(대체로 맞음, 교체 권장)**: 몸 현상은 "다 안다"고 하기 어렵다(예: 쥐가 나는 이유를 아는 사람은 적다). 교체 후보: "그런데 몸 안을 들여다보면 이야기가 달라집니다." 또는 "여기서부터가 진짜 몸속 이야기입니다." 고정 멘트로 쓰면 test_script.py:61을 같이 고친다.
- **10번째 다시 걸기(맞음, 예시만 몸으로)**: 예시 교체 제안: "그런데 더 신기한 건, 잠든 사이에도 이 일이 일어난다는 겁니다."
- **마지막 "오늘도 상식 하나 챙기셨네요?"(안 맞음)**: '상식'이라는 낱말이 옛 콘셉트에 묶여 있다. "챙기셨네요"도 건강 채널에서는 무언가 해 준 듯(처방처럼) 들릴 수 있다. 원리 설명에 머무는 교체 후보: "내 몸, 오늘 하나 더 알게 되셨네요?" 또는 "우리 몸, 생각보다 똑똑하죠?" 앞 문장에 이어 붙이지 않는다는 규칙(script.md:12)은 그대로 둔다. 좋은 예도 몸 주제로 바꾼다. 예: "하품은 졸려서가 아니라, 뇌가 서로 맞추는 신호였던 겁니다. 내 몸, 오늘 하나 더 알게 되셨네요?"
- **제목(맞음, 예시와 꼴만 교체)**: 15~30자 질문형, 답을 넣지 않는 규칙은 몸 채널에도 맞는다. 예시 교체 제안: "자고 일어나면 왜 키가 커져 있을까?", "추우면 왜 이가 딱딱 부딪칠까?", "다리에 쥐가 나는 순간, 몸에선 무슨 일이?". 공포를 부추기는 제목("이 증상 무시하면 큰일")은 금지에 더한다. trend_idea.md:24와 trend_pick.md:19의 "공포 조장" 금지와 같은 방향이다.
- **주제 찾기 공통 지시문(코드와 공통 지시문 변경 필요)**: trend_idea.md:35와 trend_pick.md:30은 몸 채널의 거의 모든 주제를 피하게 만든다. 고칠 길은 둘이다. (a) 공통 지시문 문구를 "진단·치료·약·효능을 말해야 하는 건강 주제는 피한다. 몸의 원리 설명은 괜찮다"로 좁힌다. 모든 채널에 걸리지만 ja 채널에는 거의 영향이 없다. (b) 채널별로 바꾸려면 새 키가 필요하다(예: `[trends] avoid = "…"`를 `${avoid}` 자리로). 규칙 문서는 "값이 모자라면 channel.toml 키를 더하는 걸 먼저 제안한다"고 한다 — [.claude/rules/channels.md:75](.claude/rules/channels.md). (a)가 한 줄씩 두 파일이라 더 작다.
- **"생활에서 써먹을 것" 4단계**: trend_idea.md:27, trend_pick.md:22, research.md:24 공통 문구다. 몸 채널 ideas.md에서 "4단계의 '써먹을 것'은 내 몸에서 확인해 보는 법(예: 손목 맥 짚기)까지, 치료·섭취 조언은 아님"으로 좁힌다.

### Gaps
- 채널 글(trends.md)과 공통 지시문의 건강 회피 규칙이 부딪칠 때 LLM이 어느 쪽을 따르는지는 돌려 봐야 안다.

## 6. 콘셉트·이름·설명·주제 고르기(channel.toml, trends.md, ideas.md)

### Takeaway
topic 선택의 주 손잡이는 `concept`(모든 추천과 대본에 들어감), ideas.md(아이디어 모드), trends.md(두 모드 모두)다. `[trends] keywords`는 추천 모드의 YouTube 검색어를 정한다. 비어 있으면 LLM이 concept와 trends.md로 검색어를 만든다. 몸 채널은 keywords를 채우는 편이 검색이 덜 샌다.

### Cited Findings
- 지금 값: name "그러고 보니", description은 생활 속 물음이고, concept는 "사람들에게 실제로 도움이 되는 상식"이다. 미리 듣기 문장 sample은 "오늘 알려 드릴 생활 꿀팁…"이고 category는 "22"다. production에는 "건축·과학 해설 채널 느낌"이 들어 있다 — [channels/ko-40sec-facts/channel.toml:2-4](channels/ko-40sec-facts/channel.toml), [channels/ko-40sec-facts/channel.toml:19](channels/ko-40sec-facts/channel.toml), [channels/ko-40sec-facts/channel.toml:43](channels/ko-40sec-facts/channel.toml), [channels/ko-40sec-facts/channel.toml:57](channels/ko-40sec-facts/channel.toml)
- 키워드 순서: 넣은 키워드 → 채널 keywords(` | `로 OR 묶음) → LLM이 정한 검색어 — [src/shorts_printer/core/trends.py:162-172](src/shorts_printer/core/trends.py). 지금은 `keywords = []` — [channels/ko-40sec-facts/channel.toml:56](channels/ko-40sec-facts/channel.toml)
- 검색은 `regionCode` = `[trends] region`(KR), 짧은 영상만 한다 — [src/shorts_printer/core/trends.py:186](src/shorts_printer/core/trends.py)
- 아이디어 모드는 ideas.md가 있으면 그 본문을, 없으면 빈 값을 넣는다 — [src/shorts_printer/core/trends.py:448-453](src/shorts_printer/core/trends.py)
- 지금 ideas.md 예시는 손가락 꺾는 소리·쭈글쭈글 손가락(몸)과 볼펜 뚜껑·단풍·바코드(생활)가 섞여 있다 — [channels/ko-40sec-facts/ideas.md:5-11](channels/ko-40sec-facts/ideas.md)
- 지금 trends.md는 난방비·결로·전기요금·빨래·이사철 같은 생활 절약 계절 주제를 앞세운다 — [channels/ko-40sec-facts/trends.md:3-5](channels/ko-40sec-facts/trends.md)
- 비교: ja 채널은 keywords 12개, `open = true`, `languages = ["ko","ja"]`, 그리고 ideas.md에서 "언론 기사 검색 → 어려워하는 것"을 먼저 보게 정했다 — [channels/ja-korea-trip/channel.toml:59-68](channels/ja-korea-trip/channel.toml), [channels/ja-korea-trip/ideas.md](channels/ja-korea-trip/ideas.md)

### Inferences (제안 값)
- `concept = "누구나 매일 겪는 몸 현상이 왜 일어나는지, 몸속 원리로 풀어 주는 인체 상식"`. "도움이 되는"을 빼서 처방으로 기울지 않게 한다.
- `name`·`description`: 이름은 운영자가 정한다. 설명 예: "하품은 왜 옮고, 추우면 왜 이가 딱딱 부딪칠까? 누구나 겪지만 이유는 몰랐던 몸의 일을 공식 자료로 2분 안에 풀어 드려요. 진단이나 치료 조언이 아니라 원리 설명입니다. 영상에 쓴 자료는 설명란에 적어 둡니다."
- `[publish] footer`를 쓴다(지금 비어 있음): "※ 의학적 진단·치료 조언이 아닌 일반 정보입니다. 영상은 AI로 만든 이미지입니다." footer는 코드가 설명 맨 끝에 꼭 붙이고 넘치면 출처 URL부터 줄인다 — [src/shorts_printer/core/pipeline.py:258-274](src/shorts_printer/core/pipeline.py), [src/shorts_printer/core/channel.py:70](src/shorts_printer/core/channel.py)
- `category`: 27(Education)로 바꾸는 것을 검토한다. 키 설명에 22·27 뜻이 있다 — [.claude/rules/channels.md:50](.claude/rules/channels.md)
- `[tts] sample`: "안녕하세요. 오늘은 우리 몸이 왜 이렇게 움직이는지 알려 드릴게요." 생활 꿀팁 문구를 뺀다.
- `[trends] keywords` 예: "인체의 신비", "몸의 비밀", "인체 상식", "신체 반응", "왜 그럴까 몸", "생리 현상". 실제 쇼츠 검색어로 맞는지는 웹 확인이 필요하다.
- `[trends] production`: "건축·과학 해설 채널 느낌"을 "몸속 단면·장기·세포를 보여 주는 3D 해설 애니메이션"으로 바꾼다. 그리고 "치료·약·식품 효능을 말해야 답이 되는 주제, 공식·학술 자료로 원리를 확인할 수 없는 주제는 못 만든다"를 더한다.
- `[trends] weights`: safe가 몸 주제에서 깎이는 문제는 5번 질문의 지시문 수정이 먼저다. 가중치만으로는 풀리지 않는다.
- trends.md 교체 요지: 계절 몸 현상(겨울 입김·정전기·튼 입술, 여름 땀·모기 물림, 환절기 재채기)을 우선한다. 질병관리청·국가건강정보포털·학술 자료로 원리를 확인할 수 있는 것만 고른다. 다이어트·영양제·질병 예방법 주제는 고르지 않는다.
- ideas.md 교체 요지: "누구나 몸으로 겪어 봤지만 이유를 모르는 현상"을 기준으로 한다. 예: 하품 전염, 손가락 꺾는 소리, 물에 불은 손가락, 아이스크림 두통, 다리 저림, 딸꾹질, 소름, 배꼽시계. 증상 = 질병 신호인 주제(가슴 통증, 혈변 등)는 고르지 않는다.

### Gaps
- 몸 쇼츠 검색어의 실제 인기도와 경쟁은 웹이나 YouTube 데이터가 있어야 안다(코드 범위 밖).

## 7. 영상 화풍(video_style.md, [video] style)과 Flow 쪽 콘텐츠 필터

### Takeaway
지금 화풍(둥근 3D, 글자 없음, 단면도·코랄 화살표)은 몸 해설에도 잘 맞는다. 다만 장기·세포·혈관을 그리는 규칙이 없다. 피와 노출을 피하는 규칙도 썸네일 글에만 있다. Flow가 프롬프트를 거절할 때 따로 처리하는 코드는 없다. 실패는 그저 생성 실패로 잡혀, 5분 뒤 한 번 다시 하고(크레딧이 또 든다) 그다음은 사람이 직접 올리게 남긴다.

### Cited Findings
- `[video] style`: "Stylized 3D animated explainer. Smooth matte materials, simple rounded shapes, one clear subject large in frame, limited palette of deep teal, cream, coral and mustard yellow… no readable text anywhere…" — [channels/ko-40sec-facts/channel.toml:30](channels/ko-40sec-facts/channel.toml). 이 머리말은 코드가 모든 장면 프롬프트 앞에 붙인다 — [src/shorts_printer/core/script.py:205-208](src/shorts_printer/core/script.py)
- video_style.md: 마스코트 Dot, 단면도(cutaway)·glowing coral 화살표, 글자가 들어가는 물건 금지, 카메라 4종, 한국 생활 물건 풀이(온돌·김치냉장고·교통카드·김밥) — [channels/ko-40sec-facts/video_style.md:3-14](channels/ko-40sec-facts/video_style.md)
- 공통 지시문의 장면 규칙: "사람이 필요 없는 단면도 장면에는 마스코트를 넣지 않는다", 실존 인물 얼굴 금지, "No on-screen text, no numbers, no logos." — [prompts/script.md:39-49](prompts/script.md)
- Flow 자동: 실패하면 예외 종류를 로그에 남기고 `RETRY_AFTER = 300`초 뒤 한 번만 다시 한다. 다시 실패하면 "직접 올려 주세요"로 남긴다. 생성 대기는 `GEN_TIMEOUT = 360`초다. 거절 메시지를 읽거나 프롬프트를 고쳐 다시 보내는 코드는 없다 — [src/shorts_printer/adapters/flow_auto.py:12-13](src/shorts_printer/adapters/flow_auto.py), [src/shorts_printer/adapters/flow_auto.py:38-58](src/shorts_printer/adapters/flow_auto.py), [src/shorts_printer/adapters/flow_auto.py:90-110](src/shorts_printer/adapters/flow_auto.py)
- 지금까지 shorts.db 로그에 "못 만듦"(Flow 실패)은 0건이다 — [shorts.db](shorts.db) (`select count(*) from logs where line like '%못 만듦%'`)
- 사람 손으로 클립을 올리는 경로는 step_footage의 Wait로 열려 있다 — [src/shorts_printer/core/pipeline.py:163-165](src/shorts_printer/core/pipeline.py)

### Inferences (제안)
- `[video] style`은 거의 그대로 쓴다. 해부 장면용으로 한 구절을 더한다: "…anatomy shown as clean stylized cutaways with soft translucent skin, organs and cells as smooth toy-like shapes, no blood, no gore, no realistic wounds…"
- video_style.md에 더할 규칙: (1) 몸속은 반투명 피부 너머 단면도로 보여 준다. 장기·뼈·근육·신경은 색으로 구분한 매끈한 모양으로 그린다. (2) 세포·분자는 둥근 알갱이로 크게 키워 그린다. (3) 신경 신호와 혈류는 glowing coral 선 하나로 그린다(지금 규칙을 넓힌 것). (4) 피·상처·수술·바늘·알약·병원 장면은 쓰지 않는다. 피는 "red flowing particles inside a translucent vessel"로 쓴다. (5) 몸 전체는 마스코트 Dot을 반투명하게 써서 같은 인물로 잇는다. 노출이 아니게 옷을 입힌 채로 투시한다. 한국 생활 물건 풀이 목록(온돌 등)은 몸 채널에서 필요 없으니 줄인다.
- Flow 거절 위험: 몸·피부·장기 이미지는 생성기 안전 필터에 걸릴 수 있다는 것이 일반 상식이다. 이 저장소에는 그 근거가 없다(로그 0건). 걸리면 장면당 크레딧이 두 번 들고 사람이 올려야 한다. 막는 1차 수단은 위 (4)처럼 프롬프트에 피와 노출을 넣지 않게 하는 것이다.

### Gaps
- Flow(Veo 계열)가 해부 이미지를 거절하는 기준은 저장소에 자료가 없다. 실제 몇 장면을 만들어 봐야 한다.

## 8. 썸네일 규칙(thumbnail.md, prompts/thumbnail.md)

### Takeaway
공통 썸네일 지시문은 중립이다(채널 글 + 길이 한도). 채널 thumbnail.md의 예시와 꼴이 생활 상식(주유구·바나나)이라 바꾼다. "노출·피·혐오" 금지는 몸 채널에서 더 중요해지므로 그대로 둔다.

### Cited Findings
- 공통 지시문은 `${channel_rules}`, 언어, 길이 한도, "대본에 없는 숫자 금지"뿐이다 — [prompts/thumbnail.md:5-12](prompts/thumbnail.md), [src/shorts_printer/core/thumbnail.py:15-18](src/shorts_printer/core/thumbnail.py)
- 채널 규칙: 1~2줄, 강조 낱말 하나, 물음만 던진다. 예시는 "주유구 위치 / 내리지 않고 알 수 있다?", "바나나는 / 왜 휘어져 있을까?"다. 노출·몸매 강조, 혐오·폭력·피를 금지한다 — [channels/ko-40sec-facts/thumbnail.md:7-31](channels/ko-40sec-facts/thumbnail.md)
- 길이 한도는 줄당 12자, 전체 22자 — [channels/ko-40sec-facts/channel.toml:37-39](channels/ko-40sec-facts/channel.toml)
- 썸네일 배경은 첫 장면 클립의 0.5초 화면이다 — [channels/ko-40sec-facts/thumbnail.md:25](channels/ko-40sec-facts/thumbnail.md)

### Inferences
- 예시 교체: "하품은 / 왜 옮을까?", "추우면 이가 / 왜 딱딱 부딪칠까?". 강조 낱말은 몸 부위나 현상(하품, 이)으로 한다.
- 더할 금지: 증상 공포 꼴("이 증상 보이면 위험"), 병 이름 강조. 이유는 YouTube 오해 소지 메타데이터 규칙에 이미 기대고 있다(thumbnail.md:21).
- 첫 장면이 단면도라면 썸네일 배경도 몸 단면이 된다. "피·상처 없는 장면"이라는 video_style 규칙이 썸네일까지 지켜 준다.

### Gaps
- 없음.

## 9. 코드로만 할 수 있는 것(channel.toml이나 채널 글로는 표현할 수 없는 것)

### Takeaway
채널 글과 toml만으로 콘셉트, 말투, 고정 멘트, 화풍, 출처 사이트, 설명란 꼬리말은 모두 바꿀 수 있다. 막히는 곳은 네 곳이다. (1) 민감 판정 기준(script.py:29). (2) 주제 찾기 공통 지시문의 건강 회피(trend_idea.md:35, trend_pick.md:30). (3) 공통 지시문의 "생활에서 써먹을 것" 4단계. (4) 민감 배너 문구(job.html).

### Cited Findings
- 민감 판정 기준은 필드 설명에 박혀 있다 — [src/shorts_printer/core/script.py:29](src/shorts_printer/core/script.py)
- 건강 회피 공통 지시문 — [prompts/trend_idea.md:35](prompts/trend_idea.md), [prompts/trend_pick.md:30](prompts/trend_pick.md)
- 4단계 "생활에서 써먹을 것" — [prompts/trend_idea.md:27](prompts/trend_idea.md), [prompts/trend_pick.md:22](prompts/trend_pick.md), [prompts/research.md:24](prompts/research.md)
- 배너 문구 — [src/shorts_printer/web/templates/job.html:73-77](src/shorts_printer/web/templates/job.html)
- 공통 지시문(prompts/*.md)은 모든 채널에 걸리고, 채널마다 다른 규칙은 channels/<id>/*.md에 둔다는 규칙 — [.claude/rules/conventions.md](.claude/rules/conventions.md) ("LLM 지시문" 절), [.claude/rules/channels.md:24](.claude/rules/channels.md)
- 기준 문서로 걸어 둔 `docs/plan/multi-channel.md`는 지금 저장소에 없다. 커밋 6f4e221에서 docs/plan/*.md(multi-channel, schedule, storage)가 지워졌다. 그 직전 판에는 "민감 주제 확인(sensitive_gate)은 채널 값"이라는 말만 있고 건강 콘텐츠에 대한 다른 결정은 없다(`git show 6f4e221^:docs/plan/multi-channel.md`, 32·132줄) — [git 6f4e221](.)
- 프롬프트 테스트는 모든 지시문이 ko-40sec-facts로 채워지는지(`${` 남김 없음)만 본다. 새 `${…}` 자리를 더하면 render 호출부에 값을 넘겨야 통과한다 — [tests/test_prompts.py:16-26](tests/test_prompts.py)

### Inferences
- 가장 작은 변경 묶음: script.py:29 필드 설명 한 줄, trend_idea.md:35와 trend_pick.md:30 문구를 "진단·치료·효능 조언이 필요한 건강 주제"로 좁히기. 키 추가와 테스트 변경은 없다. 다만 ja 채널에도 걸리므로 운영자 동의가 필요하다.
- 채널별로 다르게 하려면 `[trends]`에 새 키(예: `avoid`)를 더하고 두 지시문에 `${avoid}` 자리를 만든다. channel.py, rules/channels.md 표, test_prompts.py 호출을 같이 고쳐야 한다(rules/channels.md:75의 절차).

### Gaps
- docs/plan이 지워진 이유는 커밋 메시지에 없다.

## 10. (짧게) 자막 크기·글꼴·TTS 속도: 지금 채널별로 되는 것

### Takeaway
채널별로 되는 것은 글꼴(`[style] font`), 자막 한 덩어리 글자 수(`subtitle_limit`), 배치(`layout`), 목소리 크기(`voice_lufs`)다. 자막 글자 크기는 84px로 코드에 박혀 있다. TTS 말 속도는 ElevenLabs·Typecast 요청에 넣는 자리가 없어 코드를 고쳐야 한다. 이번 전환에서 바꿀 필요는 없다.

### Cited Findings
- `StyleCfg`: font, accent, background, subtitle_limit, layout, voice_lufs, sfx_lufs — [src/shorts_printer/core/channel.py:49-58](src/shorts_printer/core/channel.py)
- 자막 스타일 `Style: Cap,{font},84,…`로 크기가 고정이다 — [src/shorts_printer/core/subtitles.py:15-22](src/shorts_printer/core/subtitles.py). 한국어 기본 한 줄은 16자다("84px에서 16자가 한 줄") — [src/shorts_printer/adapters/splitters/ko.py:85](src/shorts_printer/adapters/splitters/ko.py)
- ElevenLabs 요청 본문은 text, model_id, apply_text_normalization뿐이다(voice_settings·speed 없음) — [src/shorts_printer/adapters/elevenlabs.py:40-41](src/shorts_printer/adapters/elevenlabs.py). 모델은 환경 변수 ELEVENLABS_MODEL(기본 eleven_multilingual_v2)이다 — [src/shorts_printer/config.py:44](src/shorts_printer/config.py)
- 말 빠르기는 지금 목소리 선택과 문장 길이(`[script] sentence`, "초당 약 7.1자")로만 맞춘다 — [channels/ko-40sec-facts/channel.toml:12](channels/ko-40sec-facts/channel.toml)

### Inferences
- 자막 크기를 채널 값으로 만들려면 StyleCfg에 키를 하나 더하고 subtitles.header에 넘겨야 한다. splitter 기본 limit(84px 기준)도 같이 맞춰야 한다.

### Gaps
- ElevenLabs API의 speed 설정이 지금 모델에서 되는지는 웹 문서로 확인해야 한다(이번 조사 범위 밖).

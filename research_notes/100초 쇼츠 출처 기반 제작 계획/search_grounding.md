# 검색 → 출처 읽기 → 출처 있는 대본: 검색·인용 단계 설계 노트

조사일 2026-10-16. 대상: ko 상식 채널(건강·과학·생활 "왜"), ja 한국 여행 채널(서울 동네·결제·앱·가게·가격). 채널마다 하루 1편, 약 105초, 사람이 편당 30분 검토.

현재 코드 상태(조사 출발점):
- `adapters/claude.py`는 이미 `WEB_SEARCH = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}`를 `web=True`일 때 붙이고, 검색 1회를 `SEARCH_USD = 0.01`로 비용에 더한다. 응답은 `beta.messages.parse(output_format=schema)`(구조화 출력)로 받는다 — [src/shorts_printer/adapters/claude.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/adapters/claude.py)
- `web=True`를 쓰는 곳은 주제 찾기 세 군데(`core/trends.py` 170·492·516행)뿐이고, 대본 쓰기는 검색하지 않는다 — [src/shorts_printer/core/trends.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/core/trends.py)
- 코드의 모델 단가: `claude-opus-5-5` 입력 $4·출력 $20, `claude-sonnet-5-5` $2·$10(백만 토큰당). 기본 모델은 `CLAUDE_MODEL` 없으면 `claude-opus-5-5` — [adapters/claude.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/adapters/claude.py), [config.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/config.py)
- 런타임 의존성에 `anthropic`·`playwright`가 있고 `httpx`는 dev 그룹에만 있다(설치본 httpx 0.28.1은 anthropic SDK를 통해 들어와 있다) — [pyproject.toml](/Users/jkpark/my-toy/shorts-printer/pyproject.toml)

## 1. Anthropic 서버 도구(web search·web fetch)와 Citations

### Takeaway
web search는 검색 1,000회당 $10 + 토큰, web fetch는 추가 요금 없이 토큰만 든다. 둘 다 `allowed_domains`로 허용 목록을 강제할 수 있고, 인용(url·제목·인용문)이 응답에 붙는다. 다만 **Citations는 구조화 출력(`output_format`)과 같이 쓰면 400 오류**라서, 지금 어댑터처럼 `parse()` 한 번으로 "검색 + 인용 + JSON"을 다 받을 수는 없다. 조사 호출과 대본 호출을 나눠야 한다.

### Cited Findings
- 도구 버전: `web_search_20250305`(기본), `web_search_20260209`(dynamic filtering 추가), `web_search_20260318`(response inclusion 추가). 셋 다 현행이고 베타 헤더가 필요 없다 — [Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool), [Tool reference](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-reference)
- dynamic filtering은 Claude 4.6 이후 모델에서 되고, 검색 결과를 코드 실행으로 먼저 걸러 컨텍스트 토큰을 줄인다. 이렇게 돈 코드 실행은 토큰 외 추가 요금이 없다. `20260209` 이후 버전은 `allowed_callers` 기본값이 `["code_execution_20260120"]`이고, 직접 부르려면 `["direct"]`를 준다(지원 안 하는 모델은 이게 없으면 400) — [Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- 가격: "**$10 per 1,000 searches**, plus standard token costs for search-generated content". 검색 결과는 입력 토큰으로 센다. 결과 수와 관계없이 검색 1회 = 1 use, 오류 난 검색은 과금하지 않는다. Batches API도 같은 가격 — [Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- `max_uses`: 넘으면 `max_uses_exceeded` 오류 블록. 문서 기준 "Simple factual queries typically use 1–3 searches" — [Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- 도메인 필터: `allowed_domains`와 `blocked_domains` 중 하나만(둘 다 주면 400). 항목은 스킴 없는 도메인 + 선택적 경로(`example.com/blog`). 목록이 너무 길면 `request_too_large` 오류 — [Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- 지역화: `user_location` = `{type: "approximate", city, region, country(ISO 3166-1 alpha-2), timezone(IANA)}`, 지원 안 하는 국가 코드는 400 — [Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- 검색 결과 블록: `url`, `title`, `page_age`(사이트 마지막 갱신), `encrypted_content`(다음 턴에 그대로 돌려줘야 함). 인용 블록 `web_search_result_location`: `url`, `title`, `encrypted_index`, `cited_text`(최대 150자). 인용 필드는 토큰에 안 센다. 웹 검색 인용은 항상 켜져 있다 — [Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- 문서는 "API 출력을 사용자에게 보여 줄 때는 원 출처 인용을 포함해야 하고, 가공해 보여 주면 법무 검토에 따라 적절히 표시하라"고 적는다 — [Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- 긴 검색은 `stop_reason: "pause_turn"`으로 멈추며 받은 assistant 메시지를 그대로 다시 보내면 이어 간다(지금 어댑터가 이미 4회까지 반복 처리) — [Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool), [adapters/claude.py](/Users/jkpark/my-toy/shorts-printer/src/shorts_printer/adapters/claude.py)
- web fetch 버전: `web_fetch_20250910`(기본), `20260209`(dynamic filtering), `20260309`(+`use_cache: false` 캐시 우회), `20260318`(+response inclusion) — [Web fetch tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)
- web fetch 가격: "**no additional cost**", 가져온 내용만 토큰으로. 예시: 보통 웹 페이지(10 kB) 약 2,500토큰, 큰 문서 페이지(100 kB) 약 25,000토큰, 논문 PDF(500 kB) 약 125,000토큰. `max_content_tokens`로 자를 수 있다(텍스트에만, PDF엔 안 걸림) — [Web fetch tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)
- web fetch 제약: 대화에 이미 나온 URL만 가져온다(사용자 메시지, 클라이언트 도구 결과, 이전 검색·fetch 결과). 시스템 프롬프트에만 있는 URL은 안 된다. JavaScript로 그리는 페이지는 지원하지 않는다. 결과는 캐시될 수 있다. `url_not_allowed`에는 도메인 필터와 함께 "Anthropic-side restrictions, such as private addresses, `robots.txt`"가 포함된다. URL 길이 250자 제한. 지원 형식은 text·HTML·PDF뿐 — [Web fetch tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)
- web fetch 결과: `url`, `content`(document 블록), `retrieved_at`(가져온 시각). PDF는 base64 document로 와서 첨부 PDF처럼 처리된다. 인용은 기본 꺼짐, `"citations": {"enabled": true}`로 켜면 `char_location`(start/end 문자 위치 + `cited_text`) 인용이 붙는다 — [Web fetch tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)
- web search·fetch 모두 Claude API에서 쓸 수 있고, web fetch는 Bedrock·Google Cloud에 없다. 모델이 web search를 받는지는 Models API의 `capabilities.server_tools.web_search.supported`로 확인한다 — [Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool), [Web fetch tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)
- 공식 문서 예제가 모두 `claude-opus-5-5`로 web search·web fetch(`20260318` 포함)를 부른다 — [Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool), [Web fetch tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)
- Citations 기능: 모든 활성 모델 지원. document 블록(plain text·PDF·custom content)에 `"citations": {"enabled": true}`. plain text·PDF는 문장 단위로 잘려 `char_location`/`page_location`, custom content는 준 블록 그대로 `content_block_location`. 스캔 PDF(추출 가능한 글자 없음)는 인용 불가. `cited_text`는 출력·재입력 토큰에 안 센다 — [Citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- **"Citations and structured outputs are incompatible"**: document·`search_result` 블록에 인용을 켜고 `output_config.format`(또는 deprecated `output_format`)을 같이 주면 400 — [Citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- Anthropic의 웹 검색 공급자는 Brave Search(2025-03-19 하위 처리자 목록에 추가, 검색 결과가 Brave와 정확히 일치). 하위 처리자 목록에는 turbopuffer도 있다 — [TechCrunch 2025-03-21](https://techcrunch.com/2025/03/21/anthropic-appears-to-be-using-brave-to-power-web-searches-for-its-claude-chatbot/), [Simon Willison](https://simonwillison.net/2025/Mar/21/anthropic-used-brave), [xponent21](https://xponent21.com/insights/claude-web-search-brave-turbopuffer/)

### Inferences
- 한 편 비용 추정(코드 단가 기준, Opus 5.5): 검색 4~6회 = $0.04~0.06, 허용 목록 페이지 3~5개 fetch = 1~5만 입력 토큰 ≈ $0.04~0.20. 대본 호출과 검증 호출을 더해도 편당 $0.3 안팎, 두 채널 하루 2편이면 월 $15~25 정도로 예산(수십 달러) 안이다. dynamic filtering이나 `max_content_tokens: 8000` 정도로 상한을 두면 더 낮아진다.
- 지금 `parse(output_format=…)` + `web_search`가 돌고 있는 걸 보면 웹 검색 도구 자체는 구조화 출력과 같이 쓸 수 있다. 하지만 이때 JSON 안에 인용 블록이 어떻게 붙는지(또는 버려지는지)는 문서에 없다. 출처를 사람에게 보여 주려면 (a) 조사 호출은 구조화 출력 없이 돌려 `citations`를 코드가 직접 모으거나, (b) 구조화 출력 스키마에 `url`·`quote` 필드를 넣고 코드가 그 인용문이 실제 가져온 본문에 있는지 문자열로 확인하는 두 길이 있다. (a)가 Anthropic이 보장하는 근거라 더 믿을 만하다.
- 허용 목록은 `allowed_domains`로 서버에서 강제하는 게 프롬프트로 "공식 사이트만 보라"고 하는 것보다 확실하다. ko·ja 목록 각 15~25개면 `request_too_large` 걱정은 작다(정확한 한도는 문서에 없음).
- web fetch는 대화에 나온 URL만 가져오므로, 고정 출처(예: K-ETA 공지 URL)는 user 메시지에 URL을 넣어 줘야 한다. channel별 "늘 확인할 URL" 목록을 user 메시지에 붙이는 방식이 맞다.

### Gaps
- `claude-fable-5-1`의 web search·web fetch·dynamic filtering 지원 여부는 확인하지 못했다(문서는 "4.6 이후 모델"이라고만 적음). Models API의 `capabilities` 필드로 실제 확인해야 한다. `claude-sonnet-5-5`도 문서 예제엔 없으나 "4.6 이후"에 해당할 것으로 본다(추정).
- 모델 단가($4/$20, $2/$10)는 코드 값이다. 이번에 가격 페이지로 다시 확인하지 않았다.
- 구조화 출력 + web search 조합에서 인용이 어떻게 나오는지 공식 설명을 찾지 못했다.
- Brave 기반 검색의 한국어·일본어 품질을 잰 공개 벤치마크는 찾지 못했다. Brave 색인은 네이버 블로그·지식백과를 (robots로 막혀) 거의 못 본다는 점은 아래 4절 robots 결과로 추정할 수 있을 뿐이다.
- web fetch가 robots.txt를 볼 때 어떤 User-Agent 이름(`Claude-User` 등)으로 판단하는지 문서에 없다.

## 2. 대안 검색 API(2026 기준)

### Takeaway
이 규모(하루 검색 10~20회)에서는 별도 검색 API를 붙일 이유가 약하다. Anthropic web search($10/1k)는 이미 붙어 있고 허용 목록·인용·날짜(`page_age`)까지 준다. 대안 중 쓸 만한 건 **Naver 검색 API(무료, 하루 25,000회, 한국어 색인)** 하나이고, 그것도 스니펫만 주므로 "한국어 공식 페이지 URL 찾기용 색인"으로만 의미가 있다. Google CSE·Bing은 사실상 끝났다.

### Cited Findings
- **Brave Search API**: Search $5/1,000건, 매월 $5 무료 크레딧(≈1,000건), 결제 수단 등록 필요. 예전 Free(월 2,000건)·Base·Pro 요금제는 2026년 초 폐지 — [costbench](https://costbench.com/software/ai-search-apis/brave-search-api/), [apicostcalc](https://apicostcalc.com/brave-search.html)(2차 출처). 파라미터 `country`, `search_lang`(ISO 639-1), `freshness`(pd/pw/pm/py/기간), `count` 최대 20, `extra_snippets`(결과당 추가 발췌 최대 5개), Goggles(재순위). 본문 전체가 아니라 발췌만 준다 — [Brave API docs](https://api-dashboard.search.brave.com/app/documentation/web-search/query)
- **Tavily**: 무료 월 1,000 크레딧(카드 불필요), 종량제 $0.008/크레딧, Project 요금제 $30/월 4,000 크레딧. 요청 종류(search·extract·crawl)마다 크레딧이 다르다 — [Tavily pricing](https://www.tavily.com/pricing)
- **Exa**: 무료 월 $10 크레딧. Search instant $4/1k, fast/auto $7/1k, Deep $12~15/1k, Contents(본문) $1/1k 페이지, Answer $5/1k. 10개 넘는 결과 $1/1k — [Exa pricing](https://exa.ai/pricing)
- **Perplexity**: Search API(원 검색 결과) standard $5/1k, fast $1/1k(토큰 요금 없음). Sonar 입력·출력 $1/$1 per 1M + 요청 수수료 $5~14/1k(검색 컨텍스트 크기별), Sonar Pro $3/$15. `search_domain_filter`·`search_recency_filter`·언어 필터 지원 — [Perplexity pricing](https://docs.perplexity.ai/getting-started/pricing)
- **Google Programmable Search(Custom Search JSON API)**: 2025년 신규 고객 접수 중단, 2027-01-01 종료 예정. 후속으로 권하는 Vertex AI Search는 공개 웹 결과를 주지 않는 다른 제품 — [Brave 정리글](https://brave.com/learn/google-api-shutdown/), [DEV](https://dev.to/booyaka101/google-kills-the-custom-search-json-api-on-2027-01-01-here-is-a-self-hosted-drop-in-3nk0)(공급자·2차 출처)
- **Bing Search API**: 2025-08-11 종료, Azure AI Agents의 "Grounding with Bing"으로 이전 권고 — [Microsoft Learn](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement), [The Register](https://www.theregister.com/2025/05/15/bing_search_apis_retired/)
- **Naver 검색 API**: 하루 25,000회, 무료(앱 등록·Client ID/Secret). 뉴스·블로그·지역·지식iN·책·카페·백과사전·이미지·전문자료·웹문서 — [socialcrawl](https://www.socialcrawl.dev/ko/blog/naver-crawling), [naver-encyc-mcp API 참조](https://glama.ai/mcp/servers/@cola314/naver-encyc-mcp/blob/4e3e453d86479ec87802d75051cc7cf136475855/docs/api-reference.md)(2차 출처, developers.naver.com은 이 환경에서 가져오지 못함). 별도로 NAVER Cloud의 API HUB는 "한시적 무료, 유료 전환 시 공지" — [NAVER Cloud 가이드](https://guide.ncloud-docs.com/docs/apihub-overview)
- **Yahoo! JAPAN 검색 API**: 웹 검색 API 등 6종을 2013년 3월쯤 중단한다고 2012-12-03 발표(오래된 정보, 그 뒤 재개 소식은 찾지 못함) — [@IT 2012-12-03](https://atmarkit.itmedia.co.jp/ait/spv/1212/03/news111.html)

### Inferences
- 비교(검색 1,000회 기준): Perplexity Search fast $1 < Exa instant $4 < Brave $5 = Perplexity standard $5 < Tavily $8 < Anthropic $10. 하지만 우리 사용량(월 300~600회)이면 차이가 월 $3~5라서 의미가 없고, 외부 API를 붙이면 결과를 Claude에 넣는 코드·키·어댑터가 늘어난다. Anthropic web search 유지가 가장 싸게 끝난다(코드 0줄 추가).
- Anthropic 검색이 Brave 기반이므로 Brave API를 따로 붙여도 색인 품질은 거의 같다고 본다(추정).
- 일본어 쪽은 Google·Yahoo Japan 공식 API가 없다. 일본어 질의는 Anthropic web search에 `user_location.country = "JP"`를 주거나, 아예 허용 목록 도메인 안에서만 찾게 하는 게 현실적이다.
- Naver API는 백과사전·웹문서에서 정부·기관 페이지 URL을 찾는 색인으로 쓸 수 있다. 하지만 응답은 제목·링크·요약 스니펫이고 지식백과 본문은 robots로 막혀 fetch할 수 없으니(4절), 본문 근거로 쓰지 않는다. 처음엔 붙이지 않고, ko 검색에서 공식 출처를 자주 못 찾을 때 더한다.

### Gaps
- SerpAPI 2026 가격·무료량은 확인하지 못했다.
- Naver 검색 API 이용약관의 "자동 수집·AI 학습·재배포" 조항 원문을 확인하지 못했다(developers.naver.com fetch 실패).
- Tavily 검색 1회당 크레딧 수(basic/advanced), include_domains·본문(raw_content) 지원, 각 서비스의 한국어·일본어 색인 품질은 공식 자료에서 확인하지 못했다.

## 3. 페이지 가져오기·정리(새 무거운 의존성 없이)

### Takeaway
가장 적게 짜는 길은 **Anthropic web fetch에 맡기는 것**이다. HTML 정리·PDF 텍스트 추출·robots 준수를 서버가 하고, `retrieved_at`과 인용 위치까지 준다. 직접 가져와야 할 때(JS 렌더링 페이지, 출처 문구 문자열 검증)는 stdlib `urllib.request` + `html.parser` + `urllib.robotparser`로 충분하고, JS 페이지는 이미 있는 `playwright`로 처리한다. 새 의존성은 필요 없다.

### Cited Findings
- web fetch는 HTML·text·PDF를 받고, PDF는 첨부 PDF처럼 처리(인용 가능), JS로 그리는 페이지는 못 가져온다. JS가 필요하면 browser use 도구(클라이언트 도구)를 쓰라고 권한다 — [Web fetch tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)
- robots.txt에 막힌 URL은 web fetch가 `url_not_allowed`로 거절한다 — [Web fetch tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)
- 스캔 PDF는 글자 추출이 안 돼 인용할 수 없다 — [Citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- 직접 확인(2026-10-16, curl + 정규식 태그 제거): `e-arrivalcard.go.kr` 첫 화면은 보이는 글자가 사실상 0(JS 앱), `k-eta.go.kr` 신청 화면은 약 2,000자, `encykorea.aks.ac.kr/Article/E0011383`은 약 4,500자(메뉴 포함), `japanese.visitseoul.net` 첫 화면 약 8,400자, `www.kr.emb-japan.go.jp`(주한 일본대사관)는 "Access Denied"(403, Akamai). `britannica.com`·`smithsonianmag.com`은 일반 curl에 403 — 이 노트 작성 중 직접 측정
- 런타임 의존성에 이미 `playwright>=1.64.0`이 있다 — [pyproject.toml](/Users/jkpark/my-toy/shorts-printer/pyproject.toml)

### Inferences
- 기본: Claude 호출에 `web_fetch`(`max_uses` 5, `max_content_tokens` 8000~10000, `citations.enabled`, 채널 `allowed_domains`)를 붙인다. 코드에서 HTML 파서를 짤 필요가 없다.
- 직접 가져오기가 필요한 경우만 stdlib로: `urllib.robotparser.RobotFileParser`로 robots 확인 → `urllib.request`(User-Agent에 프로젝트 이름) → `html.parser.HTMLParser`로 `script/style/nav/header/footer` 버리고 `<main>`·`<article>` 안 글자만 모은다. readability 수준 품질은 필요 없다(공식 사이트는 구조가 단순하고, 모델이 메뉴 잡음을 무시한다).
- JS 페이지(e-Arrival Card, 일부 앱 안내)는 `playwright`로 텍스트를 뽑아 **custom content document**(인용 켬)로 Claude에 넣는다. 이건 `adapters/` 쪽 일이고 core는 "출처 문서 목록"만 받는다(architecture 규칙).
- 정부 PDF: web fetch가 텍스트 PDF를 처리하므로 별도 PDF 라이브러리가 필요 없다. 스캔 PDF는 인용 불가이므로 출처에서 뺀다.
- 403을 주는 곳(일본대사관, Britannica, Smithsonian)은 Anthropic 서버에서도 막힐 수 있어 허용 목록 1순위로 두지 않는다(서버 쪽 결과는 미확인).

### Gaps
- Anthropic fetch가 Britannica·Smithsonian·주한 일본대사관 페이지를 실제로 가져오는지는 시험하지 못했다(API 키를 쓰는 실호출은 이번 범위 밖).
- web fetch 캐시 기간은 문서에 "자동 관리"라고만 있다.

## 4. 채널별 믿을 만한 출처 허용 목록

### Takeaway
목록에 넣으려던 사이트는 대부분 살아 있고 일반 HTML로 읽힌다. 핵심 예외는 셋이다. **네이버 지식백과(terms.naver.com)는 robots가 모든 봇을 막고 ClaudeBot·Claude-SearchBot을 이름으로 막는다.** 네이버 블로그도 ClaudeBot을 막는다. **e-Arrival Card 공식 사이트는 JS 앱이라 fetch로 내용이 안 나온다.** 그리고 **주한 일본대사관은 봇에 403**을 준다.

### Cited Findings
(2026-10-16 직접 확인: `https://<도메인>/`의 HTTP 상태와 robots.txt 요지. 따로 적지 않은 링크는 이 노트 작성 중 측정한 값이다.)

ko 상식 채널
- 질병관리청 [www.kdca.go.kr](https://www.kdca.go.kr/) 200, robots는 `/search.do`만 막음. 국가건강정보포털 [health.kdca.go.kr](https://health.kdca.go.kr/) 200, robots 없음
- 식품의약품안전처 [www.mfds.go.kr](https://www.mfds.go.kr/) 200, `User-agent: * Allow: /`
- 국립국어원 [www.korean.go.kr](https://www.korean.go.kr/) 200, 검색·게시판·`/kornorms/search/`만 막음
- 한국민족문화대백과사전 [encykorea.aks.ac.kr](https://encykorea.aks.ac.kr/) 200, `*`에는 검색 경로만 막고 Bingbot 등 일부 봇은 전체 차단. 항목 URL은 `/Article/E0011383` 꼴
- 국가유산청 [www.khs.go.kr](https://www.khs.go.kr/) 200, 검색·일부 게시판만 막음
- KISTI 과학향기 [scent.kisti.re.kr](https://scent.kisti.re.kr/) 200(`/site/main/home`), Googlebot에 `?sv=` 쿼리만 막음
- 한국천문연구원 [www.kasi.re.kr](https://www.kasi.re.kr/) 200, robots 없음
- 기상청 [www.weather.go.kr](https://www.weather.go.kr/) 200, `Allow: /`(검색 등 일부 제외)
- 통계청 `kostat.go.kr` → **`mods.go.kr`로 이동**(200, 검색 경로만 막음). 허용 목록엔 두 도메인을 다 넣어야 한다
- 네이버 지식백과 [terms.naver.com](https://terms.naver.com/) 200이지만 robots: `ClaudeBot`·`Claude-SearchBot`·`GPTBot`·`OAI-SearchBot`·`PerplexityBot` 등 `Disallow: /`, 그리고 `User-agent: * Allow: /$ Disallow: /` → 첫 화면 말고 전부 금지
- PubMed [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/) 200, `/api`·`/rss` 등만 막음
- NASA [www.nasa.gov](https://www.nasa.gov/) 200 `Allow: /`. NOAA [www.noaa.gov](https://www.noaa.gov/) 200. WHO [www.who.int](https://www.who.int/) 200(특정 스파이더만 차단)
- Britannica [www.britannica.com](https://www.britannica.com/) · Smithsonian [www.smithsonianmag.com](https://www.smithsonianmag.com/): 일반 curl에 **403**(robots 자체는 검색 경로만 막음)

ja 여행 채널
- 한국관광공사 일본어 [japanese.visitkorea.or.kr](https://japanese.visitkorea.or.kr/) 200(`/svc/main/index.do`), 통합검색만 막음
- VISIT SEOUL 일본어 [japanese.visitseoul.net](https://japanese.visitseoul.net/) 200, member·admin·search만 막음, 정적 HTML에 본문이 있다(첫 화면 약 8,400자)
- 법무부 출입국·외국인정책본부 [www.immigration.go.kr](https://www.immigration.go.kr/) 200, Googlebot에 일부 API·게시판만 막음. 하이코리아 [www.hikorea.go.kr](https://www.hikorea.go.kr/) 200
- K-ETA [www.k-eta.go.kr](https://www.k-eta.go.kr/) 200, Googlebot에 게시판 목록 등만 막음. 첫 화면 정적 글자 약 2,000자
- e-Arrival Card [www.e-arrivalcard.go.kr](https://www.e-arrivalcard.go.kr/) 200, robots는 게시판만 막지만 **정적 HTML에 본문이 없다(JS 렌더링)**
- 인천공항공사 [www.airport.kr](https://www.airport.kr/) 200, robots: `Disallow: /` 후 `/ap_ko/`·`/ap_en/`·`/ap_ch/`만 허용 → 일본어 경로는 허용 목록에 없다(robots 기준 금지)
- 서울교통공사 [www.seoulmetro.co.kr](https://www.seoulmetro.co.kr/) 200, 개인·임대 등 일부 경로만 막음
- 네이버 블로그(NAVER Map 공식 블로그 포함) [blog.naver.com](https://blog.naver.com/) 200이지만 robots에서 `ClaudeBot`·`Claude-SearchBot`·`GPTBot`·`Yeti`(네이버 자체 봇 일부 규칙) `Disallow: /`. `*`에는 `PostList.nhn` 등 일부만 막음
- Olive Young Global [global.oliveyoung.com](https://global.oliveyoung.com/) 200, robots 없음(첫 화면 약 21,000자, 상품 위주)
- WOWPASS [www.wowpass.io](https://www.wowpass.io/) 200, `Allow: /`
- 외교부 해외안전여행 [www.0404.go.kr](https://www.0404.go.kr/) 200. 日本外務省 海外安全ホームページ [www.anzen.mofa.go.jp](https://www.anzen.mofa.go.jp/) 200, robots 없음. JNTO [www.jnto.go.jp](https://www.jnto.go.jp/) 200
- 在大韓民国日本国大使館 [www.kr.emb-japan.go.jp](https://www.kr.emb-japan.go.jp/) **403**(`/itprtop_ja/index.html`도 "Access Denied")

사실 확인 메모(주제 후보에 바로 걸리는 것)
- K-ETA 한시 면제(일본 포함 22개국)는 2026-01-01~**2026-12-31**까지 연장. K-ETA 면제 대상도 입국 전 e-Arrival Card를 내야 하며 도착 3일 전부터 낼 수 있다 — [EY tax alert PDF](https://www.ey.com/content/dam/ey-unified-site/ey-com/en-gl/technical/tax-alerts/documents/korea-extends-temporary-electronic-travel-authorization-exemption-until-31-december-2026.pdf), [iVisa](https://www.ivisa.com/ko/news/south-korea-k-eta-exemption-extended-2026)(둘 다 2차 출처, 법무부 원문 미확인)

### Inferences
- 허용 목록은 `channels/<id>/channel.toml`에 둔다(채널 규칙: 채널 차이는 코드가 아니라 channel.toml). 예: `[sources] allowed = [...]`. 1단계는 공공기관·백과, 2단계는 국제기관·과학 매체, Wikipedia는 "검색 색인"으로만(사실 근거로 쓰지 않음)으로 두고, `allowed_domains`에는 1·2단계만 넣는다.
- ko 1단계 후보: `kdca.go.kr`(health 하위 도메인 포함 여부는 서버 규칙 확인 필요), `mfds.go.kr`, `korean.go.kr`, `encykorea.aks.ac.kr`, `khs.go.kr`, `scent.kisti.re.kr`, `kasi.re.kr`, `weather.go.kr`, `kma.go.kr`, `mods.go.kr`·`kostat.go.kr`, `nih.gov`(PubMed), `nasa.gov`, `noaa.gov`, `who.int`. Britannica·Smithsonian은 2단계(가져오기 실패 가능).
- 두산백과/네이버 지식백과는 robots로 막혀 web fetch가 거절할 것이므로 목록에서 뺀다. 같은 역할은 한국민족문화대백과사전(한국사·문화)과 국가건강정보포털(건강)이 맡는다.
- ja 1단계 후보: `japanese.visitkorea.or.kr`, `japanese.visitseoul.net`, `k-eta.go.kr`, `immigration.go.kr`, `hikorea.go.kr`, `seoulmetro.co.kr`, `0404.go.kr`, `anzen.mofa.go.jp`, `wowpass.io`, `global.oliveyoung.com`. 인천공항은 robots상 `/ap_ko/`·`/ap_en/`만 되므로 경로를 붙여 `airport.kr/ap_ko` 꼴로 넣는다. e-Arrival Card는 playwright로 따로 뽑거나, K-ETA·법무부 공지 페이지로 대신한다.
- NAVER Map 공식 블로그는 blog.naver.com이 ClaudeBot을 막으므로 web fetch로는 못 읽는다. 앱 변경(NAVER Map 일본어 지원 등)은 앱스토어 설명이나 회사 보도자료로 대신 확인해야 한다(이 대체 출처는 확인 안 함).
- 가격(올리브영 상품가, 교통비)은 자주 바뀌고 정적 HTML에 없을 수 있다. 대본에는 "약 ○○원(2026년 10월 확인)"처럼 날짜를 붙이고, 가격 하나만으로 주제를 세우지 않는다.

### Gaps
- 각 사이트의 RSS·공개 API 유무(예: 공공데이터포털의 기관별 API, KASI 천문 API)는 이번에 확인하지 못했다.
- VISIT SEOUL·visitkorea 일본어판 개별 기사의 게시일 표시 방식(HTML 안 날짜 위치)은 확인하지 못했다.
- NAVER Map·WOWPASS 공지의 공식 일본어 페이지 URL은 찾지 못했다.

## 5. 단계 구조: 질의 → 출처 순위 → 사실 시트 → 사실 시트에 묶인 대본 → 근거 검사

### Takeaway
호출을 셋으로 나눈다. ① **조사 호출**(web_search + web_fetch, 허용 목록, 인용 켬, 구조화 출력 없음) → 코드가 인용 블록을 모아 **사실 시트**(사실·URL·인용문·날짜)를 만든다. ② **대본 호출**(지금처럼 구조화 출력) — 사실 시트만 넣고 문장마다 `fact_ids`를 달게 한다. ③ **근거 검사** — 먼저 코드로 `fact_ids` 없는 문장을 잡고, 그다음 검사 호출이 문장마다 근거 인용문을 찾게 해 못 찾은 문장을 표시한다. 사람 검토 화면에는 문장 옆에 출처 링크와 인용문을 붙인다.

### Cited Findings
- Anthropic의 환각 줄이기 기본 전략: "모른다"고 말하게 허용, 긴 문서(>20k 토큰)는 먼저 원문 그대로 인용문을 뽑게 한 뒤 그 인용만으로 작업, "각 주장마다 인용과 출처를 달게 하고, 생성 뒤 각 주장에 맞는 인용문을 찾게 해 못 찾으면 그 주장을 지운다". 예시 지시: "After drafting, review each claim … find a direct quote from the documents that supports it. If you can't find a supporting quote for a claim, remove that claim … and mark where it was removed with empty [] brackets." — [Reduce hallucinations](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations)
- 고급 기법: "External knowledge restriction: Explicitly instruct Claude to only use information from provided documents and not its general knowledge", best-of-N 비교, 반복 검증. "these techniques significantly reduce hallucinations, they don't eliminate them" — [Reduce hallucinations](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations)
- Citations: RAG 조각마다 문장 단위 인용을 원하면 조각마다 plain text document로, 더 자르고 싶지 않으면 custom content document로 넣으라고 권한다. 인용은 인용문을 프롬프트로 뽑게 하는 것보다 출력 토큰이 싸다(`cited_text` 비과금) — [Citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- 서버 도구와 클라이언트 도구를 한 턴에 섞으면 `stop_reason: "tool_use"`로 서버 도구 실행이 미뤄진다 — [Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- 지시문은 코드가 아니라 `prompts/<이름>.md`, 채널별 규칙은 `channels/<id>/*.md`에 둔다 — [.claude/rules/conventions.md](/Users/jkpark/my-toy/shorts-printer/.claude/rules/conventions.md)

### Inferences
권장 설계(최소 변경):
1. **질의 만들기**는 따로 호출하지 않는다. 조사 호출의 user 메시지에 "주제, 확인할 핵심 질문 2~4개, 검색어 언어(ko: 한국어+영어 / ja: 일본어+한국어)"를 적고 `max_uses` 4~6으로 맡긴다. 주제 단계(`trend_pick`)가 이미 핵심 사실 문장을 내므로 그 문장을 "확인할 주장"으로 넘긴다.
2. **조사 호출**(새 지시문 `prompts/research.md`): tools = `web_search_20260209`(`allowed_domains` = 채널 1·2단계, `user_location.country` = ko는 `KR`, ja는 `KR`(한국 공식 사이트가 목표라서) — 일본 블로그 반응을 보는 건 주제 단계 일이다) + `web_fetch_20260309`(`citations.enabled`, `max_content_tokens` 8000, 같은 `allowed_domains`, 여행 채널은 `use_cache: false`). 구조화 출력은 쓰지 않는다. 지시: "출처에 있는 것만, 사실 하나당 한 문장, 날짜·수치는 출처 표현 그대로, 출처에서 확인 못 한 주장은 '확인 못 함'으로 적는다."
3. **사실 시트는 코드가 만든다**: 응답 text 블록의 `citations`(`web_search_result_location`의 url·title·cited_text, `char_location`의 cited_text와 `web_fetch_result`의 url·`retrieved_at`)을 모아 `[{id, fact, url, title, quote, retrieved_at, page_age}]`로 저장소(`Record.put`)에 넣는다. 인용 없는 text 블록은 사실로 치지 않는다. 이러면 "출처 없는 사실"이 구조상 시트에 들어갈 수 없다.
4. **대본 호출**: 지금 대본 지시문에 `${facts}`(id·사실·날짜만, URL은 빼서 토큰 절약)를 넣고, 출력 스키마의 문장마다 `fact_ids: list[str]`를 더한다. 지시: "사실 시트에 없는 수치·고유명사·인과 주장을 쓰지 않는다. 연결·질문·감탄 문장은 `fact_ids`를 비워도 된다." 훅·전환 문장은 사실이 아니므로 비워 둘 수 있게 해야 대본이 딱딱해지지 않는다.
5. **근거 검사**: (a) 코드 — 숫자·연도·%·원/円이 들어간 문장인데 `fact_ids`가 비었거나 없는 id를 가리키면 경고. (b) LLM 검사 호출(작은 모델로 충분, 예: sonnet) — 사실 시트를 custom content document로 넣고(인용 켬, 구조화 출력 없음) "문장마다 근거 인용을 찾고, 없으면 [근거 없음]"으로 표시. (b)는 sensitive_gate 대상(건강) 대본에만 돌려도 된다.
6. **검토 화면(job.html)**: 문장 옆에 출처 번호, 누르면 인용문(최대 150자)·URL·확인 날짜. 사람이 30분 안에 보려면 "근거 없음" 문장과 날짜가 오래된 사실만 위로 올려 보여 주면 된다.
7. 포트 변경: `LLM.ask`는 구조화 출력 전용이므로, 조사용으로 `research(system, text, *, domains, fetch_urls) -> (list[Source], usage)` 같은 메서드 하나를 `ports/llm.py`에 더하는 게 가장 작다. 인용 블록 파싱은 Claude 고유라 adapter 안에 둔다.

비용(편당, Opus 5.5 단가 가정): 조사 ≈ 검색 5회 $0.05 + 입력 3만 토큰 $0.12 + 출력 2천 토큰 $0.04 ≈ $0.21. 대본 호출은 지금과 비슷하고, 검사 호출(sonnet)은 ≈ $0.03. 두 채널 월 60편이면 조사·검사 추가분이 월 약 $15이다.

### Gaps
- 사실 시트 방식이 실제로 대본의 재미(훅·반전)를 얼마나 깎는지는 시험 자료가 없다. 파일럿으로 같은 주제를 시트 有/無로 만들어 비교해야 한다.
- 인용 블록과 `web_fetch_tool_result`를 잇는 방식(`char_location.document_index`가 fetch 결과의 몇 번째 문서를 가리키는지)은 web fetch 문서 예시에 하나뿐이라, 여러 페이지를 가져올 때의 색인 규칙은 실호출로 확인해야 한다.

## 6. 신선도: 날짜를 들고 다니기

### Takeaway
도구가 날짜 두 개를 준다. web search 결과의 `page_age`(사이트 마지막 갱신)와 web fetch의 `retrieved_at`(가져온 시각)이다. 게시일은 주지 않으므로 페이지 본문에서 뽑아야 한다. 여행 채널은 사실마다 `as_of`를 필수로 두고, 설명란에 "情報は2026年10月時点" + 출처 링크를 자동으로 붙인다. **K-ETA 일본 면제는 2026-12-31에 끝나니 지금(10월) 만드는 K-ETA 편은 날짜 문구가 꼭 있어야 한다.**

### Cited Findings
- web search 결과 `page_age`: "When the site was last updated" — [Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- web fetch 결과 `retrieved_at`: "Timestamp when the content was retrieved". 결과가 캐시될 수 있어 최신이 아닐 수 있고, `use_cache: false`(20260309 이후)로 우회한다 — [Web fetch tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool)
- K-ETA 한시 면제 기간 2026-01-01~2026-12-31(일본 포함 22개국) — [EY](https://www.ey.com/content/dam/ey-unified-site/ey-com/en-gl/technical/tax-alerts/documents/korea-extends-temporary-electronic-travel-authorization-exemption-until-31-december-2026.pdf), [eiglaw](https://eiglaw.com/south-korea-extends-k‑eta-exemption-for-22-countries-through-2026/)
- `channel.toml`의 `[publish] footer`가 설명 맨 끝에 빈 줄 하나 두고 붙는다(지금 ja는 AI 표시 문구) — [.claude/rules/channels.md](/Users/jkpark/my-toy/shorts-printer/.claude/rules/channels.md)

### Inferences
- 사실 시트 필드: `retrieved_at`(도구 값), `page_age`(검색 결과에 있으면), `published`(조사 호출이 본문에서 "게시일·수정일·기준일"을 찾아 적게 함, 없으면 빈칸). 여행 사실 중 `published`·`page_age` 둘 다 없거나 1년보다 오래되면 검토 화면에서 빨갛게 표시한다.
- 유효기간이 있는 사실(면제 기간, 요금 인상일)은 `valid_until` 칸을 두고, 그 날짜가 업로드 예정일 + 30일 안이면 경고한다. 지금 K-ETA가 바로 그 경우다.
- 설명란: 지금 `footer` 앞에 "出典:" / "출처:" 블록을 자동으로 붙인다(사실 시트에서 대본이 실제로 쓴 `fact_ids`의 URL만, 중복 제거, 최대 3~5개). ja는 "情報は2026年10月時点のものです。" 한 줄을 붙인다. 이건 core의 설명 조립 한 군데만 고치면 된다.
- 대본 문장 자체에도 바뀌기 쉬운 수치에는 "2026년 기준"을 넣게 지시한다(영상은 설명란보다 오래 돌아다닌다).

### Gaps
- K-ETA 면제가 2027년에도 연장되는지는 이번 조사에서 찾지 못했다(2026-10 기준 발표 없음으로 보이나 확인 못 함).
- e-Arrival Card "의무화" 시점과 법무부 원문은 여전히 2차 출처뿐이다.
- YouTube Shorts 설명란 링크가 클릭되는지(2023년 스팸 대책으로 막힌 것으로 기억하나) 이번에 다시 확인하지 못했다. 클릭이 안 되더라도 출처 URL을 글자로 남기는 의미는 있다.

## 7. 법·약관: 인용 한도, 링크, 자동 수집

### Takeaway
사실 자체는 저작물이 아니므로 **출처 문장을 옮겨 쓰지 말고 사실만 우리 말로 다시 쓰고 출처를 밝히는 것**이 안전하다. 한국 저작권법 제28조(정당한 범위·공정한 관행)·제37조(출처 명시), 일본 저작권법 제32조(공표된 저작물·명료 구분·주종 관계·출처 명시)가 기준이다. 자동 수집은 robots.txt를 지키는 것으로 판단하며, 네이버 지식백과·블로그는 Claude 봇을 명시적으로 막고 있으니 쓰지 않는다.

### Cited Findings
- 한국 저작권법 제28조: 공표된 저작물은 보도·비평·교육·연구 등을 위해 정당한 범위 안에서 공정한 관행에 맞게 인용할 수 있다. 제37조는 출처 명시 조항 — [국가법령정보(영문 법령 서비스)](https://elaw.klri.re.kr/kor_service/lawViewTitle.do?hseq=68604), [nepla 위키](https://www.nepla.ai/wiki/지식재산/저작권/정당한-범위-안에서의-공정한-인용-0vyn5z6m6nd7)
- 일본 저작권법 제32조 인용 요건: 공표된 저작물, 명료 구분성(따옴표 등), 주종 관계, 출처 명시 — [弁護士ドットコム](https://www.bengo4.com/c_1015/c_17/c_1263/m_419810/), [マイナビ](https://news.mynavi.jp/techplus/article/netlaw-2/)
- Anthropic: API 출력을 가공해 보여 줄 때 인용 표시는 법무 검토에 따라 적절히 하라고 적는다 — [Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
- robots.txt: terms.naver.com은 `ClaudeBot`·`Claude-SearchBot` 전체 금지 + 모든 봇 첫 화면 외 금지. blog.naver.com은 `ClaudeBot`·`Claude-SearchBot` 전체 금지. airport.kr은 ko·en·ch 경로 외 금지 — 이 노트 작성 중 직접 확인(4절)
- Yahoo! JAPAN 검색 API는 2013년쯤 중단 발표(오래된 정보) — [@IT](https://atmarkit.itmedia.co.jp/ait/spv/1212/03/news111.html)

### Inferences
- 대본은 출처 문장을 그대로 읽지 않는다. 사실 시트의 `quote`는 검토용으로만 쓰고 영상·설명란에는 넣지 않는다. 설명란엔 제목 + URL만 넣는다(링크는 인용이 아니라 출처 표시라 위 요건과 충돌이 없다).
- 짧은 직접 인용(공식 문구, 예: 법무부 안내 한 줄)이 꼭 필요하면 화면 자막에 「」/“ ”로 구분하고 출처 기관명을 말이나 자막에 넣는다(일본 32조 명료 구분·출처 명시).
- 자동 수집은 Anthropic fetch가 robots를 지키므로 그쪽에 맡기면 규칙 위반 위험이 낮다. 직접 가져오는 경로(playwright·urllib)를 만들면 `urllib.robotparser` 확인을 넣는다.
- 건강 주제는 출처가 있어도 처방형 문장을 피하는 지금 `sensitive_gate` 방침을 유지한다(이전 보고서와 같은 방향이라 반복하지 않는다).

### Gaps
- 네이버·Yahoo! JAPAN 이용약관의 자동 수집·AI 이용 조항 원문은 확인하지 못했다(robots 근거만 있음).
- 공공누리(KOGL) 유형별로 정부 사이트 글을 영상에 옮겨 써도 되는 범위는 확인하지 못했다. 다만 사실만 다시 쓰는 방식이면 영향이 작다고 본다(추정).

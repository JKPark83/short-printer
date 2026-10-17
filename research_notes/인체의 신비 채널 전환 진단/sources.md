# 인체의 신비 채널: 사실 확인·인용 출처, 근거 강도, 합의 수준, 속설

조사일 2026-10-16. 접근성은 이 컴퓨터에서 curl로 robots.txt와 실제 페이지를 받아 확인했다(아래 "직접 확인"). 이 파이프라인은 Anthropic 서버 쪽 `web_search`·`web_fetch`를 쓴다(`src/shorts_printer/adapters/claude_research.py`). 그래서 robots.txt가 `Claude-User`·`ClaudeBot`·`anthropic-ai`를 막는 사이트는 열람이 실패할 수 있다.

## (1) 인용할 수 있는 도메인 순위(한국어 먼저, 영어는 보조)

### Takeaway
일상 신체 현상을 한국어로 열 수 있고 robots가 막지 않는 가장 좋은 출처는 MSD 매뉴얼 한국어 일반인용(msdmanuals.com/ko), 서울아산병원 인체정보·질환백과(amc.seoul.kr), 서울대병원 N의학정보(snuh.org), 국가건강정보포털(health.kdca.go.kr)이다. 영어 보조 출처로는 NCBI Bookshelf의 StatPearls, PubMed·PMC, MedlinePlus, Cleveland Clinic, Harvard Health가 robots로 열려 있다. Scientific American·Nature·Science는 robots로 Claude 계열 봇을 막는다. 동아사이언스는 `ClaudeBot`과 `*`를 막고 `Claude-SearchBot`만 허용한다(검색 결과로는 나오지만 본문 열람은 막힐 수 있다).

### Cited Findings
직접 확인한 접근성(2026-10-16, curl):

| 순위 | 도메인 | robots.txt | 실제 페이지 | 권위 | 일상 현상 범위 |
|---|---|---|---|---|---|
| 1 | `msdmanuals.com` (/ko/home) | `User-agent: *`는 `/sitecore/`·`/custom/`만 막음 | 딸꾹질 문서 200, HTML 약 328KB, 한글 약 1만 8천 자, 제목 "딸꾹질 - 소화 장애 - MSD 매뉴얼 - 일반인용" | 의사가 쓰고 검토한 교과서급 참고서 | 증상 단위 문서(딸꾹질 등)와 몸 구조 개요. 질병 중심이지만 "증상" 문서가 일상 현상을 다룬다 |
| 2 | `amc.seoul.kr` (서울아산병원) | `*`는 `/asanpublic`·`/asanissue`·`/anws`만 막음. `/asan/healthinfo/`는 열림 | 인체정보 목록 `/asan/healthinfo/body/bodyList.do` 200, 제목 "인체정보 \| 의료정보 \| 건강정보 \| 서울아산병원". 질환백과 목록 200 | 상급종합병원 | **인체정보** 메뉴가 정상 해부·생리를 따로 다룬다(질병이 아닌 몸) |
| 3 | `snuh.org` (서울대병원 N의학정보) | `*`는 `/join/`·`/pub/`·`/mypage/`·`/reservation/`만 막고 `Allow: /` | `/health/nMedInfo/nView.do?...` 200, 한글 약 7.8천 자 | 국립대병원 | 질환·증상·검사 중심. 정상 생리는 적다 |
| 4 | `health.kdca.go.kr` (국가건강정보포털) | robots.txt 없음(404) = 제한 없음 | 메인 200, HTML, 한글 약 6.3천 자 | 질병관리청(정부) | 질환·건강생활 중심. 하품·소름 문서는 검색에서 찾지 못함 |
| 5 | `kdca.go.kr` | `*`는 `/search.do`만 막음 | — | 정부 | 감염병·통계. 일상 생리는 거의 없음 |
| 6 | `mfds.go.kr` (식약처) | `Allow: /` | — | 정부 | 식품·약·카페인 등. 몸 현상 자체는 적다 |
| 7 | `sciencetimes.co.kr` (사이언스타임즈) | robots.txt 없음(404) | 메인 200 | 과학 언론(한국과학창의재단 계열) | "왜 그럴까" 해설이 있다. 1차 연구로 거슬러 올라가 확인해야 한다 |
| — | `dongascience.com` | `Claude-SearchBot`·`PerplexityBot`은 허용, `GPTBot`·`ClaudeBot`·`*`는 `Disallow: /` | — | 과학 언론 | 해설은 좋지만 열람이 막힐 위험이 크다 |
| — | `scent.kisti.re.kr` (과학향기) | 응답 없음(http·https 모두 연결 실패, 코드 000) | 연결 실패 | KISTI | 기존 채널 allowlist에 있지만 이 컴퓨터에서는 열리지 않았다. 해외 IP 차단이거나 중단일 수 있다(아래 Gaps) |
| — | `kams.or.kr` (대한의학회) | 404 | — | 학회 | 일반인용 생리 해설은 확인하지 못함 |

영어 보조:

| 순위 | 도메인 | robots.txt (직접 확인) | 메모 |
|---|---|---|---|
| 1 | `ncbi.nlm.nih.gov/books` (StatPearls) | `*`는 `/cgi-bin`·`/stat`·`/entrez` 등만 막음 | NBK430685 200, 순수 HTML. 교과서급 합의 요약이며 갱신 날짜가 문서에 있다 |
| 2 | `pubmed.ncbi.nlm.nih.gov` | `*`는 `/api`·`/rss` 등만 막음 | 초록과 Publication Type이 페이지에 나온다 |
| 3 | `pmc.ncbi.nlm.nih.gov` | `Allow: /articles/` | 오픈액세스 전문 |
| 4 | `medlineplus.gov` | `*`는 `/URLchecker/`·`/cgi/` 등만 막음 | 의학백과 문서 200, HTML |
| 5 | `my.clevelandclinic.org` | `Disallow:`(빈 값) + `/search`만 | 일상 현상 문서가 많다(추측한 주소는 404였지만 사이트 응답은 HTML이었다) |
| 6 | `health.harvard.edu` | AI 봇 차단 줄이 모두 `#` 주석 처리됨 = 막지 않음 | 일부 글은 유료 회원 전용 |
| 7 | `nhs.uk` | `*`는 특정 검색 경로만 막음 | 증상 중심 |
| 8 | `britannica.com` | `*`는 `/search`·`/cdn-cgi/`만 | 해부 개요 |
| 9 | `livescience.com` | `*`는 `*/deals/compare`·`*/html/` 등만 | "왜 그럴까" 해설이 많고 1차 연구 링크를 단다 |
| ✗ | `mayoclinic.org` | robots.txt부터 403(봇 차단) | 질병 문서를 curl로 받아도 403. 열람 실패 가능성이 크다 |
| ✗ | `scientificamerican.com` | `anthropic-ai`·`ClaudeBot`·`Claude-User`·`Claude-SearchBot`을 막는 묶음이 있음 | 열람 불가로 본다 |
| ✗ | `nature.com`·`science.org` | `User-Agent: anthropic-ai` → `Disallow: /` | 기존 ko-40sec-facts `news`에 들어 있다. 결과를 못 얻을 수 있다 |
| — | `cochrane.org` | `*` 허용 | 치료·중재 리뷰라 일상 생리 현상에는 거의 해당 없음 |

- 국가건강정보포털은 질병관리청이 운영하는 일반인용 공식 건강정보이며, 질환의 정의·원인·증상·치료·예방을 광고 없이 정리한다 — [검색 요약(tilnote)](https://tilnote.io/pages/6a79107d0416719db2bbee17) (2차 출처)
- MSD 매뉴얼 한국어판 딸꾹질 문서 — [MSD 매뉴얼 일반인용: 딸꾹질](https://www.msdmanuals.com/ko/home/%EC%86%8C%ED%99%94-%EC%9E%A5%EC%95%A0/%EC%86%8C%ED%99%94-%EC%9E%A5%EC%95%A0-%EC%A6%9D%EC%83%81/%EB%94%B8%EA%BE%B9%EC%A7%88)
- 서울아산병원 인체정보 목록 — [amc.seoul.kr 인체정보](https://www.amc.seoul.kr/asan/healthinfo/body/bodyList.do)
- StatPearls 딸꾹질: 횡격막·늑간근의 불수의 수축과 성문 닫힘, 미주·횡격신경 반사궁, 뇌간에 있을 것으로 보는 중추. 급성 48시간 미만, 지속성 2일 초과, 난치성 1개월 초과 — [StatPearls: Hiccups (NBK538225)](https://www.ncbi.nlm.nih.gov/books/NBK538225/)

### Inferences
- 추천 allowlist(`[research]`): `domains = ["msdmanuals.com", "amc.seoul.kr", "snuh.org", "health.kdca.go.kr", "kdca.go.kr", "mfds.go.kr", "ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov", "medlineplus.gov", "my.clevelandclinic.org", "health.harvard.edu", "nhs.uk"]`, `news = ["sciencetimes.co.kr", "livescience.com", "britannica.com", "health.chosun.com"]`. `nature.com`·`science.org`·`scientificamerican.com`·`mayoclinic.org`는 넣어도 열람이 실패할 가능성이 크다. `dongascience.com`은 검색 결과 인용은 될 수 있으나 본문 확인이 안 될 수 있다.
- `languages = ["ko", "en"]`이 맞다. 일상 생리 현상(하품·소름·관절 소리)의 1차 연구는 거의 영어이고, 한국어 출처는 병원·MSD 해설 수준이다.
- 검색어 전략: 주제마다 (a) 한국어 해설 1개(`"<현상> 원인" site:amc.seoul.kr OR msdmanuals.com/ko`), (b) 합의용 StatPearls·MedlinePlus 1개, (c) PubMed에서 `<현상>[tiab] AND (review[pt] OR meta-analysis[pt])` 1개, (d) 대표 1차 연구 제목으로 1개, (e) 속설 확인용 `"<현상> myth"` 1개. 기본값 `queries_per_topic=5`와 맞는다.

### Gaps
- `scent.kisti.re.kr`은 이 컴퓨터에서 연결되지 않아 robots·HTML 여부를 확인하지 못했다. 한국 IP에서 다시 확인해야 한다. 기존 채널 설정에 들어 있다.
- 국가건강정보포털에 정상 생리(하품·소름 등) 문서가 있는지 찾지 못했다. 검색으로는 나오지 않았다.
- 서울대병원 N의학정보에 정상 생리 문서가 얼마나 있는지 세지 못했다.
- Anthropic 서버 쪽 `web_fetch`가 robots.txt의 어느 user-agent 줄을 따르는지는 이번에 확인하지 않았다. 위 판단은 `Claude-User`·`ClaudeBot`·`anthropic-ai` 차단이면 실패한다는 가정이다.
- 각 사이트의 개별 문서 갱신 날짜는 표본으로 확인하지 못했다(StatPearls는 문서마다 "Last Update"가 있다).
- 대한의학회·전문학회(대한피부과학회 등)의 일반인 정보 페이지는 확인하지 못했다.

## (2) 출처에서 근거 강도를 싸게 알아내는 법

### Takeaway
PubMed 페이지와 E-utilities의 Publication Type(`[pt]`: Review, Systematic Review, Meta-Analysis, Randomized Controlled Trial)과 MeSH(`Animals`, `Humans`, `Mice`)를 보면 단계를 거의 자동으로 매길 수 있다. 다만 사람/동물 구분은 MeSH가 붙은 논문에만 통한다. StatPearls·MSD 매뉴얼·MedlinePlus는 "교과서급 합의"로 따로 묶는다.

### Cited Findings
- 메타분석은 `meta-analysis[pt]`로 거른다. 기사 유형 필터로 임상시험·메타분석·RCT·리뷰·체계적 리뷰를 고를 수 있다 — [Bath 대학 도서관 PubMed 필터 안내](https://library.bath.ac.uk/pubmed/filters); [UCL PubMed 필터 안내](https://library-guides.ucl.ac.uk/pubmed/filters)
- `[mh]`(MeSH), `[majr]`(주요 MeSH), `[pt]`(출판 유형) 태그를 불리언으로 묶을 수 있다 — [UCL PubMed 필터 안내](https://library-guides.ucl.ac.uk/pubmed/filters)
- PubMed의 사람 필터는 MeSH `Humans`가 붙은 논문만 잡아서 부분 해결일 뿐이다. 대안은 MeSH로 동물만 확인된 것을 빼는 방식이다 — [UCL PubMed 필터 안내](https://library-guides.ucl.ac.uk/pubmed/filters)
- E-utilities 검색 주소는 `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi` — [UCL PubMed 필터 안내](https://library-guides.ucl.ac.uk/pubmed/filters)
- 동물 연구를 사람 이야기로 옮기면 안 되는 예: 소름 근육(입모근)과 교감신경이 모낭 줄기세포를 조절한다는 2020년 Cell 논문은 **생쥐** 실험이다 — [Harvard HSCRB: Shwartz et al., Cell 2020](https://hscrb.harvard.edu/publication/shwartz-y-gonzalez-celeiro-m-chen-cl-pasolli-ha-sheu-sh-fan-sm-shamsi-f-assaad-s-lin-et-zhang-b-tsai-pc-he-m-tseng-yh-lin-sj-hsu-yc-cell-types-promoting-goosebumps-form-a-niche-to-regul); [NYSCF 해설](https://nyscf.org/resources/why-do-we-get-goosebumps-the-answer-lies-with-the-stem-cells-that-grow-hair/)
- 작은 표본 예: 아이스크림 두통 혈류 연구는 자원자 13명 — [Science Focus: brain freeze](https://www.sciencefocus.com/the-human-body/brain-freeze/); [ScienceDaily 2013](https://sciencedaily.com/releases/2013/05/130522095335.htm)

### Inferences
조사 단계에서 사실마다 붙일 근거 꼬리표(규칙 기반, LLM 판단 최소화):

| 꼬리표 | 판정 규칙 | 대본 표현 |
|---|---|---|
| `교과서` | 도메인이 StatPearls(`/books/NBK`)·MSD 매뉴얼·MedlinePlus·병원 인체정보 | 단정해도 된다 |
| `종합` | PubMed `[pt]`에 Meta-Analysis·Systematic Review·Review | "여러 연구를 모아 보면" |
| `연구 1편` | `[pt]`가 Journal Article뿐, 사람 대상 | "한 연구에서는", 연도·인원 |
| `동물` | MeSH에 `Animals`가 있고 `Humans`가 없음, 또는 초록에 mice·rats·in vitro | "쥐 실험에서는"(필수) |
| `반박됨` | 같은 질문에 반대 결과 연구가 있음(아래 주름진 손가락) | "연구마다 다르지만" |
| `언론` | news 도메인 | "보도에 따르면" + 1차 연구로 다시 확인 |

- PubMed 문서 1쪽을 열면 Publication Type과 MeSH가 페이지 아래에 있으므로, 별도 API 없이 `web_fetch` 한 번으로 꼬리표를 붙일 수 있다(직접 열어 구조를 확인하지는 않았다. Gaps 참고).
- 인원수(n)와 연도를 사실 시트에 함께 남기면 "13명 대상 소규모 연구" 같은 완화 표현을 기계적으로 만들 수 있다.

### Gaps
- PubMed 페이지 HTML에서 Publication Type·MeSH 블록의 정확한 위치를 이번에 확인하지 않았다.
- Cochrane 요약은 치료 효과 중심이라 일상 생리 현상에 쓸 수 있는 리뷰가 거의 없을 것으로 보지만 확인하지 않았다.

## (3) 주제별 합의 수준(정설·부분 합의·미해결)과 대표 출처

### Takeaway
"무슨 일이 일어나는가(기전)"는 대개 정설이고, "왜 진화했나·무슨 쓸모인가(기능)"는 대개 미해결이다. 대본은 기전은 단정하고 기능은 반드시 완화 표현을 붙이는 식으로 나누면 안전하다.

### Cited Findings

**정설(단정 가능)**
- 관절 꺾는 소리: 실시간 MRI에서 소리가 날 때 관절 안에 공동(빈 공간)이 **생기는** 것이 보였고, 소리 뒤에도 공동이 남았다. 기존 "기포가 터지는 소리" 설명과 다르다(손가락 관절 10개, 소규모) — [Kawchuk et al., PLOS ONE 2015 (PMC4398549)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4398549/)
  - 주의: 기전 논쟁은 아직 남아 있다(공동 생성 vs 붕괴). 대본은 "MRI로 보니 관절 사이에 빈 공간이 순간 생겼다" 정도로 말하는 게 안전하다(추론).
- 관절 꺾기와 손 관절염: 50~89세 215명 사례대조 연구에서 관절을 꺾는 사람과 안 꺾는 사람의 관절염 비율이 비슷했다(18.1% vs 21.5%) — [deWeber et al., JABFM 2011](https://www.jabfm.org/content/24/2/169)
- 딸꾹질: 횡격막·늑간근의 불수의 수축 뒤 성문이 닫혀 "딸꾹" 소리가 난다. 반사궁은 미주·횡격신경 — [StatPearls NBK538225](https://www.ncbi.nlm.nih.gov/books/NBK538225/); 한국어 [MSD 매뉴얼: 딸꾹질](https://www.msdmanuals.com/ko/home/%EC%86%8C%ED%99%94-%EC%9E%A5%EC%95%A0/%EC%86%8C%ED%99%94-%EC%9E%A5%EC%95%A0-%EC%A6%9D%EC%83%81/%EB%94%B8%EA%BE%B9%EC%A7%88)
  - 딸꾹질의 **진화적 기능**은 미해결로 다룬다(출처 미확인, Gaps).
- 물 필요량: 26개국 5,600여 명의 이중표지수 측정에서 하루 물 교체량이 약 1~6L로 사람마다 크게 달라, "하루 8잔"이 모든 사람에게 맞는 기준이 아님을 보였다 — [UW–Madison 보도자료(Yamada et al., Science 2022)](https://news.wisc.edu/stop-counting-cups-theres-an-ocean-of-difference-in-our-water-needs/); [ScienceDaily 2022](https://www.sciencedaily.com/releases/2022/11/221125132035.htm)

**부분 합의(기전은 대체로, 이유는 가설)**
- 하품: Gallup의 체온 조절(뇌 냉각) 가설. 턱을 벌리고 깊이 들이마셔 뇌로 가는 혈류를 바꾸고 바깥 공기와 열을 교환한다는 설명. 하품이 특정 바깥 온도 범위에서 잘 일어난다는 "온도 창" 예측이 뒷받침한다. 지지 근거가 많지만 Gallup 연구진 중심이다 — [Gallup & Eldakar, Frontiers in Neuroscience 2013](https://www.frontiersin.org/articles/10.3389/fnins.2012.00188/pdf); [sciencenorway 해설](https://sciencenorway.no/animals-social-relations-the-body/both-animals-and-humans-yawn-why-do-we-yawn-and-why-is-it-contagious/2052457)
  - 대본: "가장 유력한 가설은 뇌를 식힌다는 것". 정설처럼 말하지 않는다.
- 소름: 기전(입모근 수축, 교감신경)은 정설. "모낭 줄기세포를 깨워 털을 자라게 한다"는 기능은 **생쥐** 연구 — [Shwartz et al., Cell 2020 (Harvard HSCRB)](https://hscrb.harvard.edu/publication/shwartz-y-gonzalez-celeiro-m-chen-cl-pasolli-ha-sheu-sh-fan-sm-shamsi-f-assaad-s-lin-et-zhang-b-tsai-pc-he-m-tseng-yh-lin-sj-hsu-yc-cell-types-promoting-goosebumps-form-a-niche-to-regul); [Science News](https://www.sciencenews.org/article/goose-bumps-could-boost-hair-growth)
- 아이스크림 두통: 차가운 것이 입천장에 닿은 뒤 뇌혈관 혈류가 늘어난다는 소규모(13명) 연구 — [Science Focus](https://www.sciencefocus.com/the-human-body/brain-freeze/); [ScienceDaily 2013](https://sciencedaily.com/releases/2013/05/130522095335.htm)

**미해결(반드시 완화 표현)**
- 꿈을 꾸는 이유: 이론은 많지만 합의가 없다. 기억 공고화·감정 조절·위협 시뮬레이션·무작위 신경 활동(활성화-합성) 가설이 경쟁한다. 프로이트식 해석은 과학적 신뢰가 낮다 — [Scarpelli et al., "The Functional Role of Dreaming in Emotional Processes" (PubMed 30930809)](https://pubmed.ncbi.nlm.nih.gov/30930809/); [Frontiers in Psychology 2013 (꿈 기능 다기능설)](https://www.frontiersin.org/articles/10.3389/fpsyg.2013.00474/pdf); [Tartu 대학 블로그](https://blog.ut.ee/why-do-we-dream/)
- 햇빛 재채기(광반사 재채기): 유병률은 연구마다 11~36%(대략 4명 중 1명)로 들쭉날쭉하고, 기전(시신경-삼차신경 합산 등)은 확정되지 않았다 — [Experimental Brain Research 2024 (Springer)](https://link.springer.com/article/10.1007/s00221-024-06988-4); [PBS NewsHour](https://www.pbs.org/newshour/amp/science/does-the-sun-make-you-sneeze)
- 물에 불은 손가락 주름의 쓸모: 2013년 연구는 젖은 물건을 더 빨리 옮긴다고 했지만, 2014년 같은 설계 재현에서 효과가 없었다 — [Kareklas et al. 2013 (OpenLB/PubMed 23302867)](https://ngdc.cncb.ac.cn:443/openlb/publication/OLB-PM-23302867); [MDC Berlin 보도자료 2014 (Haseleu et al.)](https://www.mdc-berlin.de/news/archive/2014/20140109-better_grip_with_wrinkly_fingers__mdc-rese)
  - 주름이 생기는 **기전**(신경이 조절하는 혈관 수축)은 정설로 알려졌지만 이번에 출처를 확인하지 않았다(Gaps).

### 일상 신체 주제 20개 상태표

| # | 주제 | 상태 | 확인한 대표 출처 |
|---|---|---|---|
| 1 | 관절 꺾는 소리 | 정설(공동 생성), 세부 논쟁 남음 | [Kawchuk 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4398549/) |
| 2 | 관절 꺾기 → 관절염? | 정설: 연관 없음 | [deWeber 2011](https://www.jabfm.org/content/24/2/169) |
| 3 | 딸꾹질 기전 | 정설 | [StatPearls](https://www.ncbi.nlm.nih.gov/books/NBK538225/) |
| 4 | 하품 이유 | 부분 합의(뇌 냉각 가설 유력) | [Gallup 2013](https://www.frontiersin.org/articles/10.3389/fnins.2012.00188/pdf) |
| 5 | 하품 전염 | 부분 합의(계절·온도가 영향) | [Gallup 2013](https://www.frontiersin.org/articles/10.3389/fnins.2012.00188/pdf) |
| 6 | 소름 기전 | 정설 | [Shwartz 2020 해설](https://www.sciencenews.org/article/goose-bumps-could-boost-hair-growth) |
| 7 | 소름의 쓸모(털 성장) | 생쥐 연구 | [Shwartz 2020](https://hscrb.harvard.edu/publication/shwartz-y-gonzalez-celeiro-m-chen-cl-pasolli-ha-sheu-sh-fan-sm-shamsi-f-assaad-s-lin-et-zhang-b-tsai-pc-he-m-tseng-yh-lin-sj-hsu-yc-cell-types-promoting-goosebumps-form-a-niche-to-regul) |
| 8 | 꿈의 이유 | 미해결 | [PubMed 30930809](https://pubmed.ncbi.nlm.nih.gov/30930809/) |
| 9 | 햇빛 재채기 | 현상은 확실, 기전 미해결 | [Exp Brain Res 2024](https://link.springer.com/article/10.1007/s00221-024-06988-4) |
| 10 | 아이스크림 두통 | 부분 합의(혈류 변화, 소규모) | [ScienceDaily 2013](https://sciencedaily.com/releases/2013/05/130522095335.htm) |
| 11 | 물에 불은 손가락의 쓸모 | 반박됨/미해결 | [MDC 2014](https://www.mdc-berlin.de/news/archive/2014/20140109-better_grip_with_wrinkly_fingers__mdc-rese) |
| 12 | 하루 물 필요량 | 정설: 사람마다 다름 | [Yamada 2022 보도](https://news.wisc.edu/stop-counting-cups-theres-an-ocean-of-difference-in-our-water-needs/) |
| 13 | 뇌 사용량 | 정설: 쉬는 영역 없음 | [Vreeman BMJ 2007](https://pmc.ncbi.nlm.nih.gov/articles/PMC2151163/) |
| 14 | 면도 후 털 | 정설: 굵어지지 않음 | [Vreeman BMJ 2007](https://pmc.ncbi.nlm.nih.gov/articles/PMC2151163/) |
| 15 | 죽은 뒤 손발톱·머리카락 | 정설: 자라지 않음(피부가 마름) | [Vreeman BMJ 2007](https://pmc.ncbi.nlm.nih.gov/articles/PMC2151163/) |
| 16 | 어두운 데서 책 읽기 → 시력 손상 | 정설: 영구 손상 근거 없음 | [Vreeman BMJ 2007](https://pmc.ncbi.nlm.nih.gov/articles/PMC2151163/) |
| 17 | 칠면조 먹으면 졸림 | 정설: 트립토판 탓 아님 | [Vreeman BMJ 2007](https://pmc.ncbi.nlm.nih.gov/articles/PMC2151163/) |
| 18 | 설탕 → 아이 과잉행동 | 정설: 이중맹검에서 효과 없음 | [Wolraich 1995 메타분석 해설(Live Science)](https://livescience.com/55754-does-sugar-make-kids-hyper.html) |
| 19 | 배에서 꼬르륵 소리 | 미확인 | — (Gaps) |
| 20 | 감정 눈물의 이유 | 미확인(기능은 미해결로 알려짐) | — (Gaps) |

### Inferences
- 대본 규칙 후보: 사실 시트의 꼬리표가 `동물`·`연구 1편`·`반박됨`이거나 문장에 "why/이유/쓸모"가 들어가면 완화 표현을 강제한다.
- 정설 주제(1·2·3·12~18)는 "속설 깨기" 꼴로 쓰기 좋다. 미해결 주제(8·9·11)는 "과학자도 아직 모른다"를 훅으로 쓰면 완화 표현과 재미가 함께 선다.

### Gaps
- 19 꼬르륵 소리(장 연동운동), 20 감정 눈물, 딸꾹질의 진화적 기능, 손가락 주름 기전, 얼굴 붉어짐, 쥐 나기(근육 경련 원인은 미해결로 알려짐), 혀 말기 유전(멘델 형질 아님으로 알려짐)은 이번에 출처를 확인하지 못했다. 같은 전략(StatPearls + PubMed review)으로 채워야 한다.
- Kawchuk 2015 이후 공동 붕괴설을 지지하는 반론 연구(예: 2018년 수학 모델 연구)는 확인하지 않았다.
- 꿈 주제의 최근 5년 이내 종합 리뷰는 찾지 못했다(찾은 리뷰는 2013·2019년).
- Wolraich 1995 원문(JAMA 274(20):1617-21)의 PubMed 주소는 확인하지 못했고 2차 해설만 인용했다.

## (4) 속설 목록(블랙리스트 또는 속설 깨기)

### Takeaway
BMJ 2007 "Medical myths"(Vreeman & Carroll, PMC 무료 전문) 하나가 일곱 가지 대표 속설을 반박해서, 속설 블랙리스트의 기준 출처로 쓰기 좋다. 여기에 관절염(JABFM 2011), 물 8잔(Science 2022), 설탕(JAMA 1995)을 더한다.

### Cited Findings
- BMJ 2007 크리스마스호가 검토한 일곱 가지: 하루 물 8잔, 뇌 10%만 사용, 죽은 뒤 머리카락·손발톱이 자람, 면도하면 털이 빨리·짙게·굵게 남, 어두운 데서 읽으면 시력이 나빠짐, 칠면조를 먹으면 졸림, 휴대폰이 병원 기기에 큰 전자파 간섭 — [Vreeman & Carroll, BMJ 2007 (PMC2151163)](https://pmc.ncbi.nlm.nih.gov/articles/PMC2151163/); [ScienceDaily 2007](https://www.sciencedaily.com/releases/2007/12/071220195639.htm)
- 뇌 10%: MRI·PET 등 영상 연구에서 쉬는 뇌 영역이 없다 — [Vreeman & Carroll, BMJ 2007](https://pmc.ncbi.nlm.nih.gov/articles/PMC2151163/)
- 물 8잔: 하루 8잔이 필요하다는 근거가 없다 — [Vreeman & Carroll, BMJ 2007](https://pmc.ncbi.nlm.nih.gov/articles/PMC2151163/). 2022년 26개국 5,600여 명 측정에서도 1~6L로 개인차가 컸다 — [UW–Madison 2022](https://news.wisc.edu/stop-counting-cups-theres-an-ocean-of-difference-in-our-water-needs/)
- 관절 꺾으면 관절염: 사례대조 연구에서 위험 요인이 아니었다 — [deWeber, JABFM 2011](https://www.jabfm.org/content/24/2/169)
- 설탕 → 과잉행동: 23개 이중맹검 연구 메타분석에서 효과가 없었고, 부모의 기대가 행동을 보는 눈을 바꾼다 — [Live Science 해설](https://livescience.com/55754-does-sugar-make-kids-hyper.html); [Big Think](https://bigthink.com/neurobonkers/believe-it-or-not-sugar-doesnt-cause-hyperactivity)
- 관절 소리는 "기포가 터지는 소리": 2015 MRI 연구는 공동이 생기는 순간 소리가 났다고 보고했다 — [Kawchuk 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4398549/)
- "소름은 털을 세워 체온을 지킨다"는 사람에게는 흔적 기능일 뿐이라는 설명이 흔하지만, 이번에 사람 대상 출처로 확인하지 못했다(Gaps)

### Inferences
- 블랙리스트 문장(사실 시트에 이 주장이 나오면 "속설" 꼬리표 없이는 대본에 못 쓰게): "뇌의 10%만 쓴다", "하루 물 8잔(2L)을 꼭 마셔야 한다", "면도하면 털이 굵어진다", "죽어서도 손톱·머리카락이 자란다", "어두운 데서 책 읽으면 눈이 나빠진다", "칠면조(트립토판) 때문에 졸리다", "관절 꺾으면 관절염 걸린다", "설탕 먹으면 아이가 흥분한다", "관절 소리는 기포가 터지는 소리"(최소한 단정 금지).
- 한국에서 흔한 속설(혀 지도, 찬물 마시면 배탈, 손가락 길이와 성격 등)도 추가 후보지만 이번에 출처를 확인하지 않았다.

### Gaps
- 혀 지도(맛 지도) 속설, 박하·찬물 관련 한국 속설, "소름은 흔적 기관" 설명의 1차 출처는 확인하지 못했다.
- 한국어 속설 깨기 공식 출처(질병관리청·식약처 "건강 속설" 코너 등)가 있는지 찾지 못했다.

## 5. 확장 주제 은행

### Takeaway
채널 범위(몰랐던 인체의 신비 · 생리 원리 수준의 건강 유지 비결 · 장기의 뜻밖의 역할 · 화제가 된 연구)에 맞춰 30개 주제를 1차 논문이나 교과서 출처와 함께 정리했다. "언론에서 화제가 된 연구"는 상당수가 **논쟁** 상태다(뇌 미세플라스틱, 44·60세 노화 급변, 수면 중 뇌 청소). 이런 주제는 반드시 "아직 논란"이라는 완화 표현과 함께 다뤄야 한다. 건강 유지 비결은 원리(왜 그런가)만 말하고, 몇 보·몇 분 같은 권고나 치료·보충제 조언은 하지 않는다.

상태: **확립**(교과서·다수 연구가 일치) · **부분**(기전은 맞지만 크기·기능·사람 적용은 가설) · **논쟁**(반대 결과나 방법론 비판이 공개되어 있음). "검증"은 이번 조사에서 검색으로 서지(학술지·연도)를 확인했는지를 뜻한다. DOI는 검색 결과에서 직접 본 것만 적었다.

### Cited Findings

**(a) 몰랐던 인체의 신비**

| # | 주제 | 한 줄 사실 | 출처 | 상태 | 검증 |
|---|---|---|---|---|---|
| A1 | 위 점막 교체 | 위샘의 표면(pit) 세포는 평균 약 3일마다 바뀌지만, 벽세포는 약 54일, 주세포는 약 194일로 세포마다 크게 다르다 | Karam·Leblond 계열 측정, [BioNumbers 112304](https://bionumbers.hms.harvard.edu/bionumber.aspx?id=112304) (원 논문 서지는 BioNumbers에 있음) | 확립(쥐 기반 측정이 많음 → "동물 측정" 꼬리표) | 부분: 2차 데이터베이스만 확인 |
| A2 | 간 재생 | 간을 70% 잘라 내도 남은 조직이 원래 질량과 기능을 되찾는다(주로 실험동물 부분절제 모델) | Michalopoulos 리뷰, [PMC2701258](https://pmc.ncbi.nlm.nih.gov/articles/PMC2701258); [Michalopoulos, "To divide or not to divide" (PMC3695844)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3695844/) | 확립(사람에서도 생체 간이식으로 확인된다고 알려졌지만 이번에 출처 미확인) | 확인 |
| A3 | 뼈는 계속 다시 지어진다 | 파골세포가 낡은 뼈를 녹이고 조골세포가 새 뼈를 쌓는 재형성이 평생 이어지고, 칼슘·인 균형에도 쓰인다 | [StatPearls: Physiology, Bone Remodeling (NBK499863)](https://www.ncbi.nlm.nih.gov/books/NBK499863/); [PubMed 27053737](https://pubmed.ncbi.nlm.nih.gov/27053737/) | 확립 | 확인(NBK 번호가 이 문서인지 페이지는 열어 보지 않음) |
| A4 | 눈의 맹점 | 시신경 원판에는 광수용체가 없어 시야 중심에서 약 15° 옆, 약 6°×8° 크기의 맹점이 있지만 뇌가 채워 넣어 모른다 | [bioRxiv 2023: Extrastriate activity reflects the absence of local retinal input](https://www.biorxiv.org/content/10.1101/2023.05.15.540895.full.pdf) (프리프린트); 교과서 출처 미확인 | 확립(채워 넣기의 뇌 기전은 부분) | 부분: 교과서 출처는 Gaps |
| A5 | 몸 세포 교체 속도 | 몸에는 약 30조 개 세포가 있고 하루 약 3,300억 개가 바뀐다. 대부분이 혈액세포, 다음이 장 세포 | Sender & Milo, Nature Medicine 2021, [Weizmann 해설](https://wis-wander.weizmann.ac.il/node/11205) | 확립(추정 모델) | 확인(DOI 미확인) |
| A6 | 세포 나이는 조직마다 다르다 | 탄소-14로 재 보니 대뇌피질 신경세포는 사람 나이와 같고, 장 세포 평균 약 10년, 골격근 약 15년이었다 | Spalding et al., Cell 2005, [Times Higher Education 보도](https://www.timeshighereducation.com/node/58613); [Alzforum](https://alzforum.org/node/37786) | 확립 | 부분: 원 논문 주소 미확인 |
| A7 | 갈색지방 | 성인에게도 목~가슴에 열을 내는 갈색지방이 있고, PET-CT에서 여성 7.5%·남성 3.1%에서 보였다 | Cypess et al., NEJM 2009;360(15):1509-17, [Joslin 서지](https://research.joslin.org/kahnlaboratory/publications/identification-and-importance-brown-adipose-tissue-adult-humans) | 확립(존재). 체중 조절 기여 크기는 부분 | 확인 |

**(b) 건강 유지 비결(생리 원리만, 권고 아님)**

| # | 주제 | 한 줄 사실 | 출처 | 상태 | 검증 |
|---|---|---|---|---|---|
| B1 | 잠과 기억 | 서파수면 중 낮에 익힌 기억이 다시 재생되고 렘수면이 이를 안정시킨다는 것이 수면-기억 연구의 주된 모델이다 | Rasch & Born, "About sleep's role in memory", Physiological Reviews 2013;93(2):681-766, [튀빙겐 대학 저장소](https://publikationen.uni-tuebingen.de/xmlui/handle/10900/39567) | 확립(잠이 기억을 돕는다). 단계별 역할 분담은 부분 | 확인 |
| B2 | 근육은 혈당 저장고 | 인슐린이 있을 때 들어온 포도당의 약 80~90%를 골격근이 가져간다 | DeFronzo et al., 1981 클램프 연구, [JCI 10.1172/JCI110399](https://www.doi.org/10.1172/JCI110399); [JCI 111938](https://jci.org/articles/view/111938) | 확립 | 확인(DOI 10.1172/JCI110399가 정확히 어느 논문인지 페이지는 열어 보지 않음) |
| B3 | 식후 걷기와 혈당 | 7개 연구를 모은 메타분석에서 오래 앉아 있을 때보다 가벼운 걷기를 끼워 넣으면 혈당이 평균 17%, 서 있기만 해도 9.5% 낮았다 | Buffey et al., Sports Medicine 2022, [CNN 계열 보도(KRDO)](https://krdo.com/news/2023/09/09/just-2-minutes-of-walking-after-eating-can-help-blood-sugar-study-says/) | 부분(작은 연구 7개, 효과 크기는 연구마다 다름) | 부분: 원 논문 주소 미확인 |
| B4 | 갑자기 일어서면 어지러운 이유 | 일어설 때 피가 다리로 몰려 혈압이 떨어진다. 3분 안에 수축기 20mmHg 이상 떨어지면 기립성 저혈압으로 정의한다 | [StatPearls: Orthostatic Hypotension (NBK448192)](https://www.ncbi.nlm.nih.gov/books/NBK448192/) | 확립 | 확인 |
| B5 | 하루 걸음 수와 사망 위험 | 15개 코호트 4만 7천여 명에서 60세 이상은 6,000~8,000보, 60세 미만은 8,000~10,000보까지 사망 위험이 줄다가 평평해졌다 | Paluch et al., Lancet Public Health 2022;7(3), [DOAJ](https://doaj.org/article/c3639c468b4348958202e52793ab979d) | 확립(관찰 연구 → 인과 아님) | 확인 |

**(c) 장기의 뜻밖의 역할**

| # | 주제 | 한 줄 사실 | 출처 | 상태 | 검증 |
|---|---|---|---|---|---|
| C1 | 장-뇌 축 | 장내 미생물은 면역계, 트립토판 대사, 미주신경, 장 신경계, 짧은사슬지방산 같은 대사물로 뇌와 신호를 주고받는다 | Cryan et al., Physiological Reviews 2019;99:1877-2013, DOI [10.1152/physrev.00018.2018](https://www.citedrive.com/en/discovery/the-microbiota-gut-brain-axis/); [UCC 저장소](https://cora.ucc.ie/handle/10468/10506) | 부분(연결 경로는 확립, 사람의 기분·행동 인과는 상당 부분 동물 연구) | 확인 |
| C2 | 비장은 피 저장고 | 바다 유목민 바자우족은 비장이 약 50% 더 크고, 잠수할 때 비장이 수축해 산소 실은 적혈구를 내보낸다. PDE10A 유전자 변이가 관련 | Ilardo et al., Cell 2018, [Radboudumc 보도](https://www.radboudumc.nl/en/news-items/2018/langer-duiken-door-grote-milt); [The Scientist](https://mobile.the-scientist.com/article/52347/free-divers-from-southeast-asia-evolved-bigger-spleens) | 부분(비장 수축은 확립, 유전 적응은 한 연구, 43명 대 33명) | 확인(DOI 미확인) |
| C3 | 맹장은 유익균 피난처 | 설사로 장이 비워진 뒤 장을 다시 채울 유익균을 맹장이 보관한다는 "안전가옥" 가설 | Bollinger et al., J Theor Biol 2007;249(4):826-831, [Duke Health](https://corporate.dukehealth.org/news/appendix-isnt-useless-all-its-safe-house-bacteria) | 부분(가설, 이론 논문) | 확인 |
| C4 | 맹장은 32번 진화했다 | 포유류에서 맹장은 적어도 32번 따로 생겼고 사라진 건 7번 미만이라 쓸모가 있을 가능성이 크다 | Smith et al., Comptes Rendus Palevol 2013;12(6):339-354, [MNHN](https://sciencepress.mnhn.fr/en/periodiques/comptes-rendus-palevol/12/fasc6/multiple-independent-appearances-cecal-appendix-mammalian-evolution-and-investigation-related-ecological-and-anatomical-factors) | 부분 | 확인 |
| C5 | 피부는 면역 기관 | 각질형성세포가 인플라마좀으로 위험을 감지하고, 피부에 머무는 T세포가 감시를 맡는다 | Nestle et al., "Skin immune sentinels in health and disease", Nature Reviews Immunology 2009, [PMC2947825](https://pmc.ncbi.nlm.nih.gov/articles/2947825) | 확립 | 확인 |
| C6 | 잠자는 동안 뇌 청소(글림프 계통) | 2013년 생쥐 연구는 잠잘 때 뇌세포 사이 공간이 넓어져 노폐물 청소가 최대 2배 빨라진다고 했다. 2024년 생쥐 연구는 오히려 잠·마취 중 청소가 **줄었다**고 보고했다 | Xie et al., Science 2013;342:373-377, [PMC3867735 해설](https://pmc.ncbi.nlm.nih.gov/articles/PMC3867735); Miao et al., Nature Neuroscience 2024, [UK DRI](https://ukdri.ac.uk/news-and-events/scientists-find-sleep-may-not-clear-brain-toxins-as-previously-thought); [Alzforum](https://alzforum.org/news/research-news/does-sleep-really-speed-clearance-brain) | **논쟁**(둘 다 생쥐) | 확인 |
| C7 | 간질(interstitium) "새 장기" | 2018년 내시경 현미경 연구가 장기를 감싼 체액 그물망을 "새 장기"로 제안해 화제가 됐다. 기존 조직 고정 과정에서 체액이 빠져 못 봤다는 설명 | Benias et al., Scientific Reports 2018, [JHU Newsletter](https://jhunewsletter.com/article/2018/04/researchers-discover-new-organ-the-interstitium) | **논쟁**("장기"로 볼지는 받아들여지지 않음) | 부분: 원 논문 주소 미확인 |
| C8 | 장간막은 하나로 이어진 장기 | 흩어진 조각으로 배우던 장간막이 하나로 이어진 구조라며 장기로 분류하자는 제안 | Coffey & O'Leary, Lancet Gastroenterology & Hepatology 2016, [News-Medical](https://www.news-medical.net/news/20161220/University-of-Limerick-professor-outlines-evidence-for-categorising-mesentery-as-organ.aspx); 반론 [Mental Floss "새 장기는 아니다"](https://www.mentalfloss.com/article/90495/no-scientists-have-not-found-new-organ) | 부분(구조는 받아들여짐, "새 장기 발견"이라는 표현은 과장) | 확인 |

**(d) 언론에서 화제가 된 연구(2012~2026)**

| # | 주제 | 한 줄 사실 | 출처 | 상태 | 검증 |
|---|---|---|---|---|---|
| D1 | 관절 꺾는 소리 MRI | 위 (3) 참조 | [Kawchuk 2015, PMC4398549](https://pmc.ncbi.nlm.nih.gov/articles/PMC4398549/) | 확립(세부 논쟁) | 확인 |
| D2 | 혈액 속 미세플라스틱 | 건강한 성인 22명 중 다수의 혈액에서 PET·PE·폴리스타이렌 등이 검출됐고 평균 1.6μg/mL | Leslie et al., Environment International 2022, [DOAJ](https://doaj.org/article/e1e493ea679e413facbbc33bbe99ba8a) | 부분(검출은 반복, 양·건강 영향은 미확정. 표본 22명) | 확인 |
| D3 | 혈관 플라크 속 미세플라스틱 | 경동맥 수술 환자 304명 중 약 60%의 플라크에서 폴리에틸렌이 나왔고, 이들은 34개월 동안 심근경색·뇌졸중·사망 위험이 4.5배였다 | Marfella et al., NEJM 2024, [HealthDay](https://www.healthday.com/healthpro-news/cardiovascular-diseases/risk-for-mi-stroke-death-increased-with-plastics-in-carotid-plaques) | 부분(관찰 연구 → 인과 아님, 측정 방법 비판 있음) | 확인(DOI 미확인) |
| D4 | 뇌 속 미세플라스틱 | 2016·2024년 시신 52명 분석에서 뇌가 간·신장보다 최대 30배 많았다고 보고 | Nihart et al., Nature Medicine 2025, [ScienceAlert](https://www.sciencealert.com/microplastics-could-accumulate-in-our-brains-more-than-in-kidneys-and-livers); 비판: 뇌의 약 60%인 지방이 열분해 GC/MS에서 폴리에틸렌처럼 보일 수 있음 [Science Media Centre](https://www.sciencemediacentre.org/expert-reaction-to-a-study-investigating-the-accumulation-of-microplastics-in-human-organs/); [Business Standard 2026-01](https://www.business-standard.com/health/microplastics-human-organs-studies-evidence-contamination-concerns-126012000446_1.html) | **논쟁** | 확인 |
| D5 | 44세·60세 노화 급변 | 25~75세 108명의 분자 13만 5천 종을 추적했더니 선형으로 변한 건 6.6%뿐이고 약 44세·60세에 변화가 몰렸다 | Shen et al., Nature Aging 2024, DOI [10.1038/s43587-024-00692-2](https://pmc.ncbi.nlm.nih.gov/articles/PMC11564093/) | **논쟁**: 두 통계 기법이 잡음에서도 비슷한 봉우리를 만든다는 bioRxiv 분석이 나왔고, 편집진이 신뢰성 주의 문구를 달았다는 보도가 있다 | 부분: 주의 문구는 검색 요약 한 곳에서만 봤고 다른 검색에서 못 찾음 → 확인 필요 |
| D6 | 1만 보의 기원 | 1965년 일본 야마사 사의 만보계("만보계" 상품명) 마케팅에서 나왔다 | [Harvard Health 2019](https://www.health.harvard.edu/blog/10000-steps-a-day-or-fewer-2019071117305); Lee et al., JAMA Internal Medicine 2019(고령 여성 1만 6천여 명, 약 7,500보에서 이득이 평평) | 확립(기원) | 확인 |
| D7 | 2023 걸음 수 용량-반응 메타분석 | 17개 코호트 22만 6,889명: 하루 약 3,967보부터 전체 사망, 2,337보부터 심혈관 사망 위험이 줄었다. 12개 연구 11만 1,309명: 최적 약 8,763보(사망)·7,126보(심혈관) | Banach et al., Eur J Prev Cardiol 2023, [ScienceDaily](https://sciencedaily.com/releases/2023/08/230808201935.htm); Stens et al., JACC 2023, [JYX 저장소](https://jyx.jyu.fi/handle/123456789/91833) | 확립(방향), 수치는 연구마다 다름 | 확인 |
| D8 | "7년마다 몸이 다 바뀐다" 속설 | 조직마다 세포 수명이 달라 뇌 신경세포는 평생 남는다(A5·A6) | Spalding 2005; Sender & Milo 2021 (위) | 확립: 속설 | 확인 |
| D9 | Y 염색체 완전 해독 | T2T 컨소시엄이 Y 염색체 6,246만 29염기를 빈틈없이 읽어 기존 참조에 3천만 염기 이상을 더했다(2023년 8월 Nature. 지시의 "2024"는 2023이 맞다) | Rhie et al., Nature 2023, [NHGRI 보도자료](https://www.genome.gov/news/news-release/researchers-assemble-the-first-complete-sequence-of-a-human-y-chromosome); [NIST](https://www.nist.gov/publications/complete-sequence-human-y-chromosome) | 확립 | 확인 |
| D10 | 임신하면 뇌가 줄어든다 | 첫 임신 여성 25명에서 사회 인지 영역의 회백질이 줄었고 2년 뒤에도 해마 말고는 유지됐다(2017). 한 사람을 임신 전~출산 2년 뒤까지 촘촘히 찍은 2024년 연구도 회백질 감소, 백질 증가, 출산 뒤 일부 회복을 보였다 | Hoekzema et al., Nature Neuroscience 2017, [Neuroscience News](https://neurosciencenews.com/structural-brain-change-pregnancy-5774); Pritschet et al., Nature Neuroscience 2024, [NIH Research Matters](https://www.nih.gov/news-events/nih-research-matters/brain-changes-observed-during-pregnancy) | 부분(줄어든다는 관찰은 반복. "기능이 나빠진다"는 뜻이 아니며 2024년은 1명) | 확인 |
| D11 | 뇌-컴퓨터 접속(Neuralink) | 2024년 1월 첫 사람 이식이 발표됐고, 2025년 10월 환자 3명 결과를 NEJM에 투고했다고 보도됐다. 동료 심사 논문은 이번에 확인하지 못했다 | [NBC News 2024](https://www.nbcnews.com/tech/tech-news/elon-musk-says-startup-neuralink-implanted-device-first-human-rcna136285); [The Debrief 2025](https://thedebrief.org/neuralink-submits-first-human-clinical-data-for-peer-review-marking-milestone-in-brain-computer-interface-research/) | **논쟁/미확인**(회사 발표 중심) | 부분: 게재 여부 미확인 |
| D12 | 설탕과 과잉행동 | 위 (4) 참조 | Wolraich 1995 JAMA | 확립: 속설 | 부분 |

### Inferences
- 주제 고르기: (a)·(c)의 확립·부분 주제가 가장 안전한 "몰랐던 사실" 재료다(A2·A3·A5·A7·B2·B4·C5). (d)의 논쟁 주제(C6·D4·D5·C7)는 "화제가 됐지만 반론도 있다"는 두 면을 다 보여 주는 꼴로만 쓴다. 한쪽만 말하면 오보가 된다.
- 꼬리표 규칙 추가: 출처에 "Nature Medicine·NEJM 보도"처럼 언론에 크게 난 연구는 같은 주제의 반론("critique", "contamination", "editor's note", "noise")을 한 번 더 검색하게 한다. 이번 조사에서 화제 연구 4개 중 3개에 공개 반론이 있었다(C6·D4·D5).
- 건강 유지 비결 주제(B1~B5)는 숫자 권고(몇 보, 몇 분)로 끝내지 말고 "왜"(근육이 포도당을 가져간다, 다리로 피가 몰린다)로 끝내야 치료·건강 조언 경계를 넘지 않는다. B5·D7의 걸음 수는 관찰 연구라 "많이 걸으면 오래 산다"는 인과로 쓰면 안 된다.
- 20~80대 전 연령 대상이라 B4(기립성 어지럼), D10(임신과 뇌), B2(근육과 혈당)처럼 나이대별로 와닿는 주제가 고루 있다.

### Gaps
- DOI를 직접 확인한 건 Shen 2024(10.1038/s43587-024-00692-2), Cryan 2019(10.1152/physrev.00018.2018), DeFronzo(10.1172/JCI110399, 어느 논문인지 미확인)뿐이다. 나머지는 학술지·연도·권호와 보도·저장소 주소만 확인했다. Sender & Milo 2021, Spalding 2005, Ilardo 2018, Benias 2018, Marfella 2024, Nihart 2025, Buffey 2022, Hoekzema 2017, Pritschet 2024, Rhie 2023, Miao 2024의 DOI·PubMed 주소는 파이프라인이 PubMed에서 제목으로 다시 찾아야 한다.
- D5 Nature Aging 편집진 주의 문구: 한 검색 요약에만 나왔고 다른 검색에서는 찾지 못했다. 원문 페이지에서 확인 전까지 "통계 방법에 대한 반론이 있다"까지만 쓴다.
- A1 위 세포 교체 수치는 2차 데이터베이스(BioNumbers)에서만 봤고, 원 측정이 사람인지 동물인지 확인하지 못했다.
- A4 맹점의 교과서 출처(NCBI Bookshelf Purves Neuroscience 등)를 찾지 못했다.
- D11 Neuralink의 동료 심사 논문 게재 여부는 2026-10 기준으로 확인하지 못했다.
- 사람 간 재생(생체 간이식 공여자 회복) 출처는 확인하지 못했다.

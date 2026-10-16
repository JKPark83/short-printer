# 화풍 결정: 상식 채널(ko)과 일본어 서울 여행 채널(ja)에 맞는 AI 영상 스타일 (2026년 10월 기준)

전제: Flow 안의 Omni 1.1 Flash, 9:16, 8초, 대부분 360p(6크레딧, 720p는 12크레딧), 채널당 하루 1편 × 13장면, 월 약 6,300크레딧.
지금 설정은 ko가 `Stylized 3D animated explainer, clean CGI visualization like an architecture documentary, smooth matte materials, soft even daylight, warm muted colors, same art style in every shot.`이고, ja가 `Stylized 3D animated miniature diorama explainer: a tabletop scale model of Seoul with tilt-shift depth of field, soft clay-like matte materials, ...`이다(`channels/*/channel.toml`).
이전 보고서(`reports/2분 쇼츠 퀄리티 전략.md` 3장)에서 다룬 내용(Veo 공식 프롬프트 공식, SFX 분리, "single continuous shot", 틸트시프트 대신 "handmade scale model", 참조 이미지가 일관성의 핵심, 글자는 ASS로)은 반복하지 않고 그 위에 쌓는다.
출처 대부분은 Veo 3/3.1 또는 Omni Flash 1.0(2026년 5월)을 다룬다. Omni 1.1(2026-08-27)에 한정된 자료는 드물어서, 어느 모델 이야기인지 줄마다 적었다.

## 1. 시청자 반응: 실사풍 AI와 스타일화된 애니메이션 중 무엇이 덜 거부되나

### Takeaway
한국과 일본 모두 AI 콘텐츠를 매일 접하고, 특히 어색한 표정과 움직임, 그리고 "AI 같은 분위기"에 거부감을 느낀다. 일본 조사에서는 AI임을 알아챈 사람 셋 중 하나가 시청을 멈춘다. 다만 "실사풍 대 애니메이션풍"을 직접 비교한 한국·일본 조사나 A/B 실험은 찾지 못했다. 그래서 화풍 선택의 근거는 "사람 얼굴과 감정 연기를 실사로 보여 주는 것이 가장 위험하다"는 간접 증거에 머문다.

### Cited Findings
- 일본 조사(Raycrew, 2026-07-07~08, 20~50대 1,360명): 49.5%가 AI 생성으로 보이는 콘텐츠를 주 몇 회 이상 본다. AI로 알아보는 단서는 "독특한 외형·분위기" 65.6%, "부자연스러운 말투" 47.7%, "AI 라벨·태그" 41.0%, "손·배경 왜곡 같은 시각적 이상" 35.5% 순이다. AI임을 알면 34.3%가 도중에 그만 보고, 44.3%는 다른 출처로 사실을 확인하며, 끝까지 보는 사람은 29.7%뿐이다. — [PR TIMES, Raycrew 조사](https://prtimes.jp/main/html/rd/p/000000050.000125644.html)
- 한국 조사(엠브레인 트렌드모니터, 13~69세 1,200명): 73.9%가 SNS에서 하루 몇 번씩 AI 생성 콘텐츠를 접한다. 55.6%는 "흥미롭지만 자주 보면 부정적 감정이 커진다", 48.0%는 "설명하기 어려운 불편함"을 느낀다고 답했다. AI 광고를 보면 '인위적', '부자연스러움', '어색함'을 먼저 떠올린다. — [아이보스 기사 (엠브레인 인용)](https://www.i-boss.co.kr/ab-2877-16870)(원문 페이지는 403으로 막혀 검색 요약으로만 확인했다). 첫 검색 요약에는 "표정·움직임이 어색한 AI 콘텐츠에 거부감 79.3%"라는 수치가 있었지만 두 번째 검색에서는 확인되지 않았다. 확정 수치로 쓰지 않는다.
- 일본 지상파의 AI 애니메이션 반발(2026-05-28 방송): 여러 프로그램에 생성 AI 애니메이션을 넣었다가 X에서 "보기만 해도 메스껍다", "불쾌한 골짜기"라는 비판과 방송 중단 요구가 쏟아졌다. 기사는 방송사 이름을 정확히 밝히지 않는다(중국어 표기 "日本電視台"는 '일본 TV 방송국'과 '닛폰TV' 둘 다로 읽힌다). — [unwire.hk](https://unwire.hk/2026/05/30/japan-tv-ai-anime-backlash-uncanny-valley/ai/)
- 일본 애니메이션 쪽은 AI 자체에 반발이 크다. 토에이 애니메이션이 AI 도입 계획을 밝혔다가 반발을 받았고 "지금은 쓰지 않는다"고 해명했다. — [Anime Corner](https://animecorner.me/toei-animation-ai-backlash-denies/)
- 모델 평가에서도 같은 약점이 나온다. Design Arena 분석(2026년 7월, Omni Flash)에 따르면 Omni는 감정을 과장하는 경향이 있어 "uncanny"하게 느껴지는 영상이 나오고, 풍경 프롬프트에서는 승률이 14.5%p 떨어지며 "그림 같기보다 애니메이션 같은" 결과를 낸다. — [Design Arena](https://notes.designarena.ai/gemini-omni-flash-a-video-model-for-directors/)
- 얼굴 없는(faceless) 쇼츠 업계 자료는 화풍보다 이야기와 속도가 유지율을 가른다고 본다. "45~60초 설명 쇼츠의 완주율이 최대 76%"라는 수치는 근거가 불분명한 업체 블로그 주장이다. — [saturaai 블로그](https://saturaai.com/blog/faceless-cartoon-animation-channels-arent-magic-theyre-retention-machines-with-ai-syzr_t), [anijam](https://www.anijam.ai/blog/youtube-shorts-trends/)
- 실사풍 AI 여행 영상이 실제 피해로 이어진 사례가 있다. 말레이시아의 존재하지 않는 케이블카 "Kuak Skyride" 영상(Veo 3 생성, 가짜 리포터와 관광객 인터뷰 포함)을 보고 부부가 몇 시간을 운전해 찾아갔다. — [The Standard HK](https://www.thestandard.com.hk/world/article/306539/AI-generated-fake-tourism-video-lures-Malaysian-couple-on-wild-goose-chase), [PhoneArena](https://www.phonearena.com/news/ai-travel-videos-are-getting-so-real-people-are-falling-for-fake-attractions_id172284)
- 서울 명소가 직접 걸린 사례도 있다. 2025년 7월, Veo 3로 만든 "물에 잠긴 경복궁" 영상이 실제 폭우 시기에 퍼졌다. 댓글에는 "가짜 영상 만든 사람에게 책임을 물어야 한다"는 반응이 나왔다. — [Asia News Network (Korea Herald 계열)](https://asianews.network/?p=216059)

### Inferences
- 두 채널 모두 사람 얼굴의 감정 연기를 실사로 보여 주면 거부감 단서("어색한 표정·움직임", "AI 같은 분위기")에 정면으로 걸린다. 스타일화된 3D나 미니어처는 처음부터 "만든 것"으로 읽히므로 "속였다"는 반발이 줄어들 가능성이 높다. 다만 이는 추론이며, 직접 비교한 데이터는 없다.
- 일본 시청자는 AI 애니메이션(특히 셀 애니메이션풍)에 업계 차원의 반감이 있다. ja 채널에서 "anime style"은 피하는 편이 안전하다. 미니어처나 클레이는 일본에서 '장인의 모형·스톱모션' 감성과 맞닿아 있지만, 이를 뒷받침하는 출처는 찾지 못했다.
- 여행 채널이 실사풍 AI로 실제 장소를 보여 주는 것은 Kuak Skyride나 경복궁 침수 영상과 같은 범주로 의심받기 쉽다. 일본 응답자의 44.3%가 "다른 출처로 확인한다"고 답했으므로, 실제와 다른 실사 장면은 신뢰를 직접 깎는다.

### Gaps
- 한국·일본 쇼츠에서 "AI 티 난다"·"AI臭い" 댓글이 화풍별로 얼마나 달리는지 정량 자료를 찾지 못했다. 같은 채널이 화풍을 바꿔 A/B 한 사례도 없다.
- 성공한 AI 지식 쇼츠 채널의 화풍 분포(Kurzgesagt풍 평면 2D, 3D 설명형, 스톡+텍스트)를 집계한 자료가 없다. 업체 블로그의 일화만 있다.
- 실사풍 AI 여행 쇼츠가 일본어권에서 "가짜"로 지적된 구체 사례(서울 대상)는 찾지 못했다.

## 2. 플랫폼 정책: YouTube AI 라벨, 비진정성 콘텐츠, 실제 장소·인물 생성

### Takeaway
2026년 5월부터 YouTube는 실사풍 AI 영상에 눈에 띄는 라벨을 붙인다. Shorts에서는 영상 위에 겹쳐 뜨고, 애니메이션이나 비현실적인 영상은 설명란 안쪽에만 표시된다. 라벨 자체는 추천과 수익에 영향을 주지 않는다고 YouTube가 밝혔다. 다만 실제 장소를 실사로 생성하면 공개 의무 대상이 되고, 사람을 오도할 위험도 생긴다. 수익 쪽 위험은 화풍보다 "템플릿처럼 찍어 낸 반복성"(비진정성 콘텐츠)이다.

### Cited Findings
- YouTube 블로그(2026-05-27): 실사풍이거나 의미 있게 변형된 AI 콘텐츠에는 눈에 띄는 라벨이 붙는다. 긴 영상은 플레이어 바로 아래, Shorts는 "영상 위에 오버레이"로 뜬다. "비현실적이거나 애니메이션이거나 약간만 변형된" 콘텐츠는 펼친 설명란에서만 보인다. 크리에이터가 밝히지 않아도 시스템이 의미 있는 실사풍 AI 사용을 감지하면 자동으로 라벨을 붙인다. Veo 같은 YouTube 자체 AI 도구로 만든 콘텐츠와 C2PA로 완전 생성이 표시된 콘텐츠는 라벨을 뗄 수 없다. "공개 라벨만으로 추천이나 수익 자격이 바뀌지 않는다." — [YouTube 공식 블로그](https://blog.youtube/news-and-events/improving-ai-labels-viewers-creators/), [Social Media Today](https://www.socialmediatoday.com/news/youtube-introduces-more-prominent-ai-labels/821305/)
- YouTube 도움말의 공개 의무 대상: 실제 인물이 하지 않은 말이나 행동을 하게 만드는 것, "실제 사건이나 장소의 영상을 변형하는 것", "실제로 일어나지 않은 사실적인 장면을 생성하는 것". 예시에는 실제 장소의 사실적인 가짜 기상 현상과 홍보용 실제 장소 영상 생성이 있다. 공개하지 않아도 되는 것: 비현실적인 콘텐츠(판타지, **애니메이션**)와 미용 필터나 자막 같은 사소한 수정. "공개만으로 시청자 범위나 수익 자격이 제한되지 않는다." 반복해서 공개하지 않으면 삭제나 YPP 정지 대상이 된다. — [YouTube 도움말: 변형·합성 콘텐츠 공개](https://support.google.com/youtube/answer/14328491?hl=en)(WebFetch 요약으로 읽었다. "홍보용 실제 장소" 예시의 원문 문장은 직접 확인하지 못했다)
- 비진정성(inauthentic) 콘텐츠 정책: 2025-07-15에 "반복 콘텐츠" 정책 이름이 바뀌었다. 대상은 "대량 생산되거나 반복적인 콘텐츠", 영상끼리 차이가 거의 없는 템플릿형, 쉽게 대량 복제할 수 있는 콘텐츠다. AI 사용 자체를 금지하지는 않는다. — [AIR Media-Tech 2026 타임라인](https://air.io/en/monetization/youtube-monetization-policy-changes-2026-a-complete-dated-timeline), [ytgrowth](https://ytgrowth.io/blog/youtube-ai-policy)
- 집행: 대량 생산·저품질 업로드를 이유로 구독자 합계 3,500만 명의 16개 채널이 정리됐다. 판정이 영상 단위에서 채널 단위로 바뀌었다는 보도가 있다(3자 보도, YouTube 원문은 확인하지 못했다). — [logie.ai](https://logie.ai/news/youtube-ai-slop-crackdown-2026-monetization/), [HackerNoon](https://hackernoon.com/youtubes-ai-slop-crackdown-cant-tell-a-directed-ai-film-from-a-bot-farm)
- Neal Mohan의 2026년 편지(2026-01-22 보도): 스팸과 클릭베이트를 막아 온 시스템을 바탕으로 반복적이고 저품질인 AI 콘텐츠를 줄이겠다고 했다. YouTube 자체 AI 도구로 만든 콘텐츠에는 라벨을 붙인다. — [Decrypt](https://decrypt.co/355373/youtube-plans-ai-expansion-2026-promising-crackdown-ai-slop)
- Google/Flow 콘텐츠 정책: Flow 도움말은 "미성년자와 업로드된 인물 사진을 보호하는 장치가 있어 일부 요청은 생성되지 않는다"고만 쓰고, 자세한 내용은 Generative AI Prohibited Use Policy로 넘긴다. 실제 장소를 막는다는 규정은 없다. — [Flow 도움말](https://support.google.com/flow/answer/16353333?hl=en). 그 정책은 공개 없는 사칭, 콘텐츠 출처 오인, 허위 정보를 금지한다. 교육·다큐·예술 목적에는 예외가 있다. — [Search Engine Journal](https://www.searchenginejournal.com/google-refreshes-generative-ai-prohibited-use-policy/535580/)
- Omni Flash(API 프리뷰)가 사용자의 자기 영상에도 "실제 인물 이름·초상" 차단을 건 사례가 개발자 포럼에 보고됐다. — [Google AI 개발자 포럼](https://discuss.ai.google.dev/t/real-peoples-names-or-likenesses-block-on-own-footage-gemini-omni-flash-preview-skyhill-hq/179433)
- 한국 AI기본법(2026-01-22 시행): 생성형 AI 결과물 표시 의무의 직접 주체는 AI 서비스 제공자이고, 개인 크리에이터에게는 법적 의무가 없다. 광고나 협찬이면 표시해야 한다는 해설이 있다. — [헤럴드경제](https://www.heraldk.com/article/2026012118293709444), [브런치 해설](https://brunch.co.kr/@2econd/108)(해설 수준이며 법조문은 직접 확인하지 못했다)

### Inferences
- 실사풍으로 바꾸면 모든 쇼츠 화면 위에 AI 라벨 오버레이가 뜬다. Flow로 만든 영상에는 C2PA/SynthID 메타데이터가 붙을 가능성이 높아 자동 감지도 피하기 어렵다. 스타일화된 3D·미니어처·클레이는 설명란 표시로 끝난다. 수익과 추천에는 영향이 없다고 하지만, 1번의 "AI임을 알면 34.3%가 이탈"과 합치면 오버레이 자체가 이탈 신호가 될 수 있다(추론).
- ja 채널이 실사풍으로 실제 서울 장소를 보여 주면 "실제 장소의 사실적 생성"으로 공개 의무 대상이 되고, 실제와 다르게 그리면 오도 문제까지 생긴다. 미니어처는 "명백히 모형"이라 이 두 위험을 함께 피한다.
- 수익 위험은 화풍보다 반복성에서 나온다. 13장면 모두 같은 머리말에 같은 구도로 찍어 내면 템플릿형으로 보일 수 있다. 화풍은 고정하되 장면마다 카메라와 피사체를 다양하게 하고, 대본과 사실 확인에서 독창성을 보여 주는 쪽이 정책에 맞다.

### Gaps
- Flow나 Omni가 실제 건물(상표·건축물 저작권)을 생성하지 못하게 막는 규정은 찾지 못했다. 경복궁 같은 공공 건축물은 Veo 3로 생성된 사례가 있다.
- Flow 출력물에 C2PA가 실제로 들어가는지, YouTube가 Flow 영상을 자동 라벨링하는지 확인하는 공식 문서를 찾지 못했다.

## 3. 모델 능력: 화풍별 강점과 실패

### Takeaway
Omni Flash는 화풍 전환과 지시 준수가 강하다. 하지만 사람 감정(과장), 여러 인물, 빠른 접촉, 작은 글자, 풍경 사실성에서 약하다. 클레이와 스톱모션은 질감은 잘 내지만 프레임레이트가 오락가락한다. 평면 2D가 3D로 흘러가는지, 서울의 특정 명소(성수 붉은 벽돌, 익선동 한옥)를 아는지에 대한 출처는 없다.

### Cited Findings
- Omni Flash 리뷰(invideo, 2026-06-04, 1.0으로 보인다): Pixar풍, 3D 애니메이션, 클레이, 수공예 클레이로 재스타일하는 것을 "대체로 괜찮게" 처리하지만 "화풍에 따라 드리프트가 생길 수 있다". 스톱모션 시험에서는 "부드러운 움직임과 8~12fps 느낌 사이를 오가는 경향"이 보였다. 립싱크는 6~7초 뒤 무너지고, 여러 인물 대화는 흐트러지며, 복잡한 물체 상호작용의 물리는 성공률이 절반 정도다. — [invideo](https://invideo.io/blog/gemini-omni-flash-review/)
- Design Arena(2026년 7월, Omni Flash): 생성의 81%가 지시를 지켰다(평균 63%). 화면 글자를 읽을 수 있게 그리고, 애니메이션과 제품 콘텐츠에 강하다. 약점은 풍경 사실성(-14.5%p)과 감정 과장이다. — [Design Arena](https://notes.designarena.ai/gemini-omni-flash-a-video-model-for-directors/)
- Omni는 "Gemini의 실세계 지식(물리·역사·과학·문화)"에 기댄다고 소개됐다(I/O 2026-05-19). 1.1(2026-08-27)은 장면 연장, 첫·끝 프레임, 4K 업스케일을 더했다. — [agentpedia 정리](https://agentpedia.codes/blog/gemini-omni-flash-rollout-guide), [Google 8월 업데이트 모음](https://blog.google/innovation-and-ai/technology/google-ai-updates-august-2026/)
- 이전 노트에 따르면 Omni는 작은 글자를 많이 요구하면 지저분하게 그린다. — [Sagnik Bhattacharya](https://sagnikbhattacharya.com/blog/gemini-omni-google-flow). 한·중·일 글자 벤치마크(IMG.LY)는 이미지 모델만 시험했고 Veo/Omni는 다루지 않았다. — [IMG.LY CJK 간판 벤치마크](https://img.ly/ai-benchmarks/prompts/t05-cjk-sign/)
- 실제 도시를 정확히 재현하는 일은 범용 영상 모델의 약점으로 꼽힌다. 네이버는 이 환각을 막으려고 100만 장 넘는 자사 거리뷰로 서울을 기하 기반으로 재현하는 "Seoul World Model"을 따로 만들었다. — [The Decoder](https://the-decoder.com/navers-seoul-world-model-uses-actual-street-view-data-to-stop-ai-from-hallucinating-entire-cities/)
- Veo 3 계열의 클레이는 "몸에 남은 지문, 머리의 이음매"까지 그려 낸다는 평이 있다(커뮤니티 정리). 이미지→영상에서 장면을 다시 묘사하면 원본 프레임과 싸워 드리프트가 생기므로 움직임만 쓰라는 조언도 있다. — [Replicate, Veo 3 프롬프트](https://replicate.com/blog/using-and-prompting-veo-3), [Sider 정리](https://sider.ai/blog/ai-tools/prompt-styles-for-veo-3-dialogue-animation-and-object-scenes-that-pop)
- DeepMind의 Veo 프롬프트 가이드는 화풍을 "cartoon? Claymation? Film noir shot on 35mm? VHS?"처럼 정하라고만 할 뿐, 2D·종이·미니어처 예시는 없다. 스톱모션 예시는 하나다: `Camping (Stop Motion): Camper: "I'm one with nature now!" Bear: "Nature would prefer some personal space."` — [Google DeepMind Veo 프롬프트 가이드](https://deepmind.google/models/veo/prompt-guide/)
- 공식 Veo 3.1 실사 예시(재인용, 화풍 비교 기준점): `Medium shot, a tired corporate worker, rubbing his temples in exhaustion, in front of a bulky 1980s computer in a cluttered office late at night. The scene is lit by the harsh fluorescent overhead lights and the green glow of the monochrome monitor. Retro aesthetic, shot as if on 1980s color film, slightly grainy.` — [Google Cloud Veo 3.1 가이드](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)
- Omni의 재스타일 예시 문구(3자 정리): "stop-motion claymation with warm studio lighting and visible fingerprints in the clay, while keeping the original motion and timing exactly". — [Atlabs Omni 가이드](https://www.atlabs.ai/blog/ultimate-gemini-omni-flash-prompting-guide-2026)(검색 요약)

### Inferences
- 화풍별 위험 순위(추론, 이 저장소의 360p 조건 기준):
  - 실사 사람: 감정 과장, 손, 군중, 립싱크 → 위험 최고
  - 실사 풍경과 실제 장소: 풍경 약점 + 명소 환각 → 높음
  - 평면 2D: 드리프트 근거 없음 → 미확인, 시험 필요
  - 스타일화 3D·클레이·미니어처: 지시 준수와 재스타일 강점 → 낮음. 단 스톱모션 fps 흔들림이 있다
- 클레이와 미니어처에서 "stop-motion"이라는 낱말을 넣으면 8~12fps 흔들림을 부를 수 있다. 질감은 "clay/felt/handmade scale model"로 주고 움직임은 "smooth continuous motion"으로 따로 고정하는 편이 낫다(추론).
- 평면 2D나 Kurzgesagt풍은 Omni에서의 실패 양상(3D로 흐르는지)을 다룬 출처가 없다. 바꾸기 전에 같은 장면 네 개로 비교 생성해 봐야 한다.

### Gaps
- Omni가 광화문, 성수동 붉은 벽돌 창고, 한강 다리, 익선동 한옥, 광장시장을 알아보게 그리는지 시험한 자료가 없다.
- Omni 1.1에서 한글·일본어 간판이 깨지는 정도를 시험한 출처가 없다(이미지 모델 벤치마크만 있다).
- 화풍별로 360p와 720p를 나란히 놓고 비교한 자료가 없다.

## 4. 13장면 일관성: 어떤 화풍이 드리프트에 강하고, 참조 이미지가 얼마나 돕나

### Takeaway
일관성은 화풍보다 참조 이미지(Ingredients)로 잡힌다. Omni는 참조를 1~5장 받고 캐릭터, 장소, 화풍을 각각 붙잡는다. 단순한 형태의 스타일화 마스코트가 실사 인물보다 잡기 쉽다는 것은 업계 통념이며, 정량 근거는 찾지 못했다.

### Cited Findings
- Omni Flash reference-to-video는 참조 이미지를 1~5장 받는다. 이미지는 캐릭터, 장면, 화풍 참조로 쓰이며 반복 캐릭터와 일관된 시각 정체성을 유지하는 데 가장 좋다. "캐릭터 사진, 장소 이미지, 글 설명을 주면 셋의 평균이 아니라 하나의 일관된 클립"을 낸다. — [Atlas Cloud Omni reference-to-video](https://www.atlascloud.ai/models/google/gemini-omni-flash/reference-to-video), [WaveSpeed Omni 가이드](https://wavespeed.ai/blog/ko/posts/what-is-omni-flash/)(API 기준. Flow UI의 슬롯 수는 별도 확인이 필요하다)
- Flow에서는 "사전 지시(pre-context instructions)"로 제품, 브랜드, 색, 화풍을 처음부터 고정할 수 있다. — 위 검색 요약(Android Authority 2026 기사, 원문은 403이라 직접 확인하지 못했다) [Android Authority](https://androidauthority.com/google-flow-gemini-omni-1-1-flash-video-update-3704288)
- Veo 3.1 Ingredients의 세 기둥: 피사체 이미지(정체성 고정), 환경 이미지(배경 고정), 화풍·질감 이미지(룩 고정). 최대 3장. — [Atlas Cloud, Veo 3.1 Ingredients](https://www.atlascloud.ai/blog/guides/how-to-use-veo-3-1-ingredients-to-video-transforming-static-photos-into-cinematic-ai-clips)
- 봉제 인형 "Stuffy"를 사진 한 장으로 올려 캘커타에서 버킹엄궁까지 여행시킨 Flow+Omni 실험(2026-05-24)의 평가는 "SNS 몇 개 올리기엔 충분"이었다. 장소 재현도나 인형 일관성은 평가하지 않았다. — [The Telegraph India t2](https://t2online.in/tech/deep-dive/we-made-an-iced-coffee-ad-campaign-and-a-globetrotting-stuffed-toy-using-google-s-flow-and-gemini-omni-flash/2005268)
- 저장소 실측(이전 보고서): 참조 없이 텍스트만 넣었더니 ko 주인공 옷이 "머스터드 니트"와 "남색 정장" 사이를 오갔고, ja 여행자는 캐리어와 토트백 사이를 오갔다. — `reports/2분 쇼츠 퀄리티 전략.md` 3장

### Inferences
- 13장면 일관성은 "마스코트 1장 + 화풍 기준 프레임 1장(+ 여행 채널은 장소 사진 1장)"을 매 장면 참조로 넣는 방식이 가장 효과적이다. 화풍을 바꾸는 것보다 이 변경이 크다.
- 실사 인물 마스코트는 Flow의 "업로드된 인물 사진" 보호와 실제 인물 차단에 걸릴 수 있다(2번 Flow 도움말, 개발자 포럼 사례). 같은 얼굴을 13장면 내내 유지하기도 어렵다. 스타일화된 마스코트(점토 인형, 봉제 인형, 단순한 3D 캐릭터)가 정책과 일관성 양쪽에서 유리하다(추론).

### Gaps
- 화풍별 클립 사이 드리프트를 수치로 비교한 자료가 없다.
- Flow UI의 Omni 1.1 Ingredients 슬롯 수와 크레딧 추가 여부가 공식 문서에 없다.

## 5. 360p를 1080×1920으로 키울 때 화풍별 가독성과 예산

### Takeaway
낮은 해상도를 키우면 실사는 세부 질감(모공, 천, 잎, 군중)을 잃고 지저분해진다. 큰 면과 단순한 형태는 비교적 덜 무너진다. 예산 안에서 720p는 채널마다 하루 4장면 정도만 쓸 수 있다.

### Cited Findings
- 업스케일러 업계 설명(애니메이션 업스케일러 판매사의 글이라 이해관계가 있다): 실사는 질감, 그레인, 소프트 포커스에 디테일이 숨어 있어 업스케일러가 "그럴듯한 디테일(모공, 천의 올, 잎)을 지어내야" 한다. 평면 색과 선은 따로 다뤄야 하며, 일반 도구로 키우면 선이 깨지고 색 띠(banding)가 생긴다. — [UniFab](https://unifab.ai/resource/best-ai-anime-upscalers.htm), [Aiarty](https://www.aiarty.com/ai-video-enhancer/best-ai-anime-upscalers.htm)
- 360p는 720p를 줄인 것이 아니라 따로 생성한 초안이고, 구도 확인용이다. 1080p 업스케일은 Plus 이상 무료다. 크레딧은 Omni Flash 8초 기준 360p 6, 720p 12다. — 이전 보고서 3장 ([Flow 도움말, 크레딧](https://support.google.com/flow/answer/16526234?hl=en), [Hora de Codar](https://horadecodar.com.br/gemini-omni-1-1-flash-360p/))

### Inferences
- 예산 계산(재시도 제외): 2채널 × 13장면 × 30일 = 780클립.
  - 전부 360p면 4,680크레딧이고, 6,300에서 1,620이 남는다.
  - 720p로 올리면 클립당 6크레딧이 더 들므로 남는 1,620으로 한 달 270클립, 즉 하루 9클립(채널당 4~5장면)을 올릴 수 있다.
  - 한 채널만 전부 720p로 하면 하루 234크레딧, 한 달 7,020크레딧으로 예산을 넘는다.
  - 재시도 몫을 남기려면 "채널당 첫 장면 + 재훅 2장면 = 3장면 720p"(하루 36크레딧 추가, 한 달 5,760)가 현실적이다.
- 화풍별 360p 내성(추론): 매트한 클레이와 미니어처의 큰 면 > 스타일화 3D(매끈한 재질) > 평면 2D(선과 색 띠 위험이 있지만 얇은 선을 피하면 괜찮다) > 실사(군중, 피부, 나뭇잎이 뭉개진다). 두 채널 모두 `layout = "clean"`이라 클립이 화면 전체를 채우므로 이 차이가 그대로 드러난다.
- 360p에서는 작은 글자, 가는 선, 많은 사람, 먼 풍경을 프롬프트에서 빼는 것이 화풍 선택만큼 중요하다. 피사체 하나를 가까이 크게 잡는다.

### Gaps
- Flow의 1080p 업스케일이 360p 원본에 적용되는지, 결과가 화풍별로 어떻게 다른지 공식 자료가 없다. 직접 시험해야 한다.

## 6. 혼합안과 여행 채널의 "진짜 장소 보여 주기"

### Takeaway
여러 방식을 섞는 방법은 이미 업계에서 쓰인다. 화면에 글자 없는 영상에 자막을 얹고, 참조 사진으로 장소를 고정하고, 마스코트를 일정하게 유지한다. 하지만 "실제 장소 사진을 참조로 넣으면 미니어처로도 성수·익선동·광장시장을 알아볼 수 있게 그린다"는 것을 보여 준 출처는 찾지 못했다. 이것은 이 파이프라인이 직접 시험해야 할 첫 번째 질문이다.

### Cited Findings
- Omni는 캐릭터 사진, 장소 이미지, 글 설명을 하나의 일관된 클립으로 합친다고 소개됐다(API 정리). — [WaveSpeed](https://wavespeed.ai/blog/ko/posts/what-is-omni-flash/), [Atlas Cloud](https://www.atlascloud.ai/models/google/gemini-omni-flash/reference-to-video)
- Veo 3.1 Ingredients는 환경 이미지로 "캐릭터가 안정적이고 알아볼 수 있는 공간에 머물게" 한다고 소개됐다. — [Atlas Cloud Veo 3.1](https://www.atlascloud.ai/blog/guides/how-to-use-veo-3-1-ingredients-to-video-transforming-static-photos-into-cinematic-ai-clips)
- Omni의 재스타일(영상→영상)은 움직임과 타이밍을 유지한 채 룩만 클레이 등으로 바꿀 수 있다. 실사 영상이나 사진을 미니어처·클레이로 옮기는 근거로 쓸 수 있다. — [Atlabs](https://www.atlabs.ai/blog/ultimate-gemini-omni-flash-prompting-guide-2026), [invideo](https://invideo.io/blog/gemini-omni-flash-review/)
- Omni는 작은 글자 다량 요구에 약하다(3번). 정확한 화살표와 이름표는 ASS/ffmpeg로 얹는 것이 이전 보고서의 결론이었다.

### Inferences
- ja 채널의 장소 재현은 다음 순서로 시도한다(추론).
  1. 장소마다 실제 사진(직접 찍었거나 라이선스가 있는 것) 한 장을 "장소 참조"로 넣는다.
  2. 프롬프트에는 그 장소를 알아보게 하는 형태 단서 두세 개만 쓴다. 성수는 `red-brick warehouse facades with large steel-framed windows`, 익선동은 `narrow alleys of low hanok houses with curved grey tile roofs`, 광장시장은 `rows of covered food stalls with steaming pots under warm bulbs`처럼 쓴다.
  3. 화풍은 `handmade scale model` 재료 말로 고정한다.
  4. 간판 글자는 비우고, 장소 이름은 자막으로 넣는다.
- ja 채널에서 실사 B-roll과 미니어처 마스코트를 섞는 안은 실사 클립에 YouTube 라벨 오버레이 조건과 "실제 장소의 사실적 생성" 공개 의무가 함께 걸린다. 그래서 권하지 않는다. 실사가 꼭 필요하면 AI 생성이 아니라 직접 찍은 사진이나 영상(라이선스 확보)을 그 장면에만 쓰는 쪽이 정책과 신뢰 양쪽에서 안전하다(추론, 파이프라인 변경이 필요하다).
- ko 채널에서는 실사 혼합이 필요 없다. 상식 주제는 실제 장소를 증명할 필요가 적고, 대상(물체, 몸, 원리)을 스타일화 3D로 보여 주는 편이 360p, 라벨, 일관성 모두에서 유리하다.

### Gaps
- 실제 장소 사진을 참조로 넣어 미니어처나 클레이로 생성했을 때 그 장소로 알아볼 수 있었다는 크리에이터 사례(한국어·일본어·영어)를 찾지 못했다.
- 실사 B-roll과 스타일화 마스코트를 섞은 AI 여행 쇼츠의 성과 자료가 없다.

## 7. 채널별 권고 (위 근거의 종합, 추론)

### Takeaway
- (A) ko 상식: 지금의 스타일화 3D를 유지하되, 물체·원리 중심의 단순한 형태와 고정 마스코트 참조로 다듬는다. 실사 사람은 쓰지 않는다.
- (B) ja 서울 여행: 미니어처를 유지하되, 실제 장소 사진 참조와 형태 단서로 "진짜 장소"를 보여 주고, "stop-motion"과 "tilt-shift" 낱말은 뺀다. 실사 AI는 쓰지 않는다.
- 두 채널 모두 화면 속 글자를 없애고 모든 글자를 ASS로 넣는다. 720p는 첫 장면과 재훅 장면에만 쓴다.

### Cited Findings
- 근거는 1~6번의 출처를 그대로 쓴다. 실사 AI의 Shorts 오버레이 라벨([YouTube 블로그](https://blog.youtube/news-and-events/improving-ai-labels-viewers-creators/)), 실제 장소 생성의 공개 의무([YouTube 도움말](https://support.google.com/youtube/answer/14328491?hl=en)), AI임을 알면 34.3% 이탈([Raycrew](https://prtimes.jp/main/html/rd/p/000000050.000125644.html)), Omni의 감정 과장과 풍경 약점([Design Arena](https://notes.designarena.ai/gemini-omni-flash-a-video-model-for-directors/)), 스톱모션 fps 흔들림([invideo](https://invideo.io/blog/gemini-omni-flash-review/)), 참조 1~5장([Atlas Cloud](https://www.atlascloud.ai/models/google/gemini-omni-flash/reference-to-video))이다.

### Inferences
- 화풍별 판정 요약(◎ 좋음, ○ 보통, △ 약함, × 피함):

| 화풍 | 시청자 반응 | 정책·라벨 | 모델 능력(Omni) | 360p 내성 | 13장면 일관성 | ko 상식 | ja 서울 여행 |
|---|---|---|---|---|---|---|---|
| 스타일화 3D(지금 ko) | ○ 만든 것으로 읽힘 | ◎ 설명란 표시 | ◎ 강점 | ○ | ○ 참조로 ◎ | **채택** | ○ |
| 실사풍 AI | △ 표정·분위기 거부감 | × 오버레이 + 실제 장소 공개 의무 | △ 감정 과장·풍경 약점 | × | △ 인물 차단 위험 | × | × 오도 위험 |
| 평면 2D·모션그래픽 | ○ 근거 없음 | ◎ | ? 드리프트 미확인 | ○ 띠 위험 | ? | 시험 후보 | △ 장소감 약함 |
| 미니어처·클레이(지금 ja) | ○ 공예 느낌(근거 약함) | ◎ | ○ 질감 ◎, fps 흔들림 △ | ◎ 매트한 큰 면 | ○ 참조로 ◎ | ○ | **채택** |
| 종이 오려 내기 | 근거 없음 | ◎ | 근거 없음 | ○ | 근거 없음 | 보류 | 보류 |
| 애니메·일러스트 | △ 일본 AI 애니 반발 | ◎ | ○ | ○ | ○ | △ | × |

- ko 머리말 수정안(검증 전 초안이다. 이전 보고서의 규칙인 "한 컷, 소리 따로"는 그대로 둔다): `Stylized 3D animated explainer with simple rounded shapes and smooth matte materials, one clear subject large in frame, soft even daylight, warm muted colors, no readable text or signs anywhere, same art style in every shot.` 마스코트 그림 한 장을 매 장면 참조로 붙인다.
- ja 머리말 수정안(검증 전 초안): `Macro photography of a handmade scale model of Seoul: hand-painted miniature buildings, clay and felt textures, model-railway scale figures, smooth continuous camera motion, soft warm daylight, signs left blank, same art style in every shot.` 장면마다 장소 사진 한 장과 마스코트 한 장을 참조로 붙이고, 장소 형태 단서는 장면 프롬프트에 쓴다.
- 결정 전 시험(같은 장면 4개씩, 360p로 한 번에 약 24~48크레딧):
  1. ja: 성수, 익선동, 광장시장 각각에 "참조 사진 있음/없음"을 비교한다. 일본인 시청자 관점에서 알아볼 수 있는지 본다.
  2. ko: 지금 3D와 평면 2D(`flat 2D vector motion graphics, bold shapes, limited palette`)를 비교한다. 2D가 3D로 흐르는지, 360p에서 버티는지 본다.
  3. 둘 다: 360p→1080p 업스케일 결과를 화풍별로 본다.

### Gaps
- 위 권고는 직접 비교 실험 없이 정책, 모델 리뷰, 일반 조사에서 추론한 것이다. 시청자 반응의 화풍별 차이는 업로드 후 지표(초반 이탈, 시청 지속률)로 확인해야 한다.

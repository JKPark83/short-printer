# 쇼츠 첫 1~3초와 시청 유지: 왜 초반에 넘기고, 어떤 오프닝이 그걸 줄이나

조사일: 2026-10-29. 표시 규칙: **[플랫폼 공식]** YouTube·TikTok·Meta가 직접 밝힌 것, **[크리에이터 데이터]** 실제 데이터셋을 공개한 분석, **[학술]** 논문, **[통설·검증 안 됨]** 출처가 블로그 집계뿐이거나 원문을 못 찾은 것.

## (a) 첫 몇 초에 "넘길지"가 어떻게 정해지나

### Takeaway
Shorts 피드에는 클릭이라는 "고른다"는 단계가 없어서, 재생이 시작된 뒤 처음 몇 초가 사실상 썸네일이자 제목 노릇을 한다. YouTube는 이 구간을 "Stayed to watch / Engaged views"로 따로 재고, 독립 연구에서도 넘기기(swipe)는 영상 맨 앞과 맨 끝에 몰린다. 첫 화면 노출과 기억은 0.25~1초 안에 생긴다.

### Cited Findings
- [플랫폼 공식] YouTube Studio 정의: **Stayed to watch** = "The percentage of times viewers stayed to watch past the initial seconds of a Short." **Engaged views** = "How many times viewers stayed to watch past the initial seconds, not including any loops." **Average percentage viewed** = "Average percentage of a video watched among those who stayed to watch." 즉 평균 시청 비율은 첫 몇 초를 넘긴 사람만으로 센다. "initial seconds"가 정확히 몇 초인지는 공개하지 않는다. — [YouTube Help: Understand your YouTube content performance](https://support.google.com/youtube/answer/12220281)
- [플랫폼 공식] 2025-03-31부터 Shorts "조회수"는 재생·다시 재생이 시작될 때마다 최소 시청 시간 없이 센다. 예전 조회수(일정 초 이상 본 것)는 이름이 "Engaged views"로 바뀌어 고급 분석에 남았다. 그래서 2025년 4월 이후의 "조회수"는 오프닝 성과를 보여 주지 못하고, 훅 성과는 Engaged views/조회수 비율(=Stayed to watch)로 봐야 한다. — [PPC Land, 2025](https://ppc.land/youtube-changes-how-shorts-views-are-counted-from-march-31/); [Digital Music News, 2025-03-27](https://www.digitalmusicnews.com/2025/03/27/how-does-youtube-shorts-count-views-2025/)
- [플랫폼 공식] Shorts 제품 책임자 Todd Sherman(Creator Insider, 2023): 롱폼은 시청자가 탭해서 고르지만 Shorts는 피드를 넘기며 발견하므로, 실제 영상을 틀어 보고 남는지(retention) 떠나는지(swipe away)를 봐야 한다. "Don't think algorithm, think audience. The audience is the algorithm." — [TechCrunch, 2023-08-25](https://techcrunch.com/2023/08/25/youtube-demystifies-the-shorts-algorithm-views-and-answers-other-creator-questions/); [vidIQ 요약](https://vidiq.com/blog/post/youtube-shorts-algorithm/)
- [플랫폼 공식] Jenny Hoyos(YouTube 공식 블로그 대담, 2025-01-28): "I really do think you have one second to hook someone, especially on Shorts." 또 "99.9% of the views are coming from the Shorts feed"라서 썸네일은 발견에 거의 안 쓰인다. — [YouTube Blog: Shorts deep dive with Todd Sherman and Jenny Hoyos](https://blog.youtube/creator-and-artist-stories/youtube-shorts-deep-dive/)
- [학술] Dashlet(NSDI 2023, TikTok류 시청 실험): 넘기기는 영상 재생 직후와 끝에 몰린다. 넘기기의 29%는 영상 앞 20% 안에서, 42%는 마지막 20%에서 일어났다. — [Dashlet, arXiv 2204.12954](https://arxiv.org/pdf/2204.12954)
- [학술] 마이크로 영상 추천 연구(AAAI 2025): 넘기기 대부분이 처음 5초 안에 일어나며, 짧은 시간 안의 넘기기는 강한 부정 신호, 늦은 넘기기는 약한 긍정 신호로 따로 다뤄야 추천이 좋아진다. 플랫폼 추천기가 "얼마나 빨리 넘겼나"를 신호로 쓴다는 방향의 근거. — [Exploiting Fine-Grained Skip Behaviors for Micro-Video Recommendation, AAAI](https://arxiv.org/html/2504.03107v1)
- [학술] 숏폼 QoE 크라우드소싱 연구: 시작 지연(initial delay)은 끊김(stalling)보다 처음 10초 안에 넘길 확률을 3배 높였다. 첫 프레임까지 걸리는 시간·첫 화면의 정지감이 그대로 이탈로 이어진다는 근거. — [Swiping, fast and slow (Uni Augsburg)](https://opus.bibliothek.uni-augsburg.de/opus4/frontdoor/index/index/docId/125900)
- [플랫폼 공식, 오래됨] Facebook IQ(2016, Fors Marsh Group 연구): 모바일 피드 콘텐츠는 0.25초 노출만으로 통계적으로 유의하게 기억된다. 모바일에서 한 콘텐츠에 머무는 평균 시간은 1.7초(데스크톱 2.5초). — [Marketing Dive](https://www.marketingdive.com/news/facebook-why-mobile-video-ads-must-work-fast/446217/); [Social Media Today](https://www.socialmediatoday.com/news/facebook-releases-new-guide-to-help-advertisers-maximize-video-ad-performan/450818)
- [통설·검증 안 됨] "Meta 2025 Attention Study, 1,200만 Reels 노출, 스크롤 결정 시간 1.3초"는 집계 블로그에만 있고 Meta 원문을 찾지 못했다. 인용하지 않는 게 낫다. — [blog.mean.ceo (집계)](https://blog.mean.ceo/video-hook-retention-statistics/)

### Inferences
- "넘길까"는 소리·자막을 다 듣기 전, 첫 프레임과 첫 낱말 1~2개로 정해진다(0.25~1.7초 노출 자료, Hoyos의 "1초"). 그러니 첫 문장 전체보다 **첫 프레임 + 첫 2~4음절**이 승부처다. 말이 늦게 시작하거나 첫 화면이 정적이면 질문의 질과 상관없이 잃는다.
- 끝 20%에 넘기기가 몰리는 건 숏폼 특성이라 정상이다. 개선할 곳은 앞 20%다.

### Gaps
- YouTube가 "initial seconds"를 몇 초로 보는지는 공개되지 않았다(흔히 1~3초로 추정하지만 공식 근거 없음).
- Creator Insider 영상 원문(MediaPost 기사)은 403으로 못 읽어 Sherman 발언은 TechCrunch·vidIQ 요약으로만 확인했다.

## (b) 실제로 붙잡는 훅 유형(화면·말·자막)

### Takeaway
공식·데이터 근거가 가장 튼튼한 건 ① 핵심 메시지를 처음 3초 안에 내놓기, ② 소리 없이도 무슨 영상인지 아는 첫 화면, ③ 구체적이고 짧은 첫 문장(중앙 11낱말), ④ "이/저"처럼 화면 속 물체를 가리키는 말과 "당신" 시점이다. 패턴 깨기·오픈 루프는 널리 권해지지만 숏폼에서 따로 측정한 연구는 찾지 못했다.

### Cited Findings
- [플랫폼 공식] TikTok(2020-10-21): "over 63% of all videos with the highest click-through rate (CTR) highlight their key message or product within the first 3 seconds." 최고 VTR 광고의 40%가 효과·스티커 있는 자막(text overlay)을, 3분의 1이 카메라를 보고 시청자에게 직접 말하는(4th wall) 방식을 썼다. 광고 데이터라 일반 콘텐츠와는 다를 수 있다. — [TikTok for Business: 9 creative tips](https://ads.tiktok.com/business/en-US/blog/9-creative-tips-to-drive-auction-ad-performance)
- [크리에이터 데이터] Overseer 연구(2026-08-13, 100만 조회 이상 영어 영상 3,966개 훅: Shorts 1,178개/367채널, 롱폼 2,788개/739채널, 같은 채널 74개 비교). 훅 = 자막 첫 150낱말 중 6~25낱말 완결 문장. 결과: 훅 길이 중앙 Shorts 11낱말·롱폼 12낱말(같은 채널에서도 유지). "you" 쓰는 비율 Shorts 36.8% vs 롱폼 31.0%(같은 채널 34.5% vs 27.9%, 차이 유지). "this/that" 지시어 12.6% vs 4.3%(같은 채널 7.2% vs 3.9%, 유지). 숫자 9.8% vs 16.2%(같은 채널 15.5% vs 14.5%, 차이 사라짐). 예: 롱폼 "Most people think this tiny hole in an airplane window is a manufacturing mistake..." → Shorts "This tiny hole in an airplane window is there to protect you." 한계: 성공작만 본 연구라 인과가 아니다. "Many supposed 'Shorts hook differences' were really differences between the creators, channels, eras, and content." — [Overseer: We Compared 1,178 YouTube Shorts Hooks With 2,788 Long-Form Hooks](https://www.overseeros.com/blog/youtube-shorts-hooks-study)
- [크리에이터 조언] Jenny Hoyos: "It needs to be so good that you can be watching the video on mute and still know what it's about." 예시 첫 3초 "$1 chicken sandwich"(군말 없이 대상·숫자). 기법: 결말 미리 보여 주기(foreshadowing), "Did you know about this...?", 웃음·울음 같은 감정 반응으로 시작. 구조는 shock → intrigue → satisfy, 이야기 마디를 "but"·"so"로 잇는다. — [vidIQ, 2023-11-29](https://vidiq.com/blog/post/how-jenny-hoyos-gets-10m-views-per-youtube-short/); [YouTube Blog, 2025-01-28](https://blog.youtube/creator-and-artist-stories/youtube-shorts-deep-dive/)
- [크리에이터 조언] Hoyos는 첫 프레임을 스케치로 여러 번 그려 보고, 초점 하나만 있는 단순한 화면을 고른다. "banned", "free", "one dollar", "secret", "cheap" 같은 강한 낱말을 쓴다. — [Marketing Examined: Jenny Hoyos playbook](https://www.marketingexamined.com/blog/jenny-hoyos-short-form-video-playbook); [Medium 요약](https://magus523.medium.com/i-can-make-anything-go-viral-7c2205be919c) (2차 요약이라 낮은 신뢰)
- [크리에이터 데이터] MrBeast 제작 가이드(2024-09 유출, 전직 PD 2명이 진위 확인): "The first minute captures the viewer's attention and demonstrates that their expectations from the thumbnail will be met." 6,000만 클릭 중 첫 1분에 2,100만 이탈이면 "꽤 좋은" 편. 롱폼 기준이지만 "오프닝은 약속을 지킨다는 증명"이라는 원칙은 숏폼 첫 문장(=썸네일 역할)에 그대로 옮겨진다. — [Simon Willison, 2024-09-15](https://simonwillison.net/2024/Sep/15/how-to-succeed-in-mrbeast-production/); [Netinfluencer](https://www.netinfluencer.com/mrbeast-productions-leaked-internal-document-rosanna-pansino/)
- [학술] 정보 격차 이론: Loewenstein은 호기심을 "a cognitive induced deprivation that arises from the perception of a gap in knowledge and understanding"으로 정의했다. Wojtowicz & Loewenstein은 호기심을 주의 배분의 핵심 힘으로 본다. 게임 광고 연구에서는 끝을 안 보여 준(특히 지는 장면) 미완결 영상이 완결 영상보다 관심을 더 끌었다. — [Frontiers in Psychology 2024](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2024.1374649/full)
- [학술] Molina et al.(CHI 2021) 서술에 따르면 호기심 격차가 생기려면 모르는 게 있다는 걸 알아채야 하고, 그 정보가 곧 채워질 것 같아야 하며, 점진적 해결보다 통찰(빠른 답)을 줄 것 같아야 커진다. — [Molina et al., "Does Clickbait Actually Attract More Clicks?", CHI 2021](https://pike.psu.edu/publications/chi21.pdf)
- [통설·검증 안 됨] "미완결 시각 훅이 자막 훅보다 3초 유지율 2.4배(VidMob 2025)"는 집계 블로그에만 있고 VidMob 원문을 못 찾았다. — [blog.mean.ceo (집계)](https://blog.mean.ceo/video-hook-retention-statistics/)
- [통설·검증 안 됨] "Paddy Galloway: 처음 2초에 훅이 있는 Shorts가 19% 더 남는다", "VVSA 70~90%가 최고"도 AI 영상툴 블로그 집계에만 있다. Galloway 원 분석(2023, 33채널 Shorts 5,400개)에서 확인되는 건 길이·AVD 결과뿐이다(아래 (d)). — [gofaceless.ai (집계)](https://www.gofaceless.ai/blog/mastering-first-impressions-two-second-rule); [Digital Information World, 2023-04](https://www.digitalinformationworld.com/2023/04/paddy-galloway-decoded-youtube-shorts.html)

### Inferences
- 근거가 겹치는 지점: **첫 화면에 대상 하나 + 첫 문장에 그 대상의 이름(이/저 + 명사) + 의외의 주장**. Overseer의 비행기 창문 예가 이 모양이고, Hoyos의 "$1 chicken sandwich", TikTok의 "3초 안에 핵심"과도 맞는다.
- "Most people think X"(통념 → 반전)는 롱폼 꼴이고, Shorts에서는 통념 부분을 빼고 반전 결론을 먼저 말하는 쪽으로 줄었다(같은 소재의 두 판 비교). 짧을수록 결론을 먼저.
- 패턴 깨기·오픈 루프는 이론(정보 격차)과 실무 통설은 있지만, 숏폼에서 이걸 따로 떼어 측정한 공개 데이터는 못 찾았다.

### Gaps
- 화면(시각) 훅, 말 훅, 자막 훅을 따로 떼어 비교한 공개 A/B 데이터는 못 찾았다(VidMob 수치는 원문 미확인).
- 한국어 쇼츠만 다룬 데이터셋은 못 찾았다. 모든 정량 근거는 영어권이다.

## (c) 그냥 묻는 질문·공감 질문("~하죠?", "Ever wondered why…?")이 왜 약한가

### Takeaway
"물음표" 자체가 문제가 아니라, **구체적인 대상·이해관계 없이 막연한 호기심만 건드리는 질문**이 약하다. 통제 실험에서 질문 제목은 평서 제목보다 클릭이 적거나 차이가 없었고 신뢰도는 낮았다. 숏폼 데이터에서도 질문 훅은 "바닥"은 평서문과 같고 "천장"만 높은데, 이긴 질문은 모두 구체적 필요를 겨눈 것이었다.

### Cited Findings
- [학술, 통제 실험] Molina et al.(CHI 2021): 같은 기사에 클릭베이트 특징을 하나씩만 넣은 제목 실험에서, 평범한(비클릭베이트) 제목이 "read more" 클릭될 오즈가 **질문 제목보다 1.97배**(p=.003), modal 제목보다 2.22배, 부정 최상급보다 1.81배, 긍정 최상급보다 1.68배 높았다. 지시형 형용사(this/that)·목록·"wh" 제목은 평범한 제목과 비슷했다. 목록 제목은 질문 제목보다 1.63배 더 클릭됐다(p=.04). 공유에는 차이가 없었다. "clickbait did not generate more curiosity than non-clickbait." — [Molina et al., CHI 2021](https://pike.psu.edu/publications/chi21.pdf)
- [학술 인용] 같은 논문이 인용한 Lockwood의 학술 논문 제목 분석: 긍정적·흥분되는 틀은 주목을 늘렸지만 제목을 질문으로 바꾸는 건 차이가 없었고, 말장난은 주목을 줄였다. — [Molina et al., CHI 2021](https://pike.psu.edu/publications/chi21.pdf)
- [실험] KQED·Engaging News Project 과학 뉴스 제목 실험(2019, 2022 갱신): 평서·전방 지시(forward-referencing)·질문 세 꼴 사이에 고르는 비율·참여 의향 차이는 없었지만, 질문 제목은 덜 믿을 만하다고 봤고(특히 밀레니얼) "fake news"나 "satire"로 분류되는 일이 더 많았다. 예: 평서 "Scientists Still Don't Know if Little Earthquakes Lead to a Big One" / 전방 지시 "Here's what Little Earthquakes Tell Scientists About the Likelihood of the Big One" / 질문 "Do Little Earthquakes Mean the Big One is Close at Hand?" — [KQED](https://www.kqed.org/about/13722/experimenting-with-science-news-headline-format-to-maximize-engagement); [journalism.co.uk](https://www.journalism.co.uk/readers-perceive-question-based-headlines-more-negatively-study-shows/)
- [크리에이터 데이터, 반대 방향] Content Labs(2026-08-20, TikTok·Instagram 14,424개, 355계정, 계정 평소 조회 대비): 질문 훅 평균 10.08배 vs 평서 7.04배(+43%). 하지만 평소의 2배를 넘긴 비율은 질문 30.4% vs 평서 29.9%로 거의 같다. "questions raise the ceiling, not the floor." 이긴 질문은 구체적 필요를 겨눴다: "How to answer one of the trickiest job interview questions"(2,888배), "Hey mom. Who inspired you to be an entrepreneur?"(2,404배). "the question mark isn't magic. The open loop is." 평균은 소수 대박에 끌려 올라간 값이고, 자막·화면 글자는 분석에서 뺐다. — [The Content Labs: Question Hooks Get 43% More Views](https://thecontentlabs.app/blog/question-hooks-data-study)
- [크리에이터 데이터] Overseer: 묶어 보면 Shorts 훅의 23.4%가 질문(롱폼 11.8%)이지만, 같은 채널끼리 비교하면 10.8% vs 10.6%로 차이가 사라진다. "Shorts는 질문으로 시작해야 한다"는 건 채널 구성 차이에서 생긴 착시다. — [Overseer](https://www.overseeros.com/blog/youtube-shorts-hooks-study)
- [통설·검증 안 됨] OpusClip 블로그: "Did you know that...?" 질문 훅 3초 유지 50~58%, 명령형 평서 훅 57~63%. 방법론 공개 없음. — [OpusClip: TikTok Hook Formulas](https://www.opus.pro/blog/tiktok-hook-formulas)

### Inferences
- 막연한 질문·공감 질문이 약한 이유를 근거에 맞춰 나누면:
  1. **격차가 안 생긴다**: "~하죠?", "궁금하지 않으셨나요?"는 모르는 걸 짚지 않고 시청자에게 "궁금한지"를 묻는다. Loewenstein 조건(모르는 게 구체적으로 보여야 함)이 안 채워진다.
  2. **신뢰를 깎는다**: 질문 꼴 자체가 낚시·풍자로 읽히기 쉽다(KQED). 지식 채널에는 특히 손해다.
  3. **첫 1초에 정보가 없다**: "여러분 혹시…"는 앞 2~4음절에 대상·숫자·주장이 없어, 넘길지 정하는 순간에 줄 게 없다((a) 참고).
  4. **"예/아니오"로 닫힌다**: "~하죠?"에 "응, 알아" 하는 순간 볼 이유가 끝난다. 반면 이긴 질문(Content Labs 예)은 "어떻게 답하나"처럼 열린 답이 실용적이다.
- 그러니 질문을 버릴 필요는 없다. **구체적 대상 + 의외의 사실을 먼저 말하고, 질문은 그 뒤에 "왜일까"로 붙이면** 질문의 천장 효과를 살리면서 바닥 위험을 줄인다.

### Gaps
- 숏폼 **영상**에서 같은 영상에 질문/평서 오프닝만 바꾼 통제 A/B 공개 자료는 못 찾았다(위 근거는 제목 실험 + 관찰 데이터셋).
- 한국어 "~하죠?"·"~아시나요?" 꼴만 떼어 본 자료는 없다.

## (d) 숫자 기준: 3초 유지, Viewed vs Swiped away, 60~90초 교양 쇼츠의 곡선

### Takeaway
YouTube는 Stayed to watch의 "좋은 값"을 공식으로 주지 않는다. 흔히 도는 "75~80% 이상"은 크리에이터 통설이다. 확인된 데이터로는 Galloway(2023)의 "50~60초 Shorts가 가장 많이 보이고 AVD 50초 넘는 Shorts가 평균 410만 회"가 가장 단단하다.

### Cited Findings
- [크리에이터 데이터] Paddy Galloway·Chris Gileta(2023-04, 33채널 Shorts 5,400개, 33억 회 조회): 50~60초 Shorts가 조회가 가장 많았다(대부분 크리에이터는 20~40초를 만든다). AVD 50초 넘는 Shorts 평균 410만 회 vs AVD 40~50초 180만 회. Shorts RPM은 길이와 상관없이 약 6센트. — [Digital Information World, 2023-04](https://www.digitalinformationworld.com/2023/04/paddy-galloway-decoded-youtube-shorts.html); [videogen.io 요약](https://videogen.io/blog/decoding-the-youtube-shorts-algorithm-a-deep-dive-into-3-3-billion-views)
- [통설] Viewed vs Swiped away 목표 "75~80% 이상 viewed". 근거 데이터 공개 없음. — [Subscribr](https://subscribr.ai/youtube-strategy/youtube-shorts-analytics-metrics-growth)
- [통설·검증 안 됨] "Galloway 33억 회 분석: VVSA 70~90%가 최고, 60% 아래면 배포가 급히 꺼진다"는 2차 블로그에만 있다. Galloway 원문 요약(위)에는 없다. — [gofaceless.ai](https://www.gofaceless.ai/blog/mastering-first-impressions-two-second-rule)
- [통설·검증 안 됨] "5만 개 숏폼 분석: 3초 유지 중앙 50~58%, 상위 20% 60~70%, 상위 5% 75% 이상, 2차 배포 조건 3초 60%+, 중간 지점 45%+" — 방법론 미공개. — [blog.mean.ceo](https://blog.mean.ceo/video-hook-retention-statistics/); [grow-it.se](https://www.grow-it.se/en/resources/short-form-video-retention-benchmarks)
- [통설·검증 안 됨] "이탈하는 사람의 50~60%가 처음 3초에 떠난다" — 같은 계열 집계. 다만 방향은 Dashlet(앞 20%에 넘기기 29%)과 AAAI 논문(대부분 5초 안)과 맞는다. — [blog.mean.ceo](https://blog.mean.ceo/video-hook-retention-statistics/); [Dashlet](https://arxiv.org/pdf/2204.12954)
- [통설] TikTok 3초 유지 65% 넘는 영상이 노출 4~7배 — TikTok 원문에는 없고 2차 검색 요약에서만 나왔다. — [TikTok for Business](https://ads.tiktok.com/business/en-US/blog/9-creative-tips-to-drive-auction-ad-performance) (원문에 해당 수치 없음을 확인)
- [플랫폼 공식] YouTube 평균 시청 비율은 "stayed to watch"한 사람만 기준으로 센다. 그래서 오프닝이 약하면 Stayed to watch가 떨어지고, 오프닝이 낚시면 Stayed는 높아도 평균 시청 비율이 떨어진다. 둘을 같이 봐야 한다. — [YouTube Help](https://support.google.com/youtube/answer/12220281)

### Inferences
- 60~90초 교양 쇼츠의 곡선: 첫 1~3초에 가파른 낙차(Stayed to watch로 잡힘) → 중간은 완만한 하강 → 끝 20%에서 넘기기 몰림(Dashlet) 모양을 예상할 수 있다. 개선 우선순위는 ① 첫 낙차 줄이기 ② 끝 직전 "다 알았다" 이탈을 막는 마지막 반전 배치.
- 쓸 만한 내부 목표는 플랫폼 수치가 아니라 **우리 채널 중앙값 대비**로 잡는 게 맞다(Content Labs·Overseer 모두 계정 기준 정규화가 핵심이었다).

### Gaps
- 60~90초 교양 쇼츠만 모은 공개 유지 곡선 데이터는 못 찾았다.
- YouTube 공식 "좋은 Stayed to watch" 기준은 없다.

## (e) 60~90초 교양 쇼츠의 첫 5초 구성(훅 문장 + 반전 + 약속)

### Takeaway
근거들이 같은 방향을 가리킨다: 0~1초에 대상 하나를 화면에 보여 주며 그 대상을 가리키는 의외의 주장, 1~3초에 "그런데/사실은"으로 통념을 뒤집거나 이해관계를 걸고, 3~5초에 무엇을 알게 될지 약속(답은 뒤로 미룸). 말이 첫 프레임과 동시에 시작해야 한다.

### Cited Findings
- [플랫폼 공식] 핵심 메시지를 첫 3초 안에. — [TikTok for Business](https://ads.tiktok.com/business/en-US/blog/9-creative-tips-to-drive-auction-ad-performance)
- [크리에이터 조언] shock → intrigue → satisfy, 마디를 "but"·"so"로 잇기, 음소거로도 알 수 있는 첫 화면, 결말 미리 보여 주기. — [vidIQ: Jenny Hoyos](https://vidiq.com/blog/post/how-jenny-hoyos-gets-10m-views-per-youtube-short/)
- [크리에이터 데이터] Shorts 훅은 중앙 11낱말, "this/that"과 "you"가 많다. 결론형 문장("This tiny hole … is there to protect you."). — [Overseer](https://www.overseeros.com/blog/youtube-shorts-hooks-study)
- [크리에이터 조언] 오프닝은 썸네일이 건 기대가 채워질 거라는 증명. — [MrBeast 가이드 via Simon Willison](https://simonwillison.net/2024/Sep/15/how-to-succeed-in-mrbeast-production/)
- [학술] 정보가 곧 채워질 것 같고 통찰을 줄 것 같을 때 호기심이 커진다. — [Molina et al., CHI 2021](https://pike.psu.edu/publications/chi21.pdf)
- [학술] 시작 지연은 넘기기를 크게 늘린다. — [Swiping, fast and slow](https://opus.bibliothek.uni-augsburg.de/opus4/frontdoor/index/index/docId/125900)

### Inferences
- 첫 5초 틀(위 근거를 합친 제안, 검증된 공식 아님):
  - 0~1초 **[대상 + 의외의 결론]**: 화면에 물체·몸 부위 하나, 첫 낱말이 "이 ○○" 또는 숫자. 자막 맨 위에 같은 말.
  - 1~3초 **[반전/이해관계]**: "그런데", "사실은", "근데 이게 ○○ 때문이에요"처럼 통념을 뒤집거나 시청자 몸·돈·시간에 걸린 걸 말한다.
  - 3~5초 **[약속]**: "이유는 딱 하나예요", "끝까지 보면 ○○할 때 달라집니다"처럼 답이 곧 온다는 신호. 답 자체는 아직 안 준다.
- 한국어 첫 문장 후보(약한 꼴 → 고친 꼴):
  - 약함 "여러분, 하품은 왜 옮을까요?" → "**하품은 개한테도 옮아요.** 그런데 낯선 사람 하품은 덜 옮습니다. 이유는 뇌의 한 부위예요."
  - 약함 "손톱에 하얀 점, 다들 있으시죠?" → "**손톱의 이 하얀 점, 칼슘 부족이 아니에요.** 진짜 원인은 따로 있습니다."
  - 약함 "비행기 창문에 구멍 있는 거 아셨나요?" → "**비행기 창문의 이 작은 구멍이 당신 목숨을 지킵니다.**"(Overseer 예를 옮김)
  - 약함 "물 많이 마시면 좋다고 하죠?" → "**하루 물 2리터, 근거가 없는 숫자예요.** 출발은 1945년 문장 하나였습니다."(사실 확인 필요한 예시)
  - 약함 "왼쪽으로 자면 좋을까요?" → "**자는 방향 하나로 속쓰림이 달라집니다.** 왼쪽과 오른쪽, 차이가 꽤 커요."
  - 질문을 살리는 꼴: 사실 먼저, 질문은 뒤에 — "**바나나는 방사능이 있어요.** 그럼 몇 개 먹으면 위험할까요?"
- 피할 것: "여러분/혹시/다들" 같은 대상 없는 시작어, 예/아니오로 닫히는 "~하죠?·~아시나요?", 인사·채널 소개, 첫 프레임 정지 화면.
- 위 예시 속 사실(하품·하얀 점·물 2리터·바나나)은 꼴을 보이려는 것이고 대본에 쓰기 전에 출처 확인이 필요하다.

### Gaps
- 이 5초 틀을 한국어 교양 쇼츠에서 A/B로 검증한 자료는 없다. 채널 안에서 오프닝만 바꿔 Stayed to watch·평균 시청 비율을 비교해 보는 게 유일한 확인 방법이다.

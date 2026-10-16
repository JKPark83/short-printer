# 2분(1.5~3분) 해설 쇼츠의 대본 구조와 내레이션 기법 (2025~2026)

> 출처 품질 메모: 이 주제의 웹 자료 대부분은 AI 도구 회사의 SEO 블로그(subscribr.ai, virvid.ai, faceless.so, gofaceless.ai, outlierkit 등)라서, 1차 데이터가 아닌 "권장"으로만 다뤘다. 1차 또는 준1차 자료는 YouTube 공식 블로그, Paddy Galloway의 Shorts 연구(5,400편), MrBeast 제작 문서(롱폼 대상), Netflix 자막 가이드, James Cutting의 샷 길이 연구, NHK 출신 아나운서 발언뿐이다. Jon Youshaei, Colin & Samir, Film Booth, vidIQ의 2분 쇼츠 전용 템플릿은 찾지 못했다(Gaps 참고).
>
> 프로젝트 맥락(로컬 확인): 지금 `channels/ko-40sec-facts`는 7장면, 문장 62~68자, 미스터킴 TTS 기준 초당 약 8.8자, 52~56초. `channels/ja-korea-trip`은 7장면, 문장 50~56자, 미나미 기준 초당 약 7.2자, 50~56초. 둘 다 "한 문장 = 8초 클립 하나"다. 2분이면 같은 방식으로 약 15장면이 된다.

## 1. 검증된 2분 구조 템플릿과 타이밍, 이탈 지점

### Takeaway
2분 쇼츠도 첫 1~3초에 "볼지 넘길지"가 정해지고(Viewed vs Swiped), 그 뒤로는 완주율(AVP)이 길이보다 중요하다. 실무 구조는 "훅 → 약속 → 비트 2~3개(각자 작은 보상) → 반전/최대 보상 → 즉시 끝"이고, 공개된 1차 데이터로 검증된 정확한 2분 타이밍표는 없다.

### Cited Findings
- YouTube는 2024년 10월 15일부터 정사각형 이상 세로 비율 영상을 최대 3분까지 Shorts로 올릴 수 있게 했다(그전에는 60초). — [YouTube Official Blog](https://blog.youtube/news-and-events/tall-updates-coming-to-shorts/); [Tubefilter](https://www.tubefilter.com/2024/10/03/youtube-shorts-three-minutes-max-length-redesign-trends-templates/)
- Paddy Galloway 연구(33채널, 쇼츠 5,400편): 대부분 30~40초였지만 50~60초 구간이 더 잘 됐다(평균 최대 170만 회). AVD가 50초를 넘는 쇼츠는 평균 410만 회, 40~50초 AVD는 180만 회였다. "Viewed vs swiped away"가 60% 미만이면 성과가 나빴고 70~90%면 좋았다. — [Digital Information World 요약](https://www.digitalinformationworld.com/2023/04/paddy-galloway-decoded-youtube-shorts.html); [Paddy Galloway X 스레드](https://x.com/PaddyG96/status/1646898356419981315)
  - 주의: 이 연구는 2023년 4월, 즉 60초 제한 시절 자료다. "AVD 50초+ = 조회수 높음"은 길이를 늘리라는 뜻이 아니라 오래 붙잡으라는 뜻으로 읽어야 한다.
- 기준치(2차 자료): Viewed vs Swiped 비율은 70~80% 이상을 목표로, 넘김이 40%를 넘으면 첫 장면·훅 실패 신호다. — [Subscribr](https://subscribr.ai/youtube-strategy/youtube-shorts-analytics-metrics-viral); [Creator Essentials](https://www.creatoressentials.com/glossary/viewed-vs-swiped-away/)
- 2분 쇼츠가 90% 완주하면 3분 쇼츠 25% 완주보다 우선 노출된다는 주장(시청 시간 총량이 더 적어도). 출처가 SEO 블로그라 검증되지 않은 주장이다. — [OutlierKit](https://outlierkit.com/resources/youtube-script-template/)
- 쇼츠 기본 구조로 "훅(0~3초) → 본론(가치 전달·과정·이야기) → 해결(훅이 던진 질문에 답) → 아웃트로 없이 바로 끝"을 권한다. — [Subscribr](https://subscribr.ai/p/perfect-youtube-short-length-structure-hooks)
- 일본 실무 자료도 "フック(冒頭3秒)→本編→CTA" 3단이 중심이며, 첫 부분에서 "나와 상관없다"고 판단되면 바로 이탈하고 그 이탈률이 추천 평가를 떨어뜨린다고 본다. 성과의 8할은 구성이 정한다고 말한다. — [tatap.jp](https://tatap.jp/knowledge/short-video-production/); [yoshikazunomori.com](https://yoshikazunomori.com/blog/digitalmarketing/how-to-create-ai-short-videos-2/)
- 일본 자료 중 일부는 쇼츠가 최대 3분까지 되지만 "짧을수록 알고리즘에 잘 탄다"며 15~60초 설계를 원칙으로 권한다(근거 데이터 없음). — [crexgroup.com](https://crexgroup.com/ja/marketing/content-seo/youtube-video-structure-template/)
- MrBeast 제작 문서(롱폼 대상): 첫 1분에서 가장 많이 이탈하므로 첫 1분에 가장 공을 들인다. "Stop telling people what they will be watching and start showing them." 첫 3분 안에 여러 날을 압축해 이야기에 빨리 몰입시킨다("crazy progression"). 3분과 6분에 "re-engagement"(이야기에 맞고 진짜 감탄하게 하는 내용)를 넣는다. "If we can get them to watch the first half of the video there's a very high chance they'll watch to the end." "For 50 million people to understand something it must be simple." — [How to succeed in MrBeast production (전문)](https://www.alexanderjarvis.com/memo-how-to-succeed-in-mrbeast-production/); 진위 확인: [Passionfruit](https://passionfru.it/?p=81151)
- NHK 출신 아나운서 호리오 마사아키: 뉴스 시청자의 집중력은 70초 정도만 이어지므로 한 주제는 70초 안팎으로 말해야 하고, 핵심("あんこ")은 하나여야 한다. — [現代ビジネス(gendai.media)](https://gendai.media/articles/-/42472)
- 일본어로 정보 하나를 전하기에 가장 이해하기 쉬운 길이가 1분 10초~1분 30초라는 NHK 관련 자료(검색 요약, 원문 미확인). — [newswitch.jp](https://newswitch.jp/image/16276)

### Inferences
- MrBeast의 "1분/3분/6분" 비율을 2분 쇼츠에 줄여 쓰면 대략 "첫 3초 → 첫 15~20초(몰입 구간) → 중간(약 50~60초)의 재몰입 → 후반 최대 보상"이 된다. "전반을 보면 끝까지 본다"는 말에 따르면 첫 60초 구간에 가장 강한 장면을 몰아넣어야 한다. 이건 비율을 옮긴 추론이지 측정된 값은 아니다.
- 호리오의 "70초 집중 + 핵심은 하나"는 2분을 "주제 하나를 70초씩 두 덩어리"로 나누는 근거가 된다. 즉 2분 쇼츠 = 1부(질문과 첫 답) + 재훅 + 2부(더 깊은 답과 반전).
- 제안하는 2분 뼈대(8초 클립 15장면 기준, 장면 = 문장):
  - 장면 1(0~8초): 훅. 결과·이상한 사실·질문을 바로 말한다. 인사·채널 소개 금지.
  - 장면 2(8~16초): 약속. "끝까지 보면 ~를 알게 된다/세 번째가 제일 놀랍다".
  - 장면 3~6(16~48초): 비트 1. 배경과 첫 번째 작은 보상.
  - 장면 7(48~56초): 재훅 1. "그런데 진짜 이유는 따로 있다" 같은 열린 고리.
  - 장면 8~11(56~88초): 비트 2. 두 번째 보상.
  - 장면 12(88~96초): 재훅 2/반전 예고.
  - 장면 13~14(96~112초): 반전·최대 보상.
  - 장면 15(112~120초): 짧은 정리 + 첫 문장으로 이어지는 마무리(루프) 또는 한 줄 CTA. 아웃트로 없음.
- 이 프로젝트의 지금 길이(50~56초, 7장면)에서 2분으로 늘리면 관건은 Viewed vs Swiped가 아니라 중간 이탈이다. 첫 7장면 구조는 그대로 두고 장면 7·12에 재훅을 박는 쪽이 고칠 곳이 가장 적다.

### Gaps
- 2분 쇼츠의 구간별 이탈 곡선(어느 초에서 많이 빠지는지)을 공개한 1차 데이터를 찾지 못했다. Paddy Galloway 연구는 60초 시절 자료다.
- Colin & Samir, Film Booth, vidIQ, Jon Youshaei가 1.5~3분 쇼츠 전용 템플릿을 낸 1차 자료를 찾지 못했다(검색 결과는 AI 도구 블로그뿐).
- YouTube가 3분 쇼츠를 짧은 쇼츠보다 덜/더 밀어주는지 공식 자료는 없다.

## 2. 15~25초마다 재훅 쓰는 법과 열린 고리 문구

### Takeaway
재훅은 "아직 답하지 않은 질문을 다시 상기시키거나, 새 질문을 여는 한 문장"이다. 권장 간격은 출처마다 30~90초로 제각각이고 2분 쇼츠에 맞춘 측정값은 없으므로, 70초 집중 한계와 문장=장면 구조를 고려해 약 40~50초(5~6장면)마다 하나가 현실적이다.

### Cited Findings
- 열린 고리(open loop): 보상을 질문·빈칸으로 먼저 말하면, 넘기는 것이 곧 답을 버리는 일이 되어 남는다. 예: "I tested the most-hated editing trick for 30 days". 잘 되는 훅 세 가지: 준비 과정 말고 결과·실수·놀라운 장면에서 시작, 보상을 질문·빈칸으로 제시, 로고·"안녕하세요"·채널 소개 같은 서두를 전부 자르기. — [socialk.it](https://socialk.it/en/blog/youtube-video-hook-formulas); [gofaceless.ai](https://www.gofaceless.ai/en/blog/high-retention-youtube-shorts-attributes)
- 숫자형 호기심 훅 틀: "{숫자} {실수/것} I made before {결과}". — [faceless.so](https://faceless.so/blog/15-video-hook-formulas-to-increase-watch-time-1)
- 패턴 인터럽트(말투 변화·시각 요소·새 관점·놀라운 수치)를 30~45초마다 넣으라는 권장, 그리고 재훅은 60~90초마다라는 권장이 서로 다르게 나온다(둘 다 SEO 블로그). — [TubeAI](https://learn.tubeai.app/blog/youtube-script-writing-retention); [OutlierKit](https://outlierkit.com/resources/youtube-script-template/)
- 긴 영상에서는 40~60% 지점에 "아직 이게 남았다"는 앞으로 가리키기(forward reference)를 넣어 건너뛰기를 손해처럼 느끼게 하라. — [OutlierKit](https://outlierkit.com/resources/youtube-script-template/)
- 일본 자료: 전환점마다 再フック를 두는 챕터 구성으로 다음 챕터까지 붙잡는다. 본편 영상에는 中だるみ(중간 늘어짐) 대책으로 미니 훅 여러 개를 둔다. — [crexgroup.com](https://crexgroup.com/ja/marketing/content-seo/youtube-video-structure-template/)
- MrBeast 문서의 re-engagement 정의: "content that is highly interested that fits the story and makes people genuinely impressed" — 즉 말로 예고만 하지 말고 실제로 감탄할 내용을 그 자리에 둔다. — [MrBeast production memo](https://www.alexanderjarvis.com/memo-how-to-succeed-in-mrbeast-production/)
- 훅은 주제나 질문을 던지되 핵심 비밀이나 답은 바로 주지 말라. — [Subscribr](https://subscribr.ai/p/perfect-youtube-short-length-structure-hooks)

### Inferences
- 재훅 문구 틀(한국어/일본어, TTS로 읽기 좋은 꼴). 출처가 있는 원칙(질문·빈칸으로 보상 미루기, 앞으로 가리키기)을 이 채널 말투로 옮긴 예시다:
  - 반전 예고: "그런데 진짜 이유는 따로 있어요." / 「でも、本当の理由は別にあるんです。」
  - 순위 미루기: "세 번째가 제일 중요한데, 그 전에…" / 「3つ目が一番大事なんですが、その前に…」
  - 오해 깨기: "여기까지는 다들 아는 얘기고요." / 「ここまでは知ってる人も多いはず。」
  - 손해 강조: "이걸 모르면 ~에서 돈을 그대로 버립니다." / 「これを知らないと、〇〇で損します。」
  - 수치 던지기: "그 차이가 무려 ○배입니다." / 「その差、なんと○倍。」
- 재훅은 그 자리에서 바로 작은 보상을 주어야 한다(MrBeast의 "감탄할 내용"). 예고만 하고 늦게 주면 "낚시"로 느껴져 오히려 이탈한다는 것은 추론이다.
- 문장=장면 구조에서는 재훅 문장을 "장면 하나"로 따로 두고, 그 장면 클립은 직전 장면과 화풍·구도가 확 다르게(클로즈업→와이드 등) 만들면 말과 그림이 동시에 패턴을 깬다.
- 2분 = 15장면이면 재훅 2개(장면 7, 12 전후)가 적당하다. "15~25초마다"를 그대로 지키면 장면 2~3개마다 재훅이 되어 본론이 쪼개진다. 이 판단은 추론이며 A/B로 확인할 일이다.

### Gaps
- 재훅 간격(15초 vs 30초 vs 60초)별 유지율을 비교한 데이터는 찾지 못했다.
- Jon Youshaei의 훅 공식 원문(그의 "Hook" 관련 영상·뉴스레터)은 검색에 나오지 않았다.

## 3. 내레이션 밀도: 일본어·한국어 TTS의 초당 글자 수

### Takeaway
방송 기준으로 일본어는 분당 300~400자(초당 5~6.7자), 한국어 뉴스는 분당 500~550자(초당 8.3~9.2자, 공백 포함 여부 불명)가 "알아듣기 쉬운" 속도다. 지금 설정은 한국어 8.8자/초(뉴스 속도와 같음), 일본어 7.2자/초(NHK 권장보다 빠름)다. 2분 길이에서는 같은 속도를 2배 오래 들어야 하므로, 특히 일본어는 6~6.7자/초로 낮추는 것을 검토할 만하다.

### Cited Findings
- NHK는 분당 300자를 기준으로 쓴다는 말이 있고, 분당 400자가 가장 알아듣기 쉬운 속도로 아나운서 기준이며 스포츠 중계처럼 힘이 필요한 곳은 분당 600자까지 올린다. 연습법으로 "15초에 100자"(=분당 400자). — [president.jp](https://president.jp/articles/-/13791); [東洋経済](https://toyokeizai.net/articles/-/567541?display=b) (검색 요약 기준, 두 수치가 출처마다 다름)
- 한국어 뉴스 리딩은 분당 500~550자(CPM) 정도의 빠른 방송 톤이 일반적이다. — [howmanywords.app](https://howmanywords.app/ko/블로그/1분연설단어수) (2차 자료, 공백 포함 여부 미기재)
- 한국 아나운서 18명 연구: 낭독에서 발화 속도를 늦추면 늘어난 시간의 대부분은 문장 사이 쉼(휴지)이고, 음절 자체 길이는 조금만 늘어난다. — [koreascience.kr](https://koreascience.kr/article/JAKO199520828542266.pdf)
- (로컬) 지금 채널 설정: 한국어 미스터킴 약 8.8자/초, 일본어 미나미 약 7.2자/초, 한 문장이 8초 클립을 거의 다 채우도록 맞춤. — `channels/*/channel.toml` 주석

### Inferences
- 일본어 7.2자/초 = 분당 약 430자로, NHK "가장 알아듣기 쉬운" 400자보다 조금 빠르다. 50초 동안은 괜찮아도 2분 동안은 피로가 쌓일 수 있다. 문장 길이를 50~56자 → 46~52자 정도로 줄이거나, ElevenLabs 속도를 약간 낮추면 약 6.5자/초가 된다.
- 한국어 8.8자/초는 뉴스 속도 범위 안이라 2분에서도 바로 문제는 아니다. 다만 위 휴지 연구처럼 "천천히"는 음절을 늘리기보다 문장 사이 쉼으로 만드는 게 자연스럽다. 재훅 문장 앞뒤에 0.3~0.5초 쉼을 두는 것이 속도 전체를 낮추는 것보다 낫다(추론).
- 2분에서는 문장 하나가 8초를 꽉 채우는 대신 6~7초 말 + 1초 쉼(소리·효과음)으로 리듬을 주면, 시청자가 따라올 틈이 생기고 클립 길이(8초)와도 맞는다.

### Gaps
- 세로 영상 + 자막 상황에서 일본어·한국어 TTS의 "편한" 속도를 측정한 연구는 찾지 못했다.
- ElevenLabs 일본어·한국어 목소리별 기본 발화 속도 공개 자료는 찾지 못했다(지금 값은 프로젝트에서 직접 잰 값).

## 4. 화면 전환 빈도: 2분 해설에서 몇 초마다 장면을 바꿀까

### Takeaway
측정된 근거는 영화의 평균 샷 길이(현대 약 3~4초)뿐이고, 쇼츠·해설 영상의 전환 빈도와 유지율을 잇는 공개 데이터는 찾지 못했다. 8초 AI 클립을 문장마다 하나씩 쓰는 지금 구조는 영화 기준보다 2배 느리므로, 클립 안에서 자막·확대·컷 변화로 4초 안팎마다 "무언가"가 바뀌게 하는 쪽이 안전하다.

### Cited Findings
- James Cutting(Cornell)의 1935~2005년 인기 영화 150편 분석: 평균 샷 길이는 1960년대 8~10초에서 2005년 3~4초로 줄었다. 최근 흥행작의 샷 길이 변동은 사람 주의력의 1/f 변동 패턴에 가까워졌다. — [Cornell Chronicle](https://news.cornell.edu/node/271563); [PMC 논문](https://pmc.ncbi.nlm.nih.gov/articles/PMC3485803/)
- 쇼츠 패턴 인터럽트로 시각 요소·새 관점을 30~45초마다 넣으라는 권장(근거 데이터 없음). — [TubeAI](https://learn.tubeai.app/blog/youtube-script-writing-retention)
- MrBeast 문서: 무엇을 볼지 말하지 말고 보여 주라. — [MrBeast production memo](https://www.alexanderjarvis.com/memo-how-to-succeed-in-mrbeast-production/)

### Inferences
- 문장=장면=8초는 영화 평균(3~4초)의 2배 길이라, 2분 동안 15번만 화면이 바뀐다. 클립 자체를 4초로 자르기(8초 클립에서 서로 다른 4초 두 개, 또는 장면당 클립 2개)를 검토할 만하다. 비용(Flow 크레딧)은 그대로 두고 8초 클립을 앞 4초/뒤 4초로 나눠 쓰거나, 4초 지점에 확대(Ken Burns)·반전 컷을 넣는 방법이 있다.
- Cutting의 1/f 결과는 "일정한 간격"보다 "길고 짧은 샷이 섞인 리듬"이 주의를 붙잡는다는 뜻으로 읽을 수 있다. 재훅·반전 장면은 짧게, 설명 장면은 길게 두는 식.
- 자막 덩어리가 바뀌는 것도 시각 변화다. 자막을 1.5~2.5초 단위로 끊으면 클립이 8초여도 화면에서 무언가는 2초마다 바뀐다.

### Gaps
- 쇼츠의 컷 빈도와 유지율 상관을 분석한 1차 자료(플랫폼 공개 또는 학술)는 찾지 못했다.
- AI 생성 클립(움직임이 느리고 반복적인)이 유지율에 주는 영향 데이터는 없다.

## 5. 긴 내레이션 쇼츠의 자막(번인) 길이·위치·강조

### Takeaway
방송 자막 기준으로 한국어는 한 줄 16자·초당 12자 이하, 일본어는 한 줄 13자(가로)·초당 4자 이하, 둘 다 최대 2줄이다. 일본어 내레이션(7.2자/초)은 자막을 다 읽을 수 없는 속도라서, 번인 자막은 "전문 받아쓰기"보다 "핵심어 보조"로 짧게 끊는 쪽이 맞다.

### Cited Findings
- Netflix 한국어 자막: 읽기 속도 성인 최대 초당 12자(어린이 9자), 한 줄 16자(라틴 문자·공백·문장부호는 0.5자), 최대 2줄, 넘치지 않으면 한 줄, 두 줄일 때는 아래가 무거운 피라미드 모양을 권한다. — [Netflix Korean Timed Text Style Guide](https://partnerhelp.netflixstudios.com/hc/en-us/articles/216001127)
- Netflix 일본어 자막: 초당 최대 4자, 가로 한 줄 최대 13자(세로 11자), 최대 2줄, 한 자막 최소 0.5초. SDH(청각장애인용)는 초당 7자, 가로 16자까지. — [Netflix Japanese Timed Text Style Guide](https://partnerhelp.netflixstudios.com/hc/en-us/articles/215767517-Japanese-Timed-Text-Style-Guide)
- 쇼츠 화면 위아래 UI를 피해야 한다는 점은 이 프로젝트 `layout = "full"` 설명(위아래 250px 회피)에 이미 반영돼 있다. — 로컬 `.claude/rules/channels.md`

### Inferences
- 한국어: 8.8자/초 내레이션은 Netflix 읽기 한도 12자/초 안이라 전문 자막이 가능하다. 자막 덩어리는 한 줄 16자 이하(공백 포함 대략 12~16자)로 끊으면 약 1.5~2초마다 바뀐다.
- 일본어: 내레이션 7.2자/초는 일반 자막 한도(4자/초)의 거의 2배, SDH 한도(7자/초)와 비슷하다. 2분 내내 전문 자막을 읽게 하면 피로하다. 한 덩어리 13자 이하로 짧게 끊고, 핵심어(숫자·지명·가격)를 강조색으로 칠하는 쪽이 낫다.
- 2분에서는 강조어를 문장마다 1개로 제한하면, 시청자가 강조색만 따라가도 줄거리를 잡는다. 이는 Netflix 기준이 아니라 추론이다.

### Gaps
- 세로 쇼츠의 자막 위치(가운데 vs 아래)·단어 강조가 유지율에 주는 효과를 측정한 1차 자료는 찾지 못했다.
- Netflix 기준은 번역 자막용이라, 원어 내레이션을 그대로 받아쓴 번인 자막(소리와 함께 읽음)에서는 더 빨라도 될 가능성이 있다(측정값 없음).

## 6. "여행 팁" 형식과 "상식/사실" 형식의 차이

### Takeaway
두 형식을 2분 길이에서 직접 비교한 데이터는 찾지 못했다. 원칙 수준에서는 "나와 상관있다"를 첫 3초에 보여 줘야 한다는 점이 공통이고, 여행 팁은 실용·손해 회피 훅, 상식은 호기심 빈칸 훅이 기본이다.

### Cited Findings
- 첫 부분에서 "나와 상관없다(自分には関係ない)"고 판단되면 즉시 이탈한다. — [tatap.jp](https://tatap.jp/knowledge/short-video-production/)
- 숫자형 목록 훅("{숫자} {실수}…")과 결과부터 보여 주는 훅이 잘 된다는 주장. — [faceless.so](https://faceless.so/blog/15-video-hook-formulas-to-increase-watch-time-1); [gofaceless.ai](https://www.gofaceless.ai/en/blog/high-retention-youtube-shorts-attributes)
- 호리오: 한 덩어리에 핵심은 하나("あんこはひとつ"). — [現代ビジネス](https://gendai.media/articles/-/42472)

### Inferences
- 여행 팁(ja-korea-trip): 시청자가 "저장하고 나중에 쓰는" 형식이라, 2분 목록형(5곳/5팁)도 버틸 수 있다. 첫 장면에서 장소·결과(가게 안·가격)를 보여 주고, 각 팁 끝에 구체 정보(역 이름·가격)를 작은 보상으로 둔다. 손해 회피 훅("이거 모르면 ○○원 더 냅니다")이 잘 맞는다.
- 상식(ko-40sec-facts): 호기심 빈칸 하나로 2분을 끌기 어렵다. "질문 하나 → 첫 답 → '그런데 진짜 이유는' → 더 깊은 답 → 반전" 깊이 파기형이 자연스럽다.

### Gaps
- 여행 팁 대 상식 형식의 2분 유지율 비교 데이터는 찾지 못했다.

## 7. 목록형(3가지/5가지) vs 반전 있는 깊이 파기형

### Takeaway
1차 비교 데이터는 없다. 원칙(핵심 하나, 70초 집중, 열린 고리)으로 보면, 목록형은 "마지막 항목이 제일 중요하다"는 열린 고리를 걸면 2분에 잘 맞고, 깊이 파기형은 70초 지점의 반전이 있어야 버틴다.

### Cited Findings
- 숫자형 목록 훅이 잘 된다는 주장(데이터 없음). — [faceless.so](https://faceless.so/blog/15-video-hook-formulas-to-increase-watch-time-1)
- 긴 영상에서 중간에 "아직 남은 것"을 앞으로 가리키면 건너뛰기를 손해로 느끼게 한다. — [OutlierKit](https://outlierkit.com/resources/youtube-script-template/)
- 집중은 약 70초, 핵심은 하나. — [現代ビジネス](https://gendai.media/articles/-/42472)
- 쇼츠는 해결 뒤 아웃트로 없이 바로 끝낸다. — [Subscribr](https://subscribr.ai/p/perfect-youtube-short-length-structure-hooks)
- 루프 구조(끝 문장이 첫 문장으로 이어지게)가 재시청을 늘린다는 주장(데이터 미공개). — [virvid.ai](https://virvid.ai/blog/looping-structure-shorts-retention-2026)

### Inferences
- 목록형 2분: 항목 3개 × 약 35초(장면 4개)가 맞다. 5개면 항목당 장면 3개(24초)라 설명이 얕아진다. 순서는 2번째로 강한 것 → 약한 것 → 가장 강한 것, 그리고 훅에서 "마지막 게 제일 놀랍다"를 예고(앞으로 가리키기)한다.
- 깊이 파기형 2분: 70초 덩어리 두 개. 1부 끝(장면 7~8)에 반전으로 넘어가는 재훅을 둔다.
- 45초 쇼츠와의 차이 정리(추론 포함):
  - 45초: 훅 → 답 하나 → 끝. 재훅이 필요 없고, 루프가 주 무기.
  - 2분: 약속(무엇을 얻는지) 문장, 재훅 2개, 비트마다 작은 보상, 반전이 더 필요하다. 넘김률(Viewed vs Swiped)보다 중간 이탈이 성패를 가르므로, 첫 60초에 가장 강한 장면을 몰고 아웃트로는 그대로 없다.
  - 루프 마무리는 2분에서는 재시청 효과가 작을 수 있다(2분 다시 보기는 부담). 한 줄 요약 + 다음 영상 예고가 대안이다(추론).

### Gaps
- 목록형 대 깊이 파기형의 1.5~3분 쇼츠 성과 비교 데이터를 찾지 못했다.
- 2분 쇼츠에서 루프 마무리의 효과 데이터는 없다.

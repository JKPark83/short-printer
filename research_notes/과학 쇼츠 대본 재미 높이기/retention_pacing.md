# 100~110초 설명형 쇼츠의 서사 페이싱과 유지율

(범위: 이전 보고서 `reports/2분 쇼츠 퀄리티 전략.md`가 이미 다룬 것, 즉 첫 2초 훅, 1/3·3/4 지점 재훅, Paddy Galloway 5,400편 AVD 분석, MrBeast 문서의 "재몰입" 정의, 재훅 간격 논쟁은 되풀이하지 않는다. 여기서는 보상 배치·고조·열린 고리의 질·재훅 강약·엔딩·이탈 패턴만 다룬다.)

표기: **[측정]** = 표본·방법이 있는 데이터, **[공식]** = YouTube 직접 발언·문서, **[경험]** = 크리에이터·컨설턴트의 경험칙(측정 근거 없음), **[2차]** = 출처 불명확한 요약 글.

## 1. YouTube 공식 입장: Shorts에서 무엇이 유지 신호인가

### Takeaway
YouTube가 공개한 Shorts 신호는 "본 것 vs 넘긴 것"과 "engaged view(처음 몇 초를 넘겨 본 것)" 두 가지뿐이고, 유지율·루프·만족도의 가중치는 한 번도 공개되지 않았다. 2026년 8월 24일부터 공개 조회수는 첫 프레임부터 세지만 분석 지표(AVD·유지율)는 여전히 engaged view 기준이라, 대본 품질은 조회수가 아니라 Studio의 engaged view·유지율 곡선으로 봐야 한다.

### Cited Findings
- [공식] Shorts 제품 책임자 Todd Sherman(Creator Insider, 2023-08-23): Shorts는 "그 영상을 좋아할 만한 사람들 무리를 찾아 보여 주고, 결과에 따라 트래픽이 크게 늘거나 줄어든다", "The audience is the algorithm." 길이·게시 시간·업로드 빈도에는 이상값이 없다고 했다 — [OutlierKit 정리(원 영상 타임스탬프 링크 포함)](https://outlierkit.com/resources/youtube-shorts-algorithm/), 원 영상 https://www.youtube.com/watch?v=n3jsYK_-aRU
- [공식] Sherman: "What we try and do with a view is to have it encode for your intent of watching that thing." 롱폼은 사람이 영상을 고르지만 숏폼은 "피드를 넘기며 발견한다" — [Search Engine Journal](https://searchenginejournal.com/youtube-explains-how-shorts-algorithm-works/494953)
- [공식] YouTube는 유지율·루프·만족도 설문의 Shorts 순위 가중치를 공개한 적이 없다(정리 글 작성자의 확인) — [OutlierKit](https://outlierkit.com/resources/youtube-shorts-algorithm/)
- [공식] 2025-03-31부터 Shorts 조회는 재생 시작·재시청 시마다 최소 시청 시간 없이 센다. 기존 정의는 "engaged views"로 분리되고 수익화·성과 분석은 engaged views 기준 — [PPC Land](https://ppc.land/youtube-changes-how-shorts-views-are-counted-from-march-31/), [Routenote](https://routenote.com/blog/how-are-views-counted-shorts-tiktok-reels/)
- [공식] 2026-08-24부터 모든 형식(Shorts·롱폼·라이브)의 view를 "첫 프레임부터" 센다. Engaged view = "clicking to watch or watching past the initial seconds". CTR·평균 시청 시간·유지율은 "anchored on engaged views"이고 YPP 자격도 engaged views 기준 그대로. Short가 피드에서 자동 재생되는 순간 view, 몇 초 넘게 보면 engaged view — [YouTube 공식 블로그](https://blog.youtube/inside-youtube/engaged-views-youtube-explained/)
- [공식/2차] Shorts 분석의 "본 것 vs 넘긴 것(Viewed vs swiped away)"은 피드에 떴을 때 넘기지 않고 본 비율. 여러 정리 글이 70~80% 이상을 목표로 제시하지만 이 기준선은 YouTube가 아니라 글쓴이들의 경험칙 — [Social Media Examiner](https://www.socialmediaexaminer.com/how-to-analyze-your-youtube-shorts/), [Subscribr](https://subscribr.ai/youtube-strategy/youtube-shorts-analytics-metrics-viral)
- [2차] YouTube 도움말 기반 정리: 유지율 곡선의 약점은 "시작(훅·첫 프레임)·중간·보상(payoff)" 셋으로 나눠 진단하고, "시작은 강한데 중간에서 급락하는 영상은 첫 프레임이 약한 영상과 다른 처방이 필요하다". 길이 구간(15~30초, 30~60초, 그 이상)끼리만 비교하라. 보편 기준선은 없고 채널 내 상대 비교만 의미 있다 — [Bytecap(자체 데이터 없는 문서 종합이라고 명시)](https://www.bytecap.io/research/youtube-shorts-retention-benchmarks)

### Inferences
- 우리 채널에서 "평면적 대본" 문제는 "넘긴 비율"(훅)이 아니라 유지율 곡선의 중간 기울기와 끝부분에서 드러날 것이다. 대본 개선의 효과는 같은 100~110초 영상끼리 유지율 곡선을 겹쳐 봐야 판정할 수 있다(Bytecap 권고와 일치).
- 2026-08 정의 변경 이후 공개 조회수는 노출에 가까워져 대본 품질과 더 멀어졌다. 검증 지표는 engaged views 비율, 평균 시청 비율, 곡선의 장면 5·10 근처 기울기로 잡아야 한다.

### Gaps
- YouTube가 Shorts에서 "끝까지 본 비율"과 "재시청(루프)"을 별도로 가중하는지 공식 확인 불가. 2023 Sherman 인터뷰 이후 순위 신호를 구체화한 공식 발언(2024~2026)은 찾지 못했다.
- YouTube Help의 Shorts 전용 분석 페이지 원문은 이번 조사에서 직접 확인하지 못했다(유지율 일반 문서 9314415에는 Shorts 내용 없음).

## 2. 분석가·크리에이터가 말하는 서사 기법: 열린 고리, but/therefore, 고조, 보상 배치, 엔딩

### Takeaway
측정된 근거는 거의 없고 대부분 경험칙이지만, 출처들이 한 방향으로 모인다: (1) 문장마다 "그래서/그런데"로 이야기를 앞으로 밀 것(설명 추가 금지), (2) 답 앞에 갈등을 두고 답이 불확실하게 느껴지게 긴장을 쌓을 것, (3) 예고하지 말고 보여 줄 것, (4) 끝을 알리지 말고 급하게 끝낼 것. 우리 대본의 "장면마다 사실 하나 보고"는 South Park 규칙이 말하는 "and then" 나열의 전형이다.

### Cited Findings
- [경험·1차 발언] Trey Parker·Matt Stone(NYU Tisch 강의, 2011): 비트 사이에 "and then"이 들어가면 문제다. 비트 사이에는 "therefore" 또는 "but"이 들어가야 한다. "This happened, and then this happened… that's not a movie, that's not a story." — [The Hustle](https://thehustle.co/the-storytelling-secrets-that-netted-matt-stone-and-trey-parker-600-million-dollars), [HuffPost UK](https://huffingtonpost.co.uk/entry/south-park-nyu_n_954419)
- [경험·1차 발언] Jenny Hoyos(TED, 60초 이야기 틀): ① 질문 훅("Many great stories start with a question, because it will make people stick until the end to find out the answer") ② 끊임없는 진행("Each sentence should move the story forward rather than simply adding description") ③ 갈등("if everything is smooth sailing, then nobody cares, which is why we need to add conflict before getting to our answer") ④ 긴장("build tension by making the answer feel uncertain to make a satisfying ending") ⑤ 만족스러운 끝. 예: "집에서 만든 버거가 드라이브스루보다 빠를까" 영상(4,500만 회)은 요리와 드라이브스루 줄을 병렬로 진행시키고 엄마의 반응을 갈등으로 썼다. "이야기 하는 시간이 버거 만드는 시간보다 길면 둘 다 과하게 익힌 것" — [ContentGrip](https://www.contentgrip.com/how-to-tell-a-great-story-in-60-seconds/), [TED](https://www.ted.com/talks/145078)
- [2차] Hoyos가 영상을 작은 고리로 나눠 각 구간을 호기심 틈으로 끝낸다("micro-loop", 약 30초 단위)는 정리 글이 있으나 원 발언 확인 불가 — [ShortGenius](https://shortgenius.com/blog/script-writing-techniques)
- [경험·1차 문서] MrBeast 제작 문서(롱폼 기준): 1~3분 구간은 "Stop telling people what they will be watching and start showing them." 재몰입은 "content that is highly interested that fits the story and makes people genuinely impressed." "The video endings must always be abrupt to protect retention." "Don't ever signal the end of the video unless it's to build hype for the prize or payoff at the end." 가장 재미있는 내용을 앞쪽 구간에 배치하라("plan out all the most exciting and interesting content that is also very simple") — [MrBeast 제작 문서 사본](https://www.alexanderjarvis.com/memo-how-to-succeed-in-mrbeast-production/)
- [경험] "가치를 늦게 주라(delay the value)": 모든 것을 앞에서 밝히지 말고 주인공이 고생하는 과정을 보여 줄 것 — [Medium, techwithlandon(개인 크리에이터)](https://medium.com/@techwithlandon/want-over-70-retention-on-your-short-form-videos-heres-how-to-do-it-5ce7bae94a43)
- [경험] 루프 엔딩: 끝이 처음으로 자연스럽게 이어져 시청자가 다시 시작된 걸 알아채기 전에 첫 3초를 또 보게 만드는 방식. 아웃트로·"시청 감사합니다"·엔드 화면은 넣지 말 것. 다만 vidIQ는 루프 쇼츠가 대개 7~8초 이하라고 설명 — [vidIQ](https://vidiq.com/blog/post/double-youtube-watch-time-looping-shorts/)
- [2차, 검증 불가] "루프 영상이 유지율 115%, 노출 4배"는 출처 없는 일화 — [virvid.ai](https://virvid.ai/blog/looping-structure-shorts-retention-2026) 등. 근거로 쓰지 말 것.

### Inferences
- 우리 대본 진단에 바로 맞는 점검: 13장면 사이 12개 이음매에 "그래서/그런데/그런데도/그러니까"를 넣어 읽어 보고, "그리고"만 들어가는 이음매가 있으면 그 장면은 "사실 보고"다. LLM 지시문에 "장면 n+1은 장면 n에 대한 '그런데(반박·의외)' 또는 '그래서(결과·다음 질문)'여야 한다"는 규칙으로 옮길 수 있다.
- Hoyos 틀을 설명형으로 옮기면 "갈등"은 사람 대 사람이 아니라 **설명 대 설명**(통설 vs 반례, 첫 가설이 깨지는 순간)이다. 예: "하품은 산소가 부족해서" → "그런데 산소를 넣어 줘도 하품은 줄지 않았다"(가설이 깨짐 = 갈등) → "그래서 과학자들은 뇌 온도를 의심했다". 이렇게 하면 "가장 놀라운 사실"이 숫자 나열이 아니라 가설을 깨는 반전으로 들어간다.
- "답을 불확실하게 느끼게" = 후보 답을 두세 개 세우고 하나씩 지운다. 지울 때마다 작은 보상(그렇구나)이 생기고 최종 답의 긴장은 유지된다.
- MrBeast의 "끝을 알리지 말라"는 우리 고정 CTA·요약 문장과 정면으로 부딪힌다. 요약 문장은 "이제 끝났다"는 신호라 마지막 10초 이탈을 부를 가능성이 크다(추론, 쇼츠 측정값 없음). 마지막 문장은 정리 대신 반전 한 줄·처음 질문으로 돌아가는 콜백·시청자 몸에서 바로 확인할 거리로 끝내고, CTA는 아주 짧게 붙이거나 화면 문구로 옮기는 안을 시험할 가치가 있다.
- 진짜 루프(끝→처음 이어짐)는 7~8초 영상의 기법이라 110초 설명형에는 그대로 맞지 않는다. 110초에서 쓸 만한 변형은 "마지막 문장이 첫 질문을 다른 의미로 되살리는 콜백"이다(예: 첫 문장 "하품은 왜 옮을까요?" → 마지막 "지금 이 영상 보면서 하품하셨다면, 당신 뇌는 정상입니다."). 재시청 효과는 측정 근거 없음.

### Gaps
- Paddy Galloway의 2024~2026 Shorts 서사 관련 신규 분석·인터뷰는 이번 검색으로 찾지 못했다(이전 보고서의 2023 5,400편 분석이 유일).
- "N초마다 패턴 인터럽트"의 측정 근거는 여전히 없다(이전 보고서 결론과 같음).
- 보상(가장 놀라운 사실)을 몇 % 지점에 둘 때 유지율이 가장 높은지 다룬 측정 자료는 찾지 못했다.
- Colin and Samir, Spotter, TubeBuddy의 Shorts 서사 관련 데이터는 이번 범위에서 찾지 못했다.

## 3. 60~180초 쇼츠의 중간 이탈 데이터, 60초와 2~3분의 차이

### Takeaway
2~3분 Shorts의 중간 이탈을 공개 측정한 신뢰할 만한 데이터는 찾지 못했다. 공개된 것은 롱폼 유지율의 일반 모양(초반 급락 후 평탄화)과 "길이 구간끼리만 비교하라"는 진단 원칙뿐이다.

### Cited Findings
- [2차] 롱폼 일반 패턴: 유지율이 첫 몇 초 95%에서 30초쯤 약 65%로 떨어진 뒤 평탄해진다. 초반 이탈 원인은 느린 오프닝·로고·인사, 제목·썸네일과 맞지 않는 훅. 롱폼 평균 시청 비율 30% 안팎이 "좋은" 수준 — [vidIQ](https://vidiq.com/blog/post/increase-audience-retention-youtube/) (표본·방법 미공개)
- [2차] 유지율 진단은 시작·중간·보상 셋으로 나누고, 길이 구간별로만 비교하며, 2025-03 조회 정의 변경으로 이전 수치와 직접 비교가 어렵다 — [Bytecap](https://www.bytecap.io/research/youtube-shorts-retention-benchmarks)
- [측정, 플랫폼 다름] Snapchat 실사용 짧은 영상 9만 편 데이터셋(SnapUGC)으로 참여도를 "정규화 평균 시청 비율(NAWP)"과 "참여 지속률(ECR)"로 정의. 기존 화질 평가 점수(MOS)는 참여도와 강하게 상관하지 않았다 — [arXiv 2410.00289](https://arxiv.org/abs/2410.00289v1). 즉 "화질이 좋으면 오래 본다"는 근거는 약하고 내용이 더 중요하다는 간접 증거.
- [경험] 2분 영상이 "더 길다고 밀어주지 않는다"는 공식 입장(길이에 이상값 없음) — [OutlierKit 정리의 Sherman 발언](https://outlierkit.com/resources/youtube-shorts-algorithm/)

### Inferences
- 110초 영상은 같은 이야기 힘이면 평균 시청 비율이 60초보다 낮게 나오는 게 구조적으로 당연하므로, 대본 개선 판정은 "장면 5~10 구간 곡선 기울기"처럼 중간 구간에 한정해 보는 것이 맞다.
- 롱폼 패턴(초반 급락 후 평탄)을 쇼츠에 그대로 대면 안 된다. 쇼츠 피드는 언제든 넘길 수 있어 중간 구간에서도 계속 새는 곡선이 될 가능성이 크다(추론). 그래서 "중간에 작은 보상 + 다음 질문"을 계속 걸어야 한다는 경험칙이 나온다.

### Gaps
- 60~180초 Shorts의 장면별 이탈 지점, 어떤 문장 유형에서 이탈하는지에 대한 공개 측정 데이터 없음. 우리 채널 Studio 곡선을 장면 경계와 겹쳐 보는 자체 측정이 유일한 길.
- "90초 넘으면 유지율 35%" 류 수치는 표본 미공개 SEO 글이라 제외(이전 보고서 판단 유지).

## 4. 강한 재훅 vs 약한 재훅, 강한 엔딩 vs 약한 엔딩

### Takeaway
출처들이 공통으로 가르는 기준: 강한 재훅은 (a) 지금까지의 설명을 깨거나(but) (b) 판돈을 올리고(이걸 모르면 손해·더 큰 수수께끼) (c) 곧바로 실제 놀라움을 준다. 약한 재훅은 예고만 하거나 답해도 그만인 질문을 던진다. 강한 엔딩은 급하게, 끝을 알리지 않고, 첫 질문을 회수하는 것이고 약한 엔딩은 요약·인사·"끝"을 알리는 문장이다.

### Cited Findings
- [경험·1차 문서] 재몰입은 "이야기에 맞고 진짜 감탄하게 하는" 내용이어야 한다. 예고("이제 ~를 보여 드릴게요")가 아니라 보여 주기 — [MrBeast 제작 문서](https://www.alexanderjarvis.com/memo-how-to-succeed-in-mrbeast-production/)
- [측정·심리학] 호기심은 "최대 불확실성"과 "거의 알아챈 순간" 두 지점에서 정점이다. 호기심이 클수록 사람들은 건너뛰기 버튼을 누르지 않고 기다렸다 — Hsiung, Poh, Huettel, Adcock, PNAS(2023-10 게재), 2,000명 이상, 30초 선 그리기 영상 25편, '스포일러' 버튼 — [Duke DIBS](https://dibs.duke.edu/news/what-animated-taco-reveals-about-curiosity-and-patience/), [Scientific American](https://www.scientificamerican.com/article/no-spoilers-please-why-curiosity-makes-us-patient/)
- [측정·심리학] 같은 연구: 초반 호기심은 즐거움과, 후반(답이 늦어질 때) 호기심은 좌절과 상관 — [Scientific American](https://www.scientificamerican.com/article/no-spoilers-please-why-curiosity-makes-us-patient/). 별도 연구(200명 이상): 호기심 수준은 같아도 답이 30분 뒤로 밀리면 부정적 감정이 커지고, 곧 풀릴 것 같을 때는 "거의 안다"는 긍정 쪽에 집중한다 — [NPR 13.7](https://www.npr.org/sections/13.7/2017/09/25/553443078/is-curiosity-a-positive-or-negative-feeling)
- [경험] Hoyos: 답 직전에 갈등을 넣고, 답이 불확실하게 느껴지게 해야 만족스러운 끝이 된다 — [ContentGrip](https://www.contentgrip.com/how-to-tell-a-great-story-in-60-seconds/)
- [경험·1차 문서] "엔딩은 늘 급해야 한다", "보상을 띄우는 경우가 아니면 끝을 알리지 말라" — [MrBeast 제작 문서](https://www.alexanderjarvis.com/memo-how-to-succeed-in-mrbeast-production/)
- [경험] 루프용 엔딩에는 아웃트로·감사 인사·엔드 화면을 넣지 않는다 — [vidIQ](https://vidiq.com/blog/post/double-youtube-watch-time-looping-shorts/)

### Inferences
- 우리 장면 5 고정 문구 "그런데 몸 안을 들여다보면 이야기가 달라집니다."는 방향은 맞지만(but형) 매번 같은 문장이라 무엇이 달라지는지 구체적 판돈이 없다. 강하게 만들려면 고정 문구 뒤 같은 장면에 "지금까지 설명이 틀렸다는 구체적 증거 하나"를 붙여야 한다(예고 → 즉시 보상). 고정 문구가 영상마다 반복되면 템플릿 인상도 준다(이전 보고서의 정책 우려와 겹침).
- 장면 10 재훅의 약/강 예(추론, 측정 아님):
  - 약: "그럼 다른 동물도 하품을 할까요?"(답이 뭐든 상관없는 곁가지 질문, 판돈 없음)
  - 강: "그런데 이 설명이 맞다면, 이상한 일이 하나 생깁니다. 개는 주인의 하품만 따라 합니다."(지금까지 세운 설명을 시험대에 올림 + 즉시 의외의 사실)
  - 강: "여기서 과학자들도 틀렸습니다."(가설 붕괴 = 갈등) → 다음 장면에서 바로 무엇이 틀렸는지
- PNAS 결과의 실무 번역: 답을 마지막 장면까지 통째로 미루기보다, "거의 알 것 같은" 단서를 장면 10~11에서 주고 장면 12에서 마지막 조각을 맞추는 편이 호기심을 좌절이 아닌 기대로 유지한다(추론). 반대로 장면 5~9에서 단서 없이 사실만 나열하면 "답이 늦어지는" 부정적 호기심이 쌓인다.
- "가장 놀라운 사실이 중간에 숫자와 함께 묻혀 있다"는 문제의 처방: 그 사실을 (a) 훅이나 약속에서 질문 형태로 먼저 걸고, (b) 장면 10 재훅의 반전으로 쓰거나 장면 12 보상으로 올린다. 숫자는 그 사실을 "체감"시키는 비교 한 개로만 남긴다(예: "30%" 대신 "세 명 중 한 명").
- 엔딩 약/강 예(추론):
  - 약: "이렇게 하품은 공감 능력과 뇌 온도 조절 때문에 옮는 것이었습니다."(요약 = 끝 신호)
  - 강(콜백): "그러니까 방금 하품이 나왔다면, 당신 뇌가 이 영상 속 누군가에게 공감한 겁니다."
  - 강(마지막 반전): "그리고 하나 더. 이 영상에서 하품이라는 말을 들은 것만으로도, 하품 확률이 올라갑니다."

### Gaps
- 쇼츠에서 "요약형 엔딩 vs 콜백·반전형 엔딩"을 A/B로 비교한 측정 자료는 찾지 못했다.
- 재훅 문장 유형별 이탈 차이를 측정한 자료 없음.

## 5. 짧은 영상 참여도에 관한 학술 연구

### Takeaway
학술 근거로 쓸 만한 것은 (1) 호기심이 "건너뛰기"를 줄이고 기다림 자체를 가치 있게 만든다는 PNAS 실험, (2) 화질보다 내용이 참여도를 좌우한다는 Snapchat 9만 편 연구, (3) 과학 TikTok에서 딱딱한 전문가 어조가 참여가 낮다는 소규모 내용 분석 정도다. "정보 밀도와 참여도" 관계를 직접 측정한 연구는 찾지 못했다.

### Cited Findings
- [측정] Hsiung 외, PNAS 2023: 30초 선 그리기 영상 25편, 2,000명 이상, 스포일러 버튼. 호기심이 높을수록 건너뛰지 않고 끝까지 봄. "Curiosity didn't just motivate getting answers, it increased the value of the journey itself."(Adcock) — [Duke DIBS](https://dibs.duke.edu/news/what-animated-taco-reveals-about-curiosity-and-patience/)
- [측정] SnapUGC 9만 편: 화질 점수(MOS)는 참여도(평균 시청 비율·참여 지속률)와 강하게 상관하지 않음, 영상 내용(시각·배경음·텍스트)만으로 참여도 예측 가능 — [arXiv 2410.00289](https://arxiv.org/abs/2410.00289v1)
- [측정, 소표본] 과학·AI·기후 TikTok 30편 내용 분석: 전문 제작자는 중립적 어조와 분명한 출처를 쓰지만 비전문 제작자보다 참여가 낮은 경향 — [Leiden LIACS 학위논문(2025-2026)](https://theses.liacs.nl/pdf/2025-2026-TuinAvanderAmber.pdf)
- [측정] Douyin 브랜드 영상 4,027편(54개 브랜드): 화면 모드·자막·제목 길이는 중심 경로로, 음악·내레이션은 주변 경로로 참여도에 영향 — 검색 요약만 확인, 원문 미확인 — [jyx.jyu.fi](https://jyx.jyu.fi/bitstreams/e568795f-bef8-4663-bc9d-444feb27a09a/download)
- [2차, 원문 미확인] 과학 콘텐츠 참여도와 관련된 특성으로 60초 초과 길이, 애니메이션 인포그래픽, 뉴스형 제시 등을 꼽은 연구가 있다는 검색 요약 — [Revista Latina](https://nuevaepoca.revistalatinacs.org/index.php/revista/article/download/2232/4839/15957). 어느 연구의 결과인지 확인 못 함.

### Inferences
- PNAS 결과는 "답을 늦추면 넘긴다"는 걱정과 "답을 늦춰야 남는다"는 크리에이터 경험칙을 화해시킨다: 호기심이 충분히 크고 진행이 보이면(선이 계속 그려지듯 단서가 계속 나오면) 기다린다. 우리 대본에 옮기면 "장면마다 답에 한 걸음 다가가는 단서"가 있어야 하며, 답과 무관한 곁가지 사실 장면이 이탈 위험 구간이다.
- SnapUGC 결과는 3D 애니메이션 화질 개선보다 대본 구조 개선의 우선순위가 높다는 간접 근거다.
- 소표본 과학 TikTok 결과는 "교과서 어조"가 불리할 수 있다는 약한 신호일 뿐이다.

### Gaps
- 정보 밀도(초당 사실 수)와 시청 지속의 관계를 측정한 학술 연구는 찾지 못했다.
- Douyin·Reels 플랫폼 내부의 서사 구조별 완주율 연구는 찾지 못했다(공개된 것은 대부분 추천 모델 연구).
- 한국어 쇼츠 대상 연구는 찾지 못했다.

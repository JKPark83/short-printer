# 자료 조사 → 자연스러운 이야기 대본: LLM 파이프라인 기법

조사 범위: 현재 파이프라인(사실 시트 → LLM이 장면 수·문장 길이를 맞춰 한 번에 씀 → LLM 검수)을 "사실 나열"이 아닌 한 편의 이야기로 바꾸는 방법. 2026년 Claude 기반 파이프라인에 바로 적용할 수 있는 것 위주.

참고(코드베이스 관찰): 현재 `prompts/script.md`는 장면 수·장면당 글자 수·흐름 규칙을 한 번에 지시하고, `prompts/script_proofread_ko.md`는 "검수만 하고 고치지 않는다"(지적만 하고 운영자가 고침). 아래 Inferences는 이 구조를 전제로 쓴다.

## 1. 개요(outline) 먼저 쓰고 그다음 쓰기: STORM·DOC·Re3·Plan-and-Write

### Takeaway
"계획(개요) → 쓰기"로 나누면 사람 평가에서 일관성·구성이 뚜렷하게 좋아진다는 근거가 여러 논문에 일관되게 있다(+14~28%p). 다만 모두 긴 글(위키 문서·수천 단어 소설) 대상이라 40~90초 쇼츠에서의 효과 크기는 직접 검증된 바 없다.

### Cited Findings
- STORM(Stanford, NAACL 2024): ① 여러 관점을 찾고 ② 관점마다 "질문하는 작가 ↔ 근거 기반 전문가" 대화를 시뮬레이션해 자료를 모으고 ③ 모은 자료로 개요를 만든 뒤 ④ 개요를 따라 글을 쓴다. 개요 기반 RAG 기준선 대비 위키 편집자 평가에서 "구성(organization)이 잘 됐다"가 25%p, 범위(coverage)가 10%p 높았다. 남은 문제로 편집자들은 "출처 편향이 글로 옮겨감"과 "관계없는 사실을 억지로 엮음(inappropriate fact associations)"을 꼽았다 — [Assisting in Writing Wikipedia-like Articles From Scratch with Large Language Models (STORM)](https://arxiv.org/abs/2402.14207)
- DOC(Detailed Outline Control, ACL 2023): 창작 부담을 "쓰기"에서 "계획"으로 옮겨 계층형 상세 개요를 만들고(Detailed Outliner), 쓰는 동안 각 단락이 개요 항목에 맞는지 통제(Detailed Controller). Re3 대비 사람 평가에서 줄거리 일관성 +22.5%p, 개요 충실도 +28.2%p, 재미 +20.7%p — [DOC: Improving Long Story Coherence With Detailed Outline Control](https://arxiv.org/abs/2212.10077)
- Re3(EMNLP 2022): Plan(전체 계획) → Draft(계획과 현재 상태를 매번 다시 넣어 이어 쓰기) → Rewrite(여러 후보를 일관성·전제 관련도로 재순위) → Edit(사실 일관성 고치기) 4단계. 같은 길이의 기본 모델 대비 "줄거리가 일관됨" +14%p, "전제와 관련 있음" +20%p — [Re3: Generating Longer Stories With Recursive Reprompting and Revision](https://arxiv.org/abs/2210.06774)
- Plan-and-Write(AAAI 2019): 줄거리(storyline, 키워드 순서)를 먼저 계획하고 그걸 따라 이야기를 쓰면, 계획 없이 쓴 것보다 자동·사람 평가에서 더 다양하고 일관되며 주제에 맞았다. 전체를 먼저 계획하는 static 방식과 계획·쓰기를 번갈아 하는 dynamic 방식을 비교 — [Plan-And-Write: Towards Better Automatic Storytelling](https://arxiv.org/abs/1811.05701)
- DOME(NAACL 2025): 고정된 개요의 경직성을 문제로 보고, 계획과 쓰기 단계를 섞는 동적 계층 개요 + 이미 쓴 내용 기억 모듈로 유창성·일관성을 개선했다고 보고(구체 수치는 확인 못함) — [Generating Long-form Story Using Dynamic Hierarchical Outlining with Memory-Enhancement](https://arxiv.org/abs/2412.13575v1)
- Anthropic 공식 가이드: 가장 흔한 체이닝 패턴은 "초안 생성 → 기준에 비춰 검토 → 검토 결과로 고쳐 쓰기"이며, 각 단계를 별도 API 호출로 두면 중간 결과를 로그·평가·분기할 수 있다. 최신 모델은 다단계 추론을 내부(thinking)에서 처리하므로 명시적 체이닝은 "중간 결과를 검사하거나 파이프라인 구조를 강제해야 할 때" 쓰라고 한다 — [Claude Prompting best practices: Chain complex prompts](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)

### Inferences
- 쇼츠에 맞는 최소 형태는 STORM의 "자료 → 개요 → 쓰기"를 줄인 2호출 구조: (1) 비트 시트(beat sheet) 호출 — 사실 시트에서 핵심 물음 하나, 답, 비트별 역할(훅/궁금증/반전/답/여운)과 비트마다 쓸 fact_id 1~2개만 고른다; (2) 쓰기 호출 — 비트 시트만 보고 문장을 쓴다. DOC의 "개요 충실도 통제"는 쓰기 결과의 각 장면이 비트 역할을 지켰는지 검사 단계에서 보는 것으로 대체 가능.
- STORM 편집자들이 지적한 "관계없는 사실을 억지로 엮음"은 이 프로젝트의 "사실 끼워 넣기" 증상과 같은 뿌리다: 모은 자료를 다 쓰려는 압력. 개요 단계에서 "쓰지 않을 사실"을 명시적으로 버리게 해야 한다.
- 최신 Claude는 내부 thinking이 있으므로, 비용을 아끼려면 한 호출 안에서 "먼저 `<beats>`를 출력하고 그 뒤 대본"으로 해도 된다. 다만 개요를 별도 호출로 분리하면 개요를 사람이 보고 고르거나(운영자 확인), 개요만 재생성할 수 있다는 운영상 이점이 있다.

### Gaps
- 1분 안팎 내레이션처럼 아주 짧은 글에서 개요 단계의 효과를 측정한 논문은 찾지 못했다. 위 수치는 모두 수천 단어 글 기준이다.
- "story spine"(Once upon a time… Every day… Until one day… Because of that…) 프롬프팅의 정량 평가 근거는 찾지 못했다(작법 관행으로만 존재).

## 2. 사실을 다 넣지 말고 이야기에 맞게 고르기 + 근거 유지

### Takeaway
정보 밀도와 읽기 쉬움 사이에는 분명한 맞교환이 있고, 사람은 "최대 밀도"가 아니라 중간 밀도를 선호한다(Chain of Density). 근거(출처)는 본문에 섞지 말고 "쓴 뒤 문장별로 붙이고 원문을 최소한으로만 고치는" 방식(RARR)이 흐름을 덜 해친다.

### Cited Findings
- Chain of Density(2023): 요약에 엔티티를 길이를 늘리지 않고 반복해서 더 채우는 실험. 사람은 기본 GPT-4 요약보다 더 밀도 높은 요약을 선호했지만 "사람이 쓴 요약과 거의 비슷한 밀도"에서 멈췄고, 저자들은 "정보량과 읽기 쉬움 사이에 맞교환이 있다"고 결론냈다 — [From Sparse to Dense: GPT-4 Summarization with Chain of Density Prompting](https://arxiv.org/abs/2309.04269)
- STORM 평가에서 경험 많은 위키 편집자들이 꼽은 문제: 관계없는 사실을 부적절하게 연결함(inappropriate fact associations) — [STORM](https://arxiv.org/abs/2402.14207)
- RARR(ACL 2023): 먼저 글을 쓰고, 그 뒤 (1) 문장마다 근거를 찾고 (2) 근거에 맞게 고치되 "원래 출력을 최대한 보존"하는 2단계. 이전 편집 모델보다 원문을 훨씬 많이 보존하면서 출처 일치(attribution)를 크게 높였다 — [RARR: Researching and Revising What Language Models Say, Using Language Models](https://arxiv.org/abs/2210.08726)
- Anthropic 가이드: 긴 자료는 프롬프트 맨 앞에 두고 질문·지시는 뒤에 두면 성능이 좋아진다. 또 지시의 "이유"를 알려 주면 더 목표에 맞는 응답을 한다 — [Claude Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)

### Inferences
- "핵심 통찰 하나" 선택 단계를 둔다: 비트 시트 호출에서 먼저 한 문장짜리 논지(thesis, 예: "손가락 소리는 뼈가 아니라 관절액 속 기포가 터지는 소리다")를 쓰게 하고, 사실 시트의 각 사실을 "논지를 세우는 데 필요/보강/불필요"로 분류한 뒤 필요·보강만 쓰게 한다. 쓰지 않는 사실은 설명란 출처 목록에 남기면 버리는 부담이 줄어든다.
- 근거 유지는 현재처럼 장면마다 `fact_ids`를 다는 방식이 RARR과 같은 방향이라 그대로 두면 된다. 단, "모든 장면에 fact_id 필수"는 연결 문장(물음·전환·여운)에도 사실을 끼우게 만드는 압력이므로, 연결 역할 장면은 fact_ids를 비워도 되게 허용하는 게 맞다.
- 문장 안에 "연구에 따르면", "~에 의하면" 같은 출처 표현을 매번 넣으면 끊기는 느낌이 나므로, 출처 표지는 놀라운 숫자 한두 곳에만 쓰고 나머지는 설명란 출처로 돌린다(이건 작법 판단이며 직접 근거 논문은 없음).

### Gaps
- "서사적 관련도로 사실 순위 매기기"를 정량 평가한 논문은 찾지 못했다.
- Chain of Density는 요약(읽기) 대상이라, 귀로 듣는 내레이션에서 최적 밀도가 더 낮을 것이라는 건 추정이다.

## 3. 고정 문장 수·문장당 글자 수 제약이 유창성을 해치는가, 더 나은 방법은

### Takeaway
형식 제약을 거는 것 자체가 품질을 떨어뜨린다는 근거가 있고(추론 과제 기준 최대 60%p 이상 하락), "먼저 자유롭게 쓰고 → 두 번째 단계에서 형식에 맞추기"로 나누면 손실이 거의 사라진다. 길이 지시 준수도 모델이 스스로 잘 못 세므로, 글자 수는 코드가 세고 모자라거나 넘친 장면만 고치게 하는 게 낫다.

### Cited Findings
- Let Me Speak Freely?(EMNLP 2024 Industry): JSON 모드·형식 제한 지시를 걸면 추론 성능이 떨어지고, 제약이 엄할수록 더 떨어졌다. 예: Claude-3-Haiku GSM8K 자연어 86.51% → JSON 23.44%, GPT-3.5-Turbo 76.60% → 49.25%. 반면 "자연어로 먼저 답하고 → 별도 단계에서 형식으로 변환(NL-to-Format)"은 자연어와 거의 같은 점수를 유지했다. 키 순서도 추론을 방해할 수 있다. 분류 과제는 오히려 형식 제한이 도움이 됐다 — [Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of Large Language Models](https://arxiv.org/html/2408.02442v1)
- LIFEBench(NeurIPS 2025): 26개 모델, 16~8,192단어 길이 지시를 평가. 짧은 길이는 대체로 따르지만 일정 길이를 넘으면 급격히 나빠지고, 너무 짧게 쓰거나 일찍 끝내는 경향. 추론형 모델이 길이 준수를 더 잘했다 — [LIFEBench: Evaluating Length Instruction Following in Large Language Models](https://arxiv.org/abs/2505.16234)
- 길이 제약 준수 실패는 별도 연구 주제가 될 만큼 흔하다(모델이 자기 출력 길이를 정확히 세지 못함) — [Following Length Constraints in Instructions](https://arxiv.org/pdf/2406.17744); [PositionID: LLMs can Control Lengths, Copy and Paste with Explicit Positional Awareness](https://arxiv.org/pdf/2410.07035)
- Self-Refine의 "제약 있는 생성(Constrained Generation)" 과제는 반복 고쳐 쓰기로 29.0 → 49.7(3회)까지 올라, 제약 충족은 한 번에 하기보다 고쳐 쓰기로 맞추는 게 효과가 크다 — [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/html/2303.17651)
- Anthropic 가이드: "하지 말 것"보다 "할 것"을 말하라(예: "부드럽게 흐르는 산문 단락으로 써라"). 프롬프트 형식이 출력 형식에 영향을 주므로 원하는 출력 모양에 프롬프트를 맞추라 — [Claude Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)

### Inferences
- 현재 한 호출이 "장면 정확히 N개 + 장면당 lo~hi자 + 영어 영상 프롬프트 + fact_ids + 제목·설명·태그"를 구조화 출력으로 동시에 만족해야 한다. Let Me Speak Freely의 결과로 보면 이야기 흐름(=추론에 가까운 일)이 형식 부담에 밀릴 가능성이 높다. 분리안:
  1. 이야기 쓰기: 비트 시트를 보고 장면 구분 없이 한 덩어리 내레이션을 자연어로 쓴다(전체 글자 수 범위만 준다).
  2. 장면 나누기·맞추기: 내레이션을 N개 장면으로 나누고 장면당 글자 수에 맞게 최소 편집, 영상 프롬프트·fact_ids를 붙여 JSON으로 낸다(NL-to-Format).
  3. 코드 검사: 글자 수는 앱이 세고, 넘친 장면만 "이 장면을 ~자 이하로 줄여라(앞뒤 장면 함께 제시)"로 재요청한다.
- 장면 수를 유연하게(N±2) 하면 유창성에는 유리하지만, 이 프로젝트는 장면당 영상 생성 비용(Flow 크레딧)이 있어 상한은 고정해야 한다. 절충: 상한 고정·하한만 유연, 또는 "한 장면에 짧은 문장 두 개" 허용(이미 있음)을 적극 활용.
- 장면당 글자 수 상한은 클립 8초라는 하드 제약에서 오므로 없앨 수는 없지만, "쓰는 단계"가 아니라 "맞추는 단계"에서만 강제하면 된다.

### Gaps
- 한국어 짧은 문장 단위 글자 수 제약이 유창성에 미치는 영향을 직접 측정한 연구는 찾지 못했다.
- "자유롭게 쓴 뒤 압축"과 "처음부터 제약 아래 쓰기"를 창작 글에서 직접 비교한 논문은 찾지 못했다(NL-to-Format 결과는 추론 과제 기준).

## 4. 일관성을 겨냥한 자기 비평·고쳐 쓰기 루프와 함정

### Takeaway
고쳐 쓰기 루프는 효과가 있지만 조건이 붙는다: (1) 피드백이 구체적·실행 가능해야 하고(일반적인 피드백은 효과가 크게 줄어듦), (2) 실패의 대부분은 비평 자체가 틀려서 생기며, (3) 외부 기준 없이 자기 답을 고치게 하면 오히려 나빠질 수 있다. 1~2회 반복에서 이득 대부분이 나온다.

### Cited Findings
- Self-Refine(NeurIPS 2023): 같은 LLM이 초안 → 피드백 → 고쳐 쓰기를 반복. 7개 과제 평균 약 20%p 개선. 피드백 품질 실험: 감정 반전 과제에서 구체적 피드백 43.2 / 일반적 피드백 31.2 / 피드백 없음 0, 약어 생성 56.4 / 54.0 / 48.0, 코드 최적화 27.5 / 26.0 / 24.8. 반복 효과는 초반 1~2회가 대부분이고 뒤로 갈수록 줄어든다. 실패 분석: 실패의 94%가 피드백 오류(잘못된 위치 지적 33%, 부적절한 해결책 제안 61%), 고쳐 쓰기 실수는 6% — [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/html/2303.17651)
- Large Language Models Cannot Self-Correct Reasoning Yet(ICLR 2024, Google DeepMind·UIUC): 외부 피드백 없이 스스로 고치게 하면 추론 성능이 개선되지 않고 때로 떨어진다. 이전 "자기 교정" 성공 사례 상당수는 정답 라벨(oracle)을 이용했다 — [Large Language Models Cannot Self-Correct Reasoning Yet](https://arxiv.org/abs/2310.01798)
- Re3의 Rewrite 단계는 하나를 고치는 대신 여러 후보를 만들어 일관성·전제 관련도로 재순위하고, Edit 단계는 사실 일관성만 고친다(역할 분리) — [Re3](https://arxiv.org/abs/2210.06774)
- RARR는 고쳐 쓰기의 표류(drift)를 막으려고 "원문 보존"을 명시적 목표로 두고 보존 정도를 따로 측정했다 — [RARR](https://arxiv.org/abs/2210.08726)
- Anthropic 가이드의 표준 체이닝: 초안 → 기준에 비춰 검토 → 검토로 고쳐 쓰기, 각각 별도 호출 — [Claude Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)

### Inferences
- 현재 검수(`script_proofread_ko.md`)는 "지적만 하고 고치지 않는다". Self-Refine 기준으로는 루프의 절반만 있는 셈이다. 지적(이미 장면 번호·kind·severity로 구체적임) → 고쳐 쓰기 호출 1회 → 다시 검수 1회, 최대 2바퀴로 자동화할 수 있다. 피드백이 구체적일수록 효과가 크다는 결과와 맞게, 지적에는 "어느 장면·무엇이 어긋남·어떻게 고칠지"를 반드시 담게 한다(이미 대부분 그렇게 되어 있음).
- 비평 오류가 실패의 94%라는 결과 때문에, 검수는 쓰기와 다른 관점(별도 호출, 앞 문장만 들은 청자 시뮬레이션)을 유지하는 게 맞고, 점수 판정을 앱이 하는 현 구조는 좋은 선택이다.
- "청자 테스트"를 구조화하는 방법: 장면마다 "앞 장면과의 관계"를 한 단어(그래서/그런데/왜냐하면/예를 들어/그 답은)로 먼저 적게 하고, 그 관계를 못 적는 장면을 연결 실패로 본다(South Park 작가들의 "and then 대신 but/therefore" 관행과 같은 생각. 학술 근거는 없음).
- 사실 표류 방지: 고쳐 쓰기 호출에 "지적된 장면만 고치고 나머지는 글자 그대로 둔다", "사실 시트에 없는 숫자·사실을 더하지 않는다"를 명시하고(이미 `script_revise*.md`에 있는 규칙과 같음), 고친 뒤 바뀐 장면의 fact_ids를 앱이 다시 검사한다.
- 반복은 1~2회로 제한한다(Self-Refine의 체감 감소, 비용).

### Gaps
- 내러티브 흐름 전용 LLM-as-judge 루브릭의 신뢰도(사람 판단과의 상관)를 다룬 논문은 이번 조사에서 확보하지 못했다.
- Huang et al.의 결과는 수학·추론 과제 기준이라, 글의 흐름처럼 정답이 없는 과제에서 자기 교정이 나빠지는지는 직접 근거가 없다(Self-Refine은 대화·글 과제에서 개선을 보고해 서로 과제 범위가 다름).

## 5. 자동 YouTube/TikTok 대본 생성기 사례와 교훈

### Takeaway
공개된 자동 쇼츠 파이프라인 사례는 대부분 "주제 → LLM 한 번에 대본 → TTS → 영상"의 단일 호출 구조이고, 대본 품질 개선을 체계적으로 다룬 사례 연구는 찾지 못했다. 공개 회고에서 나온 교훈은 "LLM 대본이 밋밋하고 일반적"이라는 정도다.

### Cited Findings
- MoneyPrinter(오픈소스): 주제 입력 → LLM 대본 → TTS → 스톡 영상 → 자막까지 자동. 대본은 단일 생성 단계 — [MoneyPrinter docs](https://www.mintlify.com/FujiwaraChoki/MoneyPrinter/introduction)
- 무료 AI 도구로 100% 자동 쇼츠 채널을 운영한 개인 회고: 구독자 52명 수준, LLM이 코드 작성에는 유용했지만 글은 일반적이고 밋밋했다는 교훈(일화적 근거) — [Using Free AI Tools to Create a 100% Automated Youtube Shorts Channel (HackerNoon)](https://hackernoon.com/using-free-ai-tools-to-create-a-100percent-automated-youtube-shorts-channel)
- 그 밖에 n8n·LangChain 기반 자동 쇼츠 생성기들도 "LLM 대본 → TTS → 이미지/영상 → 편집"의 같은 구조 — [ShortsIn (lablab.ai)](https://lablab.ai/submissions/cly7g68vn000p3576bo45csq7); [n8n One-click YouTube Shorts generator](https://www.growwstacks.com/workflows/one-click-youtube-shorts-generator-with-leonardo-ai-gpt-and-elevenlabs)

### Inferences
- 이 프로젝트는 이미 자료 조사·사실 시트·검수 단계를 갖춰 공개 사례보다 앞서 있다. 공개 사례에서 가져올 대본 구조 교훈은 사실상 없고, 1~4장의 논문 기반 설계(개요 분리·형식 분리·지적→고침 루프)가 더 쓸모 있다.

### Gaps
- 자동 쇼츠 대본의 시청 지속률을 단계 구조별로 비교한 공개 데이터·사례 연구는 찾지 못했다.

## 부록: 적용 설계안 요약 (위 근거에서 끌어낸 추론)

1. **비트 시트 호출(신규, `prompts/script_plan.md`)**: 입력 = 사실 시트. 출력 = 논지 한 문장, 시청자가 품을 물음 하나, 비트 목록(역할·한 줄 내용·쓸 fact_id 0~2개), 쓰지 않을 사실 목록. 근거: STORM·DOC·Plan-and-Write(개요), Chain of Density(밀도 맞교환).
2. **이야기 쓰기 호출(기존 `script.md` 축소)**: 입력 = 비트 시트(+ 사실 시트 원문은 참고용). 장면 수·장면당 글자 수 대신 전체 길이와 비트 순서만 준다. 자연어 내레이션 한 덩어리. 근거: Let Me Speak Freely(형식 부담 분리).
3. **장면 맞추기 호출**: 내레이션 → N개 장면, 장면당 상한 맞추기, 영상 프롬프트·fact_ids 붙이기(JSON). 최소 편집. 앱이 글자 수 검사 후 넘친 장면만 재요청. 근거: NL-to-Format, LIFEBench(모델은 길이를 잘 못 셈).
4. **검수 → 고쳐 쓰기 1~2회 자동 루프**: 기존 검수 지적을 그대로 고쳐 쓰기 호출에 넘기고, 지적된 장면만 고치게 한 뒤 다시 검수. 근거: Self-Refine(구체적 피드백·초반 반복 효과), Huang et al.(외부 기준 없는 막연한 자기 교정 경계), RARR(원문 보존).
- 비용: 호출이 1회 → 3~5회로 늘어난다. 비트 시트와 쓰기를 한 호출로 합치는 축소판(출력 앞부분에 `<beats>`, 뒤에 대본)도 가능하다.

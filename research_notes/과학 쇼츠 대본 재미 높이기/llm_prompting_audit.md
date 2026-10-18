# LLM 대본 프롬프트: 사실 제약 아래에서 재미있게 쓰게 하기 — 외부 근거와 우리 지시문 점검

조사일 2026-10-18. 점검한 로컬 파일(읽기만 함):
- `prompts/script.md` (공통 대본 규칙, 66줄)
- `channels/ko-40sec-facts/script.md` (채널 대본 규칙, 36줄)
- `prompts/script_proofread_ko.md` (흐름 검수, 35줄)
- `src/shorts_printer/core/script.py` (지시문·user 메시지 조립, pydantic 스키마)

## Q1. Anthropic 공식 가이드(Claude 4/5 시대)는 창작·예시·역할·"하지 마라" 대 "해라"·과한 제약에 대해 뭐라고 하나

### Takeaway
Anthropic은 (1) 금지보다 원하는 것을 말하고, (2) 규칙마다 이유를 붙이고, (3) 예시는 3~5개를 서로 다르게 주며, (4) 시스템 프롬프트에 역할을 주라고 한다. 또 최근 모델은 지시를 글자 그대로 따르고 범위를 넓혀 해석하지 않으므로, 지시하지 않은 "재미"는 저절로 나오지 않는다. 모델이 "분포의 가운데"(뻔한 것)로 수렴한다는 점은 Anthropic도 인정하고, 그 대처로 그 경향을 프롬프트에 직접 적고 구체적인 대안을 주거나 후보를 먼저 내게 한다.

### Cited Findings
- "Tell Claude what to do instead of what not to do". 예: "Do not use markdown" 대신 "Your response should be composed of smoothly flowing prose paragraphs." — [Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- "Match your prompt style to the desired output … The formatting style used in your prompt may influence Claude's response style." 목록·마크다운을 빼면 출력의 목록도 준다. — [같은 문서](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- "Providing context or motivation behind your instructions … can help Claude better understand your goals." 예시가 바로 TTS다: "NEVER use ellipses"보다 "Your response will be read aloud by a text-to-speech engine, so never use ellipses since the text-to-speech engine will not know how to pronounce them." 그리고 "Claude is smart enough to generalize from the explanation." — [같은 문서](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- 예시: "Examples are one of the most reliable ways to steer Claude's output format, tone, and structure." 예시는 Relevant, "Diverse: Cover edge cases and vary enough that Claude doesn't pick up unintended patterns", `<example>` 태그로 감싸고, "Include 3–5 examples for best results." — [같은 문서](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- 역할: "Setting a role in the system prompt focuses Claude's behavior and tone for your use case. Even a single sentence makes a difference." — [같은 문서](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- 야심을 끌어내는 수식어: "Create an analytics dashboard"보다 "… Include as many relevant features and interactions as possible. Go beyond the basics …"가 낫다. — [같은 문서](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- 뻔함으로 수렴: 프런트엔드 예시 프롬프트가 "You tend to converge toward generic, 'on distribution' outputs … this creates what users call the 'AI slop' aesthetic. Avoid this: make creative, distinctive frontends that surprise and delight."라고 그 경향을 모델에게 직접 말하고, 무엇에 집중할지(Focus on) 구체 항목을 준다. — [같은 문서, Frontend design](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- 센 말투 낮추기: "Where you might have said 'CRITICAL: You MUST use this tool when...', you can use more normal prompting" (최근 모델은 시스템 프롬프트에 더 민감해서 과하게 반응한다). — [같은 문서](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- 글자 그대로 따르기(Opus 4.8): "interprets prompts literally and explicitly … does not silently generalize an instruction from one item to another, and it does not infer requests you didn't make." — [Prompting Claude Opus 4.8](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-4-8)
- 같은 문서: "Positive examples showing how Claude can communicate with the appropriate level of concision tend to be more effective than negative examples or instructions that tell the model what not to do." — [Prompting Claude Opus 4.8](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-4-8)
- 기본값 깨기: 일반적인 금지("don't use cream")는 "tend to shift the model to a different fixed palette rather than producing variety." 잘 듣는 두 방법은 "Specify a concrete alternative"와 "Have the model propose options before building … it produces meaningfully different directions across runs." — [Prompting Claude Opus 4.8](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-4-8)
- 검수기 쪽 함의: 리뷰 프롬프트에 "be conservative", "don't nitpick"이 있으면 모델이 문제를 찾고도 기준 아래라며 보고하지 않을 수 있다. "be concrete about where the bar is rather than using qualitative terms like 'important'." — [Prompting Claude Opus 4.8](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-4-8)
- Opus 5.5는 thinking이 늘 켜져 있고 adaptive만 된다. 생각을 `<thinking>` 태그로 출력하게 하는 프롬프트는 거절될 수 있다. — [Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)

### Inferences
- 우리 대본 지시문에는 TTS·길이·사실·영상 규칙의 이유는 잘 붙어 있다(예: script.md 11·13줄). 그런데 **재미의 목표 자체가 없다.** Opus가 글자 그대로 따른다면 "재미있게"라는 지시 없이 정확·연결·길이 규칙만 꼼꼼히 지킨, 지금 같은 강의형 대본이 나오는 게 자연스럽다.
- 채널 훅 예시가 하나뿐("하품, 왜 옮을까요? … 뇌 속에서 찾아보겠습니다")이라 A·B 모두 "~속에서 찾아보겠습니다"를 그대로 따라 했다. Anthropic의 "3~5개, 서로 다르게" 권고와 정면으로 어긋난다.
- 장면 영상 prompt처럼 "slop"을 피하는 Anthropic 방식(경향을 직접 말하고 → 구체적 대안을 준다)을 대본에도 쓸 수 있다: "너는 사실을 하나씩 늘어놓는 교과서 말투로 흐르기 쉽다. 대신 …".
- Opus 5.5는 thinking이 늘 켜져 있어 계획 자체는 이미 한다. 스키마에 계획 필드를 더하면 계획을 **보이게·검사할 수 있게** 만드는 효과가 크고, 품질이 오르는지는 따로 재 봐야 한다.

### Gaps
- Anthropic 문서에 "창작 글쓰기(소설·대본)" 전용 절은 찾지 못했다. 창작 관련 조언은 프런트엔드 미감·말투 절에서 끌어온 것이다.
- Opus 5.5 전용 페이지(prompting-claude-opus-5-5)는 열어 보지 않았다. 목차 설명으로는 effort·thinking·안전 거절 위주이고 글쓰기 말투 항목은 없다.

## Q2. LLM 창작 품질 연구: 뻔함·균질화, 과한 제약, 예시 베끼기, 계획 후 쓰기, 후보 여럿 + 판정, 자기 비평

### Takeaway
LLM 글은 전문가 기준 창의성 검사를 훨씬 적게 통과하고(3~10배), 뻔한 표현·설명조·"subtext 없음"이 주된 약점이다. 다양성 붕괴는 정렬 학습의 "익숙한 것 선호(typicality bias)"와 구조화된 형식에서 온다. 계획 후 쓰기는 "더 흥미롭다"는 사람 평가를 받았고, 후보를 여럿 말하게 하면 다양성이 1.6~2.1배 늘었다. 다만 LLM 판정자는 전반적 창의성 판단에서 전문가와 상관이 거의 없어서, 판정은 구체적인 예/아니오 항목으로 쪼개야 한다.

### Cited Findings
- Art or Artifice(CHI 2024): 창의적 글쓰기 Torrance 검사(TTCW) 14항목(Fluency·Flexibility·Originality·Elaboration)으로 48편을 평가했더니 LLM 이야기는 전문 작가 글보다 3~10배 적게 통과했다. — [Chakrabarty et al., arXiv 2309.14556](https://arxiv.org/abs/2309.14556v2)
- 같은 논문: 14항목 중 Fluency에 "Narrative Pacing", "Scene vs Exposition", "Narrative Ending"이 있다. GPT-3.5의 통과율은 Originality in Form 2.8%, Language Proficiency & Literary Devices 5.6%, Rhetorical Complexity 2.8%였다. 평가자들은 LLM 글의 "pet phrases"와 상투어를 지적했고, "rely heavily on direct & expositional dialogue"라고 했다. — [arXiv 2309.14556 HTML](https://arxiv.org/html/2309.14556v2)
- 같은 논문: LLM이 TTCW를 판정하게 하자 "none of the LLMs positively correlate with the expert assessments"(전문가끼리는 Pearson 0.69). — [arXiv 2309.14556 HTML](https://arxiv.org/html/2309.14556v2)
- Can AI writing be salvaged?(Chakrabarty et al. 2024): AI 글을 고칠 때 쓰는 편집 분류에 "Cliché"와 "Unnecessary/Redundant Exposition"(지나치거나 반복되거나 굳이 말 안 해도 되는 정보)이 들어간다. — [arXiv 2409.14509](https://arxiv.org/pdf/2409.14509)
- Verbalized Sampling(Zhang, …, Manning, Shi 2025): 정렬 후 mode collapse의 원인을 선호 데이터의 "typicality bias(평가자가 익숙한 글을 고른다)"로 짚었다. "Generate 5 jokes … and their corresponding probabilities"처럼 후보 분포를 말하게 하는 프롬프트만으로 "in creative writing, VS increases diversity by 1.6-2.1x over direct prompting", "without sacrificing factual accuracy and safety". — [arXiv 2510.01171](https://arxiv.org/abs/2510.01171)
- The Price of Format(2025): 구조화된 템플릿을 쓴 지시 학습 모델은 열린 입력에도 비슷한 출력을 내며("diversity collapse"), 온도를 올려도 그대로이고 "minimal formatting yielded the most diverse outputs." — [arXiv 2505.18949](https://arxiv.org/abs/2505.18949)
- 다양성 관련 2025 연구 묶음(검색 요약에서 본 것, 원문은 확인하지 않음): 지시 학습이 어휘 다양성은 늘리지만 통사·의미 다양성은 줄인다(Guo et al. 2025). LLM 이야기는 생성마다 같은 줄거리 요소를 되풀이한다("Echoes in AI"). — [Echoes in AI, arXiv 2501.00273](https://arxiv.org/html/2501.00273v1), [The Shrinking Landscape of Linguistic Diversity, arXiv 2502.11266](https://arxiv.org/pdf/2502.11266)
- 서로 다른 LLM끼리도 창작 출력이 비슷하다("We're Different, We're the Same: Creative Homogeneity Across LLMs"). — [arXiv 2501.19361](https://arxiv.org/pdf/2501.19361)
- 계획 후 쓰기: Plan Before You Write(NeurIPS 2025 Creative AI)는 쓰기 계획을 세우고 반성하며 고친 뒤 실행하는 틀로 "79.4% of participants ranking our framework's outputs as more interesting". — [Lewenberg, Sheftel, Karov, NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/hash/9cd4b3c9f2f1bb0208d36ca986f6f4f9-Abstract-Creative_AI_Track.html)
- 더 이른 Plan-and-Write(AAAI 2019)도 줄거리를 먼저 짜면 이야기가 "more diverse, coherent, and on topic"해진다고 했다. Agents' Room(2024)은 서사 생성을 여러 단계·에이전트로 나눈다. — [Plan-and-Write, AAAI](https://ojs.aaai.org/index.php/AAAI/article/view/4726), [Agents' Room, arXiv 2410.02603](https://arxiv.org/pdf/2410.02603)
- 원칙을 준 LLM 판정자: 7B 모델의 창작(중국어 인사말)을 RLAIF로 높일 때 "principle-guided LLM-as-a-Judge"가 보상 모델보다 나은 품질을 냈다. — [Wei et al., EMNLP 2025](https://aclanthology.org/2025.emnlp-main.868)
- Best-of-N은 LLM 판정의 가장 단순한 쓰임새다(N번 뽑아 가장 좋은 것을 고른다). — [LLMs-as-Judges survey, arXiv 2412.05579](https://arxiv.org/pdf/2412.05579)
- 과학 커뮤니케이션: 비전문가에게는 서사 형식이 "increased comprehension, interest, and engagement"를 준다. 논리·과학 소통은 정확성으로 판단받는 일반 진리를, 서사는 개별 경험의 그럴듯함을 다룬다. — [Dahlstrom 2014, PNAS](https://pmc.ncbi.nlm.nih.gov/articles/PMC4183170)
- 호기심의 정보 공백 이론: "curiosity arises when attention becomes focused on a gap in one's knowledge." 아무것도 모르는 데는 궁금해하지 않고, 조금 알아야 궁금해진다. — [Loewenstein 1994, Psychological Bulletin 116(1)](https://stafforini.com/works/loewenstein-1994-psychology-curiosity-review/)

### Inferences
- A·B가 "강의 같다"는 느낌은 TTCW의 "Scene vs Exposition" 실패와 같은 모양이다: 장면(시청자가 겪는 순간)보다 설명(정의·기전·기관 발표)이 압도적으로 많다.
- 우리 파이프라인은 Opus가 pydantic 구조 출력으로 장면마다 link→sentence→80~110단어 영어 prompt→fact_ids→prompt_ko를 번갈아 쓴다. Price of Format이 직접 다룬 건 채팅 템플릿 토큰이라 그대로 옮길 수는 없다. 그래도 "형식이 무거울수록 출력이 수렴한다"는 방향은 우리 경우에도 그럴듯하다(추정).
- 후보 여럿은 대본 전체가 아니라 **훅·한 방(payoff)·마지막 줄**처럼 짧은 부분에 쓰는 게 싸고, Verbalized Sampling의 근거와도 맞는다.
- LLM 판정자가 "재미있나?"를 전체 인상으로 판정하면 믿기 어렵다(TTCW 상관 ≈ 0). 그래서 검수기에 재미를 더한다면 예/아니오로 확인할 수 있는 구체 항목(TTCW처럼)으로 쓴다.
- Dahlstrom와 Loewenstein는 모두 "시청자가 겪는 장면 + 구체적 공백"을 가리킨다. 지금 첫 장면 둘째 문장("~에서 찾아보겠습니다")은 공백을 날카롭게 하지 않고 강의 순서를 알린다.

### Gaps
- 짧은 설명형 내레이션(40초 쇼츠)을 대상으로 한 LLM 창작 연구는 찾지 못했다. 위 연구는 대부분 소설·시·유머다.
- "Self-Refine"류 자기 비평 루프가 재미(engagement)를 올린다는 정량 근거는 이번 조사에서 확인하지 못했다(CRITICS 프레임워크가 "reader engagement"를 높였다는 검색 요약만 봤고 원문은 읽지 못했다).
- 한국어 창작에서의 LLM 균질화 연구는 찾지 못했다.

## Q3. "~하지 않는다" 금지 목록과 단서(hedge) 규칙이 길면 무난하고 목록 같은 출력이 나오나

### Takeaway
금지문이 많을수록 품질이 떨어진다는 직접 실험은 대부분 옛 모델이거나 실무자 보고다. 그래도 방향은 일관된다: 제약이 많아지면 함께 지키기 어려워지고(초가산적 저하, 순서 민감), 금지 목록은 그 개념을 오히려 불러오며, 공식 가이드도 긍정형·예시가 낫다고 한다. 우리 파일은 금지형 표현이 50개 넘게 있고 "재미"를 요구하는 긍정 지시는 0개다.

### Cited Findings
- 부정 프롬프트: 부정문이 든 지시에서 LLM은 크기가 커질수록 오히려 나빠지는 inverse scaling을 보였다(2022, GPT-3·OPT 시대 모델). — [Jang et al., "Can Large Language Models Truly Understand Prompts? A Case Study with Negated Prompts", arXiv 2209.12711](https://huggingface.co/papers/2209.12711)
- 여러 제약을 한꺼번에 줄 때의 성능: 제약 순서를 바꾸면 성능이 크게 흔들리고, "hard-to-easy" 순서일 때 낫다. — [Order Matters, ACL Findings 2025](https://arxiv.org/abs/2502.17204v2)
- 실무자 보고(검증 안 됨): 하나씩은 괜찮은 지시도 겹치면 "super-additive performance degradation"이 생기고, 페르소나·긴박한 말투·형식 지시를 겹칠 때 가장 나빴다(GPT-4o). — [The Compound Constraint Problem, 2026 블로그](https://codex.danielvaughan.com/2026/09/09/compound-prompt-constraints-agents-md-factorial-codex-cli/)
- 실무자 보고(검증 안 됨): 금지 목록은 금지한 개념을 문맥에 넣어 그 꼴의 출력을 부르고, 허용 목록 꼴이 금지 목록 꼴보다 낫다. "3%" 같은 수치는 출처가 불분명하다. — [tianpan.co, 2026-05](https://tianpan.co/blog/2026-05-13-negative-examples-prompts-forbidden-list-becomes-recipe), [16x Eval "pink elephant"](https://eval.16x.engineer/blog/the-pink-elephant-negative-instructions-llms-effectiveness-analysis)
- 공식: "tell the model what not to do"보다 긍정 예시가 더 효과적이고, 일반적인 금지는 다른 고정 기본값으로 옮겨 갈 뿐이다. — [Prompting Claude Opus 4.8](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-4-8)
- 로컬 집계(정규식 `않는다|않게|말고|금지|하지 않|쓰지 않`, 대략치): `prompts/script.md` 33곳, `channels/ko-40sec-facts/script.md` 20곳, `prompts/script_proofread_ko.md` 11곳. 세 파일 모두 `재미·흥미·놀라·신기·비유·감각·여러분`으로 시청자 재미를 요구하는 지시는 없다(채널 파일의 "신기한"·"놀라운"은 10번째 장면 예문 안에만 나온다). — 로컬 grep, 2026-10-18

### Inferences
- 단서 규칙이 세 겹이다: 공통 script.md 36줄(시트의 강도 그대로), 채널 9줄(시트의 단서를 빼지 않는다, "약"), 채널 10~17줄(근거 꼬리표 6종 + 기전/기능 구분). 단서를 문장마다 다시 붙이다 보니 A9의 "가능한 설명이 있습니다 … 느낄 수 있다는 겁니다"(이중 단서)처럼 리듬이 무거워진다. 규칙 자체는 정확성에 꼭 필요하므로, 빼지 말고 **"한 사실에 한 번, 처음 나올 때만"**으로 압축하는 게 맞다.
- 금지가 많고 목표가 없으면, 모델이 가장 안전하게 모든 금지를 피하는 길은 "정의 → 기전 → 근거 → 기관 인용 → 요약"이라는 교과서 꼴이다. A·B가 바로 그 꼴이다(추정이지만 두 대본이 같은 꼴이라는 점은 관찰된다).

### Gaps
- Claude 4/5 세대에서 금지문 개수와 창작 품질의 관계를 잰 공개 실험은 찾지 못했다. 위 "super-additive" 주장은 GPT-4o, 코딩 에이전트 지시 파일 맥락이다.

## Q4. 짧은 영상(쇼츠)용 AI 대본 도구·팀은 유지율을 위해 프롬프트와 비트를 어떻게 짜나

### Takeaway
실무 틀은 거의 같다: 1~3초 훅 → 약속 → 아이디어 하나만 쌓기 → 중간 리훅(반직관 반전) → 끝 2~3초 전 한 방 → 바로 끝내거나 처음으로 돌아가는 루프. "But/Therefore"(그런데/그래서) 인과 진행과 열린 고리(open loop)가 핵심 장치다. 유지율 수치를 출처와 함께 낸 곳은 찾지 못했다.

### Cited Findings
- OutlierKit 쇼츠 템플릿(35초 이하): Hook(0~1.5초, 첫 줄이 스크롤을 멈춘다) → Build(0:01.5~0:20, "Only one idea", 필요 없는 말은 다 자른다, 약 2.5단어/초) → Payoff(0:20~0:28, 약속을 빨리 지키고 끝 2~3초 전에 터뜨린다) → Loop(마지막 1~2초, 첫 화면으로 이어지는 줄). 훅 꼴로 stakes, contrarian(시청자의 믿음에 맞선다), curiosity-gap(구체적인 답을 약속하고 미룬다)을 든다. — [OutlierKit YouTube Script Template](https://outlierkit.com/resources/youtube-script-template/)
- 같은 출처(검색 요약): "end each section before the viewer expects it to, and always with an open loop into the next". 바이럴 구조 예로 Hook(0~3초) → micro-promise(3~7초) → rapid proof(7~18초) → rehook(18~22초, counterintuitive twist) → payoff(22~28초) → loop-inducing end. — [OutlierKit 검색 결과](https://outlierkit.com/resources/youtube-script-template/)
- Subscribr: 5비트(Hook 0~3초 → Explanation/Intrigue → Climax/Content → Resolution → "Abrupt End … with no outro"), "But Therefore" 인과 진행, open loop("the final step is the most important"). 유지율 수치나 출처는 없다. — [Subscribr, Scripting YouTube Shorts](https://subscribr.ai/youtube-strategy/scripting-youtube-shorts-engagement)

### Inferences
- 우리 흐름 규칙(1·5·10·13번 장면 비트)은 실무 틀과 거의 같다. 빠진 건 두 가지다: (1) **"아이디어 하나만"**: B는 10~12번에서 두께·땀샘·지문으로 새 주제를 연다. (2) **한 방(payoff)을 끝 가까이 둔다**: B의 가장 놀라운 사실(DKK2를 없애자 모든 쥐 발바닥에 털)이 9번째에 나오고, 남은 장면은 덜 놀라운 사실이다. A의 10번 리훅("얼마나 이어지고 어떻게 끝날까요?")은 본 물음보다 작은 물음이라 리훅이 오히려 긴장을 낮춘다.
- 실무 틀의 "no outro"는 우리 채널의 고정 구독 멘트와 부딪힌다. 고정 멘트는 브랜드 결정이니 두고, 그 앞 문장을 한 방으로 만드는 게 현실적이다.
- 40초 13장면에 약 2.5단어/초(영어 기준)를 맞추는 문제는 이미 channel.toml의 길이 규칙이 다룬다.

### Gaps
- 얼굴 없는 채널 도구(예: 자동 쇼츠 생성 SaaS)의 실제 시스템 프롬프트 원문은 찾지 못했다. 템플릿 글은 마케팅 글이고, 유지율 효과의 근거가 없다.
- 한국어 과학·상식 쇼츠의 유지율 데이터는 찾지 못했다. 채널 자체의 YouTube Studio 유지율 곡선(장면별 이탈)이 가장 좋은 근거가 될 것이다(메모리상 Studio 접근 방법이 있음).

## Q5. 점검: 어떤 규칙이 건조함을 만들고, 무엇이 빠졌나(줄 단위)

### Takeaway
건조함의 주된 원인은 (1) 재미 목표·시청자 역할이 없는 역할 문장, (2) "원리·근거·예시를 한 장면에 하나씩 쌓는다"와 "장면마다 하나 더 담아 채운다"는 사실 적재 규칙, (3) 출처 이름을 말하라는 규칙과 근거 꼬리표의 연도·인원 요구, (4) 하나뿐인 훅 예시(베끼기), (5) 4번째 장면 통념 강제(B에서는 허수아비 통념), (6) 흐름만 보는 검수기다. 빠진 것은 재미 목표, 시청자의 몸 장면, 비유, 한 방의 위치, 전문 용어 상한, 요약이 아닌 마지막 줄이다.

### Cited Findings (로컬 파일 근거)
- 역할 문장에 목표·말투가 없다: "너는 유튜브 쇼츠용 ${lang} 내레이션 대본을 쓴다. 대본은 TTS가 그대로 읽고…" — `prompts/script.md:7`
- 사실 적재 규칙: "다시 거는 장면 사이에는 원리·근거·예시를 한 장면에 하나씩 쌓는다." — `prompts/script.md:20`. 채널판: "장면마다 이유·원리·비교·생활 속 예시 중 하나를 더 담아 내용으로 채운다." — `channels/ko-40sec-facts/script.md:20`
- 출처 이름 의무: "출처를 흐리는 말 … 쓰지 않는다. 시트에 출처 이름이 있으면 그 이름을 말하고, 없으면 그 사실을 쓰지 않는다." — `prompts/script.md:38`. 채널: "근거가 된 기관이나 연구는 영상에서 한두 번 말로 밝힌다" — `channels/ko-40sec-facts/script.md:19`. 꼬리표: "(연구 1편): '한 연구에서는'과 연도·인원." — `channels/ko-40sec-facts/script.md:13`
  - 결과: A12 "영국 국민보건서비스는 … 설명합니다", B6 "펜실베이니아대 연구팀은 … 밝혔습니다". 출처가 문장의 주어가 되어 뉴스 보도 꼴이 됐다.
- 훅 예시 하나: "좋은 예: 하품, 왜 옮을까요? 남이 하품하면 따라 하게 되는 이유, 뇌 속에서 찾아보겠습니다." — `channels/ko-40sec-facts/script.md:6`. 공통 규칙 "둘째 문장은 이 영상이 무엇에 답하는지 약속한다" — `prompts/script.md:17`
  - 결과: A1 "…뇌 속에서 찾아보겠습니다", B1 "…피부 속에서 찾아보겠습니다". 예시를 그대로 베꼈다.
- 4번째 장면 통념 강제: "4번째 장면은 뒤집을 흔한 설명(통념)으로 끝내고" — `channels/ko-40sec-facts/script.md:23`
  - 결과: B4 "흔히 손발바닥 피부에는 털을 만드는 장치가 아예 없다고 생각하기 쉽습니다." 시청자가 실제로 품은 통념이 아니라 지어낸 허수아비라 가짜 반전처럼 들린다. A4(귀신 이야기)는 진짜 통념이라 덜 어색하다.
- 첫 4장면이 정의로 시작: "1~4번째 장면은 누구나 겪는 몸의 순간과 흔한 설명으로" — `channels/ko-40sec-facts/script.md:22`. A2 "…상태가 바로 수면마비입니다", B2 "…털이 전혀 없는 피부입니다"는 사전식 정의다. "겪는 순간"을 시청자 시점·지금 시제로 쓰라는 말이 없다.
- 리훅의 크기 기준이 없음: "남은 물음 하나를 새로 열거나, 아직 말하지 않은 반전을 예고한다." — `channels/ko-40sec-facts/script.md:28`. A10은 더 작은 물음(지속 시간)을, B10은 다른 주제(털 대신 무엇이 있나)를 열었다.
- 마지막: "정보의 마무리나 반전을 마침표로 끝낸 뒤" — `channels/ko-40sec-facts/script.md:25`. A13 "가위눌림은 깨어난 뇌에 꿈의 마비가 남은 순간입니다."는 요약이다. B13은 쥐 이야기로 맺어 첫 물음(사람 손바닥)과 어긋난다.
- link 관계 목록이 논리 관계뿐이다: "훅·이어서·이유·반전·예시·답" — `prompts/script.md:25`, `core/script.py:18`. 시청자가 무엇을 느낄지(궁금함·놀람·아하)는 계획하지 않는다.
- 검수기는 흐름·정확성만 본다: 역할 "앞뒤가 이어진다고 느끼는지 본다. 칭찬은 쓰지 않고 고칠 것만 적는다." — `prompts/script_proofread_ko.md:7`. 8개 항목 모두 오류 찾기이고, "사소한 취향 차이는 넘긴다" — `:29`. 6번 항목은 "상투적 강조"를 지적하게 해 표현을 무난한 쪽으로 민다 — `:22`.
- 다시 쓰기는 지적받은 장면과 그 앞뒤만 고친다: "그 밖의 장면은 한 글자도 바꾸지 않는다" — `core/script.py:180-182`. 한 방의 위치나 주제 이탈처럼 구조 문제는 국소 수정으로 못 고친다.
- user 메시지에서 재미에 가장 가까운 말은 "이 분야를 즐겨 보는 시청자에게 맞는 각도로 쓴다" 한 줄이다 — `core/script.py:209`.
- 지시문의 절반 가까이(45~60줄)가 영상 prompt 규칙이고, 스키마가 장면마다 내레이션과 80~110단어 영어 prompt를 번갈아 쓰게 한다 — `prompts/script.md:45-60`, `core/script.py:16-23`.

### Inferences
- 원인 순위(영향 큰 순, 추정):
  1. **목표·역할 부재(script.md:7)**: 모델이 무엇을 최적화할지 모른다. Opus는 지시하지 않은 걸 추론해 넣지 않는다(Q1).
  2. **사실 적재(script.md:20, 채널:20)**: "장면마다 하나 더" → 장면이 사실 카드가 되고 이야기 줄기가 끊긴다. B10~12의 주제 이탈도 남은 장면을 시트의 다른 사실로 채운 결과로 보인다.
  3. **출처 주어화(script.md:38, 채널:13·19)**: 기관이 주어인 문장은 보도 꼴이다. 정확성에 필요한 건 강도 표시("쥐 실험에서는")이지 기관명이 아니다.
  4. **훅 예시 하나(채널:6)**: 두 대본 모두 같은 둘째 문장을 썼다(관찰).
  5. **4번째 통념 강제(채널:23)**: 통념이 시트에 없으면 허수아비를 만든다.
  6. **검수기의 범위(proofread:7·29)**: 재미 문제는 "취향"으로 넘겨서 건조한 대본이 통과한다.
  7. **단서 중복(공통:36, 채널:9~17)**: 정확성에 꼭 필요하지만 문장마다 되풀이하면 리듬이 무겁다.
- 빠진 지시:
  - 재미 목표와 말하는 사람(신기한 걸 막 알아낸 친구 같은 과학 커뮤니케이터)
  - 시청자의 몸에서 지금 일어나는 장면(2인칭·현재 시제·감각)
  - 어려운 원리마다 생활 비유 하나
  - "한 방" 사실 하나를 고르고 10번째 뒤에 둔다
  - 전문 용어 상한(B는 DKK2·윈트 신호·털주머니·투명층·융선, 5개)
  - 리훅은 본 물음 안에서, 더 크거나 더 가까운 물음으로
  - 마지막 줄은 요약이 아니라 첫 물음을 새로 보게 하는 한 줄
- 사실 시트도 한계일 수 있다: B는 사람 손바닥의 답이 시트에 없고 쥐 근거뿐이라 마지막을 쥐 이야기로 맺을 수밖에 없었던 것으로 보인다(시트는 보지 못함).

### Gaps
- A·B의 실제 사실 시트와 검수 로그(어떤 지적이 있었는지)는 보지 않았다. 건조함 중 시트 탓인 부분과 지시문 탓인 부분을 나누려면 시트가 필요하다.
- `prompts/script_revise*.md`는 이번 범위에서 읽지 않았다.

## Q6. 바로 넣을 수 있는 한국어 규칙과 구조 변경 제안(사실 정확성은 유지)

### Takeaway
제일 싼 순서: (1) 역할·목표 문단 하나 추가, (2) 사실 적재·출처·통념 규칙을 긍정형으로 바꿔 쓰기, (3) 훅 예시를 서로 다른 꼴 3~4개로 늘리기, (4) 비유·시청자 장면·한 방·용어 상한·마지막 줄 규칙 추가. 모두 글 파일만 고치면 되고 비용은 0이다. 다음으로 (5) 스키마에 `angle`(한 방)·`hooks`(후보 3개) 필드를 장면 앞에 두기(호출 수 그대로, 출력 토큰 조금 증가), (6) 검수기에 예/아니오 재미 항목 4~5개 추가(실패가 늘면 다시 쓰기 호출이 는다). 대본 전체를 여러 벌 쓰고 판정하는 Best-of-N과 내레이션·영상 prompt 2단계 분리는 효과 대비 비용이 커서 나중으로 미룬다.

### Cited Findings
- 근거: 긍정형 지시·이유 붙이기·다양한 예시 3~5개·역할 문장 — [Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices). 후보를 먼저 내게 하면 실행마다 다른 방향이 나온다 — [Prompting Claude Opus 4.8](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-4-8). 후보 분포를 말하게 하면 다양성 1.6~2.1배 — [Verbalized Sampling](https://arxiv.org/abs/2510.01171). 계획 후 쓰기는 79.4%가 더 흥미롭다고 평가 — [Plan Before You Write](https://proceedings.neurips.cc/paper_files/paper/2025/hash/9cd4b3c9f2f1bb0208d36ca986f6f4f9-Abstract-Creative_AI_Track.html). LLM 판정자는 전반적 창의성 판단에서 전문가와 상관이 없다 — [Art or Artifice](https://arxiv.org/html/2309.14556v2). 서사는 이해·흥미·몰입을 높인다 — [Dahlstrom 2014](https://pmc.ncbi.nlm.nih.gov/articles/PMC4183170). 아이디어 하나, 한 방은 끝 2~3초 전 — [OutlierKit](https://outlierkit.com/resources/youtube-script-template/).

### Inferences — 바로 넣을 규칙 문안(파일 말투에 맞춘 평서형)

**P1. 역할·목표(`prompts/script.md:7` 바로 뒤에 한 문단 추가)**
```
목표는 시청자가 끝까지 듣고 "아, 그래서 그랬구나" 하며 누군가에게 말해 주고 싶어지는 것이다. 신기한 걸 막 알게 된 사람이 옆 사람에게 들려주듯 쓴다. 교과서처럼 정의 → 기전 → 근거 → 요약을 늘어놓으면 시청자는 중간에 넘긴다. 정확함은 사실 시트가 지키고, 재미는 어떤 사실을 고르고 어떤 순서로 어떤 말로 꺼내는지로 만든다.
```
이유: 역할 문장과 목표·이유(Q1). 비용 0.

**P2. 사실 적재 → 이야기 줄기(`prompts/script.md:20` 바꾸기)**
```
- 다시 거는 장면 사이는 사실 목록이 아니라 한 줄기 이야기다. 장면마다 앞 장면이 남긴 물음에 답하면서 다음 물음을 하나 남긴다(그런데 → 그래서 → 그런데). 첫 장면의 물음에 답하는 데 쓰이지 않는 사실은 시트에 있어도 쓰지 않는다. 남는 길이는 새 사실이 아니라 핵심 사실을 비유나 시청자의 몸 장면으로 한 번 더 보여 주는 데 쓴다.
```
`channels/ko-40sec-facts/script.md:20`도 같은 뜻으로 바꾼다:
```
- 한 장면이 클립 8초를 거의 다 채울 만큼 길다. 새 사실을 더 얹기보다, 그 장면의 사실을 생활 비유나 시청자가 겪는 장면으로 풀어 채운다. 한 영상에 쓰는 사실은 대여섯 개면 충분하다.
```
("대여섯 개"는 조정값. 너무 적으면 장면이 비고 너무 많으면 지금처럼 목록이 된다.)

**P3. 한 방과 리훅(`prompts/script.md` 흐름 절에 추가, 19줄 보강)**
```
- 쓰기 전에 사실 시트에서 시청자가 가장 놀랄 사실 하나를 "한 방"으로 정한다. 한 방은 두 번째로 다시 거는 장면 뒤(13장면이면 11~12번째)에 둔다. 앞 장면들은 한 방을 알아듣는 데 필요한 것만 깐다.
- 다시 거는 물음은 첫 장면의 물음 안에 있어야 하고, 앞 물음보다 시청자에게 더 가깝거나 더 놀라운 물음이어야 한다. 새 주제를 열지 않는다.
```

**P4. 시청자의 몸 장면(흐름 절 또는 채널 규칙에 추가)**
```
- 적어도 세 장면은 시청자의 몸에서 지금 일어나는 장면으로 쓴다. 주어를 시청자로 두고 현재 시제로, 보이고 들리고 느껴지는 것을 말한다(예: 눈은 떠졌는데 손가락 하나 안 움직입니다). 정의("~한 상태가 바로 ~입니다")로 장면을 열지 않는다. 느낌 묘사도 사실 시트가 말한 범위 안에서 한다.
```

**P5. 비유와 전문 용어(사실 절 39줄 뒤에 추가)**
```
- 어려운 원리는 생활 속 비유 하나로 옮긴다(예: 꿈꾸는 동안 몸에 채워 두는 안전벨트). 비유는 원리를 바꾸지 않는 데까지만 쓰고, 비유에 시트에 없는 원인·숫자를 싣지 않는다.
- 전문 용어(단백질·유전자·신호·조직 이름)는 한 영상에 둘까지만 쓴다. 처음 나올 때 하는 일을 바로 붙이고("털을 막는 단백질 DKK2"), 그 뒤로는 하는 일로 부른다.
```

**P6. 출처 말하기(`prompts/script.md:38`과 `channels/…/script.md:13·19` 바꾸기)**
공통 38줄:
```
- "전문가에 따르면", "~라고들 합니다"처럼 출처를 흐리는 말은 쓰지 않는다. 시트의 사실은 모두 출처가 있으므로 문장마다 출처를 말할 필요는 없다. 말할 때는 시트의 이름 그대로 쓴다.
```
채널 19줄:
```
- 근거의 강도("쥐 실험에서는", "한 연구에서는", "관련이 있다")는 꼬리표대로 꼭 말한다. 기관·대학 이름은 영상 전체에서 한 번까지만, 그 이름이 사실을 더 믿게 하거나 더 신기하게 만들 때 쓴다. 출처를 문장의 주어로 세우지 않고 사실을 주어로 세운다(나쁜 예: 펜실베이니아대 연구팀은 ~라고 밝혔습니다 / 좋은 예: 쥐 발바닥에는 털을 막는 단백질이 따로 있었습니다).
```
채널 13줄: `(연구 1편): "한 연구에서는". 연도·인원은 그 숫자가 놀라울 때만 붙인다.`
정확성 영향: 강도 표시(동물·관찰·반론)는 그대로 두므로 사실 강도는 지켜진다. 운영상 출처 추적은 fact_ids와 설명란 출처(앱이 붙임)가 이미 맡는다.

**P7. 단서 한 번만(채널 9줄 끝에 추가)**
```
단서는 한 사실에 한 번, 그 사실이 처음 나올 때 붙인다. 같은 사실을 이어서 풀어 말할 때는 단서를 되풀이하지 않는다.
```

**P8. 4번째 장면 통념 완화(`channels/…/script.md:23` 첫 문장 바꾸기)**
```
- 이 멘트는 "앞과 다른 이야기가 나온다"는 약속이다. 4번째 장면은 멘트가 뒤집을 무언가로 끝낸다: 시트에 있는 흔한 설명이나 속설, 겉으로 보이는 모습, 또는 시청자가 당연하게 느끼는 감각. 시트에 없는 통념을 "~라고 생각하기 쉽습니다"로 지어 세우지 않는다. 멘트 뒤에는 그것과 실제로 다른 몸속 사실을 긍정형으로 말한다.
```

**P9. 훅 예시를 서로 다른 꼴로(`channels/…/script.md:6` 바꾸기)**
```
  - 예시는 꼴만 보여 준다. 둘째 문장을 예시와 같은 말("~에서 찾아보겠습니다")로 쓰지 않는다. 둘째 문장은 강의 순서를 알리지 않고, 시청자가 겪는 모순 하나로 궁금함을 날카롭게 한다.
  <examples>
  <example>하품, 왜 옮을까요? 남이 입을 벌리면 내 턱도 저절로 따라 내려갑니다.</example>
  <example>가위눌림, 왜 몸이 안 움직일까요? 정신은 또렷한데, 손가락 하나 말을 듣지 않습니다.</example>
  <example>지금 손바닥을 한번 보세요. 온몸에 나는 털이 여기에만 없습니다.</example>
  <example>추우면 왜 이가 딱딱 부딪칠까요? 내가 시킨 적도 없는데 턱이 혼자 떨립니다.</example>
  </examples>
```
주의: 예시 문장에도 사실 주장이 담긴다. 사실이 거의 없는 "겪는 순간" 묘사로만 쓰고, 다른 주제의 대본에 사실이 새어 들지 않게 한다. 지시문을 바꾸면 `tests/test_prompts.py`가 채널로 채워지는지 본다.

**P10. 마지막 줄(`channels/…/script.md:25` 보강)**
```
    - 고정 멘트 앞 문장은 요약이 아니라 한 방이다. 첫 장면의 물음에 대한 답을 앞에서 쓴 비유나 장면으로 다시 꺼내, 시청자가 그 순간을 새로 보게 하는 한 줄로 맺는다. 첫 장면이 사람의 몸을 물었으면 사람 이야기로 맺는다(시트에 동물 근거뿐이면 "쥐에서는 ~였습니다. 사람도 같은지는 아직 연구 중입니다"처럼 강도를 지킨다).
```
(괄호 안의 "아직 연구 중"은 시트에 그런 말이 있을 때만 쓸 수 있다. 없으면 "쥐 실험에서는"까지만 말한다. 이 단서는 운영자가 시트 꼴을 보고 정한다.)

**P11. link에 감정 비트 더하기(`prompts/script.md:25`, `core/script.py:18` description)**
```
link에는 앞 장면과의 관계 하나와, 이 장면을 들은 시청자가 느낄 것 하나(궁금함·놀람·아하·웃음·안도)를 함께 적는다(예: "반전·놀람: 앞 장면의 '귀신'을 뒤집는 렘수면 마비"). 같은 느낌이 세 장면 넘게 이어지지 않게 한다.
```
비용: link는 저장하지 않는 필드라(`core/script.py:17`) 출력 토큰이 조금 는다.

### Inferences — 구조 변경(비용·복잡도)

| 안 | 내용 | 비용·복잡도 | 기대 효과·위험 |
|---|---|---|---|
| S1 계획 필드 | `Script`에 `scenes`보다 앞에 `angle: str`("한 방 사실 ID와 그걸 살릴 비유 한 줄")과 `hooks: list[str]`(서로 다른 꼴 훅 3개, 마지막에 고른 것)을 둔다. 저장하지 않는다(link처럼). | 호출 수 그대로, 출력 +200~400토큰. 스키마 두 필드, `flat()`에서 빼면 된다. | 계획 후 쓰기·후보 말하기의 근거(Q2)와 맞는다. Opus 5.5는 thinking이 이미 계획하므로 효과는 **재 봐야 한다**. 자기가 낸 후보를 자기가 고르는 건 따로 판정하는 것보다 약하다. |
| S2 검수기 재미 항목 | `script_proofread_ko.md`에 "9. 시청자가 끝까지 들을 이유가 있는가"를 더하고, 예/아니오 하위 항목만 둔다: ① 첫 장면 물음과 상관없는 장면이 있는가 ② 가장 놀라운 사실이 10번째 장면 앞에 다 나왔는가 ③ 전문 용어가 셋 이상인가 ④ 기관·대학 이름이 두 번 이상이거나 문장 주어인가 ⑤ 시청자의 몸 장면이 하나도 없는가 ⑥ 마지막 고정 멘트 앞 문장이 앞 내용 요약인가 ⑦ 둘째 문장이 "~찾아보겠습니다" 같은 강의 안내인가. 역할 문장에 "흐름과 함께, 처음 듣는 시청자가 끝까지 들을지도 본다"를 넣고 "사소한 취향 차이는 넘긴다"는 이 항목들에 걸리지 않는 것만으로 좁힌다. | 글 파일만. 실패가 늘면 다시 쓰기(Opus) 호출이 는다. | TTCW처럼 구체 항목이라 LLM 판정의 낮은 신뢰도를 줄인다. **위험:** ②·①은 구조 문제라 "지적한 장면과 앞뒤만" 고치는 다시 쓰기(`core/script.py:180`)로는 못 고친다. 구조 항목은 `Verdict`에 `rewrite: bool` 같은 표시를 두어 처음부터 다시 쓰기(커밋 1d480ad의 버튼 경로)로 보내야 한다(코드 변경). 그 전엔 ③④⑤⑥⑦(국소로 고칠 수 있는 것)만 넣는 게 안전하다. |
| S3 훅 Best-of-N | 훅·마지막 줄만 후보 3개씩 따로 뽑아 별도 호출로 고른다. | 호출 +1(짧음). | 다양성 근거(Verbalized Sampling) 있음. S1으로 대부분 얻을 수 있어 S1 효과를 본 뒤에 판단. |
| S4 대본 전체 Best-of-N | 대본 2~3벌 + 판정 호출. | Opus 비용 2~3배 + 판정. | LLM 판정자의 전체 인상 판단은 믿기 어렵다(Art or Artifice). 비추천. |
| S5 내레이션과 영상 prompt 분리 | 1차: link·sentence·fact_ids만 13장면. 2차: 확정된 문장으로 prompt·prompt_ko. 또는 한 호출 안에서 스키마를 `scenes`(내레이션) 다음 `prompts` 목록으로 재배치. | 2차 호출 추가, 또는 `Script`·`flat()`·`revise` 쪽 변경. | 지시문의 절반인 영상 규칙과 장면마다 끼는 영어 100단어가 내레이션의 흐름을 끊는다는 추정(Price of Format는 간접 근거). 효과를 재기 전엔 미룬다. |

권장 순서: P1·P2·P6·P9 먼저(글 파일, 비용 0) → 같은 주제 3~5개로 전후 비교(사람이 듣고 고르기, 가능하면 Studio 유지율) → P3~P5·P7·P8·P10·P11 → S1 → S2(국소 항목만) → 필요하면 S2 구조 항목 + 다시 쓰기 경로.

검증 아이디어: 가위눌림·손바닥 털을 같은 사실 시트로 다시 돌려, 위 S2 ①~⑦ 항목 수를 전후로 세면 회귀 지표로 쓸 수 있다(사람 판단을 대신하지는 못한다).

### Gaps
- 제안의 효과는 측정하지 않았다. 문안은 근거와 두 대본의 관찰에서 끌어낸 가설이다.
- 스키마 필드 순서대로 생성된다는 전제는 기존 코드 주석(`core/script.py:17`)이 이미 기대고 있는 것이고, 이번에 따로 확인하지 않았다.
- P2의 "대여섯 개", P5의 "둘까지", P4의 "세 장면"은 근거 있는 수치가 아니라 시작값이다.

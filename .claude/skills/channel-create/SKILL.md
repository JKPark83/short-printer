---
name: channel-create
description: 새 YouTube 쇼츠 채널을 기획하고 channels/<id>/ 폴더(channel.toml·script.md·video_style.md·thumbnail.md·trends.md)를 만든다. 사용자가 새 채널을 추가·기획하고 싶어 하거나("채널 하나 더 만들자", "영어 채널 추가", "새 채널 기획해줘"), 채널 이름·채널 설명을 지어 달라고 할 때 쓴다. 코드는 고치지 않는다.
---

# 채널 만들기

shorts-printer는 `channels/<id>/` 폴더 하나가 채널 하나다. 이 스킬은 인터뷰로 채널을 정하고 그 폴더만 만든다. **코드(`src/`)는 절대 고치지 않는다.** 값이 모자라면 만들지 말고 사용자에게 말한다.

시작 전에 읽는다: `.claude/rules/channels.md`(키 설명), `channels/ko-40sec-facts/`의 다섯 파일(본보기), `channels/`(이미 있는 id).

## 1. 인터뷰

사용자에게 한국어로 묻는다. AskUserQuestion이 있으면 한 번에 2~4개씩 보기를 주고(보기마다 짧은 설명, 맨 앞이 추천), 없으면 번호 목록으로 묻는다. 이미 말한 것은 다시 묻지 않는다.

1라운드
- 콘셉트·분야: 채널이 다룰 주제 영역(좁을수록 추천이 잘 붙는다)
- 시청자: 누가, 왜 보나
- 언어: ko·en·ja 정식 지원, 그 밖은 띄어쓰기 기본 규칙(자막 품질이 떨어질 수 있다고 알린다)

2라운드
- 말투: 존댓말/반말, 차분/빠르고 자극적
- 길이와 장면 수: 예) 40~50초·7장면, 25~30초·5장면. 문장 길이는 언어에 맞게(ko 48~55자, en 12~16단어 정도에서 제안)
- 장면 화풍: 3D 해설, 실사풍, 일러스트, 미니어처 등(영어 머리말 한 줄로 정리할 것)

3라운드
- 목소리: 성별·나이대·느낌(ID는 나중에 사용자가 고른다)
- 썸네일 톤: 경고·반전·숫자형 등, 강조색
- 추천: 수집 지역(KR·US·JP…), 검색 키워드(없어도 됨)
- 하루 목표 편수, 민감 주제 확인(건강·법률·금융·정치를 다루면 켜 둔다)

## 2. 제안

한 번에 보여 주고 고르게 한다.

- **채널 이름 후보 3개**: 이름마다 이유 한 줄. 100자 이하(짧을수록 좋다), 외우기 쉽고, 대상 언어로 검색될 낱말을 담는다. 기존 유명 채널·상표와 겹치지 않게.
- **채널 설명** 하나: 1000자 이하. 첫 두 줄에 "누구에게 무엇을 주는지"(검색·채널 미리보기에 이 부분만 보인다), 대상 언어 키워드를 자연스럽게, 업로드 주기. 채널 언어로 쓴다.
- **규칙 요약**: 대본(훅·말투·마무리·제목 꼴), 장면 영상(화풍·사람 표현), 썸네일(줄 수·강조·호기심 꼴·금지), 추천(먼저 볼 주제·계절).
- **id**: 언어 접두어 + 소문자 케밥(`en-space-facts`). `channels/`에 이미 있으면 다른 것.

사용자가 고치라고 하면 고친 부분만 다시 보여 준다.

## 3. 폴더 만들기

고른 뒤 `channels/<id>/`에 다섯 파일을 쓴다. `channels/ko-40sec-facts/`와 같은 모양·같은 키 순서로, 글 파일은 같은 길이감(짧은 목록)으로.

- `channel.toml`: 맨 위 주석 한 줄 그대로(`# 채널 설정. 키 설명은 docs/plan/multi-channel.md와 .claude/rules/channels.md`).
  - `concept`·`language`·`daily_goal`·`sensitive_gate`·`llm = "claude"`
  - `[script]` scenes·sentence·unit(ko·ja `chars`, en 등 띄어쓰기 언어 `words`)·duration
  - `[tts]` provider `elevenlabs`, `sample`은 채널 언어 한두 문장. 목소리 ID를 아직 모르면 `[tts.voices]`에 `elevenlabs = "기본 목소리"` 한 줄만 두고(`.env`의 `ELEVENLABS_VOICE_ID`) `default`는 비운다.
  - `[video]` provider `flow`, `style`은 영어 한 문장(“…, same art style in every shot.”로 끝낸다)
  - `[style]` accent·background(언어 기본 글꼴이면 `font`는 적지 않는다)
  - `[thumbnail]` max_line·max_total(ko 9·16을 기준으로 언어 폭에 맞춘다. en은 단어가 길어 14·24쯤)
  - `[publish]` provider `youtube`, category(교육 27, 그 밖 22), channel_id는 비워 둔다
  - `[trends]` region·keywords·production(우리 제작 방식 한 단락: 대본·TTS·자막·장면 화풍·못 쓰는 것)·weights(합 100)
- `script.md`·`video_style.md`·`thumbnail.md`·`trends.md`: 2단계에서 정한 규칙. 제목 `# …` 한 줄 + 짧은 목록. 지시문은 한국어로 써도 되고, 대본에 그대로 나올 예시 문구는 채널 언어로.
- 비밀(키·토큰·비밀번호·이메일)은 어떤 파일에도 넣지 않는다.

확인:

```bash
uv run python -c "from shorts_printer.core import channel; print(channel.load('<id>'))"
```

오류가 나면 메시지의 키를 고치고 다시 돌린다. 통과할 때까지.

## 4. 마무리 안내

만든 파일 목록과 함께 사용자가 손으로 할 일을 알려 준다.

1. YouTube에서 같은 Google 계정으로 **브랜드 채널**을 만들고, 고른 이름과 설명을 넣는다.
2. ElevenLabs에서 그 언어 목소리를 골라 ID를 `[tts.voices]`에 `ID = "화면 이름"`으로 넣는다(기본은 `default`).
3. `uv run sp youtube-login --channel <id>`를 돌리고, Google 동의 화면에서 **그 브랜드 채널**을 고른다.
4. (선택) 스튜디오 대체 업로드를 쓰면 채널 `UC…` id를 `publish.channel_id`에 넣는다.
5. 웹 화면 상단바에서 새 채널을 고르면 대시보드·추천·새 작업이 그 채널을 따른다(서버가 켜져 있으면 채널 목록을 다시 읽도록 재시작이 필요할 수 있다).

이 스킬은 채널 폴더만 만든다. 코드·`.env`·`.secrets/`는 건드리지 않는다.

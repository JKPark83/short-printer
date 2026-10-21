# 채널 더하기

목적: 새 YouTube 채널을 코드 수정 없이 `channels/<id>/` 폴더 하나로 붙인다.

## 만드는 법

- 기본은 `channel-create` 스킬(`.claude/skills/channel-create/`): 인터뷰 → 이름·설명·스타일 제안 → 폴더 생성.
- 손으로 할 때는 `channels/ko-40sec-facts/`를 통째로 복사해 고친다.
- id는 언어 접두어가 붙은 소문자 케밥(`en-space-facts`). 정규식 `[a-z0-9][a-z0-9-]{0,63}`. 기존 작업의 `channel` 필드에 남으므로 만든 뒤 바꾸지 않는다.
- 확인: `uv run python -c "from shorts_printer.core import channel; print(channel.load('<id>'))"`. 틀리면 pydantic 오류로 어느 키인지 알려 준다.

## 파일

| 파일 | 내용 |
|---|---|
| `channel.toml` | 값(아래 표) |
| `script.md` | 대본 규칙: 훅, 말투(존댓말·반말), 사실 확인, 마지막 문장, 제목 꼴. 채널 언어로 써도 된다 |
| `video_style.md` | 장면 영상 규칙: 화풍, 물체 디테일·빛, 사람 표현, 원리 보여 주는 법 |
| `thumbnail.md` | 썸네일 문구 규칙: 줄 수, 강조, 호기심 꼴, 하지 않는 것 |
| `trends.md` | 추천 주제를 고를 때 먼저 볼 것(계절, 시청자가 바로 써먹는 것 등) |
| `ideas.md` | 선택. 주제 찾기의 주제 기준. 없으면 `concept` 안에서 고른다 |

글 파일은 부를 때마다 읽으므로 고치면 다음 작업부터 바로 반영된다. 맨 앞 `--- … ---` 머리말은 빠진다.
이 글들은 공통 지시문 `prompts/*.md`(대본 뼈대·고쳐 쓰기·썸네일·주제 고르기)의 `${channel_…}` 자리에 들어간다. 모든 채널에 걸리는 규칙은 `prompts/`를 고친다.

## channel.toml 키

| 키 | 뜻 |
|---|---|
| `name` / `description` | YouTube 채널 이름(100자 이하)·설명(1000자 이하). 브랜드 채널을 만들 때 그대로 넣는다 |
| `concept` | 채널 분야 한 줄. 대본·추천이 이 안에서 돈다 |
| `language` | 대본·음성·자막 언어 코드. `ko`·`en`·`ja` 정식, 그 밖은 띄어쓰기 기본 규칙 |
| `daily_goal` | 대시보드 하루 목표 편수 |
| `sensitive_gate` | true면 건강·법률·금융·정치 대본은 사람이 확인해야 장면을 만든다 |
| `llm` | registry `LLMS` 이름(`claude`) |
| `[script]` `scenes` | 장면(=문장) 수 |
| `[script]` `sentence` / `unit` | 문장 하나 길이 [최소, 최대]와 단위(`chars` 글자 · `words` 낱말) |
| `[script]` `duration` | 목표 길이 문구(지시문에 들어간다. 예: `"40~50초"`) |
| `[tts]` `provider` | registry `TTSES` 이름(`elevenlabs` · `typecast`) |
| `[tts]` `default` / `sample` | 기본 목소리 키(없으면 voices 맨 앞) / 미리 듣기 문장(채널 언어) |
| `[tts.voices]` | `{목소리 키: 화면 이름}`. ElevenLabs는 목소리 ID(`elevenlabs` 키는 `.env`의 `ELEVENLABS_VOICE_ID`), Typecast는 `tc_…` ID |
| `[video]` `provider` | `flow`(사람이 올림) · `flow-auto`(전용 Chrome). 쓸 수 없으면 flow |
| `[video]` `style` | 모든 장면 프롬프트 앞 머리말. 영어 |
| `[style]` `font` | 글꼴. 비우면 언어 기본(ko Apple SD Gothic Neo · ja Hiragino Sans · en Helvetica Neue) |
| `[style]` `accent` / `background` | 강조색 `#RRGGBB` / 클립 없을 때 배경 그라데이션 두 색 |
| `[style]` `subtitle_limit` | 자막 한 덩어리 길이. 0이면 언어 기본 |
| `[style]` `voice_lufs` / `sfx_lufs` | 목소리를 맞출 크기(0이면 원본 그대로) / 장면 클립 효과음을 맞출 크기(그 뒤 70%). LUFS, 기본 0 / -21 |
| `[style]` `layout` | `band`(기본, 위아래 검은 띠 + 가운데 영상) · `full`(띠 없이 9:16 전체, 제목·자막은 위아래 UI 250px을 피한다) · `clean`(띠 없이 9:16 전체, 제목은 처음 1초만 보이고 사라진다, 썸네일은 band) |
| `[thumbnail]` `max_line` / `max_total` | 썸네일 문구 한 줄 / 전체 길이 한도 |
| `[publish]` `provider` / `category` | `youtube` / YouTube 카테고리 번호(22 = People & Blogs, 27 = Education) |
| `[publish]` `channel_id` | `UC…`. 스튜디오 화면으로 올릴 때 이 채널로 간다. 비우면 Chrome에서 고른 채널 |
| `[publish]` `footer` | 업로드할 때 설명 맨 끝에 빈 줄 하나 두고 붙는 문구(AI 표시 등). 비우면 안 붙는다 |
| `[publish]` `sources_heading` | 설명란 출처 머리말(`출처`·`出典`). 비우면 출처를 붙이지 않는다 |
| `[trends]` `production` | 우리 제작 방식 한 단락(주제 찾기 지시문에 들어간다) |
| `[trends]` `weights` | `trend`(화제성)·`curious`(호기심)·`fit`(제작 적합도)·`fresh`(차별화)·`safe`(안전성) 다섯 개, 합 100 |
| `[trends]` `keywords` | 주제 찾기 [인기 쇼츠 참고]에서 쓸 YouTube 검색어 목록(OR로 묶는다). 낱말마다 띄어쓰기 없이(`우리몸`), 띄어 쓰면 검색이 거의 안 잡힌다. 비면 인기 쇼츠 참고를 못 쓴다 |
| `[research]` `provider` | registry `RESEARCHERS` 이름(`claude`) |
| `[research]` `domains` | 자료 조사 허용 사이트(`kdca.go.kr`처럼 도메인만, `https://`·경로는 떼어 읽는다). `news`와 둘 다 비면 자료 조사 단계가 멈춘다 |
| `[research]` `news` | 언론 기사 사이트. `domains`와 합쳐 검색하고, 여기서 온 사실은 "보도"로 구별한다 |
| `[research]` `open` | true면 사이트 제한 없이 블로그·일반 웹까지 검색한다. `domains`·`news`는 먼저 볼 곳이 되고, 그 밖에서 온 사실은 "웹"으로 구별한다. 기본 false |
| `[research]` `languages` | 검색 언어 코드 목록. 비우면 `language` |
| `[research]` `queries_per_topic` / `max_pages` | 한 편에 쓸 검색 수(1~10, 기본 5) / 열어 볼 쪽 수(1~20, 기본 8). 비용 상한 |

## 만든 뒤 손으로 할 일

1. YouTube에서 같은 Google 계정에 브랜드 채널을 만들고 이름·설명을 넣는다.
2. ElevenLabs에서 그 언어 목소리를 골라 ID를 `[tts.voices]`에 넣는다.
3. `uv run sp youtube-login --channel <id>` → Google 동의 화면에서 그 브랜드 채널을 고른다. 토큰은 `.secrets/channels/<id>/youtube_token.json`.
4. (선택) 스튜디오 대체 업로드를 쓰면 `publish.channel_id`에 `UC…`를 넣는다.

## 하지 않는 것

- 채널 폴더에 키·토큰·비밀번호를 넣지 않는다. 비밀은 `.env`와 `.secrets/`에만 둔다.
- 채널 때문에 코드를 고치지 않는다. 값이 모자라면 channel.toml 키를 더하는 걸 먼저 제안한다(`core/channel.py`와 이 표를 같이 고친다).

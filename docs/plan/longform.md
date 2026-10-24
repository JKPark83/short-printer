# 롱폼(16:9, 8~12분) 지도 역사 영상

목적: 숏폼과 같은 작업 흐름(주제 → 조사 → 대본 → 검수 → 제작 → 렌더 → 검수 → 업로드)으로, 지도 위에서 전선이 움직이는 역사 해설 영상을 만든다. 근거가 된 것은 `korean-war-video`(3분, HyperFrames)와 jkpark 플러그인의 `history-map-video` 스킬이다.

## 정한 것 (2026-10-24 사용자 답)

| 항목 | 결정 |
|---|---|
| 영상 | 지도 중심(HyperFrames) + 일부 장면만 Flow 클립 |
| 채널 | 롱폼 전용 새 채널(`channel-create` 스킬로 만든다, `format = "long"`) |
| 길이 | 기본 8~12분(장면 약 45~65개, `[long] minutes`) |
| 사람 확인 | 주제 고르기 · 대본 승인 · 초안 승인 · 업로드(최종) |
| 자막 | 영상에 굽는다(화면 아래 가운데, 음성 낱말 시각에 맞춰). YouTube CC는 기본으로 꺼져 있어 대부분 못 본다. SRT는 만들지도 올리지도 않는다 |
| Flow 장면 | 대본을 쓸 때 LLM이 장면마다 `map`·`clip`을 붙인다. clip은 `[long] max_clips`(기본 8개, 16:9 360p 장면당 6크레딧) 이하. 맨 첫 장면은 늘 clip, 나머지는 고루. 대본 승인 전에 사람이 바꾼다 |
| 기록 사진 | 지도 계획 때 LLM이 장마다 한 장 안팎(많아야 8장, clip 장면 제외)으로 고르고 Commons 검색어를 단다. 초안 때 `media.fetch_photo`가 퍼블릭 도메인·CC0 jpg만 받는다(지도 제외). 지도 오른쪽에 셔터 소리와 뜨고, 끝 크레딧에 "사진 Wikimedia Commons" |
| 컷 | 한 문장(장면)을 3~4초 컷으로 나눈다: 지도 계획 때 LLM이 장면마다 `shots`(낱말마다 옮겨 갈 카메라)를 달고 코드가 1.2초에 옮긴다. 조금 붙은 컷은 1.5초까지 늦추고 더 붙으면 뺀다. shots가 모자라 4초 넘게 머무는 곳은 코드가 3.5초마다 같은 자리를 당겼다 물린다 |
| 숫자·병력 | 지도 계획 때 LLM이 화살표마다 병력 그림(`unit`: 현대 soldier·tank·plane·ship, 옛날 spearman·cavalry·sailship)을, 숫자를 말하는 장면에 숫자 카드(`stats`, 10 이상만)를 단다. 배지는 화살표를 따라 줄지어 행군하고(화면에서 짧으면 뒤 배지를 뺀다), 카드는 날짜 아래에서 0부터 센다(ko는 만 단위) |
| 화면 | 웹 대시보드 + CLI |
| 썸네일 | 첫 `turn` 장면 지도 스냅샷 + 큰 글자(대본 `thumb`), 16:9 자동 |

## 단계

작업 단계는 `core/longform.py`의 `STEPS_LONG`(2~11, 열 개)이다. 1(주제)과 12(업로드)는 숏폼과 같은 주제 찾기·업로드를 쓴다.

| # | 단계 | 하는 일 | 멈춤 |
|---|---|---|---|
| 1 | 주제 | `core/trends.py`가 롱폼이면 YouTube 검색 `videoDuration: medium`(4~20분), 지시문 `prompts/long_trend_idea.md`. 주제 찾기 스케줄(source=trend)은 추천만 알리고 작업을 만들지 않는다. 주제 목록 스케줄은 작업을 만들고 대본 승인에서 멈춘다 | **사람: 주제 고르기** |
| 2 | `research` | `research.gather`. 사실 상한은 `[long] max_facts`(기본 40, 숏폼 12) | — |
| 3 | `script` | `longscript.write`: 목차(장 5~8개) → 장마다 장면 `{narration, kind: map/clip, beat, fact_ids, visual, clip_prompt}`. clip 상한은 코드(`cap_clips`)가 지킨다 | — |
| 4 | `proofread` | `longscript.proofread`: 모델 채점(날짜 순서·사실 출처·화면과 내레이션·흐름) + 코드 점검(clip 비율·어림 길이·근거 없는 숫자). 떨어져도 멈추지 않는다 | **사람: 대본 승인**(`script_ok`) |
| 5 | `voice` | 채널 TTS(`[tts] provider`), 장면마다 mp3 + 낱말 시각. 낱말 시각이 없는 TTS는 글자 수로 나눈다. 같은 글·목소리는 다시 읽지 않는다 | — |
| 6 | `plan` | `mapplan.plan`: LLM이 지도 전체(world: 범위·지명·전선 상태) 한 번 + 장마다 카메라·라벨·화살표·날짜. 시각은 고른 낱말의 시작으로 코드가 맞춘다 | — |
| 7 | `map` | Esri 타일 → 이어 붙이기·색 보정(ffmpeg) → `wide.jpg`·`detail.jpg`, Natural Earth 땅·국경 path. 지도 값이 그대로면 다시 받지 않는다 | — |
| 8 | `clips` | `kind=clip` 장면만 영상 공급자 16:9 판으로 8초 | 빠진 클립은 사람이 올릴 때까지 기다림 |
| 9 | `draft` | `film.json` → HyperFrames 프로젝트 → `check` → **장마다 스냅샷 한 장**(장 첫 장면 `시작 + max(1.5, 길이/2)`초) | **사람: 초안 승인**(`draft_ok`, "지도 고쳐 줘" → 6단계부터 다시) |
| 10 | `render` | `hyperframes render`(음악·효과음은 9단계에서 배치), 썸네일(1280×720, turn 장면 앞 쉼에서 찍어 자막이 없다), 크레딧 | — |
| 11 | `final` | 자동 측정만: 길이(±1.5초)·음량(−16 LUFS ±1, true peak −1 dBTP 이하)·3초 넘는 무음·자막 끝이 영상 끝을 넘는지. 지적은 로그로만 | **사람: 영상을 보고 업로드** |
| 12 | 업로드 | `pipeline.publish`: YouTube 비공개 + 썸네일. 자막은 영상에 구워져 따로 올리지 않는다 | — |

## 구조 (architecture.md 규칙 그대로)

| 경로 | 새로 / 고침 | 내용 |
|---|---|---|
| `core/channel.py` | 고침 | `format: Literal["short","long"] = "short"`, `LongCfg`(`minutes`, `max_clips`, `max_facts`, `music`) |
| `core/longform.py` | 새로 | 단계 함수(`STEPS_LONG`·`RUN`), 사람 대기(`gate`), 시각 계산(`clock`), 단계마다 `hyperframes.ready()` 확인 |
| `core/longscript.py` | 새로 | 대본 모델(`Chapter`·`Outline`·`Scene`·`Revision`), 쓰기·고치기·검수, clip 상한 |
| `core/mapplan.py` | 새로 | 지도 계획 모델(`World`·`Camera`·`Label`·`Arrow`·`SceneMap` 등), `plan`, `film_parts`(좌표·점 개수·키 겹침을 코드가 고친다) |
| `core/film.py` | 새로 | 스킬의 `gen.py` 엔진을 옮긴 것: film dict → `index.html` + `compositions/{map,story,end,clips}.html` |
| `core/sound.py` | 새로 | 효과음·음악 자리 계산(`assets/sfx/sfx.json`·`assets/music.json`), 크레딧 |
| `core/subtitles.py` | 고침 | 낱말 시각으로 자막 줄(`cues`, 초안 단계에서 `film.json` `captions`로 굽는다). 덩어리 길이는 `[style] subtitle_limit`, 없으면 언어 기본 × 2 |
| `core/trends.py` | 고침 | 채널 `format`에 따라 길이 필터·지시문 고르기 |
| `core/research.py` | 고침 | 사실 상한을 `[long] max_facts`로 |
| `core/schedule.py` | 고침 | 롱폼 주제 찾기 스케줄(source=trend)은 추천만 알리고 작업을 만들지 않는다. 주제 목록 스케줄은 작업을 만들고 대본 승인에서 멈춘다 |
| `infra/hyperframes.py` | 새로 | `npx hyperframes init/check/snapshot/render` 실행(시간 제한, check·snapshot 30분) |
| `infra/maptiles.py` | 새로 | Esri 타일 받기 + ffmpeg `tile`·`eq` 보정 + Natural Earth → SVG path(점 솎기만, shapely 안 씀) |
| `infra/media.py` | 새로 | 배경 음악 내려받기, `.cache/music/`에 두고 다시 쓴다 |
| `infra/ffmpeg.py` | 고침 | 음량 측정·무음 구간·썸네일 글자 카드 |
| `adapters/flow.py`·`flow_auto.py` | 고침 | 화면비를 인자로(`Flow("16:9")`·`FlowAuto("16:9")`) |
| `registry.py` | 고침 | `flow-16x9`·`flow-auto-16x9` 등록. 롱폼 채널은 `video.provider`의 `-16x9` 판을 저절로 고르고, 못 쓰면 `flow-16x9` |
| `adapters/youtube.py` | 고침 | `captions.insert`, 범위 `youtube.force-ssl` 추가 → **채널마다 다시 로그인 한 번**. 영상은 8 MiB씩 이어 올리기 |
| `prompts/long_*.md` | 새로 | 주제(`long_trend_idea`)·목차(`long_outline`)·장면(`long_scenes`)·검수(`long_proofread`)·고치기(`long_revise`)·지도(`long_map_world`·`long_map_scenes`) |
| `assets/music.json`, `assets/sfx/` | 새로 | 음악은 분위기별 incompetech(CC BY) 곡 주소 표(`war`·`loss`·`march`·`reflective`), 처음 쓸 때 받는다. 효과음은 CC0 파일 + `sfx.json`. 크레딧 문구는 표에서 |
| `web/` | 고침 | `job_long.html`: 롱폼 단계·장면 지도/클립 바꾸기·초안 스냅샷·승인 버튼·비용 어림 |
| `cli.py` | 고침 | `sp run`(롱폼 채널이면 롱폼) · `sp approve <작업> script\|draft` · `sp upload <작업>` |

새 의존성: Node의 `npx hyperframes`만(파이썬 패키지는 늘지 않는다). 렌더 하나에 수 분~십수 분이 걸려 시간 제한을 길게 둔다.

## 어려운 곳과 대응

- **LLM이 쓰는 좌표·전선**: 틀릴 수 있다. 코드로 지역 상자 밖 좌표, 상태마다 점 개수 불일치, 카메라 키 겹침을 막고, 사람은 초안 스냅샷에서 본다. "지도 고쳐 줘" 문장 → 지도 계획만 다시 쓴다.
- **전선 하나로 안 되는 이야기**(진격로·해전·포위된 곳): 스킬 `references/map.md`의 표대로 화살표·라벨·윤곽선으로 그린다. 점령 영역은 영상 하나에 하나.
- **길이**: 10분이면 TTS 약 4,000자, 대본·지도 계획 LLM 호출 여러 번, Flow 클립 8개 안팎(360p 장당 6크레딧). 작업 화면 대본 칸에 비용을 보인다.
- **렌더 시간**: 큐 한 줄이 렌더 동안 막힌다. 처음엔 그대로 두고(`worker._loop`의 `# ponytail:`), 숏폼이 밀리면 렌더 전용 스레드를 둔다.
- **Flow 거절**: 롱폼은 프롬프트를 고쳐 다시 시도하지 않는다. 사람이 [지도로 바꾸기]를 누르거나 클립을 직접 올린다.

## 순서 (마일스톤마다 테스트 + 실제 한 번)

| # | 마일스톤 | 상태 |
|---|---|---|
| 1 | **엔진**: `core/film.py` + `infra/hyperframes.py` + `infra/maptiles.py`. 한국전쟁 데이터로 원본과 같은 프레임 | 끝 |
| 2 | **채널·대본**: `LongCfg`, 롱폼 지시문, 목차 → 장면 → 검수, 지도 계획 | 끝 |
| 3 | **음성·렌더**: 채널 TTS, 음악·효과음 배치, 음량 측정, SRT, 썸네일 | 끝(3분 시험 렌더 확인) |
| 4 | **Flow 16:9 클립** | 끝 |
| 5 | **주제 찾기·웹 화면·승인 버튼·CLI** | 끝 |
| 6 | **업로드**: 이어 올리기, 자막 업로드, 다시 로그인 안내 | 끝 |
| 7 | **채널 만들기**(`channel-create`: 이름 후보 여럿 → 사용자가 고른다) → 실제 영상 한 편(8~12분) | 남음 |

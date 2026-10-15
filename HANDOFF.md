# shorts-printer 인수인계 (2026-10-13)

## 다음 세션 시작 지시문 (복사해서 붙여 넣기)

```
/Users/jkpark/my-toy/shorts-printer/HANDOFF.md를 읽고 이어서 진행해.
먼저 "다음 할 일" 1번(실제 Claude 대본 생성 확인)을 하고, 결과와 "사용자 결정 대기" 질문을 정리해서 보고해.
비용이 드는 실행은 시작 전에 예상 비용을 한 줄로 알려 줘.
```

## 배경과 목표

- 앞선 리서치에서 Claude로 숏폼(쇼츠·릴스·틱톡) 수익화 방법을 조사했다. 결론은 이미 대중화된 포맷을 따라 하루 2~3편을 만들고, 그 과정을 모니터링 사이트로 확인하는 것이다. 원문은 이전 세션 기록에 있다: `~/.claude/projects/-Users-jkpark-my-toy-shorts-factory/7fa089c3-012a-44ce-bb18-32d0748a6835.jsonl`
- 사용자 요청(원문): MoneyPrinter(https://github.com/FujiwaraChoki/MoneyPrinter)를 참고해 shorts-factory와 같은 레벨에 새 폴더를 만들고, 테스트용 파이프라인을 구성한다.
  - LLM은 Claude API를 쓴다.
  - TTS나 다른 LLM이 필요하면 먼저 말하고, 무료 플랜부터 쓴다.
  - 파이프라인이 한눈에 보이는 Web UI/UX를 만든다. 와이어프레임은 ui-ux-pro-max-skill을 최대한 활용한다.
  - 궁금한 점은 사용자에게 적극적으로 묻는다.

## 현재 상태

**완료·검증됨**
- 6단계 파이프라인: 대본(Claude, 장면마다 영어 프롬프트) → 음성(TTS 공급자) → 자막(ASS) → 영상 소스(영상 공급자, 기본 Google Flow 직접 올림) → 썸네일(Claude 문구 + 첫 장면 배경) → 렌더(ffmpeg). 결과물은 1080×1920 mp4. 위아래 검은 띠, 위 띠에 썸네일 문구, 첫 0.5초는 썸네일.
- LLM·TTS·영상·업로드는 포트(`ports/`) 뒤에 있고 `registry.py`가 채널 `channels/<id>/channel.toml`대로 고른다. 영상은 `[video] provider`(flow | flow-auto), 음성은 작업마다 고른 목소리. 구조는 `docs/plan/multi-channel.md`와 `.claude/rules/`.
- 웹 화면은 대시보드와 작업 상세 두 페이지다.
  - 대시보드: 새 작업, 환경 점검, 작업 목록, 오늘 목표 3편.
  - 작업 상세: 단계 표시, 단계별 결과 카드, 실행 로그, 완성 영상, 다시 시도.
- `uv run pytest -q` 결과 74개 통과, live 마커 2개 제외(공급자 구조 백엔드까지).
- 브라우저 E2E 통과.
  - 실패한 작업을 [다시 시도]로 이어서 완성했다.
  - 진행 중에 단계 표시와 카드가 새로고침 없이 바뀌고, 재생 중인 음성이 끊기지 않았다.
  - 375px에서 가로 스크롤이 없다.
- 코드 리뷰에서 확인된 24건과 UI/UX 리뷰에서 확인된 10건을 반영했다.

**검증 안 됨**
- 실제 Claude 대본 생성. 브라우저 E2E에서는 script.json을 손으로 넣었다.
- 사용자가 22:09에 `.env`를 저장했고, `ANTHROPIC_API_KEY`는 값이 있다(값은 열어 보지 않음). `CLAUDE_MODEL`은 비어 있다.
- Flow 반자동 흐름 전체: 휴대폰(tailscale serve)에서 프롬프트 복사 → Flow 생성 → 장면별 업로드 → 자동 재개 → 완성 뒤 클립 교체로 렌더만 다시.
- 22:12에 사용자가 `sp web`(포트 8765)을 새로 켰다. `.env`를 저장한 뒤라 키를 읽었을 것이다.

## 실행

```bash
cd /Users/jkpark/my-toy/shorts-printer
uv sync
uv run sp web                 # http://127.0.0.1:8765
uv run sp run "주제" --voice LKOcTG4J4tYTPR9DnLeM   # 화면 없이 한 편
uv run pytest -q              # 기본으로 live 제외
uv run pytest -q -m live      # 실제 Claude 호출(비용 발생)
```

## 구조

| 경로 | 역할 |
|---|---|
| `src/shorts_printer/config.py` | `.env` 로더, ffmpeg 경로, 기본 모델, 허용 호스트(`SP_HOSTS`) |
| `registry.py` / `ports/` / `channels/<id>/` | 조립 지점(이름 → 구현, 채널마다 `Services`) / 인터페이스 / 채널 설정(`channel.toml`과 대본·영상·썸네일·추천 규칙 글) |
| `core/script.py` | Claude 대본(Pydantic `Script`: 제목, 설명, 태그, 장면 6~7개 `Scene{sentence, prompt, term}`), 비용 계산. script.json에는 `sentences`·`prompts`·`search_terms`를 같은 개수의 배열로 푼다 |
| `core/scenes.py` | 장면 목록 `scenes()`(장면별 초 포함), `set_clip()`. 영상 공급자(flow, flow-auto)는 `registry.VIDEOS`, 못 쓰면 flow |
| `core/voice.py` | ElevenLabs 하나(`adapters/elevenlabs.py`)와 채널 목소리(`[tts.voices]`, ko-40sec-facts는 미스터킴이 기본). 대체 공급자는 없다. 문장별 길이를 timing.json에 기록 |
| `core/subtitles.py` / `core/render.py` / `infra/ffmpeg.py` | 자막 cue·ASS 생성, ffmpeg 렌더(타임아웃 600초). 장면은 문장 시작 시각으로 나누고(`frames()`), 클립은 1080×880 칸에 맞춰 가운데를 자른다. 짧으면 마지막 화면에서 멈춤 |
| `core/thumbnail.py` | 채널 `thumbnail.md` 본문을 지시문으로 문구를 정한다. 합성은 `render.thumbnail`(배경은 첫 장면 클립 0.5초, 없으면 단색) |
| `core/pipeline.py` | 단계 실행. 이미 끝난 단계는 건너뛰고, 실패하거나 Ctrl+C로 멈추면 failed로 기록. 빠진 장면 클립이 있으면 `Wait`로 멈춰 status `waiting`(실패 아님). `publish()`는 YouTube 업로드 |
| `adapters/youtube.py` | 표준 라이브러리만으로 데스크톱 OAuth(PKCE) 로그인(`sp youtube-login --channel <id>`), 메타데이터 한도 맞추기, 비공개 resumable 업로드 |
| `infra/store.py` / `infra/sqlite.py` | `Record`(상태·결과물 문서·로그를 저장소에), 예전 폴더 옮기기(`migrate`), 원자적 쓰기, 로그 마스킹(redact) / SQLite 저장소(`shorts.db`, `docs/plan/storage.md`) |
| `infra/worker.py` | 작업 스레드 하나와 큐. 제작과 업로드가 같은 큐를 쓴다. `redo(id, steps, script=, **fields)`는 지정한 단계만 다시 돈다(썸네일·대본 고치기, 클립 교체) |
| `web/app.py` | FastAPI와 Jinja. `/`, `/jobs`, `/jobs/{id}`, `/api/jobs/{id}`, `/api/jobs/{id}/retry`, `/api/jobs/{id}/upload`, `/api/jobs/{id}/clips/{i}`(장면 클립 업로드, raw body) |
| `web/static/app.js` / `style.css` | 폴링(작업 1.5초, 대시보드 3초), id 단위 부분 교체, 포커스 복원 |
| `design-system/shorts-printer/` | ui-ux-pro-max로 만든 MASTER.md와 pages/*.md(Minimalism & Swiss, 다크) |
| `docs/wireframe.md` | 화면 와이어프레임과 상태별 문구 |

`shorts.db`에 남는 것: 상태(예전 `job.json`), 결과물 문서 `script.json`·`clips.json`·`timing.json`·`cues.json`·`thumb.json`(문구·이전 문구, 이름은 예전 파일 이름 그대로), 로그(예전 `log.txt`). 백업은 `jobs/`·`trends/`와 `shorts.db`를 같이.

작업 폴더에 남는 파일: `voice.wav`, `subs.ass`, `final.mp4`, `poster.jpg`, `thumb.ass`, `clips/clip{i}.mp4`(장면 i 원본 클립, 0부터), `title.ass`(위 띠 제목), `thumbnail.jpg`(업로드 뒤 thumbnails.set, 실패해도 업로드는 done)

## 바꾸기 전에 알아야 할 결정

- **Claude 호출**
  - anthropic SDK 1.13.0의 `client.beta.messages.parse(output_format=Script)`를 쓴다.
  - haiku가 아닐 때만 `betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"`를 붙인다.
  - 응답을 읽기 전에 refusal인지 확인한다.
  - 비용은 `resp.model` 기준으로 계산하고, 모르는 모델이면 None으로 두고 화면에서 숨긴다.
  - 기본 모델은 `claude-opus-5-5`이고, `.env`의 `CLAUDE_MODEL`로 바꾼다.
- **썸네일**: 규칙은 채널 `thumbnail.md` 한 곳에만 둔다(코드에 규칙을 다시 적지 않는다). 렌더의 위 띠 제목은 thumb.json의 문구를 쓰고, 없으면 대본 제목. 글자 크기는 `1400 // 가장 긴 줄 글자 수`(위 띠 최대 140, 썸네일 최대 150).
- **ffmpeg**: 자막 필터(libass) 때문에 `ffmpeg-full`(`/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg`)을 쓴다.
- **공급자**
  - 영상 공급자 계약은 `label`, `hint`, `ready()`, `make(scenes, out, log)`. 등록부는 dict 하나다. TTS는 ElevenLabs 하나뿐이다.
  - 영상 공급자는 job.json에 고정하지 않는다. 영상 소스 단계가 돌 때마다 채널 `channel.toml`의 `[video] provider`를 읽어서, 그 값을 바꾸고 서버를 다시 켜면 대기 중 작업도 [다시 시도]로 새 공급자로 이어 간다.
  - 목소리 값은 ElevenLabs 목소리 ID이고 `"elevenlabs"`는 .env `ELEVENLABS_VOICE_ID`(미스터최)다. 예전 작업의 edge·say 목소리는 음성 단계에서 "다른 목소리를 골라 주세요"로 멈춘다.
- **단계 순서**: script → voice → subtitles → footage → thumbnail → render. 음성을 먼저 만들어 공급자와 작업 화면이 장면별 초(`sec`)를 안다. 사람을 기다리는 단계는 뒤로 갔다.
- **클립 대기**: 빠진 장면이 있으면 공급자가 아니라 `step_footage`가 `Wait`를 던진다(수동·자동 같은 규칙). 마지막 클립이 올라가면 서버가 바로 큐에 넣는다. footage가 done인 작업에서 클립을 바꾸면 렌더만(장면 0이면 썸네일도) 다시 돈다. 올린 작업은 409.
- **새 영상 공급자 붙이기**(Seedance·Veo는 구현 안 함): `adapters/`에 파일 하나 + `registry.VIDEOS`에 한 줄 + `.env.example`에 키 한 줄(`.claude/rules/providers.md`). `make`가 지킬 것:
  - 없는 장면만 받는다. `scene["prompt"]`가 None이면 log 남기고 건너뛴다.
  - 길이는 지원 길이 가운데 `sec - 0.5` 이상인 가장 짧은 값. 화면비는 4:3, 없으면 16:9, 소리 끔.
  - 결과는 `out / scene["file"]`에 원자적으로 쓰고(tmp에 쓴 뒤 `os.replace`), 장면마다 `{"file", "source": label}`을 yield.
  - 장면 하나의 영구 실패(정책 거절)는 건너뛰고, 429·5xx는 안에서 재시도, 인증 오류는 던진다(다시 시도하면 없는 장면만 다시 요청).
  - 비동기 생성이면 작업 ID를 `out / f"clip{i}.task"`에 적어 두고 재시작 때 새로 요청하지 말고 그 ID를 폴링한다(두 번 과금 방지).
  - 유료 공급자를 붙이면 `job_cost`에 영상 비용을 더한다.
- **보안**
  - `TrustedHostMiddleware`는 127.0.0.1, localhost, `.env`의 `SP_HOSTS`만 받는다(DNS 리바인딩 방지).
  - Origin 헤더가 다른 POST는 403으로 막는다(클립 업로드 포함). 다른 사이트가 사용자 브라우저를 통해 작업을 만들어 Claude 비용을 쓰지 못하게 하기 위해서다.
  - 휴대폰 접속은 `tailscale serve`(tailnet 전용)로만 연다. 로그인이 없으므로 `tailscale funnel`은 쓰지 않는다. 기계를 여럿이 쓰면 로그인을 먼저 붙인다.
  - `redact()`는 이름이 `_API_KEY`나 `_AUTH_TOKEN`으로 끝나는 환경 변수 값(8자 이상)을 가린다. 새 키는 이름만 맞추면 된다.
- **Flow 워터마크**: 한국 계정의 Flow 결과물에는 워터마크가 붙는다. YouTube에 올릴 때 스튜디오에서 AI 생성 콘텐츠 라벨을 켠다(업로드 코드는 켜지 않는다).
- **정적 파일 캐시**: `?v=`가 서버 시작 시각이다. CSS나 JS를 고친 뒤에는 서버를 다시 켜야 브라우저가 새 파일을 받는다.
- **레이아웃**: 오른쪽 칸(영상과 로그)은 화면 높이가 1100px 이상일 때만 sticky다. 낮은 화면에서 sticky로 두면 로그 아래쪽이 가려진다.

## 알려진 한계 (일부러 남김)

- `sp run`이 도는 중에 `sp web`을 켜면 그 작업이 "중단"으로 표시된다. README에 안내했고, `recover()`에 ponytail 주석을 달았다. 고치려면 job.json에 pid를 남긴다.
- 작업 취소 버튼, 배경음악, 동시 작업은 없다. 작업 스레드는 하나뿐이다.
- 예전 스톡 작업에 덜 받은 `clip{n}.mp4`가 남아 있을 수 있다. 렌더가 깨진 클립에서 실패하면 그 장면을 다시 올린다.
- 업로드는 YouTube 비공개만, PUT 한 번에 보낸다(청크·이어 올리기 없음). 올리는 중 서버가 꺼지거나 PUT 응답을 못 받으면 failed로 두고 스튜디오에서 확인하라고 안내한다. TikTok·Instagram은 없다.

## 다음 할 일

1. **실제 Claude 대본 생성 확인**
   - 대시보드의 환경 점검에서 "Claude API 키"가 ✓인지 본다. ✕이거나 서버가 꺼져 있으면 서버를 다시 켠다.
   - `uv run pytest -q -m live`를 돌린다.
   - 웹에서 실제 주제로 한 편을 만들고 대본 품질, 토큰, 비용(opus 기준 몇 센트)을 보고한다.
   - 사용자가 `uv run sp youtube-login --channel ko-40sec-facts`를 한 번 하고, 그 영상을 비공개로 한 번 올려 스튜디오에서 확인한다.
2. **사용자 결정 대기** (지난 세션 끝에 물었고 아직 답이 없음)
   1. 기본 모델을 opus로 둘지, sonnet-5-5나 haiku-4-5로 바꿀지
   2. 따라 할 포맷(잡학 사실, 썰 읽기, 명언, 순위 등)
   3. 한국어만 할지, 영어도 만들지
   4. 업로드: YouTube 비공개는 붙임. TikTok·Instagram도 할지
   5. 하루 2~3편을 예약해서 자동으로 만들지, 지금처럼 버튼으로 만들지
   6. 배경음악을 넣을지
   7. ~~휴대폰 등 밖에서 접속할지~~ → `tailscale serve`(tailnet 전용)로 열었고 로그인은 없다. 기계를 여럿이 쓰거나 공개로 열 때 로그인을 붙인다
   8. ~~edge-tts를 유지할지~~ → 지우고 ElevenLabs 목소리 넷만 쓴다
   9. 지금 상태로 커밋할지
3. **답에 따라 할 일**: 예약 실행, Gemini TTS, 배경음악, 로그인

## 규칙

- 커밋과 푸시는 사용자가 요청할 때만 한다. 저장소는 `git init`만 한 master 브랜치이고 커밋이 없다. 커밋 메시지 끝에는 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`를 붙인다.
- 키는 `.env`에만 둔다(gitignore에 `.env*`, `!.env.example`). 값을 읽거나 출력하지 않는다. 확인이 필요하면 `grep -c '^KEY=..*' .env`처럼 설정 여부만 본다. 로그 마스킹(redact)은 그대로 둔다.
- `/Users/jkpark/my-toy/client_secret_*.json`과 `AuthKey_*.p8`는 읽지 않는다.
- 코드 주석과 문서는 짧은 한국어로, 기존 스타일에 맞춘다. 표준 라이브러리를 우선하고 의존성은 늘리지 않는다.
- 로직을 바꾸면 테스트를 하나 남기고, `uv run pytest -q`로 확인한다.
- 브라우저로 테스트했다면 직접 연 탭은 닫는다. 폼 제출은 로컬 앱(127.0.0.1)의 테스트 데이터일 때만 한다.
- `jobs/`의 작업 3개는 테스트 결과물이라 지워도 된다.

# shorts-printer

주제 한 줄을 넣으면 세로 쇼츠(1080×1920 mp4) 한 편을 만드는 테스트 파이프라인입니다.
[MoneyPrinter](https://github.com/FujiwaraChoki/MoneyPrinter)의 흐름을 따르되, 대본은 Claude API로 쓰고 진행 상황은 웹 화면에서 봅니다.

```
주제 → 1 대본(Claude) → 2 영상 소스(Pexels·Pixabay 또는 그라데이션) → 3 음성(ElevenLabs 또는 edge-tts) → 4 자막(ASS) → 5 썸네일(Claude + Pixabay 사진) → 6 렌더(ffmpeg) → final.mp4
```

## 준비

```bash
brew install uv ffmpeg-full      # ffmpeg-full에 자막 필터(libass)가 들어 있습니다
uv sync
cp .env.example .env             # ANTHROPIC_API_KEY를 채웁니다
```

| 서비스 | 필요 여부 | 비용 | 없으면 |
|---|---|---|---|
| Claude API (`ANTHROPIC_API_KEY`) | 필수 | 유료, 한 편에 몇 센트 | 대본 단계에서 멈춥니다 |
| Pixabay (`PIXABAY_API_KEY`) | 선택 | 무료 | 그라데이션 배경으로 만듭니다 |
| Pexels (`PEXELS_API_KEY`) | 선택 | 무료, 2026-10부터 새 키 발급 중단 | 키가 둘 다 있으면 세로 필터가 있는 Pexels를 씁니다 |
| ElevenLabs (`ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`) | 선택 | 유료, Starter 월 $6에 3만 글자(한 편 약 350자) | 목소리 목록에 안 나옵니다. 실패하면 edge-tts로 다시 읽습니다 |
| edge-tts | 키 없음 | 무료(비공식) | macOS `say`(Yuna)로 읽습니다 |
| YouTube Data API (`YOUTUBE_CLIENT_SECRET`) | 선택 | 무료, 하루 업로드 100편 | 업로드 버튼이 안 나옵니다. 직접 올립니다 |
| YouTube Data API 키 (`YOUTUBE_API_KEY`) | 선택 | 무료, 하루 10,000유닛(주제 찾기 한 번 약 101유닛) | 주제 찾기를 못 씁니다. 주제는 직접 넣습니다 |

대본 모델은 기본이 `claude-opus-5-5`입니다. 비용을 줄이려면 `.env`의 `CLAUDE_MODEL`을 `claude-sonnet-5-5`나 `claude-haiku-4-5`로 바꿉니다.

## 실행

```bash
uv run sp web                    # http://127.0.0.1:8765
uv run sp run "고양이가 상자를 좋아하는 이유" --voice ko-KR-InJoonNeural   # 화면 없이 한 편
```

- 대시보드에서 주제와 목소리를 고르고 [만들기]를 누르면 대기열에 들어갑니다. 한 번에 한 편씩 만듭니다.
- 작업 화면에서 단계별 진행, 대본·영상 소스·음성·자막 결과, 실행 로그, 완성 영상을 볼 수 있습니다.
- 실패하면 [다시 시도]가 끝난 단계는 건너뛰고 실패한 단계부터 이어서 만듭니다.
- 서버를 껐다 켜면 만들던 작업은 "중단"으로 표시됩니다. [다시 시도]로 이어 갈 수 있습니다.
- `sp run`이 도는 동안 `sp web`을 새로 켜면 그 작업도 "중단"으로 표시됩니다. 둘을 동시에 쓰지 마세요.

결과물은 `jobs/<작업 id>/`에 쌓입니다. `final.mp4`가 완성 영상이고 `script.json`에 제목·설명·태그가 있습니다.

## 썸네일과 화면 구성

- 썸네일 규칙은 `.claude/skills/shorts-thumbnail/SKILL.md`에 있습니다. 썸네일 단계가 이 파일 본문을 그대로 Claude 지시문으로 읽으므로, 규칙을 바꾸려면 이 파일만 고치면 됩니다.
- Claude가 문구(1~2줄, 강조 낱말 하나는 노랑)와 영어 검색어를 정하고, Pixabay 사진 후보 가운데 한 장을 고릅니다. 다른 영상에서 이미 쓴 사진은 후보에서 빠집니다. 사진이 없거나 `PIXABAY_API_KEY`가 없으면 첫 장면이나 단색 배경을 씁니다.
- 영상은 위아래가 검은 띠이고 가운데(560~1440px)에 영상이 들어갑니다. 위 띠에는 썸네일 문구가 영상 내내 뜨고, 자막은 영상 칸 아래쪽에 들어갑니다. 아래 띠는 쇼츠 화면의 채널명·제목에 가리므로 비워 둡니다.
- 썸네일은 영상 첫 0.5초에도 전체 화면으로 들어갑니다. 쇼츠 피드는 맞춤 썸네일 대신 영상 장면을 보여 줄 때가 많기 때문입니다.
- 완성된 작업은 썸네일 카드의 [다시 만들기]로 썸네일과 영상을 다시 만들 수 있습니다(이미 올린 영상은 스튜디오에서 바꾸세요).

## 주제 찾기

지금 조회수가 빨리 오르는 한국 쇼츠를 모아 뜯어보고, 바로 만들 만한 주제를 추천합니다. 웹의 주제 찾기 화면이나 `uv run sp trends [키워드] --period 1d|3d|7d`로 돌립니다.

1. **수집**: YouTube Data API로 기간 안의 한국어 쇼츠(3분 이하)를 모아 시간당 조회수 순으로 8개를 고릅니다.
2. **분석**: 영상마다 yt-dlp로 받아 컷(장면 전환)을 세고 컷마다 프레임을 뽑아 Claude에게 보여 줍니다. 주제·포맷·훅·영상 종류·내레이션·인기 이유·따라 만들기 쉬운 정도를 받습니다. 받은 영상은 바로 지우고 프레임(jpg)만 남깁니다. 다운로드가 막히면 썸네일과 정보로만 봅니다.
3. **선정**: Claude가 우리 제작 방식(스톡 영상·TTS·자막)으로 만들 수 있는 주제 3~5개를 고르고, 화제성·제작 적합도·차별화·안전성 점수(가중치 35·35·15·15)로 순위를 매깁니다. 화제성은 참고 쇼츠의 시간당 조회수로 코드가 계산합니다.

추천 주제로 작업을 만들면 그 각도가 대본 참고로 넘어갑니다. 결과는 `trends/<id>/`에 쌓입니다. Claude 비용은 기본 모델(opus)로 한 번에 대략 $0.3~0.8입니다(영상 8개 분석 + 선정 1번).

키는 [Google Cloud 콘솔](https://console.cloud.google.com/)에서 YouTube Data API v3를 사용 설정하고 사용자 인증 정보 → API 키로 만들어 `.env`의 `YOUTUBE_API_KEY`에 넣습니다. 업로드용 OAuth(`YOUTUBE_CLIENT_SECRET`)와는 따로입니다.

## YouTube 업로드

완성된 작업 화면에서 [승인하고 YouTube에 올리기]를 누르면 `script.json`의 제목·설명·태그로 내 채널에 **비공개**로 올립니다. 공개 전환은 YouTube 스튜디오에서 직접 합니다. 하루 100편까지 올릴 수 있습니다.

처음 한 번만 준비합니다.

1. [Google Cloud 콘솔](https://console.cloud.google.com/)에서 프로젝트를 만들고 **YouTube Data API v3**를 사용 설정합니다.
2. OAuth 동의 화면을 **외부(External)**로 만들고 테스트 사용자에 내 계정을 넣습니다.
3. 게시 상태를 **프로덕션(In production)**으로 바꿉니다. 테스트 상태로 두면 로그인이 7일마다 풀립니다. 혼자 쓰면 앱 인증은 필요 없고, 로그인할 때 "확인되지 않은 앱" 경고에서 [고급] → [이동]을 누르면 됩니다.
4. 사용자 인증 정보에서 OAuth 클라이언트 ID를 **데스크톱 앱**으로 만들고 JSON을 내려받습니다.
5. `.env`의 `YOUTUBE_CLIENT_SECRET`에 그 JSON 경로를 넣습니다.
6. `uv run sp youtube-login`을 실행하고 브라우저에서 허용합니다. 토큰은 `.secrets/youtube_token.json`에 저장됩니다.

## 테스트

```bash
uv run pytest                    # 외부 API 없이 도는 테스트
uv run pytest -m live            # 실제 Claude API를 부르는 테스트(키 필요, 비용 발생)
```

## 알아 둘 점

- **edge-tts 패치.** 2026년 10월 Microsoft 쪽 주소 변경으로 edge-tts 7.2.8이 403을 냅니다. `voice.py`에서 접속 주소를 새 주소로 바꿔 씁니다([rany2/edge-tts#491](https://github.com/rany2/edge-tts/pull/491)). edge-tts가 고쳐진 버전을 내면 그 줄을 지우면 됩니다.
- **키 관리.** 키는 `.env`에만 둡니다. 로그와 화면의 오류 메시지에서는 키 값을 가립니다.
- **업로드는 YouTube 비공개만 합니다.** 올리는 도중 서버를 끄면 "실패"로 남습니다. 이미 올라갔을 수 있으니 YouTube 스튜디오에서 확인한 뒤 [다시 올리기]를 누르세요.

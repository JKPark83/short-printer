---
name: topic-insights
description: 채널의 유튜브·인스타 성과와 사용자가 준 터진 영상 링크(내 것·남의 것, 인스타 릴스·유튜브 쇼츠)를 분석해 주제 선정을 고친다. 추천 점수(CRITERIA) 가중치와 trends.md 점수 예시를 실제 성과로 보정하고, 터진 패턴으로 후속 주제를 제안하고, HTML 보고서를 낸다. "이 릴스 왜 터졌는지 분석해줘", "요즘 터진 영상 분석", "주제 선정 개선", "추천 점수 보정", "인사이트 분석", "/topic-insights" 같은 요청이나 주간 자동 실행(--auto)에 쓴다. 코드는 고치지 않는다.
---

# 주제 인사이트

목적: 무엇이 터졌고 왜 터졌는지(주제 덕인지 훅 덕인지) 숫자로 가리고, 그 결과를 주제 찾기에 되먹인다. 손대는 곳은 `channels/<id>/channel.toml`의 `[trends] weights`, `channels/<id>/trends.md`, `reports/`뿐이다. **`src/`는 고치지 않는다.**

시작 전에 읽는다: `.claude/rules/channels.md`, `channels/<id>/trends.md`, `channels/<id>/channel.toml`.

## 입력

`/topic-insights [링크…] [--channel <id>] [--auto]`

- `--channel`이 없으면 `channels/`의 채널 중에서 묻는다(링크가 있고 채널이 하나로 보이면 그 채널).
- 링크: `instagram.com/reel/…`·`/p/…`, `youtube.com/shorts/…`·`youtu.be/…`. 내 채널 영상이면 아래 1~3단계 데이터에서 찾아 깊게 보고, 남의 영상이면 4단계로 본다.
- `--auto`: 사람이 없는 주간 실행이다. 아무것도 묻지 않고 8단계의 PR 흐름으로 끝낸다.

도우미 스크립트: `S=.claude/skills/topic-insights/scripts/insights.py`, 실행은 `uv run python $S …`. 숫자(순위·상관·가중치 제안·터진 영상)는 스크립트가 정한다. 직접 다시 세지 않는다. 임시 파일은 스크래치패드(없으면 `mktemp -d`)에 둔다.

## 1. 유튜브 숫자 모으기

```
uv run python $S collect --channel <id> --out $T/data.json
```

YouTube Analytics API로 업로드한 영상마다 누적 조회수·계속 시청(engagedViews/views)·평균 시청 비율·공유·구독을 붙이고, 추천 당시 축별 점수(job `source` → picks.json)와 제목·첫 문장도 붙인다.

`youtube_error`가 있으면 사용자에게 그대로 알리고 인스타만으로 계속한다. 자주 나오는 것:
- "YouTube Analytics API를 켜야 해요": Google Cloud 콘솔 → API 및 서비스 → 라이브러리 → YouTube Analytics API 사용.
- 만료·권한 없음: `uv run sp youtube-login --channel <id>`(사용자가 터미널에서 한다).

## 2. 인스타 숫자 모으기 (내 채널)

`channel.toml`의 `publish.also`에 `instagram`이 있을 때만 한다. API는 429가 나서 쓰지 않고, 로그인된 Chrome에서 읽는다(claude-in-chrome. 도구는 ToolSearch로 한 번에 불러온다: `tabs_context_mcp`(createIfEmpty), `navigate`, `get_page_text`, `javascript_tool`, `computer`).

1. `https://www.instagram.com/accounts/insights/content/`에서 기간을 가장 길게 두고 릴스 카드 목록을 읽는다.
2. 릴스마다 `/insights/media/<pk>/`를 열어 조회·공유·저장·좋아요·댓글·도달·팔로워 아닌 사람 비율을 읽는다. 웹에는 평균 시청 시간이 없다.
3. 캡션 첫 줄과 주소(`/reel/<code>/`)도 같이 적어 `$T/ig.json`에 저장한다:
   `[{"caption": "…", "url": "https://www.instagram.com/reel/…/", "views": 0, "shares": 0, "saves": 0, "likes": 0, "comments": 0, "reach": 0, "nonfollower": 99.1}]`

숫자를 못 읽은 칸은 비워 두고(null), 지어내지 않는다. 다 읽으면 연 탭을 닫는다.

## 3. 보정 계산

```
uv run python $S fit $T/data.json --ig $T/ig.json > $T/fit.json
```

`fit.json`에 담기는 것:
- `counts`·`ig_unmatched`: 작업에 잇지 못한 릴스. 손으로 올린 릴스는 캡션 첫 줄을 제목과 맞춰 잇는다. 많으면 보고서에 적는다.
- `correlation`: 축마다 추천 점수와 성과 순위의 상관(유튜브·인스타·합친 것). 7일 안 된 영상은 뺀다.
- `weights`: 제안 가중치와 이유, `toml` 한 줄. trend·curious·fresh만 축당 ±5까지 옮기고, fit·safe는 그대로 둔다. 표본이 30편 미만이면 바꾸지 않는다.
- `hits`: 최근 28일 동안 채널 중앙값의 3배를 넘은 영상(유튜브 조회, 인스타 조회, 인스타 공유율 따로)과 바닥 5편.
- `outliers`: LLM이 높게(4~5) 매겼는데 바닥인 영상, 낮게(1~2) 매겼는데 최고인 영상.

## 4. 링크로 받은 영상 보기

링크마다 Chrome으로 연다.
- 공개 숫자(조회·좋아요·댓글, 유튜브는 공유가 안 보이면 빈칸), 캡션, 상위 댓글 10개를 읽는다. 댓글에서 사람들이 무엇에 반응했는지 본다(친구 태그·"나도"·반박).
- 화면: 열자마자(첫 1초) 한 장, 중간쯤 한 장을 `computer` screenshot으로 찍어 훅(첫 화면의 글자·장면·첫 문장)을 적는다.
- 같은 계정 평균: 프로필 릴스(쇼츠) 탭에서 최근 12편 조회수의 중앙값을 내고 몇 배인지 적는다. 유튜브는 `uv run yt-dlp -j --skip-download <링크>`와 `uv run yt-dlp --flat-playlist -j --playlist-end 12 <채널>/shorts`로 숫자를 받아도 된다.
- 내 채널 유튜브 영상이면 `uv run python $S video --channel <id> <videoId>`로 구간 유지율·유입 경로까지 본다.

## 5. 왜 터졌나 가르기

터진 영상과 바닥 영상을 나란히 놓고 갈래를 가린다. 근거 숫자를 함께 적는다.
- **주제가 끌었다**: 인스타 공유율이 높거나 친구 태그 댓글이 많다. 처음 보는 사람(팔로워 아닌 사람) 비율이 높다. 남에게 보내고 싶은 이야기다.
- **훅·대본이 붙잡았다**: 유튜브 계속 시청·평균 시청 비율이 높고, 첫 3초 유지율이 높다. 주제는 평범한데 첫 문장이 다르다.
- **같은 영상이 플랫폼마다 다르게 갔다**: 유튜브는 유지력, 인스타는 공유로 퍼진다. 한쪽에서만 터졌다면 왜 그런지 적는다.
- 내 채널 터진 영상은 상위 5~10편에 `video` 명령을 돌려 유입 경로(Shorts 피드 비율)와 첫 구간 유지율을 확인한다.
- 시청자층·유입 경로가 크게 바뀌었으면(예: 45세 이상 쏠림) 따로 적는다.

추천에서 만든 영상만 점수가 있다(사람이 10개 중 골랐다). 그래서 상관은 "고른 것 안에서"의 신호라는 점을 보고서에 적는다.

## 6. CRITERIA 보정안

- **가중치**: `fit.json`의 `weights.proposed`를 그대로 쓴다. 바꾸지 않는다는 결론이면 이유(`why`)를 적는다.
- **점수 예시**: `trends.md`의 "호기심 점수 예시(우리 채널 실적 …)"를 `outliers`와 `hits`로 고친다.
  - 5점 줄에는 실제로 터진 우리 영상을, 1~2점 줄에는 바닥 영상을 넣는다. 영상마다 근거 숫자를 괄호에 적는다(예: 인스타 공유 15.6%, 유튜브 계속 시청함 71%).
  - 점수 줄마다 3개 안팎만 남기고, 머리말의 날짜(예: 2026-10)를 이번 달로 바꾼다.
  - 같은 결이 되풀이되면(예: 민망한 몸 이야기가 공유를 끈다) 위쪽 규칙 목록에 한 줄을 더하거나 고치는 것도 제안한다. 규칙은 짧게, 기존 말투(평서형)로 쓴다.
- fit·safe 가중치와 금지 주제 규칙은 건드리지 않는다.

## 7. 후속 주제 5~10개

1. `uv run python $S seen --channel <id> > $T/seen.txt`로 만든 영상과 추천받은 주제를 모두 뺀다(말만 바꾼 같은 물음도 뺀다).
2. 터진 패턴(5단계)을 같은 결의 새 소재로 옮긴다. 흔한 일상 궁금증은 이미 다 봤으니, 기이한 의학 사례·최신 연구·진화·극한 환경처럼 덜 흔한 결로 넓힌다.
3. `trends.md`의 금지·출처 규칙을 지킨다. 핵심 사실을 공식·학술 자료로 확인할 수 있는지 웹에서 한 번씩 확인한다.
4. 후보마다 주제(물음 꼴), 어느 터진 영상의 어떤 패턴을 옮겼는지, 공유형인지 유지형인지, 근거 출처 하나를 적는다.

## 8. 보고서와 반영

**보고서**: `reports/<YYYY-MM-DD> 주제 인사이트 <id>.html` 하나로 쓴다. 쓰기 전에 `artifact-design` 스킬을 불러 그 규칙을 따른다. 담을 것:
1. 한 줄 결론
2. 터진 영상·바닥 영상 표(숫자, 몇 배인지, 주제냐 훅이냐)
3. 링크로 받은 영상 분석
4. 축별 상관과 가중치 지금 → 제안
5. trends.md 바꿀 줄
6. 후속 주제
7. 한계(표본 수, 잇지 못한 릴스, 고른 것 안의 신호)

**사람이 부른 경우**
1. 보고서를 Artifact로 올리고 링크를 준다.
2. `channel.toml`·`trends.md` 수정을 diff로 보여 주고 AskUserQuestion으로 승인을 받는다(보기: 둘 다 반영 / 가중치만 / trends.md만 / 반영 안 함).
3. 승인한 것만 고친 뒤 `uv run python -c "from shorts_printer.core import channel; print(channel.load('<id>').trends.weights)"`로 읽히는지 확인한다.
4. 커밋은 사용자가 원할 때만 한다.

**`--auto`** (아무것도 묻지 않는다. 사용자 작업 폴더를 건드리지 않게 worktree에서 한다)
```
B=insights/<id>-$(date +%Y%m%d); W=$(mktemp -d)/wt
git fetch -q origin dev && git worktree add -q -b $B $W origin/dev
```
1. `$W` 안의 `channels/<id>/channel.toml`(weights 한 줄), `channels/<id>/trends.md`, `reports/…html`을 고친다. 바꿀 게 없어도 보고서는 넣는다.
2. 커밋한다. 메시지는 `주제 인사이트 <id>: 가중치 …→…, 점수 예시 갱신`(바꾼 게 없으면 `변경 없음`).
3. `git push -u origin $B`, `gh pr create --base dev`로 올린다. 본문에는 결론·가중치 표·바꾼 줄 요약을 넣는다.
4. `git worktree remove $W`.
5. PR 링크를 알린다: `uv run python -c "from shorts_printer import registry; registry.notify('주제 인사이트 <id>: <한 줄 결론> <PR 링크>')"`.
6. 중간에 막히면(Chrome 연결 실패, 토큰 만료, 숫자 없음) 거기서 멈춘다. 무엇이 막혔는지 같은 방법으로 알리고, 반쯤 만든 PR은 올리지 않는다.

## 하지 않는 것

- `src/`·`prompts/`를 고치지 않는다. 축을 새로 만들거나 축 설명을 바꿔야 할 것 같으면 보고서에 제안만 적는다.
- 숫자를 지어내지 않는다. 못 읽은 값은 빈칸으로 두고 이유를 적는다.
- `.env`·`.secrets/`·토큰 파일을 읽거나 출력하지 않는다.

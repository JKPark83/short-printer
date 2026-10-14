# shorts-printer

## 서버 재시작

코드·템플릿·정적 파일을 바꿔서 서버를 다시 켜야 반영되는 경우, 사용자에게 미루지 말고 항상 직접 재시작한다.

- 대상: `sp web --port 8765` (127.0.0.1:8765)
- 먼저 `jobs/*/job.json`에서 `running`·`queued`·`uploading` 작업을 확인한다. 돌고 있으면 끝난 뒤에 재시작하고, 기다릴 수 없으면 사용자에게 알린다.
- 재시작: `pkill -f "sp web --port 8765"; nohup .venv/bin/sp web --port 8765 > /tmp/sp-web.log 2>&1 &`
- 재시작 후 `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/` 로 200을 확인한다.

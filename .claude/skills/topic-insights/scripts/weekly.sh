#!/bin/zsh -l
# 주간 주제 인사이트: launchd가 월요일 09:00에 부른다. 채널마다 PR 하나를 올리고 알림을 보낸다.
cd "${0:A:h}/../../../.." || exit 1
CHANNELS=(momjob)   # ko-map-history는 youtube-login 다시 한 뒤 더한다
for ch in $CHANNELS; do
  echo "=== $(date '+%F %T') $ch"
  /Users/jkpark/.claude/local/claude -p "/topic-insights --channel $ch --auto" --chrome --permission-mode bypassPermissions
done

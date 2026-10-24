# 효과음 출처

롱폼 지도 영상(`core/sound.py`)이 쓰는 효과음. `korean-war-video`에서 쓴 파일을 그대로 가져왔다.

| 파일 | 제목 | 만든 이 | 출처 | 라이선스 |
|---|---|---|---|---|
| `distant-boom.mp3` | Distant Explosion | BBQGiraffe | https://freesound.org/people/BBQGiraffe/sounds/523224 | CC0 |
| `distant-boom2.mp3` | Distant Boom.wav | Henrythetrain | https://freesound.org/people/Henrythetrain/sounds/142598 | CC0 |
| `cannon-near.mp3` | S20-14 Cannon fire; shells fall nearby.wav | craigsmith | https://freesound.org/people/craigsmith/sounds/675611 | CC0 |
| `artillery-guns.mp3` | R12-31-Artillery Guns Firing.wav | craigsmith | https://freesound.org/people/craigsmith/sounds/486027 | CC0 |
| `artillery-seq.mp3` | R12-11-Artillery Explosion Sequence.wav | craigsmith | https://freesound.org/people/craigsmith/sounds/486020 | CC0 |
| `shutter.mp3` | Camera Shutter Click | Kodack | https://freesound.org/people/Kodack/sounds/271010 | CC0 |
| `whoosh-cinematic.mp3` | whoosh-cinematic | Pixabay | https://pixabay.com/sound-effects/ (media-use 스킬 묶음) | Pixabay Content License |
| `riser.mp3` | riser | Pixabay | https://pixabay.com/sound-effects/ (media-use 스킬 묶음) | Pixabay Content License |
| `impact-bass-2.mp3` | impact-bass-2 | Pixabay | https://pixabay.com/sound-effects/ (media-use 스킬 묶음) | Pixabay Content License |

- Freesound 파일은 CC0이라 표기 의무가 없지만 끝 화면에 만든 이를 적는다. Freesound 미리 듣기 mp3(hq)다.
- Pixabay 파일은 CC0가 아니라 Pixabay Content License다(상업 사용·영상 속 재배포 가능, 표기 의무 없음). 효과음만 따로 재배포하지는 않는다.

## sfx.json 값

- `duration`: ffprobe 길이(초).
- `onset`: 소리가 시작하는 곳. `silencedetect=n=-35dB:d=0.25`의 첫 무음이 0초에서 시작하면 그 끝, 아니면 0.
- `peak`: 큰 소리 구간의 끝. 50 ms마다 RMS를 재서 최대에서 3 dB 안인 마지막 칸의 끝(라이저가 터지는 곳, 휙 소리가 닿는 곳).
- `role`: move(카메라 이동) · turn(이야기 전환) · hit(한 방) · final(마지막 선) · photo(사진) · bed(깔리는 포성).
- `credit`: 끝 화면 표기. 첫 낱말이 출처(Freesound·Pixabay), 나머지가 만든 이.

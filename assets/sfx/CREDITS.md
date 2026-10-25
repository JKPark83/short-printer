# 효과음 출처

롱폼 지도 영상(`core/sound.py`)이 쓰는 효과음. `korean-war-video`에서 쓴 파일을 그대로 가져왔다.

| 파일 | 제목 | 만든 이 | 출처 | 라이선스 |
|---|---|---|---|---|
| `distant-boom.mp3` | Distant Explosion | BBQGiraffe | https://freesound.org/people/BBQGiraffe/sounds/523224 | CC0 |
| `distant-boom2.mp3` | Distant Boom.wav | Henrythetrain | https://freesound.org/people/Henrythetrain/sounds/142598 | CC0 |
| `cannon-near.mp3` | S20-14 Cannon fire; shells fall nearby.wav | craigsmith | https://freesound.org/people/craigsmith/sounds/675611 | CC0 |
| `artillery-guns.mp3` | R12-31-Artillery Guns Firing.wav | craigsmith | https://freesound.org/people/craigsmith/sounds/486027 | CC0 |
| `artillery-seq.mp3` | R12-11-Artillery Explosion Sequence.wav | craigsmith | https://freesound.org/people/craigsmith/sounds/486020 | CC0 |
| `hooves-1.mp3` | Wild Horses Galopp (0~4.5초) | D4XX | https://freesound.org/people/D4XX/sounds/564626 | CC0 |
| `hooves-2.mp3` | Horses running final.wav (2~6.5초) | C-V | https://freesound.org/people/C-V/sounds/583261 | CC0 |
| `march-1.mp3` | MARCHING_SOUND.mp3 (0~3.1초) | ciapaqua | https://freesound.org/people/ciapaqua/sounds/637107 | CC0 |
| `march-2.mp3` | R27-41-Metal Gear Rattles on Army.wav (0~4.5초) | craigsmith | https://freesound.org/people/craigsmith/sounds/481931 | CC0 |
| `shout-1.mp3` | People screaming in agony when charging into battle (11~15.5초) | florianreichelt | https://freesound.org/people/florianreichelt/sounds/563011 | CC0 |
| `shout-2.mp3` | People screaming in agony when charging into battle (0.4~4.9초) | florianreichelt | https://freesound.org/people/florianreichelt/sounds/563011 | CC0 |
| `clash-1.mp3` | warriors fighting swords shields (0~4.5초) | mario1298 | https://freesound.org/people/mario1298/sounds/177084 | CC0 |
| `clash-2.mp3` | warriors fighting swords shields (6~10.5초) | mario1298 | https://freesound.org/people/mario1298/sounds/177084 | CC0 |
| `arrows-1.mp3` | S23-22 Arrows fly & hit; indoors.wav (0~4.45초) | craigsmith | https://freesound.org/people/craigsmith/sounds/675820 | CC0 |
| `arrows-2.mp3` | Arrows Fly By.mp3 (0~3.2초) | DigPro120 | https://freesound.org/people/DigPro120/sounds/394004 | CC0 |
| `fire-1.mp3` | Fire Crackle and Flames 002 (8~12.5초) | TheWoodlandNomad | https://freesound.org/people/TheWoodlandNomad/sounds/363092 | CC0 |
| `fire-2.mp3` | fire-crackling.wav (10~14.5초) | jmehlferber | https://freesound.org/people/jmehlferber/sounds/370938 | CC0 |
| `gun-1.mp3` | S21-03 Musket volley.wav (0~4.5초) | craigsmith | https://freesound.org/people/craigsmith/sounds/675623 | CC0 |
| `gun-2.mp3` | old musket bang.wav (0~3.56초) | bruno.auzet | https://freesound.org/people/bruno.auzet/sounds/538795 | CC0 |
| `cannon-fire.mp3` | Cannon fire.wav (0~4.24초) | Jon285 | https://freesound.org/people/Jon285/sounds/106850 | CC0 |
| `sea-1.mp3` | Boat_waves.wav (4~8.5초) | Lydmakeren | https://freesound.org/people/Lydmakeren/sounds/510900 | CC0 |
| `sea-2.mp3` | rowing boat rear wave.wav (0~4.5초) | Fenodyrie | https://freesound.org/people/Fenodyrie/sounds/588308 | CC0 |
| `shutter.mp3` | Camera Shutter Click | Kodack | https://freesound.org/people/Kodack/sounds/271010 | CC0 |
| `whoosh-cinematic.mp3` | whoosh-cinematic | Pixabay | https://pixabay.com/sound-effects/ (media-use 스킬 묶음) | Pixabay Content License |
| `riser.mp3` | riser | Pixabay | https://pixabay.com/sound-effects/ (media-use 스킬 묶음) | Pixabay Content License |
| `impact-bass-2.mp3` | impact-bass-2 | Pixabay | https://pixabay.com/sound-effects/ (media-use 스킬 묶음) | Pixabay Content License |

- 새로 더한 Freesound 파일(말발굽·행군·함성·칼·화살·불·총·포·바다)은 미리 듣기에서 괄호 안 구간을 잘라 -15 LUFS로 맞췄다.
- 효과음에 사람 말소리(구령·녹음 슬레이트)가 섞이면 안 된다. 넣기 전에 음성 검출(Silero VAD, faster-whisper의 `get_speech_timestamps`)로 말소리 구간이 없는지 본다. 옛 arrows-1(mcaseydesign 474121)은 영어 대사가 섞여 바꿨다.
- Freesound 파일은 CC0이라 표기 의무가 없지만 끝 화면에 만든 이를 적는다. Freesound 미리 듣기 mp3(hq)다.
- Pixabay 파일은 CC0가 아니라 Pixabay Content License다(상업 사용·영상 속 재배포 가능, 표기 의무 없음). 효과음만 따로 재배포하지는 않는다.

## sfx.json 값

- `duration`: ffprobe 길이(초).
- `onset`: 소리가 시작하는 곳. `silencedetect=n=-35dB:d=0.25`의 첫 무음이 0초에서 시작하면 그 끝, 아니면 0.
- `peak`: 큰 소리 구간의 끝. 50 ms마다 RMS를 재서 최대에서 3 dB 안인 마지막 칸의 끝(라이저가 터지는 곳, 휙 소리가 닿는 곳).
- `role`: move(카메라 이동) · turn(이야기 전환) · final(마지막 선) · photo(사진) · bed(깔리는 포성), 번쩍임 kind(cannon · gun · clash · arrows · fire · shout), 화살표 행군(hooves · march · sea). 실제로 고르는 건 `sound.CUES`의 이름 목록이다.
- `credit`: 끝 화면 표기. 첫 낱말이 출처(Freesound·Pixabay), 나머지가 만든 이.

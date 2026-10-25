"""core.mapplan: 가짜 LLM으로 지도 계획 두 단계, film_parts의 시각·카메라·전선·라벨·정리."""
from types import SimpleNamespace

from shorts_printer.core import mapplan

USAGE = {"model": "m", "input_tokens": 1, "output_tokens": 2, "cost_usd": None}
CH = SimpleNamespace(concept="지도로 보는 역사", language="ko", lang_name="한국어")
BOX = [116, 44, 139.5, 32.5]   # 한국전쟁 영상과 같은 상자(fixture tiles와 맞는다)
DETAIL = [123.6, 43.2, 131.4, 32.9]
PLACES = {"seoul": {"name": "서울", "lng": 126.98, "lat": 37.57},
          "busan": {"name": "부산", "lng": 129.07, "lat": 35.18},
          "tokyo": {"name": "도쿄", "lng": 139.7, "lat": 35.7},
          "pyongyang": {"name": "평양", "lng": 125.75, "lat": 39.03}}
NARR = ["1950년 6월 25일 새벽 북한군이 38선을 넘었습니다", "사흘 만에 서울이 함락됐습니다",
        "국군은 부산까지 밀려났습니다", "그때 맥아더가 인천을 노렸습니다"]


class FakeLLM:
    label = "Claude"

    def __init__(self, *outs):
        self.outs, self.calls = list(outs), []

    def ask(self, system, text, schema, *, refusal, what, images=(), web=False):
        self.calls.append(dict(system=system, text=text, schema=schema))
        return self.outs.pop(0), USAGE


def make_script(kinds=("map", "map", "map", "clip")) -> dict:
    scenes = [{"narration": t, "kind": k, "chapter": int(i >= 2), "beat": "turn" if i == 2 else "", "visual": "지도",
               "fact_ids": [], "clip_prompt": "", "clip_prompt_ko": ""}
              for i, (t, k) in enumerate(zip(NARR, kinds, strict=True))]
    return {"title": "한국전쟁", "chapters": [{"title": "개전", "first": 0}, {"title": "반격", "first": 2}],
            "scenes": scenes, "sentences": NARR, "fact_ids": [[]] * 4}


def make_timing(texts=NARR, beats=("", "", "turn", "")) -> list[dict]:
    """계약의 시계: S[0]=1.4, 낱말 0.5초씩, 다음 장면이 turn이면 1.4초 쉼."""
    t, out = 1.4, []
    for i, text in enumerate(texts):
        words = [{"text": w, "start": round(t + 0.5 * k, 2)} for k, w in enumerate(text.split())]
        dur = 0.5 * len(words)
        out.append({"text": text, "start": t, "end": round(t + dur, 2), "words": words,
                    "file": f"voice/s{i + 1:02d}.mp3", "duration": dur})
        t = round(t + dur + (1.4 if i + 1 < len(beats) and beats[i + 1] == "turn" else 0.8), 2)
    return out


def scene(i, **kw) -> dict:
    return mapplan.SceneMap(scene=i, **kw).model_dump()


def make_plan(scenes, states=None, side="north") -> dict:
    return {"world": {"box": BOX, "zoom": 9, "detail": DETAIL, "land": ["KOR", "PRK"], "border": ["CHN"],
                      "border_box": None, "side": side, "states": states or {}, "places": PLACES},
            "scenes": [next((s for s in scenes if s["scene"] == i), scene(i)) for i in range(4)]}


def parts(p, script=None, timing=None):
    timing = timing or make_timing()
    return mapplan.film_parts(p, script or make_script(), timing, timing[-1]["end"] + 0.75, "#C9302C", "#F3EFE7")


def test_plan_world_then_one_call_per_chapter():
    world = mapplan.World(box=[139.5, 32.5, 116, 44], zoom=12, detail=[120, 45, 131.4, 32.9], land=["KOR"],
                          border=[], side="north", places=[mapplan.Place(id="seoul", name="서울", lng=127, lat=37.5)],
                          states=[mapplan.State(name="L0", when="1950. 6. 25 38선", points=[[124, 38], [130, 38]])])
    ch1 = mapplan.Chapter(scenes=[mapplan.SceneMap(scene=1, front="L0"), mapplan.SceneMap(scene=3, front="L0")])
    ch2 = mapplan.Chapter(scenes=[mapplan.SceneMap(scene=2, front="L0")])
    llm = FakeLLM(world, ch1, ch2)
    facts = [{"id": "F1", "text": "1950년 6월 25일 개전", "kind": "official"}]
    p, usage = mapplan.plan(llm, CH, make_script(), make_timing(), facts)
    assert [c["schema"] for c in llm.calls] == [mapplan.World, mapplan.Chapter, mapplan.Chapter]
    assert "F1. 1950년 6월 25일 개전" in llm.calls[0]["text"] and "지도로 보는 역사" in llm.calls[0]["system"]
    # 장마다 그 장의 장면만, 지명·상태와 함께
    assert "1. [map" in llm.calls[1]["text"] and "2. [map" not in llm.calls[1]["text"]
    assert "3. [clip" in llm.calls[2]["text"] and "seoul: 서울" in llm.calls[2]["text"]
    assert "- L0: 1950. 6. 25 38선" in llm.calls[2]["text"]   # 상태마다 언제 어떤 선인지
    w = p["world"]
    assert w["box"] == [116, 44, 139.5, 32.5] and w["zoom"] == 9 and w["detail"] == [120, 44, 131.4, 32.9]
    assert w["places"]["seoul"] == {"name": "서울", "lng": 127, "lat": 37.5}
    assert w["states"]["L0"] == [[124, 38], [130, 38]]
    # 장 밖 번호(3은 1장 밖)는 버리고, 답이 없는 장면은 빈 계획
    assert [s["front"] for s in p["scenes"]] == ["", "L0", "L0", ""]
    assert usage["input_tokens"] == 3

    # 고쳐 줘: 지난 계획과 말을 둘 다 준다
    llm2 = FakeLLM(world, ch1, ch2)
    mapplan.plan(llm2, CH, make_script(), make_timing(), [], note="부산을 더 크게", old=p)
    assert all("부산을 더 크게" in c["text"] and "지난 계획" in c["text"] for c in llm2.calls)
    assert '"L0"' in llm2.calls[2]["text"]   # 2장의 지난 장면 계획


def test_times_come_from_word_anchors():
    t = make_timing()
    p = make_plan([scene(0, date={"year": "1950", "big": "6. 25", "small": "새벽", "at": "새벽"}),
                   scene(1, labels=[{"place": "seoul", "at": "서울"}], flashes=[{"place": "seoul", "at": "없는말"}])])
    f = parts(p, timing=t)
    assert f["dates"] == [[t[0]["words"][3]["start"], "1950", "6. 25", "새벽"]]
    lab = f["labels"][0]
    assert lab[:4] == ["s1-0", "서울", 126.98, 37.57] and lab[4] == t[1]["words"][2]["start"]   # "서울이"에 걸린다
    assert lab[5] == round(t[1]["end"] + 0.6, 2)
    assert f["flashes"] == [[round(t[1]["start"] + 0.3, 2), 126.98, 37.57, "cannon"]]   # 못 찾으면 장면 시작 + 0.3
    assert f["date_end"] == t[-1]["end"] + 0.75 and f["date_pos"] == [112, 120] and f["night"] is None


def test_gunpowder_sound_before_its_time_becomes_clash():
    p = make_plan([scene(0, date={"year": "1019", "big": "2월", "at": "새벽"},
                         flashes=[{"place": "seoul", "at": "새벽", "kind": "cannon"},
                                  {"place": "seoul", "at": "새벽", "kind": "arrows"}])])
    f = parts(p)
    assert sorted(x[3] for x in f["flashes"]) == ["arrows", "clash"] and any("1019년" in w for w in f["warnings"])
    p["scenes"][0]["date"]["year"] = "1636"
    assert sorted(x[3] for x in parts(p)["flashes"]) == ["arrows", "cannon"]


def test_camera_keys_never_overlap_and_skip_repeats():
    texts = ["서울", "부산", "평양", "도쿄"]   # 0.5초 장면이라 2.4초 이동이 겹친다
    t = make_timing(texts, ("",) * 4)
    cams = [{"place": "seoul", "scale": 0.5}, {"place": "busan", "scale": 0.8}, {"place": "busan", "scale": 0.8},
            {"place": "pyongyang", "scale": 0.6}]
    f = parts(make_plan([scene(i, camera=c) for i, c in enumerate(cams)]), make_script(("map",) * 4), t)
    cam = f["cam"]
    assert cam[0] == [0, 0, 126.98, 37.57, 0.5] and cam[1][:2] == [0, round(t[1]["start"] - 0.3, 2)]
    assert len(cam) == 4   # 장면 2는 앞과 같아 뺐다
    for a, b in zip(cam, cam[1:], strict=False):
        assert b[0] >= round(a[0] + a[1], 2)
    # clip 장면의 카메라는 안 움직인다
    f = parts(make_plan([scene(0, camera=cams[0]), scene(3, camera=cams[3])]))
    assert {tuple(k[2:4]) for k in f["cam"]} == {(126.98, 37.57)}   # 머무는 동안 당겼다 물리기만 한다


def test_scale_clamps():
    f = parts(make_plan([scene(0, camera={"place": "tokyo", "scale": 1.0}),
                         scene(1, camera={"place": "seoul", "scale": 9}),
                         scene(2, camera={"lng": 200, "lat": 37, "scale": 0.01}),
                         scene(3, camera={"place": "busan", "scale": 0.01})]), make_script(("map",) * 4))
    cam = f["cam"]
    assert cam[0][4] == 0.3   # detail 밖은 0.3 이하
    assert cam[2][2:] == [126.98, 37.57, 1.4]
    assert cam[3][2] == 139.5 and cam[3][4] == cam[4][4]   # 상자 안으로
    assert 0.2 < cam[4][4] < 0.25   # 지도 이미지가 화면을 덮는 가장 작은 scale(0.15보다 크다)


def test_states_resampled_to_same_count_and_direction():
    states = {"L0": [[124, 38], [129.5, 38]], "L1": [[129.5, 36], [127, 36.5], [124, 37]],
              "L2": [[124, 35 + i * 0.01] for i in range(10)], "bad": [[124, 38]]}
    p = make_plan([scene(0, front="nope"), scene(1, front="L0"), scene(2, front="L1"), scene(3, front="L0")], states)
    f = parts(p)
    assert set(f["states"]) == {"L0", "L1", "L2"} and {len(v) for v in f["states"].values()} == {10}
    assert f["states"]["L1"][0] == [124, 37] and f["states"]["L1"][-1] == [129.5, 36]   # 서→동으로 뒤집었다
    assert f["states"]["L0"][1] == [124.6111, 38.0]
    assert f["front"][0] == [0, 0, "L0"] and f["front"][1][2] == "L1" and len(f["front"]) == 2
    assert any("bad" in x for x in f["warnings"]) and any("nope" in x for x in f["warnings"])
    assert any("되돌아가는" in x for x in f["warnings"])   # L1 뒤 L0은 시간을 거슬러 뺀다
    assert any("#map-occ" in tw for tw in f["map_tweens"])   # 장면 1부터 나오니 그때까지 숨긴다
    assert f["map_credit"].endswith("전선은 대략적 위치")


def test_sanitizes_text():
    p = make_plan([scene(0, labels=[{"place": "x", "at": "1950년"}],
                         date={"year": '19"50', "big": "<b>6&25", "small": "", "at": "x"})])
    p["world"]["places"]["x"] = {"name": '<script>"서&울', "lng": 127, "lat": 37}
    f = parts(p)
    assert f["labels"][0][1] == "script서울" and f["dates"][0][1:3] == ["1950", "b625"]


def test_label_cap_and_unknown_ids_dropped():
    labs = [{"place": k, "at": w} for k, w in
            [("seoul", "1950년"), ("busan", "6월"), ("tokyo", "25일"), ("pyongyang", "새벽"), ("ghost", "38선을")]]
    arrows = [{"points": ["seoul", "ghost", "busan"], "at": "넘었습니다"},
              {"points": ["seoul", [127.5, 36.5], "busan"], "at": "넘었습니다", "color": "ink"},
              {"points": ["pyongyang", "seoul"], "at": "넘었습니다", "color": "red"}]
    f = parts(make_plan([scene(0, labels=labs, arrows=arrows, flashes=[{"place": "ghost", "at": "새벽"}])]))
    labels = f["labels"]
    assert [x[0] for x in labels] == ["s0-0", "s0-1", "s0-2", "s0-3"]
    assert labels[0][5] == max(labels[3][4], round(labels[0][4] + 0.6, 2))   # 넷째가 뜰 때 첫째를 끝낸다
    for x in labels:   # 어느 순간에도 3개까지
        assert sum(y[4] <= x[4] < y[5] for y in labels) <= 3
    ar = f["arrows"]
    assert [a[0] for a in ar] == ["s0-1", "s0-2"] and ar[0][5] == "#F3EFE7" and ar[1][5] == "#C9302C"
    assert len(ar[1][1]) == 3 and ar[1][3] == 0.9 and ar[0][6] == f["cam"][1][4]
    assert f["flashes"] == [] and sum("ghost" in w for w in f["warnings"]) == 3


def test_small_box_grows_so_camera_stays_under_close():
    w = mapplan._world(mapplan.World(box=[126.8, 37.7, 127.1, 37.5], zoom=9, detail=[126.8, 37.7, 127.1, 37.5],
                                     land=[], border=[], side="north", places=[], states=[]))
    (x0, y0), (x1, y1) = mapplan._world_px(w["box"], w["zoom"])
    assert max(mapplan.SIZE[0] / (x1 - x0), mapplan.SIZE[1] / (y1 - y0)) <= mapplan.CLOSE + 0.02
    assert w["detail"] == [126.8, 37.7, 127.1, 37.5]


def test_close_up_near_detail_edge_capped():
    f = parts(make_plan([scene(0, camera={"place": "busan", "scale": 1.0}),
                         scene(1, camera={"place": "seoul", "scale": 1.0})]), make_script(("map",) * 4))
    # 부산은 detail 동쪽 끝에서 848px: 1.0이면 화면이 detail 밖으로 나가 가운데를 서쪽으로 민다(배율은 그대로)
    lng, lat, s = f["cam"][0][2:]
    (_, _), (east, _) = mapplan._world_px(DETAIL, 9)
    (x, _), _ = mapplan._world_px([lng, lat, lng, lat], 9)
    assert s == 1.0 and lat == 35.18 and abs(x + mapplan.SIZE[0] / 2 - east) < 1
    assert f["cam"][2][2:] == [126.98, 37.57, 1.0]   # 서울은 화면이 detail 안이라 그대로


def test_close_box_lets_camera_zoom_past_close_and_fills_screen():
    """좁은 해협(울돌목)을 말할 때 zoom 9 지도로는 점만 보였다: close 상자 안은 높은 줌 그림으로 더 다가간다."""
    w = mapplan._world(mapplan.World(box=BOX, zoom=9, detail=DETAIL, close=[126.1, 34.7, 126.5, 34.45], land=[],
                                     border=[], side="north", places=[], states=[]))
    assert w["close_zoom"] == 14 and mapplan._tiles(w["close"], 15) > mapplan.CLOSE_TILES   # 타일 상한 안 가장 높은 줌
    top = mapplan.close_top(w)
    assert top == 44.8
    p = make_plan([scene(0, camera={"lng": 126.31, "lat": 34.57, "scale": 60}),
                   scene(1, camera={"lng": 126.49, "lat": 34.57, "scale": 3}),
                   scene(2, camera={"place": "seoul", "scale": 3})])
    p["world"] |= {"close": w["close"], "close_zoom": 14}
    cam = parts(p)["cam"]
    assert cam[0][2:] == [126.31, 34.57, top]   # 상한까지
    lng, _, s = cam[2][2:]   # close 상자를 화면에 채우는 배율로 올리고 동쪽 끝을 넘지 않게 민다
    (x0, _), (x1, _) = mapplan._world_px(w["close"], 9)
    assert s == round(mapplan.SIZE[0] / (x1 - x0), 3) and lng < 126.49
    assert cam[3][4] == mapplan.CLOSE   # close 밖은 CLOSE까지


def test_arrows_capped_and_drawn_before_they_end():
    arrows = [{"points": ["seoul", "busan"], "at": w} for w in NARR[0].split()]
    f = parts(make_plan([scene(0, arrows=arrows)]))
    assert len(f["arrows"]) == mapplan.ARROWS and any("화살표가 많아" in w for w in f["warnings"])
    assert all(a[4] >= a[2] + a[3] + 0.5 - 0.01 for a in f["arrows"])


def test_date_and_front_pulled_to_scene_that_says_it():
    """clip 장면(3)이 날짜를 말하는데 모델이 다음 장면에 달면, 클립 뒤 지도에 지난 날짜가 남는다."""
    narr = [*NARR[:3], "1951년 1월 4일 서울을 다시 내줬습니다", "물러난 선은 평택에서 멈췄습니다"]
    script = make_script(("map", "map", "map", "clip", "map")[:4])
    script["scenes"].append(dict(script["scenes"][3], narration=narr[4], kind="map"))
    script["scenes"][3]["narration"] = narr[3]
    t = make_timing(narr, ("", "", "turn", "", ""))
    p = make_plan([scene(1, front="A")], states={"A": [[124, 38], [130, 38]], "B": [[124, 37], [130, 37]]})
    p["scenes"].append(scene(4, front="B", date={"year": "1951", "big": "1. 4", "small": "", "at": "물러난"}))
    f = parts(p, script, t)
    assert f["dates"] == [[t[3]["words"][1]["start"], "1951", "1. 4", ""]]   # "1월"
    assert f["front"][-1][2] == "B" and f["front"][-1][0] == t[3]["start"]
    assert any("장면 3로 당겼어요" in w for w in f["warnings"])
    assert p["scenes"][4]["date"]   # 계획은 그대로 두고 film 칸만 고친다


def test_stats_become_counters_and_units_pass_through():
    stats = [{"label": "피란민", "value": 30000.0, "unit": "명", "at": "38선을"},
             {"label": "둘째", "value": 90, "at": "새벽"}]
    arrows = [{"points": ["seoul", "busan"], "at": "새벽", "unit": "tank"},
              {"points": ["busan", "seoul"], "at": "북한군이"}]
    nameless, small = [{"label": "", "value": 10, "at": "서울이"}], [{"label": "작은 수", "value": 3, "at": "부산까지"}]
    f = parts(make_plan([scene(0, arrows=arrows, stats=stats), scene(1, stats=nameless), scene(2, stats=small)]))
    t = make_timing()
    assert len(f["counters"]) == 1   # 장면당 하나, 이름 없는 것·STAT_MIN보다 작은 수는 버린다
    c = f["counters"][0]
    assert c[:4] == ["s0", "피란민", 30000, "명"] and c[4] == t[0]["words"][5]["start"]
    assert c[5] <= c[4] + 7 and c[6:] == list(mapplan.STAT_POS)
    assert [a[7] for a in f["arrows"]] == ["tank", ""]


def test_shots_move_camera_inside_scene_and_long_holds_drift():
    narr = [NARR[0], "사흘 만에 서울이 함락됐고 국군은 한강 다리를 끊은 채 남쪽으로 내려가 부산 앞까지 밀렸습니다",
            *NARR[2:]]
    t = make_timing(narr)
    w = t[1]["words"]
    shots = [{"place": "busan", "scale": 0.8, "at": "남쪽으로"}, {"place": "seoul", "scale": 0.9, "at": "서울이"},
             {"place": "tokyo", "scale": 0.3, "at": "부산"}]
    p = make_plan([scene(0, camera={"place": "pyongyang", "scale": 0.4}),
                   scene(1, camera={"place": "seoul", "scale": 0.4}, shots=shots)])
    f = parts(p, make_script(("map",) * 4), t)
    cam = f["cam"]
    keys = [(k[0], k[1], k[2]) for k in cam]
    # 서울이: 장면 카메라가 아직 옮겨 가는 중이라 뺀다, 부산: 앞 shot 뒤 HOLD까지 조금 늦춰 살린다
    assert sum("너무 빨리" in x for x in f["warnings"]) == 1
    shot = round(w[9]["start"] - 0.3, 2)
    assert keys[2:5] == [(round(t[1]["start"] - 0.3, 2), mapplan.MOVE, 126.98),
                        (shot, mapplan.SHOT_MOVE, 128.1041),   # 남쪽으로 → 부산(detail 안으로 민 가운데)
                        (round(shot + mapplan.SHOT_MOVE + mapplan.HOLD, 2), mapplan.SHOT_MOVE, 139.5)]
    for a, b in zip(cam, cam[1:], strict=False):
        assert b[0] >= round(a[0] + a[1], 2) - 0.01

    # 장면 1~3 내내 그대로면 같은 자리를 CUT초마다 당겼다 물린다
    cam = parts(make_plan([scene(0, camera={"place": "seoul", "scale": 0.3})]), make_script(("map",) * 4))["cam"]
    cuts = cam[2:]
    assert len(cuts) >= 2 and all(c[2:4] == cam[1][2:4] for c in cuts)
    assert cuts[0][4] > cam[1][4] and cuts[1][4] == cam[1][4]
    for a, b in zip(cuts, cuts[1:], strict=False):
        assert 2 <= b[0] - a[0] <= mapplan.CUT

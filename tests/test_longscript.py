import pytest

from shorts_printer.core import channel, longscript, prompts
from shorts_printer.core.longscript import Chapter, Edit, Outline, Revision, Scene, Scenes
from shorts_printer.core.script import Issue, Verdict

USAGE = {"model": "m", "input_tokens": 1, "output_tokens": 2, "cost_usd": 0.01}
FACTS = [{"id": "F1", "text": "1950년 6월 25일 전쟁이 시작됐다", "url": "https://a.kr/1", "kind": "official"}]


class FakeLLM:
    """llm.ask 호출을 기록하고 정해진 답을 차례로 준다(네트워크 없음)."""
    label = "Claude"

    def __init__(self, *outs):
        self.outs, self.calls = list(outs), []

    def ask(self, system, text, schema, *, refusal, what, images=(), web=False):
        self.calls.append(dict(system=system, text=text, schema=schema, what=what))
        return self.outs.pop(0), USAGE


def _ch(clips=1, style="STYLE."):
    ch = channel.load("ko-40sec-facts")
    return ch.model_copy(update={"format": "long", "long": channel.LongCfg(max_clips=clips),
                                 "video": ch.video.model_copy(update={"style": style})})


def _sc(text, kind="map", prompt="", chapter=0, **kw):
    return dict(narration=text, kind=kind, beat="", visual="v", fact_ids=[], clip_prompt=prompt,
                clip_prompt_ko="", chapter=chapter) | kw


def _s(scenes, chapters=({"title": "1장", "first": 0},)):
    return {"title": "t", "description": "d", "tags": ["a"], "thumb": ["썸"], "sensitive": "",
            "chapters": list(chapters), "scenes": scenes, "sentences": [x["narration"] for x in scenes],
            "fact_ids": [x["fact_ids"] for x in scenes]}


def test_write_outlines_then_writes_each_chapter_and_caps_clips():
    ch = _ch(clips=2)
    outline = Outline(title="오르내린 선", description="d", tags=["a"], thumb=["선 하나"], sensitive="", spine="왜?",
                      chapters=[Chapter(title="시작", summary="s1", scenes=3, beats=["turn"]),
                                Chapter(title="반격", summary="s2", scenes=3)])
    one = Scenes(scenes=[Scene(narration="첫", kind="map", visual="v", fact_ids=["F1"]),
                         Scene(narration="둘", kind="clip", visual="v", clip_prompt=" boats land "),
                         Scene(narration="셋", kind="clip", visual="v", clip_prompt="march")])
    two = Scenes(scenes=[Scene(narration="넷", kind="clip", visual="v", clip_prompt="bridge"),
                         Scene(narration="다섯", kind="map", visual="v", clip_prompt="stray", clip_prompt_ko="x"),
                         Scene(narration="여섯", kind="clip", visual="v")])   # 프롬프트 없는 clip은 만들 수 없다
    llm = FakeLLM(outline, one, two)
    s, usage = longscript.write(llm, ch, "한국전쟁", facts=FACTS)
    v = longscript.values(ch)
    assert llm.calls[0]["system"] == prompts.render("long_outline", **v) and llm.calls[0]["schema"] is Outline
    assert llm.calls[1]["system"] == prompts.render("long_scenes", **v)
    assert "지금 쓸 장: 1. 시작" in llm.calls[1]["text"]
    # 둘째 장은 목차와 앞 장 내레이션을 같이 받는다
    assert "지금 쓸 장: 2. 반격" in llm.calls[2]["text"] and "1. 첫\n2. 둘\n3. 셋" in llm.calls[2]["text"]
    assert "F1. 1950년" in llm.calls[2]["text"] and "2. 반격 (장면 3개" in llm.calls[2]["text"]
    assert usage["input_tokens"] == 3 and usage["cost_usd"] == 0.03
    assert s["chapters"] == [{"title": "시작", "first": 0}, {"title": "반격", "first": 3}]
    assert s["sentences"] == ["첫", "둘", "셋", "넷", "다섯", "여섯"] and s["fact_ids"][0] == ["F1"]
    assert [x["chapter"] for x in s["scenes"]] == [0, 0, 0, 1, 1, 1] and s["thumb"] == ["선 하나"]
    # 상한 2개: 맨 첫 장면 clip이 없으니 앞뒤에서 가장 먼 4번, 그다음 고루 떨어진 2번이 남고 3번은 map으로
    assert [x["kind"] for x in s["scenes"]] == ["map", "clip", "map", "clip", "map", "map"]
    assert s["scenes"][1]["clip_prompt"] == "STYLE. boats land" and s["scenes"][2]["clip_prompt"] == ""
    assert s["scenes"][4]["clip_prompt"] == s["scenes"][4]["clip_prompt_ko"] == ""
    assert s["notes"] == ["clip 장면 3개가 상한 2개를 넘어 map으로 바꾼 장면: 3"]
    assert {"title", "description", "tags", "sensitive"} <= s.keys()


def test_write_refuses_empty_outline_or_chapter():
    empty = Outline(title="t", description="d", tags=[], thumb=[], sensitive="", spine="", chapters=[])
    with pytest.raises(RuntimeError, match="목차"):
        longscript.write(FakeLLM(empty), _ch(), "x")
    one = empty.model_copy(update={"chapters": [Chapter(title="a", summary="s", scenes=2)]})
    with pytest.raises(RuntimeError, match="1장"):
        longscript.write(FakeLLM(one, Scenes(scenes=[])), _ch(), "x")


def test_values_and_estimate_follow_minutes():
    ch = _ch()
    v = longscript.values(ch)
    assert (v["scenes_lo"], v["scenes_hi"], v["scene_lo"], v["scene_hi"], v["max_clips"]) == (44, 65, 56, 98, 1)
    assert longscript.estimate_seconds(ch, ["가나 다라", "마바사"]) == pytest.approx(7 / 7 + 8 + 1.6)
    with pytest.raises(ValueError, match="long.minutes"):
        channel.LongCfg(minutes=(12, 8))


def test_proofread_lists_scenes_and_adds_code_checks():
    ch = _ch(clips=0)
    scenes = [_sc("1950년 6월에 시작됐다", fact_ids=["F1"]), _sc("1951년의 일", beat="turn"),
              _sc("배가 닿는다", "clip", "STYLE. boats", chapter=1), _sc("눈 속", "clip", "STYLE. snow", chapter=1)]
    s = _s(scenes, [{"title": "시작", "first": 0}, {"title": "반격", "first": 2}])
    llm = FakeLLM(Verdict(issues=[Issue(scene=1, kind="문장", severity="작음", problem="p", fix="f")]))
    out, usage = longscript.proofread(llm, ch, s, FACTS, topic="한국전쟁")
    text = llm.calls[0]["text"]
    assert text.startswith("주제: 한국전쟁\n제목: t") and "## 1장. 시작\n1. [map] 1950년" in text
    assert "## 2장. 반격\n3. [clip] 배가 닿는다\n   (화면: v / 클립: boats)" in text and "2. [map/turn]" in text
    assert "(근거: F1)" in text and "F1. 1950년" in text and usage == USAGE
    # 모델 지적 + clip 상한(0개) + 짧은 길이 + 근거 없는 날짜(2번)
    assert [(i.scene, i.kind) for i in out.issues] == [(1, "문장"), (0, "화면"), (0, "낭독·자막"), (2, "사실")]
    assert "8~12분" in out.issues[2].problem and not out.passed


def test_revise_keeps_untouched_scenes_and_prefers_edited_clips():
    ch = _ch()
    old = [_sc("하나", "clip", "STYLE. a"), _sc("둘"), _sc("셋"), _sc("넷", chapter=1), _sc("다섯", chapter=1)]
    s = _s(old, [{"title": "a", "first": 0}, {"title": "b", "first": 3}]) | {"notes": ["예전"]}
    edit = Edit(scene=3, narration="새 셋", kind="clip", visual="배", fact_ids=["F1"], clip_prompt="ship")
    llm = FakeLLM(Revision(title="새 제목", description="d", tags=["a"], thumb=["썸"], scenes=[edit]))
    new, _ = longscript.revise(llm, ch, s, "3번을 배 클립으로", FACTS)
    v = longscript.values(ch)
    assert llm.calls[0]["system"] == prompts.render("long_scenes", **v) + "\n\n" + prompts.render("long_revise")
    assert "사용자 수정 요청: 3번을 배 클립으로" in llm.calls[0]["text"] and "F1. 1950년" in llm.calls[0]["text"]
    assert new["title"] == "새 제목" and new["sentences"] == ["하나", "둘", "새 셋", "넷", "다섯"]
    assert new["scenes"][1] == old[1] and new["scenes"][2]["chapter"] == 0 and new["fact_ids"][2] == ["F1"]
    # 상한 1개: 사람이 고친 3번 clip이 남고 1번이 map으로
    assert [x["kind"] for x in new["scenes"]] == ["map", "map", "clip", "map", "map"]
    assert new["scenes"][2]["clip_prompt"] == "STYLE. ship" and new["notes"][0].endswith("map으로 바꾼 장면: 1")
    assert s["scenes"][0]["kind"] == "clip"   # 받은 대본은 건드리지 않는다
    bad = Revision(title="t", description="d", tags=[], thumb=[], scenes=[edit.model_copy(update={"scene": 9})])
    with pytest.raises(RuntimeError, match="장면 번호"):
        longscript.revise(FakeLLM(bad), ch, s, "x")


def test_cap_clips_keeps_first_and_middle():
    scenes = [_sc(str(i), "clip", "p") for i in range(9)]
    notes = longscript.cap_clips(_ch(clips=2), scenes)
    assert [i for i, x in enumerate(scenes) if x["kind"] == "clip"] == [0, 4] and notes


def test_cap_clips_keeps_first_scene_then_spreads_and_checks_want_first_clip():
    scenes = [_sc(str(i), "clip", "p") for i in range(10)]
    notes = longscript.cap_clips(_ch(clips=3), scenes, prefer=[9])
    assert [i for i, x in enumerate(scenes) if x["kind"] == "clip"] == [0, 4, 9]   # 고친 9번, 맨 첫 0번, 그 사이 가운데
    assert notes == ["clip 장면 10개가 상한 3개를 넘어 map으로 바꾼 장면: 2, 3, 4, 6, 7, 8, 9"]
    s = _s([_sc("가"), _sc("나", "clip", "p")])
    assert any(i.problem == "영상 맨 첫 장면이 clip이 아님" for i in longscript.checks(_ch(clips=2), s, []))
    assert not any("맨 첫" in i.problem for i in longscript.checks(_ch(clips=0), s, []))


def test_outro_is_appended_and_never_edited():
    ch = _ch(clips=0)
    ch = ch.model_copy(update={"long": ch.long.model_copy(update={"outro": "구독 눌러 주세요!"})})
    outline = Outline(title="t", description="d", tags=[], thumb=["썸"], sensitive="", spine="왜?",
                      chapters=[Chapter(title="시작", summary="s", scenes=1)])
    s, _ = longscript.write(FakeLLM(outline, Scenes(scenes=[Scene(narration="첫", kind="map", visual="v")])), ch, "x")
    assert s["sentences"] == ["첫", "구독 눌러 주세요!"] and s["scenes"][-1]["outro"]
    # 고치기 요청이 마무리 인사를 건드려도 그대로 두고, 목록에는 고정이라고 적는다
    llm = FakeLLM(Revision(title="t", description="d", tags=[], thumb=["썸"],
                           scenes=[Edit(scene=2, narration="바뀐 인사", kind="map", visual="v")]))
    new, _ = longscript.revise(llm, ch, s, "끝을 바꿔")
    assert new["sentences"][-1] == "구독 눌러 주세요!" and "[채널 마무리 인사, 고정" in llm.calls[0]["text"]

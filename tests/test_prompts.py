import pytest

from shorts_printer import config
from shorts_printer.core import prompts


def test_render_strips_front_matter_and_fills_values(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROMPTS_DIR", tmp_path)
    (tmp_path / "x.md").write_text("---\n설명 ${lang}\n---\n${lang}로 {중괄호}·$$5 그대로\n", encoding="utf-8")
    assert prompts.render("x", lang="${x}") == "${x}로 {중괄호}·$5 그대로"   # 값 속 $는 다시 채우지 않는다
    (tmp_path / "x.md").write_text("${lang} ${oops}", encoding="utf-8")   # 고치면 다음 호출에 바로 반영
    with pytest.raises(KeyError, match="oops"):
        prompts.render("x", lang="일본어")


def test_every_prompt_file_renders_for_a_real_channel():
    from shorts_printer.core import channel, research, script, thumbnail, trends
    ch = channel.load("ko-40sec-facts")
    opened = ch.model_copy(update={"research": ch.research.model_copy(update={"open": True})})
    for s in (script.system(ch), prompts.render("script_revise"), prompts.render("script_revise_draft"),
              prompts.render("script_proofread", lang=ch.lang_name, limit=10),
              prompts.render("script_proofread_ko", lang=ch.lang_name, limit=10),
              thumbnail.system(ch), trends.system_idea(ch), research.system(ch),
              research.system(opened), prompts.render("translate", lang=ch.lang_name),
              prompts.render("scene_reprompt", channel_video=ch.video_rules())):
        assert s and "${" not in s and "---" not in s.splitlines()[0]


def test_every_long_prompt_renders_for_a_real_channel():
    from shorts_printer.core import channel, longscript, research, trends
    ch = channel.load("ko-40sec-facts").model_copy(update={"format": "long"})
    v = longscript.values(ch)
    for s in (prompts.render("long_outline", **v), prompts.render("long_scenes", **v), trends.system_series(ch),
              prompts.render("long_proofread", **v), prompts.render("long_revise"), research.system(ch),
              prompts.render("long_thumb", concept=ch.concept, style=ch.video.style)):
        assert s and "${" not in s and "---" not in s.splitlines()[0]
    assert "사실은 40개까지" in research.system(ch)   # 롱폼은 [long] max_facts

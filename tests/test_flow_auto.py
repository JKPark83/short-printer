from shorts_printer.adapters.flow_auto import _state


def test_state_reads_only_the_front_tile():
    assert _state([{"done": False, "error": None}, {"done": True, "error": None}]) is None   # 만드는 중
    assert _state([{"done": True, "error": None}]) == ("done", "")
    assert _state([{"done": False, "error": "막힘"}, {"done": True, "error": None}]) == ("error", "막힘")

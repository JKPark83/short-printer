import io
import json
import shutil
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from shorts_printer.infra import hyperframes as hf

REF = Path("/Users/jkpark/my-toy/korean-war-video")   # 실제 CLI 시험에 쓰는 완성 영상(3분)


def _fake_run(monkeypatch, stdout: str, code: int = 0, stderr: str = "", effect=None) -> list:
    calls = []

    def run(cmd, **kw):
        calls.append((cmd, kw))
        if effect:
            effect(cmd)
        return subprocess.CompletedProcess(cmd, code, stdout, stderr)
    monkeypatch.setattr(hf.subprocess, "run", run)
    return calls


def test_check_skips_prefix_line_and_keeps_json_on_nonzero_exit(tmp_path, monkeypatch):
    report = {"ok": False, "lint": {"errorCount": 1, "warningCount": 2, "findings": []}}
    calls = _fake_run(monkeypatch, "Update available 0.9.0\n" + json.dumps(report) + "\ntrailer", code=1)
    assert hf.check(tmp_path) == report
    cmd, kw = calls[0]
    assert cmd == ["npx", "--yes", "hyperframes@0.8.188", "check", "--json"] and kw["cwd"] == tmp_path
    assert "shell" not in kw


def test_errors_are_korean_and_redacted(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_API_KEY", "sk-very-secret-value")
    _fake_run(monkeypatch, "no json here", code=2, stderr="boom sk-very-secret-value")
    with pytest.raises(RuntimeError, match="실패") as e:
        hf.check(tmp_path)
    assert "sk-very-secret-value" not in str(e.value) and "***" in str(e.value)

    def missing(cmd, **kw):
        raise FileNotFoundError("npx")
    monkeypatch.setattr(hf.subprocess, "run", missing)
    with pytest.raises(RuntimeError, match="npx가 없어요"):
        hf.check(tmp_path)


def test_snapshot_returns_time_named_pngs_in_out(tmp_path, monkeypatch):
    out = tmp_path / "shots"
    frames = [{"path": str(out / "at-5s.png"), "time": 5}, {"path": str(out / "at-62.5s.png"), "time": 62.5}]

    def write(cmd):
        for f in frames:
            Path(f["path"]).write_bytes(b"png")
    calls = _fake_run(monkeypatch, "◇ saved\n" + json.dumps({"ok": True, "frames": frames}), effect=write)
    paths = hf.snapshot(tmp_path, [5.0, 62.5], out)
    assert [p.name for p in paths] == ["at-5s.png", "at-62.5s.png"]
    cmd = calls[0][0]
    assert cmd[cmd.index("--at") + 1] == "5,62.5" and cmd[cmd.index("-o") + 1] == str(out.resolve())
    assert {"--keep", "--no-end"} <= set(cmd) and cmd[cmd.index("--describe") + 1] == "false"


def test_snapshot_missing_frame_is_error(tmp_path, monkeypatch):
    _fake_run(monkeypatch, json.dumps({"ok": True, "frames": []}))
    with pytest.raises(RuntimeError, match="snapshot 실패"):
        hf.snapshot(tmp_path, [1.0], tmp_path / "shots")


def test_init_writes_skeleton_once_and_caches_fonts(tmp_path, monkeypatch):
    got = []

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): pass

    def urlopen(req, timeout):
        got.append(req.full_url)
        return Resp(b"woff2")
    monkeypatch.setattr(hf, "urlopen", urlopen)
    monkeypatch.setattr(hf, "FONT_CACHE", tmp_path / "cache")
    project = tmp_path / "film"
    hf.init(project, "한국전쟁 3년")
    meta = json.loads((project / "meta.json").read_text())
    assert meta["id"] == "film" and meta["name"] == "한국전쟁 3년"
    assert json.loads((project / "hyperframes.json").read_text())["media"]["autoProxy"] is True
    scripts = json.loads((project / "package.json").read_text())["scripts"]
    assert scripts["render"] == "npx --yes hyperframes@0.8.188 render"
    assert (project / "compositions").is_dir() and len(got) == 4
    assert (project / "assets/fonts/Pretendard-Black.woff2").read_bytes() == b"woff2"

    before = (project / "meta.json").read_text()
    hf.init(project, "다른 제목")   # 두 번째는 아무것도 바꾸지 않는다
    shutil.rmtree(project / "assets")
    hf.init(tmp_path / "film2", "둘째")   # 다른 작업도 캐시에서 복사한다
    assert (project / "meta.json").read_text() == before and len(got) == 4


class _Proc:
    """render가 부르는 Popen 가짜. lines를 내보내고 wait에서 tmp에 영상을 쓴다."""
    lines: list = []

    def __init__(self, cmd, **kw):
        assert "shell" not in kw
        self.tmp, self.code, self.stdout = Path(cmd[cmd.index("-o") + 1]), None, iter(self.lines)
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def poll(self): return self.code
    def wait(self):
        self.tmp.write_bytes(b"mp4")
        self.code = 0
        return 0


def test_render_throttles_log_and_replaces_atomically(tmp_path, monkeypatch):
    out = tmp_path / "out" / "film.mp4"
    monkeypatch.setattr(_Proc, "lines", ["\x1b[32mframe 1/100\x1b[0m\n", "frame 2/100\n", "\n", "done\n"])
    clock = iter([0.0, 1.0, 40.0])   # 빈 줄을 뺀 줄 셋
    monkeypatch.setattr(hf.subprocess, "Popen", _Proc)
    monkeypatch.setattr(hf.time, "monotonic", lambda: next(clock) + 1000)
    logs = []
    assert hf.render(tmp_path, out, logs.append) == out
    assert out.read_bytes() == b"mp4" and not list(out.parent.glob("*.part.mp4"))
    assert logs == ["frame 1/100", "done"]


def test_render_kills_on_cancel_and_on_silent_hang(tmp_path, monkeypatch):
    killed = threading.Event()

    def hang():   # 아무 줄도 없이 멈춘 렌더. 끊길 때까지 기다린다
        killed.wait(5)
        yield from ()
    monkeypatch.setattr(hf, "_kill", lambda p: killed.set())
    monkeypatch.setattr(hf.subprocess, "Popen", _Proc)
    monkeypatch.setattr(_Proc, "lines", ["frame 1\n"])

    def cancel(line):
        raise KeyboardInterrupt   # 작업 취소처럼 log가 던진다
    with pytest.raises(KeyboardInterrupt):
        hf.render(tmp_path, tmp_path / "a.mp4", cancel)
    assert killed.is_set()   # 렌더가 끝날 때까지 기다리지 않고 끊는다

    killed.clear()
    monkeypatch.setattr(hf, "RENDER_TIMEOUT", 0.05)
    monkeypatch.setattr(_Proc, "lines", hang())
    with pytest.raises(RuntimeError, match="끝나지 않았어요"):
        hf.render(tmp_path, tmp_path / "b.mp4", print)
    assert not (tmp_path / "b.mp4").exists()


@pytest.mark.live
def test_live_check_and_snapshot(tmp_path):
    if not REF.exists() or not hf.ready():
        pytest.skip("korean-war-video나 npx가 없다")
    project = tmp_path / "kwv"
    skip = shutil.ignore_patterns("renders", "node_modules", ".hyperframes", ".thumbnails", ".waveform-cache")
    shutil.copytree(REF, project, ignore=skip)
    report = hf.check(project)
    assert report["lint"]["errorCount"] == 0 and "warningCount" in report["craft"]
    paths = hf.snapshot(project, [5, 62.5], tmp_path / "shots")
    assert [p.name for p in paths] == ["at-5s.png", "at-62.5s.png"] and all(p.stat().st_size for p in paths)


def test_ready_needs_node_22(monkeypatch):
    monkeypatch.setattr(hf.shutil, "which", lambda name: f"/bin/{name}")
    for version, ok in (("v18.17.0\n", False), ("v22.22.0\n", True)):
        monkeypatch.setattr(hf.subprocess, "run", lambda *a, v=version, **k: SimpleNamespace(stdout=v))
        assert hf.ready() is ok
    monkeypatch.setattr(hf.shutil, "which", lambda name: None)
    assert hf.ready() is False

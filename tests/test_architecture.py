"""의존 방향 지키기(.claude/rules/architecture.md). core는 구현(adapters)·조립(registry)·화면을 모른다."""
import ast
from pathlib import Path

PKG = "shorts_printer"
SRC = Path(__file__).parents[1] / "src" / PKG
# 층마다 import해도 되는 패키지 안 층. 여기 없는 층(registry·web·cli)은 검사하지 않는다
ALLOWED = {
    "ports": {"ports"},
    "core": {"core", "ports", "infra", "config"},
    "adapters": {"adapters", "ports", "infra", "config"},
    "infra": {"infra", "ports", "core", "config"},
}
VENDORS = {"anthropic", "kiwipiepy", "playwright", "yt_dlp"}   # core가 직접 부르면 안 되는 외부 SDK
EXCEPT: set[tuple[str, str]] = set()   # core가 외부 SDK를 직접 부르는 예외(지금은 없다)


def _imports(path: Path) -> tuple[str, set[str]]:
    """(모듈 이름, import한 절대 이름들). 상대 import는 절대로 푼다. 함수 안 import도 센다."""
    rel = path.relative_to(SRC.parent).with_suffix("").parts
    mod = rel[:-1] if rel[-1] == "__init__" else rel
    pkg = rel[:-1]
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = ".".join(pkg[:len(pkg) - node.level + 1]) if node.level else ""
            module = ".".join(p for p in (base, node.module) if p)
            names |= {f"{module}.{a.name}" for a in node.names}
    return ".".join(mod), names


def _violations() -> list[str]:
    out = []
    for path in sorted(SRC.rglob("*.py")):
        mod, names = _imports(path)
        layer = mod.split(".")[1] if "." in mod else ""
        for name in sorted(names):
            parts = name.split(".")
            if parts[0] == PKG:
                target = parts[1] if len(parts) > 1 else ""
                if layer in ALLOWED and target not in ALLOWED[layer]:
                    out.append(f"{mod} → {name}")
            elif layer == "core" and parts[0] in VENDORS and (mod.removeprefix(f"{PKG}."), parts[0]) not in EXCEPT:
                out.append(f"{mod} → {name}")
    return out


def test_resolves_relative_imports():
    mod, names = _imports(SRC / "core" / "services.py")
    assert mod == f"{PKG}.core.services"
    assert f"{PKG}.ports.llm.LLM" in names and f"{PKG}.core.channel.Channel" in names


def test_dependency_direction():
    assert not (v := _violations()), "의존 방향 위반:\n" + "\n".join(v)

"""Google Flow 직접 올림 공급자."""


class Flow:
    """Google Flow는 API가 없다. 사람이 장면 프롬프트를 복사해 만들고 올린다."""
    label = "Google Flow"
    hint = "직접 올림 · 장면 프롬프트를 복사해 Flow에서 16:9 · 8초 · 결과 1개로 만들어요"

    def ready(self) -> bool:
        return True

    def make(self, scenes, out, log):
        return ()

"""异步流式的单元测试（用假上游，不联网）。"""
import unittest

from app.service import qa


class _FakeResponse:
    def __init__(self, lines):
        self._lines = lines

    async def aiter_lines(self):
        for ln in self._lines:
            yield ln

    def raise_for_status(self):
        return None


class _FakeStreamCM:
    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        return _FakeResponse(self._lines)

    async def __aexit__(self, *exc):
        return False


class _FakeClient:
    def __init__(self, lines):
        self.lines = lines

    def stream(self, *a, **kw):
        return _FakeStreamCM(self.lines)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


async def _collect(agen):
    out = []
    async for item in agen:
        out.append(item)
    return out


class TestAsyncStream(unittest.TestCase):
    def test_yields_tokens_then_done(self):
        lines = [
            'data: {"choices":[{"delta":{"content":"你"}}]}',
            'data: {"choices":[{"delta":{"content":"好"}}]}',
            "data: [DONE]",
        ]
        import asyncio

        items = asyncio.run(_collect(qa.astream_answer(
            [{"role": "user", "content": "hi"}],
            client_factory=lambda: _FakeClient(lines),
        )))
        texts = [i["text"] for i in items if i["type"] == "token"]
        self.assertEqual(texts, ["你", "好"])
        self.assertEqual(items[-1]["type"], "done")

    def test_tool_calls_are_accumulated(self):
        lines = [
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1",'
            '"function":{"name":"get_weather","arguments":"{\\"city\\":\\"北京\\"}"}}]}}]}',
            "data: [DONE]",
        ]
        import asyncio

        items = asyncio.run(_collect(qa.astream_answer(
            [{"role": "user", "content": "北京天气"}],
            tools=[{"type": "function", "function": {"name": "get_weather"}}],
            client_factory=lambda: _FakeClient(lines),
        )))
        calls = [i for i in items if i["type"] == "tool_calls"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["calls"][0]["function"]["name"], "get_weather")

    def test_bad_json_line_is_skipped(self):
        lines = ["data: not-json", 'data: {"choices":[{"delta":{"content":"ok"}}]}', "data: [DONE]"]
        import asyncio

        items = asyncio.run(_collect(qa.astream_answer(
            [{"role": "user", "content": "x"}],
            client_factory=lambda: _FakeClient(lines),
        )))
        self.assertEqual([i["text"] for i in items if i["type"] == "token"], ["ok"])


if __name__ == "__main__":
    unittest.main()

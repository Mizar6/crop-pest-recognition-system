"""SSE 帧格式的单元测试。"""
import json
import unittest

from app.service.sse import (
    EVENT_DONE, EVENT_ERROR, EVENT_META, EVENT_PING, EVENT_TOKEN, EVENT_TOOL,
    SSE_HEADERS, frame,
)


class TestFrame(unittest.TestCase):
    def test_format_has_id_event_data(self):
        s = frame(EVENT_TOKEN, {"text": "你好"}, 3)
        self.assertTrue(s.startswith("id: 3\nevent: token\ndata: "))
        self.assertTrue(s.endswith("\n\n"))
        payload = s.split("data: ", 1)[1].strip()
        self.assertEqual(json.loads(payload)["text"], "你好")

    def test_event_names_are_stable(self):
        self.assertEqual(
            (EVENT_META, EVENT_TOOL, EVENT_TOKEN, EVENT_PING, EVENT_DONE, EVENT_ERROR),
            ("meta", "tool", "token", "ping", "done", "error"),
        )

    def test_headers_disable_buffering(self):
        self.assertEqual(SSE_HEADERS["Cache-Control"], "no-cache")
        self.assertEqual(SSE_HEADERS["X-Accel-Buffering"], "no")
        self.assertIn("keep-alive", SSE_HEADERS["Connection"])

    def test_non_ascii_not_escaped(self):
        s = frame(EVENT_TOKEN, {"text": "锈病"}, 1)
        self.assertIn("锈病", s)  # ensure_ascii=False，中文直出


if __name__ == "__main__":
    unittest.main()

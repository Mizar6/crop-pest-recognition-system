"""阈值门控的单元测试（纯函数，不碰真实 registry）。"""
import unittest

from app.service.model_service import can_activate


class TestGate(unittest.TestCase):
    def test_manual_model_not_gated(self):
        ok, _ = can_activate({"id": "m1", "source": "upload"})
        self.assertTrue(ok)

    def test_train_model_below_threshold_blocked(self):
        ok, reason = can_activate({"source": "train", "map50": 0.31, "threshold": 0.5})
        self.assertFalse(ok)
        self.assertIn("未达阈值", reason)

    def test_train_model_above_threshold_allowed(self):
        ok, _ = can_activate({"source": "train", "map50": 0.62, "threshold": 0.5})
        self.assertTrue(ok)

    def test_train_model_missing_metric_blocked(self):
        ok, reason = can_activate({"source": "train", "map50": None, "threshold": 0.5})
        self.assertFalse(ok)
        self.assertIn("没有 mAP50", reason)

    def test_default_threshold_is_half(self):
        ok, _ = can_activate({"source": "train", "map50": 0.51})
        self.assertTrue(ok)
        ok2, _ = can_activate({"source": "train", "map50": 0.49})
        self.assertFalse(ok2)

    def test_boundary_equal_passes(self):
        ok, _ = can_activate({"source": "train", "map50": 0.5, "threshold": 0.5})
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()

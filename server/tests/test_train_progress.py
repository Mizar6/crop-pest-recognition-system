"""进度解析与曲线数据的单元测试。"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.service.train_service import read_results


class TestReadResults(unittest.TestCase):
    def test_parses_full_csv(self):
        with TemporaryDirectory() as d:
            p = Path(d)
            (p / "results.csv").write_text(
                "epoch,time,train/box_loss,val/box_loss,metrics/precision(B),metrics/recall(B),"
                "metrics/mAP50(B),metrics/mAP50-95(B)\n"
                "1,10,2.5,2.7,0.30,0.20,0.10,0.05\n"
                "2,20,2.0,2.3,0.40,0.30,0.20,0.10\n",
                encoding="utf-8",
            )
            r = read_results(p)
            self.assertTrue(r["has_data"])
            self.assertEqual(r["epochs"], [1, 2])
            self.assertEqual(r["losses"]["train_box"], [2.5, 2.0])
            self.assertEqual(r["metrics"]["map50"], [0.1, 0.2])
            self.assertEqual(r["metrics"]["precision"], [0.3, 0.4])

    def test_missing_columns_return_empty_not_crash(self):
        with TemporaryDirectory() as d:
            p = Path(d)
            (p / "results.csv").write_text("epoch,time\n1,10\n", encoding="utf-8")
            r = read_results(p)
            self.assertEqual(r["epochs"], [1])
            self.assertEqual(r["metrics"]["map50"], [])
            self.assertEqual(r["losses"]["val_box"], [])

    def test_no_csv(self):
        with TemporaryDirectory() as d:
            r = read_results(Path(d))
            self.assertFalse(r["has_data"])
            self.assertEqual(r["epochs"], [])

    def test_blank_cells_become_none(self):
        with TemporaryDirectory() as d:
            p = Path(d)
            (p / "results.csv").write_text(
                "epoch,metrics/mAP50(B)\n1,\n2,0.3\n", encoding="utf-8"
            )
            r = read_results(p)
            self.assertEqual(r["metrics"]["map50"], [None, 0.3])


if __name__ == "__main__":
    unittest.main()

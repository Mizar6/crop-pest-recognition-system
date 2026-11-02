"""训练任务启动 / 取消的单元测试（不真的训练，spawn 被替换掉）。"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.db.session import Base, SessionLocal, engine
from app.models.train import TrainDataset, TrainTask  # noqa: F401
from app.service import train_service


class _FakeProc:
    pid = 999999

    def poll(self):
        return None


class TestStartTraining(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.query(TrainTask).delete()
        self.db.commit()
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.db.close)

    def _make_dataset(self, class_names=None):
        root = Path(self.tmp.name) / "ds"
        (root / "images" / "train").mkdir(parents=True)
        (root / "labels" / "train").mkdir(parents=True)
        for i in range(3):
            (root / "images" / "train" / f"a{i}.jpg").write_bytes(b"x")
            (root / "labels" / "train" / f"a{i}.txt").write_text("0 0.5 0.5 0.2 0.2\n")
        dataset_id = "ds" + self.tmp.name[-4:]
        meta_dir = train_service.DATA_ROOT / "datasets" / dataset_id
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "meta.json").write_text(json.dumps({
            "dataset_id": dataset_id, "name": "测试集", "root": str(root),
            "class_names": class_names or ["健康叶片", "锈病叶片"],
        }), encoding="utf-8")
        self.addCleanup(lambda: __import__("shutil").rmtree(meta_dir, ignore_errors=True))
        return dataset_id

    def test_start_creates_task_and_calls_spawn(self):
        ds = self._make_dataset()
        calls = []
        task = train_service.start_training(
            self.db, ds, "yolo26s", "quick", 30, 0.5,
            spawn=lambda params, log: (calls.append(params), _FakeProc())[1],
        )
        self.assertEqual(task.status, "running")
        self.assertEqual(task.total_epochs, 30)
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0]["data_yaml"].endswith("data.yaml"))

    def test_second_start_rejected(self):
        ds = self._make_dataset()
        train_service.start_training(
            self.db, ds, "yolo26s", "quick", 30, 0.5,
            spawn=lambda params, log: _FakeProc(),
        )
        with self.assertRaises(ValueError) as ctx:
            train_service.start_training(
                self.db, ds, "yolo26s", "quick", 30, 0.5,
                spawn=lambda params, log: _FakeProc(),
            )
        self.assertIn("已有训练任务在运行", str(ctx.exception))

    def test_missing_dataset_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            train_service.start_training(
                self.db, "nope", "yolo26s", "quick", 30, 0.5,
                spawn=lambda params, log: _FakeProc(),
            )
        self.assertIn("数据集不存在", str(ctx.exception))

    def test_cancel_marks_canceled(self):
        ds = self._make_dataset()
        task = train_service.start_training(
            self.db, ds, "yolo26s", "quick", 30, 0.5,
            spawn=lambda params, log: _FakeProc(),
        )
        r = train_service.cancel_training(self.db, task.id)
        self.assertTrue(r["canceled"])
        self.db.expire_all()
        again = self.db.query(TrainTask).filter(TrainTask.id == task.id).first()
        self.assertEqual(again.status, "canceled")

    def test_ensure_data_yaml_splits_val(self):
        root = Path(self.tmp.name) / "ds"
        (root / "images" / "train").mkdir(parents=True)
        (root / "labels" / "train").mkdir(parents=True)
        for i in range(20):
            (root / "images" / "train" / f"b{i}.jpg").write_bytes(b"x")
            (root / "labels" / "train" / f"b{i}.txt").write_text("0 0.5 0.5 0.2 0.2\n")
        yml = train_service.ensure_data_yaml(root, ["健康", "患病"])
        text = yml.read_text(encoding="utf-8")
        self.assertIn("val: images/val", text)
        self.assertTrue((root / "images" / "val").is_dir())
        self.assertGreaterEqual(len(list((root / "images" / "val").iterdir())), 1)


if __name__ == "__main__":
    unittest.main()

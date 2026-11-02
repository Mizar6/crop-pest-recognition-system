"""重启恢复与目录清理的测试。"""
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.db.session import Base, SessionLocal, engine
from app.models.train import TrainTask
from app.service import train_service


class TestHousekeeping(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.query(TrainTask).delete()
        self.db.commit()
        self.addCleanup(self.db.close)

    def test_running_becomes_interrupted(self):
        t = TrainTask(id="t1", dataset_id="d1", status="running", progress=5)
        self.db.add(t)
        self.db.commit()
        n = train_service.recover_interrupted(self.db)
        self.assertGreaterEqual(n, 1)
        self.db.expire_all()
        again = self.db.query(TrainTask).filter(TrainTask.id == "t1").first()
        self.assertEqual(again.status, "interrupted")
        self.assertIn("服务重启", again.error)

    def test_prune_keeps_latest(self):
        with TemporaryDirectory() as d:
            old_root = train_service.RUN_ROOT
            train_service.RUN_ROOT = Path(d)
            try:
                for i in range(7):
                    p = Path(d) / f"run{i}"
                    p.mkdir()
                    os.utime(p, (time.time() - 1000 + i, time.time() - 1000 + i))
                removed = train_service.prune_old_runs(keep=5)
                self.assertEqual(removed, 2)
                self.assertEqual(len(list(Path(d).iterdir())), 5)
            finally:
                train_service.RUN_ROOT = old_root

    def test_prune_when_dir_missing(self):
        with TemporaryDirectory() as d:
            old_root = train_service.RUN_ROOT
            train_service.RUN_ROOT = Path(d) / "nope"
            try:
                self.assertEqual(train_service.prune_old_runs(keep=5), 0)
            finally:
                train_service.RUN_ROOT = old_root


if __name__ == "__main__":
    unittest.main()

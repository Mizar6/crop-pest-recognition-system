"""数据集校验的单元测试（标准库 unittest，无第三方依赖）。

运行：
    cd server
    python -m unittest tests.test_train_dataset -v
"""
import io
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from app.service.train_service import parse_zip, validate_dataset_dir


def _write(p: Path, content: str = "") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _dataset(root: Path, labels: dict, names: list[str] | None = None) -> Path:
    """造一个最小数据集：labels = {"train/a.txt": "0 0.5 0.5 0.2 0.2"}"""
    for rel, body in labels.items():
        stem = Path(rel).with_suffix("")
        split = stem.parts[0] if len(stem.parts) > 1 else "train"
        img_name = stem.name + ".jpg"
        img = root / "images" / split / img_name
        img.parent.mkdir(parents=True, exist_ok=True)
        img.write_bytes(b"fake-image")
        _write(root / "labels" / split / (stem.name + ".txt"), body)
    if names:
        body = "names:\n" + "".join(f"  {i}: {n}\n" for i, n in enumerate(names))
        _write(root / "data.yaml", body)
    return root


class TestValidateDataset(unittest.TestCase):
    def test_accepts_valid_dataset(self):
        with TemporaryDirectory() as d:
            root = _dataset(Path(d), {"train/a.txt": "0 0.5 0.5 0.2 0.2\n",
                                      "val/b.txt": "1 0.3 0.3 0.1 0.1\n"},
                            names=["健康叶片", "锈病叶片"])
            r = validate_dataset_dir(root)
            self.assertTrue(r["ok"], r["errors"])
            self.assertEqual(r["classes"], 2)
            self.assertEqual(r["images"], 2)
            self.assertEqual(r["boxes"], 2)
            self.assertEqual(r["class_names"], ["健康叶片", "锈病叶片"])

    def test_rejects_unpaired_label(self):
        with TemporaryDirectory() as d:
            root = _dataset(Path(d), {"train/a.txt": "0 0.5 0.5 0.2 0.2\n"})
            _write(root / "labels" / "train" / "orphan.txt", "0 0.5 0.5 0.1 0.1\n")
            r = validate_dataset_dir(root)
            self.assertFalse(r["ok"])
            self.assertTrue(any("orphan" in e for e in r["errors"]), r["errors"])

    def test_rejects_unpaired_image(self):
        with TemporaryDirectory() as d:
            root = _dataset(Path(d), {"train/a.txt": "0 0.5 0.5 0.2 0.2\n"})
            (root / "images" / "train" / "lonely.jpg").write_bytes(b"x")
            r = validate_dataset_dir(root)
            self.assertFalse(r["ok"])
            self.assertTrue(any("lonely" in e for e in r["errors"]), r["errors"])

    def test_rejects_class_id_out_of_range(self):
        with TemporaryDirectory() as d:
            root = _dataset(Path(d), {"train/a.txt": "5 0.5 0.5 0.2 0.2\n"},
                            names=["健康叶片", "锈病叶片"])
            r = validate_dataset_dir(root)
            self.assertFalse(r["ok"])
            self.assertTrue(any("类别" in e for e in r["errors"]), r["errors"])

    def test_rejects_bad_column_count(self):
        with TemporaryDirectory() as d:
            root = _dataset(Path(d), {"train/a.txt": "0 0.5 0.5\n"})
            r = validate_dataset_dir(root)
            self.assertFalse(r["ok"])
            self.assertTrue(any("5 列" in e or "列" in e for e in r["errors"]), r["errors"])

    def test_clips_out_of_bounds_coordinate(self):
        with TemporaryDirectory() as d:
            root = _dataset(Path(d), {"train/a.txt": "0 0.5 0.5 1.2 0.2\n"})
            r = validate_dataset_dir(root)
            self.assertTrue(r["ok"], r["errors"])
            self.assertEqual(r["clipped"], 1)

    def test_allows_empty_label_as_negative(self):
        # 规则：空标签 ≤ 10%。11 张里 1 张空（约 9%）应通过
        with TemporaryDirectory() as d:
            labels = {f"train/p{i}.txt": "0 0.5 0.5 0.2 0.2\n" for i in range(10)}
            labels["train/neg.txt"] = ""
            root = _dataset(Path(d), labels)
            r = validate_dataset_dir(root)
            self.assertTrue(r["ok"], r["errors"])
            self.assertEqual(r["images"], 11)
            self.assertEqual(r["boxes"], 10)
            self.assertEqual(r["empty_labels"], 1)

    def test_rejects_too_many_empty_labels(self):
        with TemporaryDirectory() as d:
            root = _dataset(Path(d), {"train/a.txt": "", "train/b.txt": "", "train/c.txt": ""})
            r = validate_dataset_dir(root)
            self.assertFalse(r["ok"])
            self.assertTrue(any("空标签" in e for e in r["errors"]), r["errors"])

    def test_missing_dirs(self):
        with TemporaryDirectory() as d:
            r = validate_dataset_dir(Path(d))
            self.assertFalse(r["ok"])
            self.assertTrue(r["errors"])


class TestParseZip(unittest.TestCase):
    def _zip(self, dest: Path, entries: dict) -> Path:
        p = dest / "ds.zip"
        with zipfile.ZipFile(p, "w") as z:
            for name, body in entries.items():
                z.writestr(name, body)
        return p

    def test_parses_normal_zip(self):
        with TemporaryDirectory() as d:
            d = Path(d)
            zp = self._zip(d, {"images/train/a.jpg": b"x", "labels/train/a.txt": "0 0.5 0.5 0.2 0.2"})
            out = parse_zip(zp, d / "out")
            self.assertTrue((out / "images" / "train" / "a.jpg").exists())
            self.assertTrue((out / "labels" / "train" / "a.txt").exists())

    def test_blocks_zip_slip(self):
        with TemporaryDirectory() as d:
            d = Path(d)
            zp = self._zip(d, {"../evil.txt": "boom"})
            with self.assertRaises(ValueError):
                parse_zip(zp, d / "out")

    def test_strips_single_top_folder(self):
        with TemporaryDirectory() as d:
            d = Path(d)
            zp = self._zip(d, {"mydata/images/train/a.jpg": b"x",
                               "mydata/labels/train/a.txt": "0 0.5 0.5 0.2 0.2"})
            out = parse_zip(zp, d / "out")
            self.assertTrue((out / "images" / "train" / "a.jpg").exists())


if __name__ == "__main__":
    unittest.main()

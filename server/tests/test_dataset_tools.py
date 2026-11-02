"""数据处理模块测试：清洗、去重、均衡、增强。"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from app.service import dataset_tools as dt


def make_dataset(root: Path, spec):
    """spec: {class_id: 图片数量}，生成最简单的纯色图 + 标注。"""
    (root / "images" / "train").mkdir(parents=True)
    (root / "labels" / "train").mkdir(parents=True)
    n = 0
    for cid, count in spec.items():
        for _ in range(count):
            n += 1
            img = root / "images" / "train" / f"img_{n}.jpg"
            # 画点纹理：纯色图没有可比较的结构，指纹会退化，真实照片不会这样
            pic = Image.new("RGB", (64, 64), (n * 7 % 255, cid * 40 % 255, 100))
            for x in range(n * 3 % 60, 60, 7):
                for y in range(0, 64, 5):
                    pic.putpixel((x, y), (255, 255, 255))
            pic.save(img)
            (root / "labels" / "train" / f"img_{n}.txt").write_text(
                f"{cid} 0.500000 0.500000 0.200000 0.200000\n", encoding="utf-8"
            )


class TestScan(unittest.TestCase):
    def test_counts_and_imbalance(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            make_dataset(root, {0: 8, 1: 2})
            s = dt.scan(root)
            self.assertEqual(s["images"], 10)
            self.assertEqual(s["boxes"], 10)
            self.assertEqual(s["class_count"], 2)
            self.assertEqual(s["max_class"], 8)
            self.assertEqual(s["min_class"], 2)
            self.assertEqual(s["imbalance_ratio"], 4.0)

    def test_missing_and_empty_label(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            make_dataset(root, {0: 2})
            (root / "images" / "train" / "no_label.jpg").write_bytes(b"x")
            (root / "images" / "train" / "empty.jpg").write_bytes(b"x")
            (root / "labels" / "train" / "empty.txt").write_text("", encoding="utf-8")
            s = dt.scan(root)
            self.assertEqual(s["missing_label"], 1)
            self.assertEqual(s["empty_label"], 1)

    def test_out_of_range_and_tiny(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            make_dataset(root, {0: 1})
            (root / "labels" / "train" / "img_1.txt").write_text(
                "0 1.500000 0.500000 0.001000 0.200000\n", encoding="utf-8"
            )
            s = dt.scan(root)
            self.assertEqual(s["out_of_range"], 1)
            self.assertEqual(s["tiny_box"], 1)


class TestDedup(unittest.TestCase):
    def test_removes_identical_copy(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            make_dataset(root, {0: 3})
            src = root / "images" / "train" / "img_1.jpg"
            (root / "images" / "train" / "copy.jpg").write_bytes(src.read_bytes())
            (root / "labels" / "train" / "copy.txt").write_text(
                "0 0.5 0.5 0.2 0.2\n", encoding="utf-8"
            )
            r = dt.dedup(root)
            # 3 张原图 + 1 张副本 → 应该只删掉 1 张
            self.assertEqual(len(r["removed"]), 1)
            self.assertEqual(r["kept"], 3)
            leftovers = [(root / "images" / "train" / n).exists() for n in ("copy.jpg", "img_1.jpg")]
            self.assertEqual(sum(leftovers), 1, "copy.jpg 与 img_1.jpg 只能留一个")
            # 被删的那张，图片和标注要一起消失（不能留下孤儿标注）
            removed_name = Path(r["removed"][0]).stem
            self.assertFalse((root / "images" / "train" / f"{removed_name}.jpg").exists())
            self.assertFalse((root / "labels" / "train" / f"{removed_name}.txt").exists())


class TestBalance(unittest.TestCase):
    def test_oversample_minority_keeps_val_untouched(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            make_dataset(root, {0: 8, 1: 2})
            before_val = len(list((root / "images" / "train").iterdir()))
            dt.balance(root, target="max", max_multiple=10)
            counts = {}
            for lbl in (root / "labels" / "train").glob("*.txt"):
                for line in lbl.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        counts[int(line.split()[0])] = counts.get(int(line.split()[0]), 0) + 1
            self.assertGreaterEqual(counts[1], counts[0] - 2)
            self.assertGreater(len(list((root / "images" / "train").iterdir())), before_val)

    def test_max_multiple_caps_copying(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            make_dataset(root, {0: 100, 1: 2})
            r = dt.balance(root, target="max", max_multiple=3)
            # 单类最多复制 2 倍（原 2 张 → 最多新增 4 张）
            self.assertLessEqual(r["per_class_added"].get(1, 0), 4)


class TestAugment(unittest.TestCase):
    def test_flip_fixes_x_center(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            make_dataset(root, {0: 1})
            (root / "labels" / "train" / "img_1.txt").write_text(
                "0 0.200000 0.500000 0.100000 0.100000\n", encoding="utf-8"
            )
            r = dt.augment(root, modes=("flip",), factor=1)
            self.assertEqual(r["added"], 1)
            out = (root / "labels" / "train" / "img_1__aug0flip.txt").read_text(encoding="utf-8")
            cx = float(out.split()[1])
            self.assertAlmostEqual(cx, 0.8, places=5)  # 0.2 → 1-0.2

    def test_bright_keeps_labels(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            make_dataset(root, {0: 1})
            dt.augment(root, modes=("bright",), factor=1)
            out = (root / "labels" / "train" / "img_1__aug0bright.txt").read_text(encoding="utf-8")
            self.assertAlmostEqual(float(out.split()[1]), 0.5, places=5)


if __name__ == "__main__":
    unittest.main()

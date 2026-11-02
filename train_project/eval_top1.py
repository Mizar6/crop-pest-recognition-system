"""在 val 集上评测：mAP 之外，再算“单张叶片 top-1 分类准确率”。

检测框本质是整片叶子，业务上用户关心“这张图是哪类病害”，
top-1 准确率比 mAP 更贴近答辩要讲的效果。
"""
import sys
from collections import Counter
from pathlib import Path

from ultralytics import YOLO

BASE = Path(__file__).resolve().parent


def main(weight: str):
    model = YOLO(weight)
    names = model.names
    img_dir = BASE / "plantdiseases" / "images" / "val"
    lab_dir = BASE / "plantdiseases" / "labels" / "val"

    total = hit = empty = 0
    conf_sum = 0.0
    wrong_pairs = Counter()

    for img in sorted(img_dir.glob("*")):
        lab = lab_dir / (img.stem + ".txt")
        if not lab.exists():
            continue
        rows = [ln.split() for ln in lab.read_text().strip().splitlines() if ln.strip()]
        if not rows:
            continue
        truth_ids = [int(float(r[0])) for r in rows]
        truth = Counter(truth_ids).most_common(1)[0][0]

        result = model.predict(str(img), conf=0.25, verbose=False, device=0)[0]
        if result.boxes is None or len(result.boxes) == 0:
            empty += 1
            total += 1
            continue
        best_i = int(max(range(len(result.boxes)), key=lambda i: float(result.boxes[i].conf[0])))
        pred = int(result.boxes[best_i].cls[0])
        conf_sum += float(result.boxes[best_i].conf[0])
        total += 1
        if pred == truth:
            hit += 1
        else:
            wrong_pairs[(names.get(truth, truth), names.get(pred, pred))] += 1

    print(f"weight = {weight}")
    print(f"images = {total}")
    print(f"top-1 hit = {hit}  ({hit / max(total, 1) * 100:.2f}%)")
    print(f"no detection = {empty}")
    print(f"avg conf of top box = {conf_sum / max(total - empty, 1):.3f}")
    print("top-8 常见混淆 (真值 -> 预测):")
    for (t, p), c in wrong_pairs.most_common(8):
        print(f"  {t} -> {p}  x{c}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(BASE / "best.pt"))

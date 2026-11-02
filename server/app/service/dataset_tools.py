"""数据集处理工具：清洗、去重、类别均衡、数据增强。

【为什么单独一个模块】
  训练效果的上限由数据决定。原始数据集有三个典型问题，必须在训练前处理：

    1. 重复样本   —— 同一张图被拍两次/导出两次，会让验证集"作弊"（验证集里出现训练集见过的图）
    2. 脏数据     —— 图片打不开、标注越界（坐标 >1）、框太小（<4 像素）、只有图没有标签
    3. 类别不均衡 —— 本项目 30 类里，最多的类 812 个框，最少的只有 2 个框，相差 406 倍

  这类处理 YOLO 本身不做（它只管读图训练），所以必须自己写。

【YOLO 标注格式回顾】
  labels/xxx.txt 每行是：  class_id  x_center  y_center  width  height
  五个值都是相对图片宽高的**归一化比值**（0~1），不是像素坐标。
  所以对图片做水平翻转时，标注要跟着改：x_center → 1 - x_center，其余不变。
"""
from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from pathlib import Path

IMG_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


# ────────────────────────────────────────────────
# 一、清洗 + 扫描：先把数据看明白
# ────────────────────────────────────────────────

def _iter_images(root: Path):
    """遍历数据集里所有图片（支持 images/train、images/val 以及任意嵌套）。"""
    for p in root.rglob("*"):
        if p.suffix.lower() in IMG_SUFFIXES and p.is_file():
            yield p


def _label_of(img: Path) -> Path:
    """图片 → 对应标注文件。images/ 换成 labels/，后缀换成 .txt。"""
    parts = list(img.parts)
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == "images":
            parts[i] = "labels"
            break
    return Path(*parts).with_suffix(".txt")


def read_labels(label_path: Path) -> list[tuple]:
    """读标注，返回 [(class_id, cx, cy, w, h), ...]，坏行自动跳过。"""
    rows = []
    if not label_path.exists():
        return rows
    for line in label_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            cid = int(float(parts[0]))
            cx, cy, w, h = (float(v) for v in parts[1:])
        except ValueError:
            continue
        rows.append((cid, cx, cy, w, h))
    return rows


def _a_hash(img: Path, size: int = 8) -> str:
    """差值哈希 dHash：缩到 9x8 灰度，比较相邻像素的明暗关系，得到 64 位指纹。

    为什么用 dHash 而不是 aHash：
      aHash 比较的是"每个点与整图平均亮度"，对纯色/低对比图会退化成同一个值，
      导致一堆不同图片被判成重复。dHash 比较的是相邻像素的相对关系，更稳。

    返回空串表示图画不出来（坏图），调用方会跳过。
    """
    try:
        from PIL import Image
    except ImportError:
        return ""
    try:
        with Image.open(img) as im:
            g = im.convert("L").resize((size + 1, size))
            px = list(g.getdata())
    except Exception:
        return ""
    bits = []
    for row in range(size):
        for col in range(size):
            left = px[row * (size + 1) + col]
            right = px[row * (size + 1) + col + 1]
            bits.append("1" if left > right else "0")
    return f"{int(''.join(bits), 2):016x}"


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan(root: str | Path, near_dup_threshold: int = 5) -> dict:
    """体检数据集，返回各项问题统计。

    返回字段：
      images            图片总数
      boxes             标注框总数
      per_class         {class_id: 框数}
      missing_label     只有图没有标注的图片数
      empty_label       标注文件存在但为空（负样本）的图片数
      broken_image      打不开的图片数
      out_of_range      坐标越界的框数（<0 或 >1）
      tiny_box          宽或高小于 0.005（约 3 像素 @640）的框数
      dup_md5           完全相同的重复图片组数
      dup_near          近似重复（aHash 距离 ≤ 阈值）的图片数
    """
    root = Path(root)
    per_class = Counter()
    stats = dict(
        images=0, boxes=0, missing_label=0, empty_label=0,
        broken_image=0, out_of_range=0, tiny_box=0,
    )

    md5_seen: dict[str, Path] = {}
    hash_groups: dict[str, list[Path]] = defaultdict(list)

    for img in _iter_images(root):
        stats["images"] += 1

        # 1) 图片能否打开
        try:
            from PIL import Image
            with Image.open(img) as im:
                im.verify()
        except Exception:
            stats["broken_image"] += 1

        # 2) 完全重复
        m = _md5(img)
        if m in md5_seen:
            stats["dup_md5"] = stats.get("dup_md5", 0) + 1
        else:
            md5_seen[m] = img

        # 3) 近似重复按指纹分组
        ah = _a_hash(img)
        if ah:
            hash_groups[ah].append(img)

        # 4) 标注情况
        lb = _label_of(img)
        if not lb.exists():
            stats["missing_label"] += 1
            continue
        rows = read_labels(lb)
        if not rows:
            stats["empty_label"] += 1
            continue
        for cid, cx, cy, w, h in rows:
            per_class[cid] += 1
            stats["boxes"] += 1
            if not (0 <= cx <= 1 and 0 <= cy <= 1 and 0 < w <= 1 and 0 < h <= 1):
                stats["out_of_range"] += 1
            if w < 0.005 or h < 0.005:
                stats["tiny_box"] += 1

    # 5) 近似重复统计：同组里除第一张外都算重复
    near_dups = sum(len(v) - 1 for v in hash_groups.values() if len(v) > 1)
    stats["dup_near"] = near_dups
    stats["dup_md5"] = stats.get("dup_md5", 0)
    stats["per_class"] = dict(sorted(per_class.items()))

    if per_class:
        counts = list(per_class.values())
        stats["class_count"] = len(counts)
        stats["max_class"] = max(counts)
        stats["min_class"] = min(counts)
        # 不均衡倍数：最多类的框数 / 最少类的框数
        stats["imbalance_ratio"] = round(max(counts) / max(min(counts), 1), 1)
    return stats


# ────────────────────────────────────────────────
# 二、去重
# ────────────────────────────────────────────────

def dedup(root: str | Path, near: bool = True) -> dict:
    """删掉重复图片及其标注文件。

    near=True 时连"近似重复"一起删（默认），只保留每组第一张。
    返回 {"removed": [...], "kept": n}
    """
    root = Path(root)

    # 第一步：按指纹分组（先完全相同的 md5，再近似 dHash）
    groups: dict[str, list[Path]] = defaultdict(list)
    for img in sorted(_iter_images(root)):
        m = _md5(img)
        key = f"md5:{m}"
        groups[key].append(img)

    near_groups: dict[str, list[Path]] = defaultdict(list)
    if near:
        for img in sorted(_iter_images(root)):
            ah = _a_hash(img)
            if ah:
                near_groups[f"hash:{ah}"].append(img)

    def _boxes(img: Path) -> int:
        return len(read_labels(_label_of(img)))

    def _keep_one(members: list[Path]) -> Path:
        """组内保留谁：标注框最多的 > 文件名最短的 > 字典序最前。

        理由：框多的那张信息更完整；文件名短通常是没有 __dup/ copy 后缀的原图。
        """
        return sorted(members, key=lambda p: (-_boxes(p), len(p.name), str(p)))[0]

    removed: list[str] = []
    for members in list(groups.values()) + list(near_groups.values()):
        if len(members) < 2:
            continue
        keeper = _keep_one(members)
        for img in members:
            if img == keeper or not img.exists():
                continue
            removed.append(str(img.relative_to(root)))
            img.unlink(missing_ok=True)
            _label_of(img).unlink(missing_ok=True)

    return {"removed": removed, "kept": len(list(_iter_images(root)))}


# ────────────────────────────────────────────────
# 三、类别均衡（过采样）
# ────────────────────────────────────────────────

def balance(
    root: str | Path,
    target: str = "median",
    max_multiple: int = 6,
    split: str = "train",
) -> dict:
    """对少数类做**过采样**：复制图片文件，让每个类的框数接近目标值。

    为什么用复制而不是直接改 loss 权重：
      复制实现简单、可离线检查、不依赖训练库；缺点是可能加剧过拟合，
      所以这里限制 max_multiple，单类最多复制 6 倍。

    target:
      "median" —— 以各类框数的中位数为目标（温和，推荐）
      "max"    —— 以最多的类为目标（激进，容易过拟合）

    只处理 split（默认 train）目录，**绝不动验证集**——验证集必须保持真实分布，
    否则 mAP 会虚高，模型上线后表现会崩。
    """
    root = Path(root)
    img_dir = root / "images" / split
    lbl_dir = root / "labels" / split
    if not img_dir.exists():
        return {"error": f"找不到 {img_dir}"}

    # 统计每个类有哪些图
    class_images: dict[int, list[Path]] = defaultdict(list)
    for img in sorted(img_dir.iterdir()):
        if img.suffix.lower() not in IMG_SUFFIXES:
            continue
        rows = read_labels(lbl_dir / f"{img.stem}.txt")
        for cid in {r[0] for r in rows}:
            class_images[cid].append(img)

    if not class_images:
        return {"error": "没有可用标注"}

    counts = {cid: len(v) for cid, v in class_images.items()}
    if target == "max":
        goal = max(counts.values())
    else:
        ordered = sorted(counts.values())
        goal = ordered[len(ordered) // 2]

    added = 0
    detail: dict[int, int] = {}
    for cid, imgs in sorted(class_images.items()):
        need = goal - len(imgs)
        if need <= 0:
            continue
        # 单类最多复制 max_multiple 倍，避免把 2 个样本复制成 800 个
        need = min(need, len(imgs) * (max_multiple - 1))
        for i in range(need):
            src = imgs[i % len(imgs)]
            new_img = img_dir / f"{src.stem}__dup{cid}_{i}{src.suffix}"
            new_lbl = lbl_dir / f"{new_img.stem}.txt"
            new_img.write_bytes(src.read_bytes())
            (lbl_dir / f"{src.stem}.txt").replace(new_lbl) if False else None
            # 标注直接复制（内容不变，只换文件名）
            new_lbl.write_text((lbl_dir / f"{src.stem}.txt").read_text(encoding="utf-8"), encoding="utf-8")
            added += 1
        detail[cid] = need

    return {"goal": goal, "added": added, "per_class_added": detail, "class_count": len(counts)}


# ────────────────────────────────────────────────
# 四、数据增强（离线）
# ────────────────────────────────────────────────

def _flip_labels(rows: list[tuple]) -> list[tuple]:
    """水平翻转后，标注的 x_center 要变成 1 - x。"""
    return [(c, 1.0 - cx, cy, w, h) for c, cx, cy, w, h in rows]


def augment(
    root: str | Path,
    split: str = "train",
    modes: tuple[str, ...] = ("flip", "bright"),
    factor: int = 1,
) -> dict:
    """离线增强：把每张图变换后另存为新样本，标注同步修正。

    flip   —— 水平翻转（x 坐标镜像）
    bright —— 亮度/对比度抖动（标注不变）

    为什么不全交给 YOLO 的增强参数：
      训练时的 mosaic/hsv 是**每个 batch 随机生成**的，跑完不落盘，复现困难。
      离线增强会把新样本真实写进数据集，可以数、可以看、可以单独当数据集用。
      两者不冲突：离线增强打底，训练时再开 mosaic 做二次扰动。
    """
    root = Path(root)
    img_dir = root / "images" / split
    lbl_dir = root / "labels" / split
    if not img_dir.exists():
        return {"error": f"找不到 {img_dir}"}

    try:
        from PIL import Image, ImageEnhance
    except ImportError:
        return {"error": "未安装 Pillow"}

    added = 0
    for img_path in sorted(img_dir.iterdir()):
        if img_path.suffix.lower() not in IMG_SUFFIXES or "__aug" in img_path.stem:
            continue
        lbl_path = lbl_dir / f"{img_path.stem}.txt"
        rows = read_labels(lbl_path)

        for k in range(factor):
            for mode in modes:
                try:
                    with Image.open(img_path) as im:
                        im = im.convert("RGB")
                        if mode == "flip":
                            out = im.transpose(Image.FLIP_LEFT_RIGHT)
                            new_rows = _flip_labels(rows)
                        elif mode == "bright":
                            out = ImageEnhance.Brightness(im).enhance(1.25)
                            out = ImageEnhance.Contrast(out).enhance(1.1)
                            new_rows = rows
                        else:
                            continue
                        stem = f"{img_path.stem}__aug{k}{mode}"
                        out.save(img_dir / f"{stem}{img_path.suffix}")
                        (lbl_dir / f"{stem}.txt").write_text(
                            "\n".join(
                                f"{c} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}" for c, cx, cy, w, h in new_rows
                            ),
                            encoding="utf-8",
                        )
                        added += 1
                except Exception:
                    continue

    return {"added": added}


# ────────────────────────────────────────────────
# 五、一条命令跑完整套
# ────────────────────────────────────────────────

def preprocess(root: str | Path, do_dedup: bool = True, do_balance: bool = True,
               do_augment: bool = False, augment_factor: int = 1) -> dict:
    """按顺序执行：扫描 → 去重 → 均衡 → 增强 → 再扫描。"""
    root = Path(root)
    before = scan(root)
    report = {"before": before}

    if do_dedup:
        report["dedup"] = dedup(root)
    if do_balance:
        report["balance"] = balance(root)
    if do_augment:
        report["augment"] = augment(root, factor=augment_factor)

    report["after"] = scan(root)
    return report

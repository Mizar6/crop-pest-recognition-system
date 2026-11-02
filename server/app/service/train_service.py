"""训练模块服务层：数据集校验、解压、训练任务管理。

【为什么单独一个文件】
  训练相关逻辑多且互相关联（校验 → 解压 → 起进程 → 读进度 → 注册模型），
  放在 api 层会让路由文件臃肿；集中在这里，路由只做参数收发。
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from pathlib import Path

from app.db.session import SessionLocal

# 允许的图片后缀
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
# 空标签（负样本）允许的最大占比
MAX_EMPTY_RATIO = 0.10
# zip 解压后大小上限（10GB）
MAX_UNZIP_BYTES = 10 * 1024 * 1024 * 1024
# 训练档位 → 轮数
PRESETS = {"quick": 30, "standard": 120, "fine": 300}


# ============================================================
# 一、数据集校验
# ============================================================


def _read_names(root: Path) -> list[str]:
    """从 data.yaml 里读类别名；读不到就用空列表（调用方再兜底）。"""
    yaml_path = root / "data.yaml"
    if not yaml_path.exists():
        for candidate in root.glob("*.yaml"):
            yaml_path = candidate
            break
    if not yaml_path.exists():
        return []

    names: dict[int, str] = {}
    in_names = False
    for raw in yaml_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.strip().startswith("names:"):
            in_names = True
            continue
        if in_names:
            if not line.startswith((" ", "\t")):
                in_names = False
                continue
            body = line.strip()
            if ":" not in body:
                continue
            k, v = body.split(":", 1)
            try:
                idx = int(k.strip())
            except ValueError:
                continue
            names[idx] = v.strip().strip("'\"")
    if not names:
        return []
    return [names[i] for i in sorted(names)]


def _iter_label_files(root: Path):
    label_root = root / "labels"
    for p in label_root.rglob("*.txt"):
        yield p


def _matching_image(label_file: Path, root: Path) -> Path | None:
    """labels/train/a.txt → images/train/a.(jpg|png|...)"""
    rel = label_file.relative_to(root / "labels")
    stem_dir = rel.parent
    for suf in IMAGE_SUFFIXES:
        cand = root / "images" / stem_dir / (rel.stem + suf)
        if cand.exists():
            return cand
    return None


def validate_dataset_dir(root: Path) -> dict:
    """严格 YOLO 校验。返回 {ok, classes, images, boxes, class_names, errors, clipped}。"""
    root = Path(root)
    errors: list[str] = []
    result = {
        "ok": False,
        "classes": 0,
        "images": 0,
        "boxes": 0,
        "class_names": [],
        "errors": errors,
        "clipped": 0,
        "empty_labels": 0,
    }

    if not (root / "images").is_dir():
        errors.append("缺少 images/ 目录")
    if not (root / "labels").is_dir():
        errors.append("缺少 labels/ 目录")
    if errors:
        return result

    names = _read_names(root)
    label_files = list(_iter_label_files(root))
    if not label_files:
        errors.append("labels/ 下没有任何 .txt 标签文件")
        return result

    seen_ids: set[int] = set()
    boxes = 0
    images_seen: set[Path] = set()
    empty = 0

    for lf in label_files:
        rel = lf.relative_to(root)
        img = _matching_image(lf, root)
        if img is None:
            errors.append(f"标签没有对应图片：{rel}")
            continue
        images_seen.add(img)

        try:
            text = lf.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            errors.append(f"读取失败：{rel}（{exc}）")
            continue

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            empty += 1
            continue

        for lineno, ln in enumerate(lines, 1):
            parts = ln.split()
            if len(parts) != 5:
                errors.append(f"{rel}:{lineno} 应为 5 列（class cx cy w h），实际 {len(parts)} 列")
                continue
            try:
                cid = int(float(parts[0]))
                cx, cy, w, h = (float(x) for x in parts[1:])
            except ValueError:
                errors.append(f"{rel}:{lineno} 含非数字字段")
                continue

            if cid < 0:
                errors.append(f"{rel}:{lineno} 类别 id 为负数（{cid}）")
                continue
            if names and cid >= len(names):
                errors.append(f"{rel}:{lineno} 类别 id {cid} 超出范围（data.yaml 只有 {len(names)} 类）")
                continue
            if w <= 0 or h <= 0:
                errors.append(f"{rel}:{lineno} 宽高必须大于 0（w={w}, h={h}）")
                continue

            clipped = False
            if w > 1 or h > 1 or cx < 0 or cy < 0 or cx > 1 or cy > 1:
                w, h = min(w, 1.0), min(h, 1.0)
                cx, cy = min(max(cx, 0.0), 1.0), min(max(cy, 0.0), 1.0)
                clipped = True
                result["clipped"] += 1
                errors.append(
                    f"{rel}:{lineno} 坐标越界，已自动裁剪为 cx={cx:.4f} cy={cy:.4f} w={w:.4f} h={h:.4f}"
                )

            seen_ids.add(cid)
            boxes += 1

    # 有图片没标签的文件（孤儿图片）
    for img in (root / "images").rglob("*"):
        if img.suffix.lower() in IMAGE_SUFFIXES and img not in images_seen:
            errors.append(f"图片没有对应标签：{img.relative_to(root)}")

    total = len(label_files)
    if total and empty / total > MAX_EMPTY_RATIO:
        errors.append(
            f"空标签（负样本）占 {empty}/{total} 超过 {int(MAX_EMPTY_RATIO * 100)}%，请检查标注是否漏做"
        )

    guessed = (max(seen_ids) + 1) if seen_ids else 0
    class_names = names if names else [f"class_{i}" for i in range(guessed)]

    # 只有"裁剪"这类告警不算失败
    hard_errors = [e for e in errors if "已自动裁剪" not in e]
    result.update(
        ok=not hard_errors and boxes > 0,
        classes=len(class_names),
        images=len(images_seen),
        boxes=boxes,
        class_names=class_names,
        empty_labels=empty,
    )
    return result


# ============================================================
# 二、zip 解压（防 zip-slip）
# ============================================================


def parse_zip(zip_path: Path, dest: Path) -> Path:
    """安全解压数据集 zip 到 dest，返回数据集根目录（自动去掉多余的那层文件夹）。"""
    zip_path, dest = Path(zip_path), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    dest_root = dest.resolve()

    total = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename
            if name.endswith("/"):
                continue
            target = (dest / name).resolve()
            if not str(target).startswith(str(dest_root)):
                raise ValueError(f"zip 内路径非法（疑似路径穿越）：{name}")
            total += info.file_size
            if total > MAX_UNZIP_BYTES:
                raise ValueError("解压后超过 10GB，已拒绝")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)

    # 如果只有一层文件夹（例如 zip 里是 mydata/images/...），钻进去
    entries = [p for p in dest.iterdir() if p.name not in ("__MACOSX",)]
    if len(entries) == 1 and entries[0].is_dir():
        inner = entries[0]
        if (inner / "images").is_dir() or (inner / "labels").is_dir():
            return inner
    return dest


# ============================================================
# 三、data.yaml 与训练启动
# ============================================================

# 训练根目录：server/data/train_runs
DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
RUN_ROOT = DATA_ROOT / "train_runs"

# 全局训练锁：同一时间只允许一个训练任务
_TRAIN_LOCK = threading.Lock()
# 当前正在跑的子进程（用于取消）
_CURRENT: dict[str, subprocess.Popen] = {}


def ensure_data_yaml(root: Path, class_names: list[str]) -> Path:
    """生成严格 YOLO 的 data.yaml；缺少 val 时按 9:1 切分。"""
    root = Path(root)
    yaml_path = root / "data.yaml"

    # 上传包里的 data.yaml 可能只有 names（Roboflow 导出常见），
    # 缺 train/val 会让训练直接报错，所以这里一律按真实目录重建。
    if not class_names:
        class_names = _read_names(root)

    images_root = root / "images"
    splits = [p.name for p in images_root.iterdir() if p.is_dir()] if images_root.exists() else []
    if "val" not in splits and "train" in splits:
        train_dir = images_root / "train"
        files = sorted(train_dir.iterdir())
        val_dir = images_root / "val"
        val_dir.mkdir(parents=True, exist_ok=True)
        take = max(1, len(files) // 10)
        for f in files[-take:]:
            label = root / "labels" / "train" / (f.stem + ".txt")
            f.rename(val_dir / f.name)
            if label.exists():
                (root / "labels" / "val").mkdir(parents=True, exist_ok=True)
                label.rename(root / "labels" / "val" / label.name)
        splits.append("val")

    if "train" not in splits:
        raise ValueError("数据集缺少 images/train 目录，无法训练")

    lines = [
        f"path: {root.as_posix()}",
        "train: images/train",
        f"val: images/{'val' if 'val' in splits else 'train'}",
        "",
        "names:",
    ]
    lines += [f"  {i}: {n}" for i, n in enumerate(class_names)]
    yaml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return yaml_path


def _default_spawn(params: dict, log_path: Path) -> subprocess.Popen:
    """真的起一个训练子进程（测试时可被替换掉）。"""
    param_file = log_path.parent / "params.json"
    param_file.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
    log = log_path.open("a", encoding="utf-8")
    log.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} 启动训练 ===\n")
    log.flush()
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    return subprocess.Popen(
        [sys.executable, "-m", "app.service.train_runner", str(param_file)],
        stdout=log, stderr=subprocess.STDOUT,
        cwd=str(Path(__file__).resolve().parents[2]),
        env=env, start_new_session=True,
    )


def start_training(db, dataset_id: str, base_model: str, preset: str,
                   epochs: int, threshold: float, spawn=_default_spawn):
    """启动一次训练。返回 TrainTask。已有任务在跑则抛 ValueError。"""
    from app.models.train import TrainTask

    if not _TRAIN_LOCK.acquire(blocking=False):
        raise ValueError("已有训练任务在运行，请等它结束或先取消")

    try:
        running = db.query(TrainTask).filter(TrainTask.status.in_(["pending", "running"])).first()
        if running is not None:
            raise ValueError("已有训练任务在运行，请等它结束或先取消")

        meta_file = DATA_ROOT / "datasets" / dataset_id / "meta.json"
        if not meta_file.exists():
            raise ValueError("数据集不存在，请重新上传")
        meta = json.loads(meta_file.read_text(encoding="utf-8"))

        class_names = meta.get("class_names") or []
        data_yaml = ensure_data_yaml(Path(meta["root"]), class_names)

        task_id = uuid.uuid4().hex[:16]
        run_dir = RUN_ROOT / task_id
        run_dir.mkdir(parents=True, exist_ok=True)

        task = TrainTask(
            id=task_id,
            dataset_id=dataset_id,
            dataset_name=meta.get("name") or "",
            base_model=base_model,
            preset=preset,
            epochs=epochs,
            batch=16,
            imgsz=640,
            status="pending",
            total_epochs=epochs,
            threshold=threshold,
            run_dir=str(run_dir),
        )
        db.add(task)
        db.commit()

        params = {
            "base_model": f"{base_model}.pt",
            "data_yaml": str(data_yaml),
            "epochs": epochs,
            "batch": 16,
            "imgsz": 640,
            "project": str(RUN_ROOT),
            "name": task_id,
            "device": "0",
        }
        proc = spawn(params, run_dir / "train.log")
        _CURRENT[task_id] = proc
        task.status = "running"
        db.commit()
        return task
    finally:
        _TRAIN_LOCK.release()


def cancel_training(db, task_id: str) -> dict:
    """取消训练：杀进程组，标记 canceled。"""
    from app.models.train import TrainTask

    task = db.query(TrainTask).filter(TrainTask.id == task_id).first()
    if task is None:
        raise ValueError("任务不存在")
    if task.status not in ("pending", "running"):
        raise ValueError("任务已结束，无法取消")

    proc = _CURRENT.pop(task_id, None)
    killed = False
    if proc is not None and proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            killed = True
        except Exception:
            try:
                proc.kill()
                killed = True
            except Exception:
                pass

    task.status = "canceled"
    from datetime import datetime as _dt
    task.finished_at = _dt.now()
    db.commit()
    return {"task_id": task_id, "canceled": True, "killed": killed}

# ============================================================
# 四、进度解析 / 曲线 / 模型注册
# ============================================================

# 指标列名（ultralytics 的 results.csv 带 (B) 后缀）
_METRIC_COLS = {
    "precision": "metrics/precision(B)",
    "recall": "metrics/recall(B)",
    "map50": "metrics/mAP50(B)",
    "map50_95": "metrics/mAP50-95(B)",
}
_LOSS_COLS = {
    "train_box": "train/box_loss",
    "train_cls": "train/cls_loss",
    "val_box": "val/box_loss",
    "val_cls": "val/cls_loss",
}


def _f(row: dict, key: str):
    val = row.get(key)
    if val is None or str(val).strip() == "":
        return None
    try:
        return float(val)
    except ValueError:
        return None


def read_results(run_dir: Path) -> dict:
    """解析 results.csv，返回曲线数据。缺列返回空数组，绝不抛异常。"""
    import csv

    out = {
        "epochs": [],
        "losses": {k: [] for k in _LOSS_COLS},
        "metrics": {k: [] for k in _METRIC_COLS},
        "has_data": False,
    }
    run_dir = Path(run_dir or "")
    csv_path = run_dir / "results.csv"
    if not csv_path.exists():
        return out

    try:
        with csv_path.open("r", encoding="utf-8", errors="ignore") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            header = {(h or "").strip() for h in (reader.fieldnames or [])}
    except Exception:
        return out

    for row in rows:
        clean = {(k or "").strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        ep = _f(clean, "epoch")
        out["epochs"].append(int(ep) if ep is not None else len(out["epochs"]) + 1)
        # 列不存在就不追加（保持空数组），存在但为空则记 None
        for key, col in _LOSS_COLS.items():
            if col in header:
                out["losses"][key].append(_f(clean, col))
        for key, col in _METRIC_COLS.items():
            if col in header:
                out["metrics"][key].append(_f(clean, col))

    out["has_data"] = bool(out["epochs"])
    return out


def task_to_dict(task) -> dict:
    return {
        "task_id": task.id,
        "dataset_id": task.dataset_id,
        "dataset_name": task.dataset_name,
        "base_model": task.base_model,
        "preset": task.preset,
        "status": task.status,
        "progress": task.progress,
        "total_epochs": task.total_epochs,
        "map50": task.map50,
        "map50_95": task.map50_95,
        "precision": task.precision_,
        "recall": task.recall_,
        "threshold": task.threshold,
        "passed": bool(task.passed),
        "model_id": task.model_id,
        "error": task.error,
        "created_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S") if task.created_at else None,
        "finished_at": task.finished_at.strftime("%Y-%m-%d %H:%M:%S") if task.finished_at else None,
    }


def watch(db, task_id: str, interval: float = 5.0) -> None:
    """后台守护线程：更新进度 → 完成后读指标 → 注册模型。"""
    from app.models.train import TrainTask

    def _loop():
        rdb = SessionLocal()
        try:
            while True:
                task = rdb.query(TrainTask).filter(TrainTask.id == task_id).first()
                if task is None or task.status not in ("pending", "running"):
                    return

                run_dir = Path(task.run_dir or "")
                res = read_results(run_dir)
                if res["epochs"]:
                    task.progress = res["epochs"][-1]
                    rdb.commit()

                proc = _CURRENT.get(task_id)
                alive = proc is not None and proc.poll() is None
                if alive:
                    time.sleep(interval)
                    continue

                _finish(rdb, task, run_dir)
                return
        finally:
            rdb.close()

    threading.Thread(target=_loop, daemon=True, name=f"watch-{task_id}").start()


def _finish(db, task, run_dir: Path) -> None:
    """训练进程结束后的收尾：读指标、判定达标、注册模型。"""
    from datetime import datetime as _dt

    from app.service import model_service

    res = read_results(run_dir)
    best = run_dir / "weights" / "best.pt"
    map50 = None
    for key in ("map50", "map50_95", "precision", "recall"):
        series = res["metrics"].get(key) or []
        val = series[-1] if series else None
        if key == "map50":
            map50 = val
    task.map50 = map50
    task.map50_95 = res["metrics"].get("map50_95", [None])[-1] if res["metrics"].get("map50_95") else None
    task.precision_ = res["metrics"].get("precision", [None])[-1] if res["metrics"].get("precision") else None
    task.recall_ = res["metrics"].get("recall", [None])[-1] if res["metrics"].get("recall") else None
    task.passed = 1 if (task.map50 is not None and task.map50 >= task.threshold) else 0
    task.finished_at = _dt.now()

    if not best.exists():
        task.status = "failed"
        task.error = (task.error or "") + " 训练结束但没有产出 best.pt"
        db.commit()
        return

    try:
        entry = model_service.add_model(
            f"train_{task.id}.pt", best.read_bytes(), name=f"训练模型 {task.dataset_name or task.id}"
        )
        entry.update({"map50": task.map50, "threshold": task.threshold, "passed": task.passed,
                      "source": "train", "task_id": task.id})
        model_service.update_entry(entry["id"], entry)
        task.model_id = entry["id"]
    except Exception as exc:
        task.status = "failed"
        task.error = f"模型注册失败：{exc}"
        db.commit()
        return

    task.status = "success"
    if task.map50 is None:
        task.passed = 0
    db.commit()
    _CURRENT.pop(task.id, None)

# ============================================================
# 五、收尾：重启恢复 + 目录清理
# ============================================================


def recover_interrupted(db) -> int:
    """服务重启时把残留的 running/pending 任务标记为 interrupted。

    不做这一步，前端会永远转圈等一个已经死掉的进程。
    """
    from datetime import datetime as _dt

    from app.models.train import TrainTask

    rows = db.query(TrainTask).filter(TrainTask.status.in_(["pending", "running"])).all()
    for row in rows:
        row.status = "interrupted"
        row.error = (row.error or "") + " 服务重启，训练进程已丢失"
        row.finished_at = _dt.now()
    if rows:
        db.commit()
    return len(rows)


def prune_old_runs(keep: int = 5) -> int:
    """只保留最近 keep 个训练目录（按修改时间）。返回删除数量。"""
    if not RUN_ROOT.exists():
        return 0
    dirs = [d for d in RUN_ROOT.iterdir() if d.is_dir()]
    dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    removed = 0
    for d in dirs[keep:]:
        shutil.rmtree(d, ignore_errors=True)
        removed += 1
    return removed
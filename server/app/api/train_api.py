"""训练模块接口：数据集上传 / 训练任务 / 进度与曲线。"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.train import TrainTask

from app.service import train_service
from app.utils.response import fail, success

router = APIRouter(prefix="/api/train", tags=["模型训练"])

# 数据集根目录：server/data/datasets
DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
DATASET_ROOT = DATA_ROOT / "datasets"
MAX_ZIP_BYTES = 2 * 1024 * 1024 * 1024  # 2GB


def _dataset_dir(dataset_id: str) -> Path:
    return DATASET_ROOT / dataset_id


@router.post("/datasets")
async def upload_dataset(file: UploadFile = File(...)):
    """上传 YOLO 数据集 zip，校验通过才留下。"""
    name = file.filename or "dataset.zip"
    if not name.lower().endswith(".zip"):
        return fail("请上传 .zip 压缩包（内含 images/ 与 labels/）")

    dataset_id = uuid.uuid4().hex[:16]
    work = _dataset_dir(dataset_id)
    work.mkdir(parents=True, exist_ok=True)
    zip_path = work / "raw.zip"

    # 边读边写，顺带卡 2GB 上限
    size = 0
    try:
        with zip_path.open("wb") as out:
            while chunk := await file.read(1 << 22):  # 4MB
                size += len(chunk)
                if size > MAX_ZIP_BYTES:
                    raise ValueError("压缩包超过 2GB")
                out.write(chunk)
    except ValueError as exc:
        shutil.rmtree(work, ignore_errors=True)
        return fail(str(exc))

    try:
        root = train_service.parse_zip(zip_path, work / "dataset")
    except Exception as exc:  # zip 损坏 / 路径穿越
        shutil.rmtree(work, ignore_errors=True)
        return fail(f"解压失败：{exc}")

    report = train_service.validate_dataset_dir(root)
    if not report["ok"]:
        shutil.rmtree(work, ignore_errors=True)
        tail = report["errors"][:8]
        return fail("数据集不符合 YOLO 格式：" + "；".join(tail), data={"errors": report["errors"][:50]})

    meta = {
        "dataset_id": dataset_id,
        "name": name,
        "root": str(root),
        "classes": report["classes"],
        "images": report["images"],
        "boxes": report["boxes"],
        "class_names": report["class_names"],
        "empty_labels": report["empty_labels"],
        "clipped": report["clipped"],
        "warnings": [e for e in report["errors"] if "已自动裁剪" in e][:20],
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    (work / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    zip_path.unlink(missing_ok=True)  # 校验完不再留 zip

    return success(meta, "数据集校验通过")


@router.get("/datasets")
def list_datasets():
    """已上传的数据集列表。"""
    items = []
    if DATASET_ROOT.exists():
        for meta_file in sorted(DATASET_ROOT.glob("*/meta.json"), reverse=True):
            try:
                items.append(json.loads(meta_file.read_text(encoding="utf-8")))
            except Exception:
                continue
    return success({"items": items})


@router.delete("/datasets/{dataset_id}")
def remove_dataset(dataset_id: str):
    work = _dataset_dir(dataset_id)
    if not work.exists():
        return fail("数据集不存在")
    shutil.rmtree(work, ignore_errors=True)
    return success({"removed": dataset_id})


@router.post("/start")
def start_training_api(payload: dict = Body(...), db: Session = Depends(get_db)):
    """启动训练。payload: {dataset_id, base_model, preset, epochs, threshold}"""
    dataset_id = payload.get("dataset_id")
    if not dataset_id:
        return fail("缺少 dataset_id")

    base_model = payload.get("base_model") or "yolo26s"
    if base_model not in ("yolo26n", "yolo26s", "yolo26m"):
        return fail("base_model 只能是 yolo26n / yolo26s / yolo26m")

    preset = payload.get("preset") or "standard"
    epochs = int(payload.get("epochs") or train_service.PRESETS.get(preset, 120))
    threshold = float(payload.get("threshold") if payload.get("threshold") is not None else 0.5)
    if not (0 < threshold <= 1):
        return fail("mAP50 阈值必须在 0 与 1 之间")

    try:
        task = train_service.start_training(db, dataset_id, base_model, preset, epochs, threshold)
    except ValueError as exc:
        return fail(str(exc))
    train_service.watch(db, task.id)
    return success({"task_id": task.id, "epochs": epochs, "threshold": threshold}, "训练已启动")


@router.post("/{task_id}/cancel")
def cancel_task(task_id: str, db: Session = Depends(get_db)):
    try:
        return success(train_service.cancel_training(db, task_id), "已取消")
    except ValueError as exc:
        return fail(str(exc))


@router.get("/{task_id}")
def task_detail(task_id: str, db: Session = Depends(get_db)):
    task = db.query(TrainTask).filter(TrainTask.id == task_id).first()
    if task is None:
        return fail("任务不存在")
    return success(train_service.task_to_dict(task))


@router.get("/{task_id}/curves")
def task_curves(task_id: str, db: Session = Depends(get_db)):
    task = db.query(TrainTask).filter(TrainTask.id == task_id).first()
    if task is None:
        return fail("任务不存在")
    return success(train_service.read_results(Path(task.run_dir or "")))
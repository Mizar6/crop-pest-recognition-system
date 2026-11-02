"""YOLO 模型加载与推理封装（固定权重版）。

砍掉「模型管理」后，系统只使用 settings.MODEL_PATH 指定的一个权重，
进程内缓存，避免每次请求重复加载。并发安全由线程锁保证。
"""
import threading
import time
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np
from ultralytics import YOLO

from app.core.config import settings
from app.service import model_service
from app.service.file_service import save_bytes

# 单例模型与锁
_model: Optional[Any] = None
_model_lock = threading.Lock()


def load_model() -> Any:
    """返回当前激活的模型（由 model_service 管理热切换）。"""
    return model_service.active_model()


def model_info() -> dict:
    """返回当前模型的基本信息，供前端展示。"""
    model = load_model()
    meta = model_service.active_meta()
    return {
        "model_name": meta.get("name") or settings.MODEL_NAME,
        "file": Path(meta.get("path", "")).name if meta.get("path") else settings.model_abs_path.name,
        "class_num": len(model.names),
        "conf_default": settings.DEFAULT_CONF,
        "imgsz": settings.DEFAULT_IMGSZ,
    }


def class_names() -> list[dict]:
    """返回全部类别（id + 中文名），用于前端下拉/图例。"""
    model = load_model()
    return [{"class_id": cid, "class_name": name} for cid, name in model.names.items()]


def parse_boxes(result: Any, names: dict) -> list[dict]:
    """解析 Ultralytics 单张检测结果，转为字典列表。"""
    items: list[dict] = []
    if result.boxes is None or len(result.boxes) == 0:
        return items
    for box in result.boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        xyxy = box.xyxy[0].tolist()
        items.append(
            {
                "class_id": cls_id,
                "class_name": names.get(cls_id, str(cls_id)),
                "confidence": round(conf, 4),
                "x1": round(xyxy[0], 2),
                "y1": round(xyxy[1], 2),
                "x2": round(xyxy[2], 2),
                "y2": round(xyxy[3], 2),
            }
        )
    return items


def predict_image(
    model: Any,
    source,
    conf: float = 0.25,
    imgsz: int = 640,
) -> tuple[list[dict], Any, int]:
    """对图片路径或 numpy 帧执行检测。

    Returns:
        (boxes, ultralytics 结果对象, 耗时毫秒)
    """
    start = time.time()
    results = model.predict(source=source, conf=conf, imgsz=imgsz, verbose=False)
    cost_ms = int((time.time() - start) * 1000)
    result = results[0]
    boxes = parse_boxes(result, model.names)
    return boxes, result, cost_ms


def draw_and_save(result: Any, suffix: str = ".jpg") -> str:
    """将带检测框的结果图保存到 results 目录，返回相对路径。"""
    plotted = result.plot()
    ok, buf = cv2.imencode(".jpg", plotted)
    if not ok:
        raise RuntimeError("检测结果图编码失败")
    return save_bytes(buf.tobytes(), "results", suffix)


def encode_frame_jpg(frame: np.ndarray) -> bytes:
    """将 OpenCV 帧编码为 JPEG 字节。"""
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("帧编码失败")
    return buf.tobytes()


def summarize(boxes: list[dict]) -> dict:
    """汇总检测结果：同类合并取最高置信度，按置信度倒序。

    供记录落库与 AI 问答的「病害实体」抽取使用。
    """
    merged: dict[int, dict] = {}
    for b in boxes:
        cid = b["class_id"]
        if cid not in merged or b["confidence"] > merged[cid]["confidence"]:
            merged[cid] = {**b, "count": 0}
        merged[cid]["count"] += 1
    items = sorted(merged.values(), key=lambda x: x["confidence"], reverse=True)
    top = items[0] if items else None
    return {"items": items, "top": top, "count": len(boxes)}

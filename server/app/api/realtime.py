"""WebSocket 实时检测：前端推送 JPEG 帧，后端回传检测框。

已砍：Token 鉴权、告警规则联动。现在只做「推帧 → 检测 → 回框」，
必要时（前端 save=true）落库一条检测记录。
"""
import base64
from datetime import datetime

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.detect import DetectDetail, DetectRecord
from app.service.file_service import save_bytes
from app.service.yolo_service import load_model, predict_image

router = APIRouter(tags=["实时检测"])


def _persist_frame(boxes: list[dict], conf: float, cost_ms: int) -> int | None:
    """把当前帧的检测结果写入记录表，返回 record_id。"""
    if not boxes:
        return None
    db = SessionLocal()
    try:
        top = max(boxes, key=lambda x: x["confidence"])
        record = DetectRecord(
            detect_type="realtime",
            source_name="camera_frame",
            target_count=len(boxes),
            top_class=top["class_name"],
            top_confidence=top["confidence"],
            conf_threshold=conf,
            cost_ms=cost_ms,
            detect_time=datetime.now(),
        )
        db.add(record)
        db.flush()
        for box in boxes:
            db.add(
                DetectDetail(
                    record_id=record.id,
                    class_id=box["class_id"],
                    class_name=box["class_name"],
                    confidence=box["confidence"],
                    x1=box["x1"],
                    y1=box["y1"],
                    x2=box["x2"],
                    y2=box["y2"],
                )
            )
        db.commit()
        return record.id
    finally:
        db.close()


@router.websocket("/api/detect/realtime")
async def realtime_detect(websocket: WebSocket):
    """实时检测 WebSocket。

    客户端发送：{"image": "base64...", "conf": 0.25, "save": false}
    服务端回传：{"code": 200, "boxes": [...], "cost_ms": n, "record_id": ...}
    """
    await websocket.accept()
    try:
        model = load_model()
    except Exception as e:
        await websocket.send_json({"code": 500, "msg": f"模型加载失败：{e}"})
        await websocket.close()
        return

    try:
        while True:
            message = await websocket.receive_json()
            b64 = message.get("image") or ""
            conf = float(message.get("conf") or settings.DEFAULT_CONF)
            do_save = bool(message.get("save"))
            if "," in b64:
                b64 = b64.split(",", 1)[1]
            try:
                raw = base64.b64decode(b64)
                frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    await websocket.send_json({"code": 400, "msg": "无法解析图像"})
                    continue
                boxes, _result, cost_ms = predict_image(model, frame, conf=conf)
            except Exception as e:
                await websocket.send_json({"code": 500, "msg": f"推理失败：{e}"})
                continue

            record_id = None
            if do_save and boxes:
                try:
                    save_bytes(raw, "frames", ".jpg")
                except Exception:
                    pass
                record_id = _persist_frame(boxes, conf, cost_ms)

            await websocket.send_json(
                {
                    "code": 200,
                    "boxes": boxes,
                    "cost_ms": cost_ms,
                    "record_id": record_id,
                }
            )
    except WebSocketDisconnect:
        return

"""视频抽帧推理并写出带框结果视频。"""
import time
from pathlib import Path
from typing import Callable, Optional

import cv2

from app.service.file_service import abs_path, save_bytes
from app.service.yolo_service import parse_boxes


# 任务进度缓存：task_id -> {status, progress, result_path, error, record_id}
video_tasks: dict[str, dict] = {}


def process_video(
    task_id: str,
    model,
    source_rel: str,
    conf: float,
    on_progress: Optional[Callable[[int], None]] = None,
) -> tuple[list[dict], str, int]:
    """
    对视频逐帧检测并写出结果视频。

    Args:
        task_id: 后台任务ID
        model: YOLO 模型
        source_rel: 源视频相对路径
        conf: 置信度阈值
        on_progress: 进度回调 0-100
    Returns:
        (全部目标框, 结果视频相对路径, 耗时毫秒)
    """
    src = abs_path(source_rel)
    if src is None or not src.exists():
        raise FileNotFoundError("视频文件不存在")

    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise RuntimeError("无法打开视频文件")

    fps = cap.get(cv2.CAP_PROP_FPS) or 15
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    from datetime import datetime
    import uuid

    from app.core.config import settings

    day = datetime.now().strftime("%Y%m%d")
    out_name = f"{uuid.uuid4().hex}.mp4"
    rel_dir = f"results/{day}"
    dest_dir = Path(settings.UPLOAD_ROOT) / rel_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / out_name

    writer = None
    for fourcc_name in ("avc1", "mp4v", "XVID"):
        fourcc = cv2.VideoWriter_fourcc(*fourcc_name)
        writer = cv2.VideoWriter(str(dest), fourcc, fps, (width, height))
        if writer.isOpened():
            break
        writer.release()
        writer = None
    if writer is None:
        cap.release()
        raise RuntimeError("无法创建结果视频编码器")

    all_boxes: list[dict] = []
    start = time.time()
    index = 0
    sample_every = 1
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if index % sample_every == 0:
                results = model.predict(source=frame, conf=conf, imgsz=640, verbose=False)
                result = results[0]
                boxes = parse_boxes(result, model.names)
                all_boxes.extend(boxes)
                plotted = result.plot()
                if plotted.shape[1] != width or plotted.shape[0] != height:
                    plotted = cv2.resize(plotted, (width, height))
                writer.write(plotted)
            else:
                writer.write(frame)
            index += 1
            if total > 0 and on_progress:
                on_progress(min(99, int(index * 100 / total)))
            video_tasks[task_id]["progress"] = min(99, int(index * 100 / max(total, 1)))
    finally:
        cap.release()
        writer.release()

    cost_ms = int((time.time() - start) * 1000)
    relative = f"{rel_dir}/{out_name}".replace("\\", "/")
    return all_boxes, relative, cost_ms

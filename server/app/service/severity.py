"""病害严重程度估计：在检测框内按病斑颜色占比分级。

思路：健康叶片是绿色，病斑是褐/橙/黄。框内做一次 HSV 阈值分割，
用病斑像素占框面积的比例分级，再与病害固有危害等级相乘得到风险等级。
"""
from pathlib import Path

import cv2
import numpy as np

# 病斑色域（OpenCV H: 0-180）
LESION_RANGES = [
    ((0, 40, 40), (22, 255, 255)),     # 橙褐 / 锈色
    ((22, 40, 40), (35, 255, 255)),    # 黄化
    ((160, 40, 30), (180, 255, 200)),  # 深褐偏红
]

LEVEL_SCORE = {"高": 3, "中": 2, "低": 1}
SEVERITY_SCORE = {"轻": 1, "中": 2, "重": 3}


def _lesion_mask(roi: np.ndarray) -> np.ndarray:
    """返回 ROI 内的病斑掩膜。"""
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lo, hi in LESION_RANGES:
        mask |= cv2.inRange(hsv, np.array(lo), np.array(hi))
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


def _grade(ratio: float) -> str:
    if ratio < 0.05:
        return "轻"
    if ratio < 0.20:
        return "中"
    return "重"


def estimate(image_path: str | Path, boxes: list[dict], level: str | None = None) -> dict:
    """估计严重程度。

    Args:
        image_path: 原图路径
        boxes: 检测框列表（含 x1,y1,x2,y2,class_name,confidence）
        level: 该病害的固有危害等级（高/中/低），来自知识库
    Returns:
        {"ratio": 0.12, "severity": "中", "risk": "中高", "per_box": [...]}
    """
    img = cv2.imread(str(image_path))
    if img is None or not boxes:
        return {"ratio": 0.0, "severity": "未知", "risk": "未知", "per_box": []}

    h, w = img.shape[:2]
    per_box = []
    lesion_total = 0
    area_total = 0

    for b in boxes:
        x1 = max(0, int(b["x1"]))
        y1 = max(0, int(b["y1"]))
        x2 = min(w, int(b["x2"]))
        y2 = min(h, int(b["y2"]))
        if x2 - x1 < 8 or y2 - y1 < 8:
            continue
        roi = img[y1:y2, x1:x2]
        mask = _lesion_mask(roi)
        lesion = int(mask.sum() // 255)
        area = roi.shape[0] * roi.shape[1]
        lesion_total += lesion
        area_total += area
        per_box.append(
            {
                "class_name": b["class_name"],
                "ratio": round(lesion / area, 4),
                "severity": _grade(lesion / area),
            }
        )

    ratio = round(lesion_total / area_total, 4) if area_total else 0.0
    severity = _grade(ratio)

    risk = "未知"
    if level in LEVEL_SCORE and severity in SEVERITY_SCORE:
        score = LEVEL_SCORE[level] * SEVERITY_SCORE[severity]
        risk = "低" if score <= 2 else ("中" if score <= 4 else ("高" if score <= 6 else "极高"))

    return {"ratio": ratio, "severity": severity, "risk": risk, "per_box": per_box}

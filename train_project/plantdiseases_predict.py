
from pathlib import Path
import sys
from typing import Any

from ultralytics import YOLO

sys.path.append(str(Path(__file__).resolve().parents[1]))

# 脚本所在目录，避免工作目录不对时找不到权重和图片
HERE = Path(__file__).resolve().parent
WEIGHTS = HERE / "best.pt"
IMAGE = HERE / "test.jpg"


def ensure_dir(path: str | Path) -> Path:
    """确保目录存在并返回 Path。"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def print_detections(result: Any, names: dict) -> None:
    """
    打印单张图的检测结果。

    Args:
        result: Ultralytics Results 对象（单张）
        names: 类别 id -> 名称 映射
    """
    if result.boxes is None or len(result.boxes) == 0: # 如果检测结果为空，则打印未检测到目标
        print("  （未检测到目标）")
        return

    for i, box in enumerate(result.boxes): # 遍历检测结果 Boxes，可以理解为「这一张图里所有检测到的目标框」。
        cls_id = int(box.cls[0]) # 类别id
        conf = float(box.conf[0]) # 置信度
        xyxy = box.xyxy[0].tolist() # 边界框坐标
        name = names.get(cls_id, str(cls_id)) # 类别名称
        print(
            f"  [{i}] {name:16s} conf={conf:.3f} " # 打印检测结果
            f"xyxy=[{xyxy[0]:.1f}, {xyxy[1]:.1f}, {xyxy[2]:.1f}, {xyxy[3]:.1f}]" # 打印边界框坐标
        )



def main() -> None:
    """加载自定义权重并对单张图片推理、打印并保存结果。"""
    if not WEIGHTS.exists():
        raise FileNotFoundError(f"未找到模型权重: {WEIGHTS}")
    if not IMAGE.exists():
        raise FileNotFoundError(f"未找到待推理图片: {IMAGE}")

    model = YOLO(str(WEIGHTS))  # 加载自己训练的模型
    out_dir = ensure_dir(HERE / "runs")  # 推理结果保存目录

    results = model.predict(
        source=str(IMAGE),
        conf=0.1,  # 置信度阈值，低于该值的框会被丢掉
        imgsz=960,  # 比训练默认 640 更大，适配高分辨率原图
        save=True,  # 保存带检测框的图片
        project=str(out_dir),
        name="plantdiseases_predict",
        exist_ok=True,
    )

    print(f"类别: {model.names}")
    print_detections(results[0], model.names)
    print(f"结果已保存到: {out_dir / 'test_predict'}")

    results[0].show()  # 弹窗显示检测结果


if __name__ == "__main__":
    main()
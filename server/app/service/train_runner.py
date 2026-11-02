"""训练执行器：被 train_service 以子进程方式拉起。

用法：python -m app.service.train_runner <json 参数文件>

单独写一个脚本的好处：
  - 训练崩了只影响这个子进程，API 进程不受影响
  - 日志直接写到指定文件，进度由 results.csv 读取
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    params = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

    from ultralytics import YOLO  # 放在函数内，避免被 API 进程提前加载

    model = YOLO(params["base_model"])
    model.train(
        data=params["data_yaml"],
        epochs=params["epochs"],
        batch=params["batch"],
        imgsz=params["imgsz"],
        optimizer="auto",
        lr0=0.01,
        cos_lr=True,
        cache="ram",
        close_mosaic=10,
        pretrained=True,
        plots=True,
        verbose=True,
        project=params["project"],
        name=params["name"],
        exist_ok=True,
        device=params.get("device", "0"),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

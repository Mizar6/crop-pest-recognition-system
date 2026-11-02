"""
YOLO26n 重训脚本（针对原始 best.pt 仅训练 5 轮、mAP50 实测仅 0.216 的问题）

用法:
    cd train_project
    python retrain.py
    python retrain.py --epochs 200 --batch 48

训练结果输出到 runs_retrain/yolo26n/<时间戳或名称>/weights/best.pt
不覆盖原始 runs/ 与 best.pt，便于做新旧对比。
"""
import argparse
from pathlib import Path

from ultralytics import YOLO

BASE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(BASE / "yolo26n.pt"), help="预训练起点")
    ap.add_argument("--data", default=str(BASE / "plantdiseases.yaml"), help="数据集配置")
    ap.add_argument("--epochs", type=int, default=150)
    ap.add_argument("--patience", type=int, default=40, help="早停耐心值")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", default="0", help="0=第一块 GPU, cpu=处理器")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--name", default="yolo26n_e150")
    ap.add_argument("--cache", default="ram", help="ram/disk/false，ram 可显著加速")
    args = ap.parse_args()

    model = YOLO(args.model)
    model.train(
        data=args.data,
        epochs=args.epochs,
        patience=args.patience,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
        workers=args.workers,
        cache=(False if args.cache in ("false", "0", "") else args.cache),
        project=str(BASE / "runs_retrain"),
        name=args.name,
        exist_ok=True,
        pretrained=True,
        optimizer="auto",
        lr0=0.01,
        cos_lr=True,
        plots=True,
        verbose=True,
    )


if __name__ == "__main__":
    main()

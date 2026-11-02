from ultralytics import YOLO

model = YOLO("yolo26n.pt")  # 加载预训练权重
results = model.train(data="plantdiseases.yaml", epochs=5, imgsz=640)
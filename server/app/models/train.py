"""训练任务与数据集的 ORM 模型。"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.db.session import Base


class TrainDataset(Base):
    """上传的数据集（校验通过才会落库）。"""

    __tablename__ = "t_train_dataset"

    id = Column(String(32), primary_key=True)
    name = Column(String(120))
    root = Column(String(255), comment="解压后的数据集根目录")
    classes = Column(Integer, default=0)
    images = Column(Integer, default=0)
    boxes = Column(Integer, default=0)
    class_names = Column(Text, comment="JSON 数组")
    status = Column(String(20), default="ready")
    created_at = Column(DateTime, default=datetime.now)


class TrainTask(Base):
    """一次训练任务。"""

    __tablename__ = "t_train_task"

    id = Column(String(32), primary_key=True)
    dataset_id = Column(String(32), nullable=False, index=True)
    dataset_name = Column(String(120))
    base_model = Column(String(40), default="yolo26s")
    preset = Column(String(20), default="standard")
    epochs = Column(Integer, default=120)
    batch = Column(Integer, default=16)
    imgsz = Column(Integer, default=640)
    status = Column(String(20), default="pending")  # pending/running/success/failed/canceled/interrupted
    progress = Column(Integer, default=0)
    total_epochs = Column(Integer, default=0)
    map50 = Column(Float)
    map50_95 = Column(Float)
    precision_ = Column(Float)
    recall_ = Column(Float)
    threshold = Column(Float, default=0.5)
    passed = Column(Integer, default=0)
    model_id = Column(String(32))
    error = Column(Text)
    run_dir = Column(String(255))
    created_at = Column(DateTime, default=datetime.now)
    finished_at = Column(DateTime)
    threshold_updated_at = Column(DateTime)

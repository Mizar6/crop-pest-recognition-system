"""检测记录与检测明细 ORM 模型。"""
from sqlalchemy import Column, DateTime, Integer, Numeric, String, func

from app.db.session import Base


class DetectRecord(Base):
    """一次图片、视频或实时检测的汇总记录。"""

    __tablename__ = "t_detect_record"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    user_id = Column(Integer, comment="检测用户ID")
    model_id = Column(Integer, comment="使用的模型ID")
    detect_type = Column(String(20), nullable=False, comment="检测类型")
    source_name = Column(String(200), comment="原始文件名")
    source_path = Column(String(255), comment="原始文件相对路径")
    result_path = Column(String(255), comment="结果文件相对路径")
    target_count = Column(Integer, default=0, comment="检测到的目标数量")
    top_class = Column(String(80), comment="最高置信度类别名称")
    top_confidence = Column(Numeric(6, 4), default=0, comment="最高置信度")
    conf_threshold = Column(Numeric(6, 4), default=0.25, comment="置信度阈值")
    cost_ms = Column(Integer, default=0, comment="推理耗时")
    detect_time = Column(DateTime, nullable=False, server_default=func.now(), comment="检测时间")


class DetectDetail(Base):
    """单次检测中的每一个目标框。"""

    __tablename__ = "t_detect_detail"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    record_id = Column(Integer, nullable=False, comment="所属检测记录ID")
    class_id = Column(Integer, comment="类别ID")
    class_name = Column(String(80), comment="类别名称")
    confidence = Column(Numeric(6, 4), default=0, comment="置信度")
    x1 = Column(Numeric(10, 2), default=0, comment="框左上角X")
    y1 = Column(Numeric(10, 2), default=0, comment="框左上角Y")
    x2 = Column(Numeric(10, 2), default=0, comment="框右下角X")
    y2 = Column(Numeric(10, 2), default=0, comment="框右下角Y")

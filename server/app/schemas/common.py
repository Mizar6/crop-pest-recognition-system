"""检测记录相关请求/响应模型（已砍：告警、登录日志、操作日志、用户、模型）。"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class DetectBox(BaseModel):
    """单个检测框。"""

    class_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float


class DetectRecordOut(BaseModel):
    """检测记录。"""

    id: int
    detect_type: str
    source_name: Optional[str] = None
    source_path: Optional[str] = None
    result_path: Optional[str] = None
    target_count: int = 0
    top_class: Optional[str] = None
    top_confidence: float = 0
    conf_threshold: float = 0.25
    cost_ms: int = 0
    detect_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class DetectDetailOut(BaseModel):
    """检测明细。"""

    id: int
    record_id: int
    class_id: Optional[int] = None
    class_name: Optional[str] = None
    confidence: float = 0
    x1: float = 0
    y1: float = 0
    x2: float = 0
    y2: float = 0

    class Config:
        from_attributes = True


class DiseaseOut(BaseModel):
    """病害知识条目（结构化知识库，供 AI 问答检索使用）。"""

    id: int
    class_id: int
    class_name: str
    crop_name: Optional[str] = None
    disease_name: Optional[str] = None
    is_healthy: int = 0
    symptom: Optional[str] = None
    harm: Optional[str] = None
    control_plan: Optional[str] = None
    level: Optional[str] = None
    image_path: Optional[str] = None

    class Config:
        from_attributes = True


class PageResult(BaseModel):
    """通用分页结果。"""

    total: int
    list: List = []

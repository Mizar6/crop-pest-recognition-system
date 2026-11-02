# ORM 模型包（已砍：User / DetectModel / Alarm / AlarmRule / LoginLog / OperLog）
from app.models.chat import ChatMessage, ChatSession
from app.models.detect import DetectDetail, DetectRecord

__all__ = ["DetectRecord", "DetectDetail", "ChatMessage", "ChatSession"]

from app.models.kg import KgEntity, KgRelation  # noqa: F401
from app.models.train import TrainDataset, TrainTask  # noqa: F401

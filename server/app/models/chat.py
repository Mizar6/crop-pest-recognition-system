"""会话消息表：按 session_id 隔离的多轮对话记录。"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db.session import Base


class ChatMessage(Base):
    """一条对话消息（user 或 assistant）。"""

    __tablename__ = "t_chat_message"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True, comment="会话ID")
    role = Column(String(16), nullable=False, comment="user / assistant")
    content = Column(Text, nullable=False, comment="消息内容")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")


class ChatSession(Base):
    """一次对话的元信息（标题、活跃时间）。"""

    __tablename__ = "t_chat_session"

    id = Column(String(64), primary_key=True)
    title = Column(String(120), default="新对话")
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
"""文档抽取出来的图谱实体与关系（与 t_disease 的自动构建图合并展示）。"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from app.db.session import Base


class KgEntity(Base):
    __tablename__ = "t_kg_entity"
    __table_args__ = (UniqueConstraint("name", "type", name="uq_kg_entity"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    type = Column(String(30), nullable=False, comment="作物/病害/症状/药剂/措施/病原/媒介/气象/阈值")
    doc_id = Column(String(60), comment="来源文档")
    created_at = Column(DateTime, default=datetime.now)


class KgRelation(Base):
    __tablename__ = "t_kg_relation"
    __table_args__ = (UniqueConstraint("src", "rel", "dst", name="uq_kg_relation"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    src = Column(String(120), nullable=False)
    rel = Column(String(30), nullable=False)
    dst = Column(String(120), nullable=False)
    doc_id = Column(String(60))
    created_at = Column(DateTime, default=datetime.now)
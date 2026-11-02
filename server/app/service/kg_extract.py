"""从文档片段抽取实体与关系，写进图谱扩展表。

成本：qwen-plus 每块约 0.0007 元；930 块约 0.65 元。
"""
import json
import re

import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.kg import KgEntity, KgRelation

# 实体类型注册表：新增类型只改这里
ENTITY_TYPES = {
    "作物": "CROP",
    "病害": "DISEASE",
    "虫害": "PEST",
    "症状": "SYMPTOM",
    "药剂": "DRUG",
    "措施": "MEASURE",
    "病原": "PATHOGEN",
    "媒介": "VECTOR",
    "气象": "WEATHER",
    "阈值": "THRESHOLD",
}
RELATION_TYPES = ["患", "表现为", "用药", "措施", "病原为", "传播靠", "发生于", "阈值为"]

PROMPT = """你是农业植保知识抽取器。从下面的资料片段中抽取实体和关系。

实体类型只能是：{types}
关系只能是：{rels}

规则：
1. 实体名要短（2-12 字），用资料中的原词
2. 只能从资料中抽取，不要编造
3. 没有可抽的就返回空数组

输出严格的 JSON，不要多余文字：
{{"entities":[{{"name":"","type":""}}],"relations":[{{"src":"","rel":"","dst":""}}]}}

资料：
{text}"""


def _chat(messages: list[dict]) -> str:
    r = requests.post(
        f"{settings.RAG_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": settings.RAG_QA_MODEL, "messages": messages, "temperature": 0.1},
        timeout=90,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"entities": [], "relations": []}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"entities": [], "relations": []}
    return {
        "entities": data.get("entities") or [],
        "relations": data.get("relations") or [],
    }


def extract_chunk(text: str) -> dict:
    """对单个片段做抽取，返回 {entities, relations}。"""
    prompt = PROMPT.format(
        types="、".join(ENTITY_TYPES.keys()),
        rels="、".join(RELATION_TYPES),
        text=text[:1500],
    )
    raw = _chat([{"role": "user", "content": prompt}])
    return _parse_json(raw)


def save_graph(db: Session, data: dict, doc_id: str) -> dict:
    """写入扩展表，按唯一约束去重。"""
    added_e, dup_e = 0, 0
    for item in data.get("entities", []):
        name = (item.get("name") or "").strip()[:120]
        etype = (item.get("type") or "").strip()
        if not name or etype not in ENTITY_TYPES:
            continue
        exists = db.query(KgEntity).filter(KgEntity.name == name, KgEntity.type == etype).first()
        if exists:
            dup_e += 1
            continue
        db.add(KgEntity(name=name, type=etype, doc_id=doc_id))
        added_e += 1

    added_r, dup_r = 0, 0
    for item in data.get("relations", []):
        src = (item.get("src") or "").strip()[:120]
        rel = (item.get("rel") or "").strip()
        dst = (item.get("dst") or "").strip()[:120]
        if not (src and rel and dst) or rel not in RELATION_TYPES:
            continue
        exists = db.query(KgRelation).filter(
            KgRelation.src == src, KgRelation.rel == rel, KgRelation.dst == dst
        ).first()
        if exists:
            dup_r += 1
            continue
        db.add(KgRelation(src=src, rel=rel, dst=dst, doc_id=doc_id))
        added_r += 1

    db.commit()
    return {"entities_added": added_e, "entities_dup": dup_e, "relations_added": added_r, "relations_dup": dup_r}


def graph_extra(db: Session) -> dict:
    """把扩展表转成 {nodes, links}，供 kg.build_graph 合并。"""
    ents = db.query(KgEntity).all()
    rels = db.query(KgRelation).all()
    # 与 kg.CATEGORY_NAMES 的顺序保持一致，否则扩展实体会挂错类别
    type_index = {
        "作物": 0, "病害": 1, "症状": 2, "药剂": 3, "措施": 4,
        "病原": 5, "媒介": 6, "气象": 7, "阈值": 8, "虫害": 9,
    }
    nodes = [
        {
            "id": f"x:{e.id}",
            "name": e.name,
            "category": type_index.get(e.type, 4),
            "symbolSize": 14 if e.type in ("病害", "作物") else 10,
            "extra_type": e.type,
        }
        for e in ents
    ]
    name_to_id = {e.name: f"x:{e.id}" for e in ents}
    # 端点不在扩展表里时保留原始名字，交给 build_graph 按名字挂到主图节点
    links = [
        {
            "source": name_to_id.get(r.src, r.src),
            "target": name_to_id.get(r.dst, r.dst),
            "value": r.rel,
        }
        for r in rels
    ]
    return {"nodes": nodes, "links": links, "stats": {"entities": len(ents), "relations": len(rels)}}
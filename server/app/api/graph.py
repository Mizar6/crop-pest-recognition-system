"""知识图谱接口：graphs 由 service/kg.py 统一构建，页面与问答共用同一份。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.service import kg as kg_service
from app.utils.response import success

router = APIRouter(prefix="/api/graph", tags=["知识图谱"])


@router.get("")
def graph(db: Session = Depends(get_db)):
    """返回 { nodes, links, categories, stat }，直接喂 ECharts graph。"""
    return success(kg_service.build_graph(db))


@router.post("/extract")
def extract(doc_id: str = "", limit: int = 40, db: Session = Depends(get_db)):
    """对指定文档的片段做实体抽取，写入图谱。不传 doc_id 则取最近导入的文档。"""
    import json

    from app.models.kg import KgEntity, KgRelation
    from app.service import kg_extract

    from app.core.config import settings

    base = settings.vstore_path
    docs_file = base / "documents.json"
    chunks_file = base / "chunks_zh.json"
    if not docs_file.exists() or not chunks_file.exists():
        raise HTTPException(status_code=400, detail="知识库还没有导入内容")

    docs = json.loads(docs_file.read_text(encoding="utf-8"))
    if not docs:
        raise HTTPException(status_code=400, detail="知识库还没有导入内容")
    doc = next((d for d in docs if d["id"] == doc_id), docs[-1])

    chunks = json.loads(chunks_file.read_text(encoding="utf-8"))
    mine = [c for c in chunks if str(c.get("id", "")).startswith(doc["id"])][:limit]
    if not mine:
        raise HTTPException(status_code=400, detail="该文档没有可抽取的片段")

    total = {"entities_added": 0, "entities_dup": 0, "relations_added": 0, "relations_dup": 0}
    for chunk in mine:
        try:
            data = kg_extract.extract_chunk(chunk["text"])
            res = kg_extract.save_graph(db, data, doc["id"])
            for k in total:
                total[k] += res[k]
        except Exception:
            continue

    return success({
        "doc_id": doc["id"],
        "title": doc.get("title", ""),
        "chunks_processed": len(mine),
        **total,
    })


@router.get("/query")
def query(q: str = "", db: Session = Depends(get_db)):
    """按问题检索图谱：返回命中的节点 id 与一跳事实（供页面高亮）。"""
    ids = kg_service.match_ids(db, q)
    facts = kg_service.expand(db, q) if ids else []
    return success({"ids": ids, "facts": facts})

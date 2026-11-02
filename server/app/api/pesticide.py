"""药剂资料接口：读 t_pesticide（大模型从防治方案里抽出来的结构化药剂表）。

数据来源链：
    t_knowledge.control_plan（防治方案文本）
        ↓ 大模型抽取（tools/extract_pesticide.py）
    t_pesticide（药名/剂型/剂量/安全间隔期）
    t_pesticide_knowledge（药剂 ↔ 知识条目 关联）

返回结构与旧版保持一致，前端 Pesticides.vue 不用改。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.utils.response import success

router = APIRouter(prefix="/api/pesticide", tags=["药剂资料"])


PAGE_SIZE = 24


@router.get("/list")
def list_all(q: str = "", page: int = 1, size: int = PAGE_SIZE, db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            "SELECT p.id, p.name, p.formulation, p.crops, p.dosage, p.safety_interval, "
            "       COUNT(pk.knowledge_id) AS disease_count "
            "FROM t_pesticide p "
            "LEFT JOIN t_pesticide_knowledge pk ON pk.pesticide_id = p.id "
            "WHERE (:q = '' OR p.name LIKE CONCAT('%', :q, '%') OR p.crops LIKE CONCAT('%', :q, '%')) "
            "GROUP BY p.id "
            "ORDER BY disease_count DESC, p.name"
        ),
        {"q": (q or "").strip()},
    ).mappings().all()

    # 每种药剂适用的病害名（取前 3 个做简介）
    items = []
    for r in rows:
        names = db.execute(
            text(
                "SELECT k.name FROM t_pesticide_knowledge pk "
                "JOIN t_knowledge k ON k.id = pk.knowledge_id "
                "WHERE pk.pesticide_id = :pid ORDER BY k.id LIMIT 3"
            ),
            {"pid": r["id"]},
        ).all()
        items.append(
            {
                "id": r["id"],
                "name": r["name"],
                "formulation": r["formulation"] or "",
                "crops": [c for c in (r["crops"] or "").split("、") if c],
                "disease_count": int(r["disease_count"] or 0),
                "brief": "、".join(n[0] for n in names),
                "dosage": r["dosage"] or "",
                "safety_interval": r["safety_interval"] or "",
            }
        )
    total = len(items)
    page = max(1, int(page or 1))
    size = min(max(1, int(size or PAGE_SIZE)), 200)
    start = (page - 1) * size
    items = items[start:start + size]
    return success({
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size if size else 0,
        "items": items,
    })


@router.get("/{name}")
def detail(name: str, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT * FROM t_pesticide WHERE name = :n LIMIT 1"), {"n": name}
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="未找到该药剂")

    diseases = db.execute(
        text(
            "SELECT k.id, k.name, k.crop, k.category FROM t_pesticide_knowledge pk "
            "JOIN t_knowledge k ON k.id = pk.knowledge_id "
            "WHERE pk.pesticide_id = :pid ORDER BY k.id"
        ),
        {"pid": row["id"]},
    ).mappings().all()

    return success(
        {
            "id": row["id"],
            "name": row["name"],
            "formulation": row["formulation"] or "",
            "crops": [c for c in (row["crops"] or "").split("、") if c],
            "dosage": row["dosage"] or "",
            "safety_interval": row["safety_interval"] or "",
            "note": row["note"] or "",
            "verified": bool(row["verified"]),
            "diseases": [
                {"id": d["id"], "crop": d["crop"] or "未标注", "disease": d["name"], "category": d["category"]}
                for d in diseases
            ],
            "raw": [row["note"]] if row["note"] else [],
        }
    )

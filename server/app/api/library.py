"""病虫害图鉴接口：读 t_knowledge，按名字匹配、分页、按作物分类。

本版规则（按需求定稿）：
  1. 图鉴页默认不显示「健康叶片」（可通过 include_healthy=1 调出）
  2. 分页：page（从 1 开始）+ size（默认 24，最大 200）
  3. 按作物分类：返回 crops 列表（含每个作物的条目数），可用 crop 参数筛选
  4. 详情按 id 查，字段与旧前端保持兼容
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.service import kg as kg_service
from app.utils.response import success

router = APIRouter(prefix="/api/library", tags=["病虫害图鉴"])

MAX_SIZE = 200
DEFAULT_SIZE = 24


def _brief(text_value: str, n: int = 46) -> str:
    s = (text_value or "").strip().replace("\n", " ")
    return s[:n] + "…" if len(s) > n else s


@router.get("/list")
def list_items(
    q: str = "",
    crop: str = "",
    category: str = "",
    include_healthy: int = 0,
    page: int = 1,
    size: int = DEFAULT_SIZE,
    db: Session = Depends(get_db),
):
    """按关键字 / 作物 / 类别检索知识条目（分页）。"""
    page = max(1, int(page or 1))
    size = min(max(1, int(size or DEFAULT_SIZE)), MAX_SIZE)
    offset = (page - 1) * size

    where = ["(:q = '' OR k.name LIKE CONCAT('%', :q, '%') OR k.crop LIKE CONCAT('%', :q, '%') "
             "OR k.symptom LIKE CONCAT('%', :q, '%') OR k.name_en LIKE CONCAT('%', :q, '%'))",
             "(:crop = '' OR k.crop = :crop)",
             "(:category = '' OR k.category = :category)"]
    if not include_healthy:
        where.append("k.category <> '健康'")

    cond = " AND ".join(where)
    params = {"q": (q or "").strip(), "crop": (crop or "").strip(), "category": (category or "").strip()}

    total = db.execute(text(f"SELECT COUNT(*) FROM t_knowledge k WHERE {cond}"), params).scalar() or 0

    rows = db.execute(
        text(
            "SELECT k.id, k.name, COALESCE(k.name_en,'') AS name_en, COALESCE(k.crop,'未标注') AS crop, "
            "       COALESCE(k.level,'中') AS level, COALESCE(k.category,'病害') AS category, "
            "       COALESCE(k.symptom, k.harm, '') AS brief, k.verified "
            f"FROM t_knowledge k WHERE {cond} "
            "ORDER BY FIELD(k.category,'虫害','病害','健康'), FIELD(k.level,'高','中','低'), k.id "
            "LIMIT :lim OFFSET :off"
        ),
        {**params, "lim": size, "off": offset},
    ).mappings().all()

    items = [
        {
            "id": r["id"],
            "name": r["name"],
            "class_name": r["name_en"],
            "crop": r["crop"],
            "level": r["level"],
            "category": r["category"],
            "brief": _brief(r["brief"]),
            "verified": bool(r["verified"]),
        }
        for r in rows
    ]

    # 作物分类（只统计非健康，除非要包含健康）
    crop_sql = "SELECT crop, COUNT(*) AS n FROM t_knowledge WHERE crop IS NOT NULL AND crop <> ''"
    if not include_healthy:
        crop_sql += " AND category <> '健康'"
    crop_sql += " GROUP BY crop ORDER BY n DESC, crop"
    crops = [{"name": r[0], "count": int(r[1])} for r in db.execute(text(crop_sql)).all()]

    return success(
        {
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size if size else 0,
            "items": items,
            "crops": crops,
            "crop_total": len(crops),
        }
    )


@router.get("/{entry_id}")
def detail(entry_id: int, db: Session = Depends(get_db)):
    row = db.execute(text("SELECT * FROM t_knowledge WHERE id = :i"), {"i": entry_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="未找到该条目")

    try:
        neighbors = kg_service.expand(db, row["name"], limit=12)
    except Exception:
        neighbors = []

    return success(
        {
            "id": row["id"],
            "name": row["name"],
            "class_name": row["name_en"] or "",
            "crop": row["crop"] or "未标注",
            "level": row["level"] or "中",
            "category": row["category"] or "病害",
            "overview": row["harm"] or "",
            "symptom": row["symptom"] or "",
            "control": row["control_plan"] or "",
            "regulation": "",
            "neighbors": neighbors,
            "filled_by": row["filled_by"],
            "verified": bool(row["verified"]),
        }
    )

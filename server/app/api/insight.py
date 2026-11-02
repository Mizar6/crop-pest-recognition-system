"""数据洞察接口：知识库覆盖、类别构成、字段完整度、查询趋势。

数据源已切到新表 t_knowledge（117 条），与图鉴、药剂口径一致。
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.chat import ChatMessage
from app.models.detect import DetectRecord
from app.service.kg import split_drugs
from app.utils.response import success

router = APIRouter(prefix="/api/insight", tags=["数据洞察"])


@router.get("")
def insight(db: Session = Depends(get_db)):
    rows = db.execute(
        text("SELECT name, crop, category, symptom, harm, control_plan FROM t_knowledge ORDER BY id")
    ).mappings().all()

    crops: dict[str, int] = {}
    drugs: set[str] = set()
    cat = {"病害": 0, "虫害": 0, "健康": 0}
    for d in rows:
        crop = d["crop"] or "未标注"
        crops[crop] = crops.get(crop, 0) + 1
        drugs.update(split_drugs(d["control_plan"] or ""))
        category = d["category"] or "病害"
        cat[category] = cat.get(category, 0) + 1

    total = len(rows)
    completeness = {
        "概述": sum(1 for d in rows if d["harm"]),
        "为害症状": sum(1 for d in rows if d["symptom"]),
        "防治方法": sum(1 for d in rows if d["control_plan"]),
        "发生规律": 0,
    }

    # 近 14 日查询量（用户提问）
    today = datetime.now().date()
    start = datetime.combine(today - timedelta(days=13), datetime.min.time())
    q_rows = (
        db.query(func.date(ChatMessage.created_at), func.count(ChatMessage.id))
        .filter(ChatMessage.role == "user", ChatMessage.created_at >= start)
        .group_by(func.date(ChatMessage.created_at))
        .all()
    )
    q_map = {str(day): int(n) for day, n in q_rows}
    trend = []
    for i in range(14):
        day = today - timedelta(days=13 - i)
        trend.append({"date": day.strftime("%m-%d"), "count": q_map.get(str(day), 0)})

    detect_total = db.query(func.count(DetectRecord.id)).scalar() or 0
    query_total = (
        db.query(func.count(ChatMessage.id)).filter(ChatMessage.role == "user").scalar() or 0
    )

    return success(
        {
            "totals": {
                "diseases": total,
                "crops": len(crops),
                "pesticides": len(drugs),
                "queries": int(query_total),
                "detects": int(detect_total),
            },
            "crop_coverage": sorted(
                [{"name": k, "value": v} for k, v in crops.items()],
                key=lambda x: -x["value"],
            ),
            "categories": [{"name": k, "value": v} for k, v in cat.items() if v],
            "completeness": [
                {"name": k, "value": v, "rate": round(v / total * 100, 1) if total else 0}
                for k, v in completeness.items()
            ],
            "query_trend": trend,
        }
    )

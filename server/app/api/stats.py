"""首页与统计分析聚合接口（已去掉告警/模型/用户维度）。"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.detect import DetectDetail, DetectRecord
from app.utils.convert import to_dict
from app.utils.response import success

router = APIRouter(prefix="/api/stats", tags=["统计分析"])

TYPE_TEXT = {"image": "图片识别", "video": "视频识别", "realtime": "实时检测"}


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    """首页顶部统计卡片数据。"""
    today = datetime.now().strftime("%Y-%m-%d")
    detect_today = (
        db.query(func.count(DetectRecord.id))
        .filter(func.date(DetectRecord.detect_time) == today)
        .scalar()
        or 0
    )
    detect_total = db.query(func.count(DetectRecord.id)).scalar() or 0
    target_total = db.query(func.coalesce(func.sum(DetectRecord.target_count), 0)).scalar() or 0
    class_total = db.query(func.count(func.distinct(DetectDetail.class_name))).scalar() or 0
    return success(
        {
            "detect_today": int(detect_today),
            "detect_total": int(detect_total),
            "target_total": int(target_total),
            "class_total": int(class_total),
        }
    )


@router.get("/trend")
def trend(days: int = Query(7, ge=1, le=30), db: Session = Depends(get_db)):
    """近 N 天检测数量趋势。"""
    start = datetime.now().date() - timedelta(days=days - 1)
    rows = (
        db.query(func.date(DetectRecord.detect_time).label("d"), func.count(DetectRecord.id))
        .filter(DetectRecord.detect_time >= datetime.combine(start, datetime.min.time()))
        .group_by("d")
        .all()
    )
    mapping = {str(r[0]): int(r[1]) for r in rows}
    labels, values = [], []
    for i in range(days):
        day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        labels.append(day)
        values.append(mapping.get(day, 0))
    return success({"labels": labels, "values": values})


@router.get("/top-class")
def top_class(limit: int = Query(10, ge=1, le=30), db: Session = Depends(get_db)):
    """病害类别检测次数 TOP。"""
    rows = (
        db.query(DetectDetail.class_name, func.count(DetectDetail.id))
        .group_by(DetectDetail.class_name)
        .order_by(func.count(DetectDetail.id).desc())
        .limit(limit)
        .all()
    )
    return success([{"name": r[0], "value": int(r[1])} for r in rows if r[0]])


@router.get("/type-ratio")
def type_ratio(db: Session = Depends(get_db)):
    """检测类型占比。"""
    rows = (
        db.query(DetectRecord.detect_type, func.count(DetectRecord.id))
        .group_by(DetectRecord.detect_type)
        .all()
    )
    return success([{"name": TYPE_TEXT.get(r[0], r[0]), "value": int(r[1])} for r in rows])


@router.get("/latest")
def latest(db: Session = Depends(get_db)):
    """最新检测记录。"""
    rows = db.query(DetectRecord).order_by(DetectRecord.id.desc()).limit(8).all()
    data = []
    for i in rows:
        item = to_dict(i)
        item["detect_type_text"] = TYPE_TEXT.get(i.detect_type, i.detect_type)
        data.append(item)
    return success(data)

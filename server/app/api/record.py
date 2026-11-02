"""检测记录查询、详情、删除与导出（已去掉用户隔离与操作日志）。"""
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.detect import DetectDetail, DetectRecord
from app.service.file_service import public_url
from app.utils.convert import to_dict
from app.utils.response import fail, page_data, success

router = APIRouter(prefix="/api/record", tags=["检测记录"])

TYPE_TEXT = {"image": "图片识别", "video": "视频识别", "realtime": "实时检测"}


def _enrich(row: DetectRecord) -> dict:
    """补充前端可直接使用的访问地址。"""
    return to_dict(
        row,
        extra={
            "source_url": public_url(row.source_path),
            "result_url": public_url(row.result_path),
            "detect_type_text": TYPE_TEXT.get(row.detect_type, row.detect_type),
        },
    )


@router.get("/page")
def page_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    detect_type: str = Query(""),
    keyword: str = Query(""),
    db: Session = Depends(get_db),
):
    """分页查询检测记录。"""
    q = db.query(DetectRecord)
    if detect_type:
        q = q.filter(DetectRecord.detect_type == detect_type)
    if keyword:
        q = q.filter(
            (DetectRecord.top_class.like(f"%{keyword}%"))
            | (DetectRecord.source_name.like(f"%{keyword}%"))
        )
    total = q.count()
    rows = q.order_by(DetectRecord.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return success(page_data([_enrich(i) for i in rows], total))


@router.get("/export/excel")
def export_excel(db: Session = Depends(get_db)):
    """导出检测记录为 Excel。"""
    rows = db.query(DetectRecord).order_by(DetectRecord.id.desc()).limit(2000).all()
    wb = Workbook()
    ws = wb.active
    ws.title = "检测记录"
    ws.append(["ID", "检测类型", "文件名", "目标数", "主要类别", "置信度", "耗时(ms)", "检测时间"])
    for row in rows:
        data = _enrich(row)
        ws.append(
            [
                data.get("id"),
                data.get("detect_type_text"),
                data.get("source_name"),
                data.get("target_count"),
                data.get("top_class"),
                data.get("top_confidence"),
                data.get("cost_ms"),
                data.get("detect_time"),
            ]
        )
    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    filename = f"detect_records_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{record_id}")
def record_detail(record_id: int, db: Session = Depends(get_db)):
    """检测记录详情（含全部目标框）。"""
    row = db.query(DetectRecord).filter(DetectRecord.id == record_id).first()
    if not row:
        return fail("记录不存在")
    details = db.query(DetectDetail).filter(DetectDetail.record_id == record_id).all()
    return success({"record": _enrich(row), "details": [to_dict(i) for i in details]})


@router.delete("/{record_id}")
def delete_record(record_id: int, db: Session = Depends(get_db)):
    """删除检测记录及其明细。"""
    row = db.query(DetectRecord).filter(DetectRecord.id == record_id).first()
    if not row:
        return fail("记录不存在")
    db.query(DetectDetail).filter(DetectDetail.record_id == record_id).delete()
    db.delete(row)
    db.commit()
    return success(None, "删除成功")

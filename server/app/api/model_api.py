"""模型管理接口：上传 / 列表 / 切换 / 删除。"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.service import model_service
from app.utils.response import success

router = APIRouter(prefix="/api/model", tags=["模型管理"])

MAX_SIZE = 300 * 1024 * 1024


@router.get("/list")
def list_all():
    return success(model_service.list_models())


@router.post("/upload")
async def upload(file: UploadFile = File(...), name: str = Form("")):
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="文件超过 300MB")
    try:
        entry = model_service.add_model(file.filename or "model.pt", content, name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(entry)


@router.post("/{model_id}/activate")
def activate(model_id: str, db: Session = Depends(get_db)):
    try:
        entry = model_service.activate(model_id)
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


    return success({
        "activated": entry["id"],
        "name": entry["name"],
        "class_num": entry["class_num"],
    })


@router.delete("/{model_id}")
def remove(model_id: str):
    try:
        model_service.remove_model(model_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success({"removed": model_id})
@router.post("/{model_id}/threshold")
def set_threshold_api(model_id: str, payload: dict):
    """调整该模型的 mAP50 上线阈值，返回重算后的结果。"""
    try:
        threshold = float(payload.get("threshold"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="threshold 必须是数字")
    if not (0 < threshold <= 1):
        raise HTTPException(status_code=400, detail="threshold 必须在 0 与 1 之间")
    try:
        entry = model_service.set_threshold(model_id, threshold)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success({"id": model_id, "threshold": entry.get("threshold"), "passed": entry.get("passed")})
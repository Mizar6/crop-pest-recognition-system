"""知识库接口：上传文档、查看来源、删除、统计。"""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.service import kb_service
from app.utils.response import success

router = APIRouter(prefix="/api/kb", tags=["知识库"])

MAX_SIZE = 20 * 1024 * 1024


@router.get("/stats")
def get_stats():
    return success(kb_service.stats())


@router.get("/documents")
def documents():
    docs = kb_service.all_documents()
    return success({"total": len(docs), "items": docs})


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    crop: str = Form(""),
    title: str = Form(""),
):
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="文件超过 20MB")
    try:
        result = kb_service.ingest(file.filename or "doc.txt", content, crop, title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(result)


@router.delete("/documents/{doc_id}")
def remove(doc_id: str):
    try:
        result = kb_service.remove_document(doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(result)
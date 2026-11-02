"""农作物病虫害叶片智能识别系统 - 后端入口。

已砍模块：登录/注册、用户管理、模型管理、告警中心、病害知识库页面、系统日志。
保留模块：图片识别、视频识别、实时检测、检测记录、统计分析。
新增模块：AI 问答（检测 + 向量检索 + 大模型）。
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import chat, detect, graph, insight, kb_api, library, model_api, pesticide, realtime, record, stats, train_api
from app.core.config import settings
from app.db.session import Base, engine
from app.service.file_service import ensure_upload_dirs

# 注册 ORM 模型并建表（已存在的表不会重建）
import app.models  # noqa: F401

Base.metadata.create_all(bind=engine)

ensure_upload_dirs()

# 训练任务：重启后把残留的 running 标记为 interrupted，避免前端一直转圈
try:
    from app.db.session import SessionLocal as _SessionLocal
    from app.service.train_service import recover_interrupted, prune_old_runs

    _db = _SessionLocal()
    try:
        recover_interrupted(_db)
        prune_old_runs(keep=5)
    finally:
        _db.close()
except Exception as _exc:  # 训练模块异常不影响主服务启动
    print('[train] 启动自检失败:', _exc)

app = FastAPI(title=settings.APP_NAME, version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_ROOT), name="uploads")


app.include_router(detect.router)
app.include_router(realtime.router)
app.include_router(record.router)
app.include_router(stats.router)
app.include_router(chat.router)
app.include_router(graph.router)
app.include_router(library.router)
app.include_router(model_api.router)
app.include_router(train_api.router)
app.include_router(kb_api.router)
app.include_router(pesticide.router)
app.include_router(insight.router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    """将 HTTPException 转为统一 JSON 结构。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "msg": exc.detail, "data": None},
    )


@app.get("/")
def root():
    """健康检查。"""
    return {"code": 200, "msg": settings.APP_NAME, "data": "ok"}



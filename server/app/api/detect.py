"""图片识别与视频识别接口。

已砍：登录鉴权、模型选择（固定权重）、告警联动、操作日志。
"""
import threading
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, get_db
from app.models.detect import DetectDetail, DetectRecord
from app.service.file_service import abs_path, public_url, save_upload
from app.service import kg as kg_service
from app.service.disease_map import normalize, resolve as resolve_disease, resolve_name
from app.service.model_service import active_meta
from app.service.severity import estimate as estimate_severity
from app.service.yolo_service import (
    class_names,
    draw_and_save,
    load_model,
    model_info,
    predict_image,
    summarize,
)
from app.utils.convert import to_dict
from app.utils.response import fail, success
from app.utils.video import process_video, video_tasks

router = APIRouter(prefix="/api/detect", tags=["检测"])


def _name_map(db: Session, model_id) -> dict:
    """当前模型的 类别号 → 标准中文名（没有就空字典）。"""
    try:
        from app.service.model_service import class_names_zh

        return class_names_zh(model_id)
    except Exception:
        return {}

def _persist_record(
    db: Session,
    detect_type: str,
    source_name: str,
    source_path: str,
    result_path: str,
    boxes: list,
    conf: float,
    cost_ms: int,
    name_map: dict | None = None,
) -> DetectRecord:
    """保存检测记录与明细。"""
    name_map = name_map or {}
    top = max(boxes, key=lambda x: x["confidence"]) if boxes else None
    record = DetectRecord(
        detect_type=detect_type,
        source_name=source_name,
        source_path=source_path,
        result_path=result_path,
        target_count=len(boxes),
        top_class=name_map.get(top["class_id"], top["class_name"]) if top else None,
        top_confidence=top["confidence"] if top else 0,
        conf_threshold=conf,
        cost_ms=cost_ms,
        detect_time=datetime.now(),
    )
    db.add(record)
    db.flush()
    for box in boxes:
        db.add(
            DetectDetail(
                record_id=record.id,
                class_id=box["class_id"],
                class_name=name_map.get(box["class_id"], box["class_name"]),
                confidence=box["confidence"],
                x1=box["x1"],
                y1=box["y1"],
                x2=box["x2"],
                y2=box["y2"],
            )
        )
    db.commit()
    db.refresh(record)
    return record


@router.get("/model")
def get_model_info(db: Session = Depends(get_db)):
    """当前模型信息与全部类别（前端用于展示、AI 问答用于实体映射）。"""
    info = model_info()
    classes = class_names()
    info["classes"] = classes

    # 类别与知识表的匹配情况：模型译名 → 按名字匹配 t_knowledge
    from app.service.disease_map import match_by_name
    from app.service.model_service import class_names_zh

    # 已绑定数 = t_model_class 里该模型 knowledge_id 非空的行数
    try:
        _mid = active_meta().get("id")
        rows = db.execute(
            text("SELECT class_id, knowledge_id FROM t_model_class WHERE model_id = :m"),
            {"m": _mid},
        ).all()
        bound = {int(r[0]) for r in rows if r[1]}
    except Exception:
        bound = set()
    matched = len(bound)
    unmapped = [c["class_name"] for c in classes if int(c["class_id"]) not in bound]

    info["mapping"] = {
        "total": len(classes),
        "matched": matched,
        "unmapped": unmapped[:20],
        "mismatched": [],
        "translated": len(bound),
    }
    return success(info)


@router.post("/image")
def detect_image(
    file: UploadFile = File(...),
    conf: float = Form(settings.DEFAULT_CONF),
    db: Session = Depends(get_db),
):
    """上传图片进行病虫害识别。"""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
        return fail("请上传 jpg/png/bmp/webp 图片")
    relative, _ = save_upload(file, "images")
    try:
        model = load_model()
        source = abs_path(relative)
        boxes, result, cost_ms = predict_image(
            model, str(source), conf=conf, imgsz=settings.DEFAULT_IMGSZ
        )
        result_path = draw_and_save(result)
    except Exception as e:
        return fail(f"识别失败：{e}")

    try:
        _mid = active_meta().get("id")
    except Exception:
        _mid = None
    record = _persist_record(
        db, "image", file.filename or "", relative, result_path, boxes, conf, cost_ms,
        name_map=_name_map(db, _mid),
    )

    # ========================================================
    # 下面这一段是"识别结果"和"病害知识表"对接的地方，看懂这段就懂全流程了
    #
    # boxes 长这样（一张图可能检出多个病斑）：
    #   [ {"class_id": 2, "class_name": "苹果锈病叶片", "confidence": 0.93,
    #      "x1": 120, "y1": 88, "x2": 402, "y2": 366}, ... ]
    #
    # 1) 先挑出"最可信的那个框"（confidence 最大的），用它代表这张图的主要病
    # 2) 拿它的编号 + 名字，去 t_disease 表里找对应那一行
    #      row 可能找到（有知识），也可能是 None（表里没收录，页面显示"未知"）
    # 3) row.level 是这一行里记的"危害等级"（轻/中/重），
    #    它代表"这种病本身有多厉害"，不是"这张图有多严重"，
    #    所以下面还要再结合图片像素算一次真实严重度
    # ========================================================
    level = None
    known = False
    name_zh = None
    knowledge_detail = None
    if boxes:
        top = max(boxes, key=lambda b: b["confidence"])   # 置信度最高的那个框

        try:
            mid = active_meta().get("id")
        except Exception:
            mid = None
        # 新规则：模型编号 → 中文名 → 按名字去知识表里找（不再用 id 绑定）
        _res = resolve_name(db, mid, top["class_id"], top["class_name"])
        name_zh = _res.get("name_zh") or top["class_name"]
        known = bool(_res.get("known"))
        _k = _res.get("knowledge") or {}
        level = _k.get("level")
        if known:
            knowledge_detail = {
                "name": _k.get("name"),
                "level": _k.get("level"),
                "symptom": _k.get("symptom"),
                "control": _k.get("control"),
                "verified": _k.get("verified"),
            }

    # 等级口径统一：新知识表用 轻/中/重，风险算法用 低/中/高，这里做一次映射
    LEVEL_ALIAS = {"轻": "低", "重": "高", "中": "中", "低": "低", "高": "高"}
    if level:
        level = LEVEL_ALIAS.get(str(level).strip(), level)

    # 算严重度：打开原图，在检测框里数"病斑颜色"的像素占比 → 轻/中/重
    # 然后把上面的 level（病害天生多厉害）和这次的 severity（这次多严重）相乘 → 风险
    sev = estimate_severity(source, boxes, level)

    # 再从知识图谱里取一跳关系，比如「苹果锈病 —用药→ 三唑酮」
    kg_facts = kg_service.expand(db, top["class_name"]) if boxes else []
    return success(
        {
            "record": to_dict(record),
            "record_id": record.id,
            "boxes": boxes,
            "summary": summarize(boxes),
            "severity": sev,
            "knowledge": kg_facts,
            "name_zh": name_zh,
            "known": known,
            "knowledge_detail": knowledge_detail,
            "source_url": public_url(relative),
            "result_url": public_url(result_path),
            "model_name": settings.MODEL_NAME,
        },
        "识别完成",
    )


def _summarize_classes(boxes: list[dict]) -> list[dict]:
    """按类别聚合视频里的全部检出：每类的次数、最高置信度、代表框。

    视频是逐帧检测，同一个病斑会在多帧里重复出现，所以这里的 count 是
    「累计检出次数」，classes 的条数才代表画面里出现过多少种病虫害。
    """
    agg: dict[str, dict] = {}
    for b in boxes:
        name = b.get("class_name") or "未知"
        item = agg.get(name)
        if item is None:
            agg[name] = {
                "class_name": name,
                "class_id": b.get("class_id"),
                "count": 1,
                "max_conf": b.get("confidence", 0),
                "x1": b.get("x1"), "y1": b.get("y1"),
                "x2": b.get("x2"), "y2": b.get("y2"),
            }
        else:
            item["count"] += 1
            if b.get("confidence", 0) > item["max_conf"]:
                item["max_conf"] = b.get("confidence", 0)
                item["x1"], item["y1"] = b.get("x1"), b.get("y1")
                item["x2"], item["y2"] = b.get("x2"), b.get("y2")
    out = sorted(agg.values(), key=lambda x: (-x["max_conf"], -x["count"]))
    for it in out:
        it["max_conf"] = round(float(it["max_conf"]), 4)
    return out


def _run_video_task(task_id: str, source_rel: str, source_name: str, conf: float) -> None:
    """后台线程执行视频识别。"""
    db = SessionLocal()
    try:
        video_tasks[task_id]["status"] = "running"
        model = load_model()
        boxes, result_path, cost_ms = process_video(task_id, model, source_rel, conf)
        record = _persist_record(
            db, "video", source_name, source_rel, result_path, boxes, conf, cost_ms,
            name_map=_name_map(db, None),
        )
        classes = _summarize_classes(boxes)
        video_tasks[task_id].update(
            {
                "status": "done",
                "progress": 100,
                "result_path": result_path,
                "result_url": public_url(result_path),
                "record_id": record.id,
                "target_count": len(boxes),
                "top_class": record.top_class,
                "class_count": len(classes),
                "classes": classes,
                "cost_ms": cost_ms,
            }
        )
    except Exception as e:
        video_tasks[task_id]["status"] = "error"
        video_tasks[task_id]["error"] = str(e)
    finally:
        db.close()


@router.post("/video")
def detect_video(
    file: UploadFile = File(...),
    conf: float = Form(settings.DEFAULT_CONF),
):
    """上传视频进行病虫害识别，立即返回任务ID，前端轮询进度。"""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".mp4", ".avi", ".mov", ".mkv", ".wmv"):
        return fail("请上传 mp4/avi/mov/mkv 视频")
    relative, _ = save_upload(file, "videos")
    task_id = uuid.uuid4().hex
    video_tasks[task_id] = {"status": "pending", "progress": 0, "error": None}
    threading.Thread(
        target=_run_video_task,
        args=(task_id, relative, file.filename or "", conf),
        daemon=True,
    ).start()
    return success({"task_id": task_id}, "视频识别任务已提交")


@router.get("/video/progress")
def video_progress(task_id: str = Query(...)):
    """查询视频识别进度。"""
    info = video_tasks.get(task_id)
    if not info:
        return fail("任务不存在")
    return success(info)

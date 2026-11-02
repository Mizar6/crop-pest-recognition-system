"""AI 问答接口：图片（可选）+ 文字 -> 意图判断 -> 检测 -> 检索 -> 流式回答。

流程：
  1. 意图判断（一次轻量调用）：闲聊/无关 -> 直接答；病害诊断 -> 检索
  2. 有图则先跑 YOLO，病害名参与检索加权
  3. 检索得分低于阈值、或问题涉及时效信息 -> 开启联网搜索兜底
"""
import json
from pathlib import Path
from typing import Optional

from fastapi import Body, APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, get_db, get_db
from app.models.chat import ChatMessage
from app.service.asr import transcribe
from app.service.disease_map import resolve as resolve_disease, resolve_name
from app.service.model_service import active_meta
from app.service.file_service import abs_path, save_upload
from app.service.tools import TOOL_SCHEMAS, run_tool
from app.service.sse import (EVENT_DONE, EVENT_ERROR, EVENT_META, EVENT_TOKEN, EVENT_TOOL, SSE_HEADERS, frame)
from app.service.qa import astream_answer
from app.service.qa import build_messages, classify_intent, stream_answer
from app.service import kg as kg_service
from app.service.rag import build_context, retrieve
from app.service.severity import estimate as estimate_severity
from app.service.yolo_service import load_model, predict_image
from app.utils.response import fail, success

MAX_TOOL_ROUNDS = 3

router = APIRouter(prefix="/api/chat", tags=["AI问答"])

# 中文类别名 -> UC IPM 的作物目录名
CROP_MAP = {
    "番茄": "tomato",
    "玉米": "corn",
    "马铃薯": "potato",
    "苹果": "apple",
    "葡萄": "grape",
    "草莓": "strawberry",
    "树莓": "caneberries",
    "蓝莓": "blueberry",
    "樱桃": "cherry",
    "桃": "peach",
    "甜椒": "peppers",
    "南瓜": "cucurbits",
}

# 中文病害名 -> 资料库英文标题关键词（用于精确加权）
DISEASE_HINT = {
    "锈病": "rust",
    "晚疫": "late-blight",
    "早疫": "early-blight",
    "灰斑": "gray-leaf-spot",
    "大斑": "northern-leaf-blight",
    "白粉": "powdery-mildew",
    "黑星": "scab",
    "叶斑": "leaf-spot",
    "黑腐": "black-rot",
    "褐斑": "septoria",
    "细菌性斑点": "bacterial-spot",
    "斑点": "bacterial-spot",
    "花叶病毒": "mosaic",
    "黄化": "yellow-leaf-curl",
    "叶霉": "leaf-mold",
    "二斑叶螨": "spider-mite",
    "螨": "mite",
    "白霉": "white-mold",
}


def _guess_crop(class_name: str) -> Optional[str]:
    for zh, en in CROP_MAP.items():
        if zh in class_name:
            return en
    return None


def _guess_disease(class_name: str) -> Optional[str]:
    for zh, en in DISEASE_HINT.items():
        if zh in class_name:
            return en
    return None


def _history(db: Session, session_id: str, limit: int) -> list[dict]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    return [{"role": r.role, "content": r.content} for r in reversed(rows)]


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/ask")
async def ask(
    message: str = Form(""),
    session_id: str = Form("default"),
    conf: float = Form(0.25),
    file: Optional[UploadFile] = File(None),
):
    """提问：可带图片。返回 SSE 流（intent / detection / sources / token / done）。"""
    detection = None
    question = (message or "").strip()

    # ---- 1. 有图先检测 ----
    if file is not None and file.filename:
        suffix = Path(file.filename).suffix.lower()
        if suffix not in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
            return fail("图片格式不支持")
        relative, _ = save_upload(file, "images")
        try:
            model = load_model()
            boxes, _result, _cost = predict_image(
                model, str(abs_path(relative)), conf=conf, imgsz=settings.DEFAULT_IMGSZ
            )
        except Exception as e:
            return fail(f"识别失败：{e}")
        if boxes:
            top = max(boxes, key=lambda b: b["confidence"])
            _db = SessionLocal()
            _name_zh = None
            try:
                # 新表优先：按 (模型, 类别号) 查，跟名字无关
                try:
                    _mid = active_meta().get("id")
                except Exception:
                    _mid = None
                _res = resolve_name(_db, _mid, top["class_id"], top["class_name"])
                _name_zh = _res.get("name_zh")
                level = (_res.get("knowledge") or {}).get("level")
                if level is None:
                    try:
                        row = resolve_disease(_db, top["class_id"], top["class_name"])
                        level = row.level if row else None
                    except Exception:
                        level = None
            finally:
                _db.close()
            LEVEL_ALIAS = {"轻": "低", "重": "高", "中": "中", "低": "低", "高": "高"}
            if level:
                level = LEVEL_ALIAS.get(str(level).strip(), level)
            sev = estimate_severity(abs_path(relative), boxes, level)
            detection = {
                "class_name": _name_zh or top["class_name"],
                "confidence": round(top["confidence"], 4),
                "class_id": top["class_id"],
                "severity": sev["severity"],
                "risk": sev["risk"],
                "ratio": sev["ratio"],
            }
        else:
            detection = {"class_name": None, "confidence": 0, "note": "未检出病害"}

    # ---- 2. 意图判断（有图时默认就是诊断） ----
    intent = {"intent": "diagnosis", "crop": "", "symptom": "", "time_sensitive": False}
    if question:
        intent = classify_intent(question, detection)

    # ---- 3. 组装检索语句 ----
    parts = []
    if detection and detection.get("class_name"):
        parts.append(detection["class_name"])
    if intent.get("symptom"):
        parts.append(str(intent["symptom"]))
    if question:
        parts.append(question)
    query = " ".join(parts) or "农作物叶片病害防治"

    crop = _guess_crop(detection["class_name"]) if detection and detection.get("class_name") else None
    # 没图时用意图判断里抽到的作物名
    if not crop and intent.get("crop"):
        crop = _guess_crop(str(intent["crop"]))
    hint = _guess_disease(detection["class_name"]) if detection and detection.get("class_name") else None
    if not hint and intent.get("symptom"):
        hint = _guess_disease(str(intent["symptom"]))

    # ---- 4. 决定是否检索 / 联网 ----
    hits: list[dict] = []
    use_search = False
    if intent["intent"] == "diagnosis":
        hits = retrieve(query, crop=crop, title_hint=hint)
    # 图谱：用检测出的病害名 + 用户问题去图里找一跳关系
    _db2 = SessionLocal()
    try:
        kg_text, kg_hits = kg_service.graph_context(_db2, f"{query}")
    finally:
        _db2.close()
        top_score = hits[0]["score"] if hits else 0.0
        # 图谱里有事实时，不因为向量偏低就联网
        use_search = bool(intent.get("time_sensitive")) or (
            top_score < settings.RAG_SEARCH_THRESHOLD and not kg_hits
        )
    context = build_context(hits) if hits else ""

    # ---- 5. 落库（用户消息） ----
    db = SessionLocal()
    try:
        history = _history(db, session_id, settings.RAG_HISTORY_LIMIT)
        db.add(ChatMessage(session_id=session_id, role="user", content=question or query))
        # 首条消息顺手把会话标题定下来
        _touch_session(db, session_id, title=(question or query)[:40])
        db.commit()
    finally:
        db.close()

    messages = build_messages(question or query, detection, context, history, use_search, kg_text)

    async def event_stream():
        seq = 0

        def send(event: str, data: dict) -> str:
            nonlocal seq
            seq += 1
            return frame(event, data, seq)

        yield send(EVENT_META, {"session_id": session_id, "use_search": use_search, "intent": intent})
        if detection:
            yield send("detection", detection)

        msgs = list(messages)
        answer_parts: list[str] = []
        try:
            # 工具循环：最多 3 轮，超过就强制收尾（不再给 tools）
            for round_no in range(MAX_TOOL_ROUNDS):
                calls = None
                round_text: list[str] = []
                async for ev in astream_answer(
                    msgs,
                    tools=TOOL_SCHEMAS if round_no < MAX_TOOL_ROUNDS else None,
                    use_search=use_search and round_no == 0,
                ):
                    if ev["type"] == "token":
                        round_text.append(ev["text"])
                        yield send(EVENT_TOKEN, {"text": ev["text"]})
                    elif ev["type"] == "tool_calls":
                        calls = ev["calls"]
                    elif ev["type"] == "error":
                        yield send(EVENT_ERROR, {"text": ev["text"]})
                        return

                if not calls:
                    answer_parts.extend(round_text)
                    break

                # 把模型的工具调用意图记下来，再逐个执行
                msgs.append({
                    "role": "assistant",
                    "content": "".join(round_text) or "",
                    "tool_calls": calls,
                })
                for call in calls:
                    name = (call.get("function") or {}).get("name", "")
                    raw_args = (call.get("function") or {}).get("arguments") or "{}"
                    yield send(EVENT_TOOL, {"name": name, "status": "running"})
                    try:
                        args = json.loads(raw_args) if raw_args.strip() else {}
                    except json.JSONDecodeError:
                        args = {}
                    result = await run_tool(name, args)
                    yield send(EVENT_TOOL, {"name": name, "status": "done"})
                    msgs.append({
                        "role": "tool",
                        "tool_call_id": call.get("id") or name,
                        "content": result,
                    })

            answer = "".join(answer_parts)
            if answer:
                s = SessionLocal()
                try:
                    s.add(ChatMessage(session_id=session_id, role="assistant", content=answer))
                    _touch_session(s, session_id)
                    s.commit()
                finally:
                    s.close()
            yield send(EVENT_DONE, {"session_id": session_id, "chars": len(answer)})
        except Exception as exc:  # 兜底：任何异常都要让前端知道
            yield send(EVENT_ERROR, {"text": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream; charset=utf-8",
        headers=SSE_HEADERS,
    )


@router.post("/asr")
async def asr(
    audio: UploadFile = File(...),
):
    """语音转文字：前端上传 WAV（16k 单声道），返回识别文本。"""
    if not settings.DASHSCOPE_API_KEY:
        return fail("未配置语音识别服务")
    data = await audio.read()
    if not data:
        return fail("音频为空")
    if len(data) > 10 * 1024 * 1024:
        return fail("音频过大（上限 10MB）")
    text = transcribe(data, Path(audio.filename or "a.webm").suffix)
    if not text:
        return fail("没听清，请再说一次")
    return success({"text": text})


@router.get("/history")
def history(session_id: str = Query("default"), db: Session = Depends(get_db)):
    """取某个会话的历史消息（用于前端刷新后恢复）。"""
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.asc())
        .limit(200)
        .all()
    )
    return success([{"role": r.role, "content": r.content, "time": r.created_at} for r in rows])


@router.delete("/session/{session_id}")
def clear_session(session_id: str, db: Session = Depends(get_db)):
    """清空会话（新建对话）。"""
    n = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.commit()
    return success({"deleted": n}, "会话已清空")




# ---------------- 会话管理 ----------------

def _touch_session(db, session_id: str, title: str = "") -> None:
    """有消息就更新会话的活跃时间；标题为空时用首条问题生成。"""
    from datetime import datetime as _dt

    from app.models.chat import ChatSession

    row = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if row is None:
        row = ChatSession(id=session_id, title=(title or "新对话")[:40], created_at=_dt.now())
        db.add(row)
    if title and (not row.title or row.title in ("新对话", "")):
        row.title = title[:40]
    row.updated_at = _dt.now()
    row.message_count = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count()


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db)):
    """会话列表，按活跃时间倒序。"""
    from app.models.chat import ChatSession

    rows = db.query(ChatSession).order_by(ChatSession.updated_at.desc()).all()
    items = [{
        "id": r.id,
        "title": r.title or "新对话",
        "message_count": r.message_count or 0,
        "updated_at": r.updated_at.strftime("%Y-%m-%d %H:%M") if r.updated_at else "",
    } for r in rows]
    known = {i["id"] for i in items}
    for (sid,) in db.query(ChatMessage.session_id).distinct().all():
        if sid not in known:
            items.append({"id": sid, "title": "历史会话", "message_count": 0, "updated_at": ""})
    return success({"items": items})


@router.post("/sessions")
def create_session(payload: dict = Body(default={})):
    """新建会话。"""
    import uuid as _uuid
    from datetime import datetime as _dt

    from app.models.chat import ChatSession

    db = SessionLocal()
    try:
        sid = payload.get("id") or _uuid.uuid4().hex[:16]
        title = (payload.get("title") or "新对话")[:40]
        if db.query(ChatSession).filter(ChatSession.id == sid).first() is None:
            db.add(ChatSession(id=sid, title=title, created_at=_dt.now(), updated_at=_dt.now()))
            db.commit()
        return success({"id": sid, "title": title})
    finally:
        db.close()


@router.patch("/sessions/{session_id}")
def rename_session(session_id: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    from app.models.chat import ChatSession

    row = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if row is None:
        return fail("会话不存在")
    title = (payload.get("title") or "").strip()
    if not title:
        return fail("标题不能为空")
    row.title = title[:40]
    db.commit()
    return success({"id": session_id, "title": row.title})


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    """删除会话及其全部消息（不留残留）。"""
    from app.models.chat import ChatSession

    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.query(ChatSession).filter(ChatSession.id == session_id).delete()
    db.commit()
    return success({"removed": session_id})
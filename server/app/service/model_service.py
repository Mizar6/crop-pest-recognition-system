"""模型注册与热切换。

把「用哪个权重」从写死的配置改成可切换的注册表：
- 权重文件放在 server/data/models/*.pt
- 元数据写 data/models.json
- 切换时重载单例，并同步类别映射
"""
import json
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Optional

from ultralytics import YOLO

from app.core.config import settings

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "models"

SERVER_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_path(p) -> Path:
    """路径解析：绝对路径直接用；相对路径按 server 根目录拼（方便整体拷贝到别的电脑）。"""
    path = Path(p)
    if path.is_absolute():
        return path
    return (SERVER_ROOT / path).resolve()

META_FILE = MODELS_DIR / "models.json"

_lock = threading.Lock()
_model_cache: Optional[Any] = None
_current_id: Optional[str] = None


def _ensure() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if not META_FILE.exists():
        META_FILE.write_text(
            json.dumps({"models": [], "active": None}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _read() -> dict:
    _ensure()
    return json.loads(META_FILE.read_text(encoding="utf-8-sig"))


def _write(data: dict) -> None:
    _ensure()
    META_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _models() -> list[dict]:
    """注册表内容；首次运行时自动收录 config 里的默认权重。"""
    data = _read()
    if not data["models"]:
        default = settings.model_abs_path
        if default.exists():
            data["models"].append({
                "id": "default",
                "name": settings.MODEL_NAME,
                "file": default.name,
                "path": str(default),
                "class_num": 30,
                "size_mb": round(default.stat().st_size / 1024 / 1024, 1),
                "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "note": "系统自带权重",
            })
            data["active"] = "default"
            _write(data)
    return data["models"]


def list_models() -> dict:
    data = _read()
    models = _models()
    return {
        "active": data.get("active"),
        "models": [{**m, "active": m["id"] == data.get("active")} for m in models],
    }


def _probe(path: Path) -> dict:
    """尝试加载权重，读出类别数与名称，失败抛异常。"""
    model = YOLO(str(path))
    names = model.names
    class_num = len(names)
    sample = [names[i] for i in sorted(names)[:6]]
    return {"class_num": class_num, "class_names": sample}


def add_model(file_name: str, content: bytes, name: str = "") -> dict:
    """保存权重并注册。非法权重会被拒绝且不留垃圾文件。"""
    _ensure()
    model_id = f"m{int(time.time())}"
    suffix = Path(file_name).suffix.lower()
    if suffix != ".pt":
        raise ValueError("只接受 .pt 权重文件")

    target = MODELS_DIR / f"{model_id}{suffix}"
    target.write_bytes(content)

    try:
        info = _probe(target)
    except Exception as exc:  # 加载失败：删掉文件，不污染注册表
        target.unlink(missing_ok=True)
        raise ValueError(f"权重无法加载：{exc}") from exc

    data = _read()
    entry = {
        "id": model_id,
        "name": name or Path(file_name).stem,
        "file": file_name,
        "path": str(target),
        "class_num": info["class_num"],
        "class_sample": info["class_names"],
        "size_mb": round(target.stat().st_size / 1024 / 1024, 1),
        "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    data["models"].append(entry)
    if not data.get("active"):
        data["active"] = model_id
    _write(data)

    # 新模型如果是英文类名，顺手翻译成中文（失败不影响注册）
    try:
        result = translate_class_names(model_id)
        entry["translated"] = result.get("translated", 0)
    except Exception:
        entry["translated"] = 0
    return entry


def _save_zh_to_db(model_id: str, names: dict, zh_map: dict) -> int:
    """把译名写进 t_model_class（每类一行），返回写入行数。"""
    from app.db.session import SessionLocal
    from sqlalchemy import text

    rows = 0
    db = SessionLocal()
    try:
        for cid, raw in names.items():
            zh = zh_map.get(int(cid)) or raw
            db.execute(
                text(
                    "INSERT INTO t_model_class (model_id, class_id, name_raw, name_zh) "
                    "VALUES (:m, :c, :raw, :zh) "
                    "ON DUPLICATE KEY UPDATE name_raw = VALUES(name_raw), name_zh = VALUES(name_zh)"
                ),
                {"m": model_id, "c": int(cid), "raw": str(raw), "zh": zh},
            )
            rows += 1
        db.commit()
    finally:
        db.close()
    return rows


def class_name_from_db(model_id: str, class_id: int) -> str:
    """从 t_model_class 取中文名（没有返回空串）。"""
    from app.db.session import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT name_zh FROM t_model_class WHERE model_id = :m AND class_id = :c"),
            {"m": model_id, "c": int(class_id)},
        ).first()
        return row[0] if row and row[0] else ""
    except Exception:
        return ""
    finally:
        db.close()


def class_names_zh(model_id: str | None = None) -> dict:
    """返回 {class_id: 中文名}；没有译名时返回空字典。"""
    data = _read()
    mid = model_id or data.get("active")
    entry = next((m for m in data["models"] if m["id"] == mid), None)
    if not entry:
        return {}
    raw = entry.get("class_names_zh") or {}
    return {int(k): v for k, v in raw.items()}


def class_name_of(class_id, model_id: str | None = None, fallback: str = "") -> str:
    """取某个类别的中文名：先查数据库对照表，没有再查 models.json。"""
    if class_id is None:
        return fallback
    data = _read()
    mid = model_id or data.get("active")
    if mid:
        zh = class_name_from_db(mid, int(class_id))
        if zh:
            return zh
    return class_names_zh(model_id).get(int(class_id), fallback)


def translate_class_names(model_id: str) -> dict:
    """调用大模型把该模型的英文类名批量翻译成中文，写回 models.json。

    - 类名已经是中文的会跳过
    - 失败不影响模型使用（返回 {"translated": 0, "error": "..."}）
    """
    import json as _json
    import os as _os

    import requests as _requests

    data = _read()
    entry = next((m for m in data["models"] if m["id"] == model_id), None)
    if not entry:
        raise ValueError("模型不存在")

    model = YOLO(str(entry["path"]))
    names = {int(k): str(v) for k, v in model.names.items()}
    need = {k: v for k, v in names.items() if not any("\u4e00" <= ch <= "\u9fff" for ch in v)}
    if not need:
        return {"translated": 0, "note": "类名已经是中文"}

    key = _os.getenv("DASHSCOPE_API_KEY", "")
    base = _os.getenv("RAG_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
    if not key:
        return {"translated": 0, "error": "没有 DASHSCOPE_API_KEY"}

    pairs = sorted(need.items())
    zh_map = {}
    for i in range(0, len(pairs), 40):
        batch = pairs[i:i + 40]
        items = [{"id": cid, "en": n.replace("_", " ")} for cid, n in batch]
        prompt = (
            "把这些农业害虫/病害的英文名翻译成简短中文通用名，只输出 JSON 数组，"
            "元素为 {\"id\": 编号, \"zh\": \"中文名\"}。\n" + _json.dumps(items, ensure_ascii=False)
        )
        resp = _requests.post(
            base + "/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": _os.getenv("RAG_QA_MODEL", "qwen-plus"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            },
            timeout=120,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        s, e = text.find("["), text.rfind("]")
        if s >= 0 and e > s:
            for d in _json.loads(text[s:e + 1]):
                if d.get("zh"):
                    zh_map[int(d["id"])] = str(d["zh"]).strip()

    if not zh_map:
        return {"translated": 0, "error": "翻译结果为空"}

    saved = _save_zh_to_db(model_id, names, zh_map)
    entry["class_names_zh"] = {str(k): v for k, v in zh_map.items()}
    _write(data)
    return {"translated": len(zh_map), "db_rows": saved}


def remove_model(model_id: str) -> None:
    data = _read()
    entry = next((m for m in data["models"] if m["id"] == model_id), None)
    if not entry:
        raise ValueError("模型不存在")
    if data.get("active") == model_id:
        raise ValueError("正在使用的模型不能删除，请先切换到其他模型")
    Path(entry["path"]).unlink(missing_ok=True)
    data["models"] = [m for m in data["models"] if m["id"] != model_id]
    _write(data)


def can_activate(entry: dict) -> tuple[bool, str]:
    """判断这个模型能不能上线（mAP50 阈值门控）。

    只对"训练产生的模型"生效：人工上传的模型没有 map50，视为不受门控。
    """
    if entry.get("source") != "train":
        return True, ""
    map50 = entry.get("map50")
    threshold = entry.get("threshold")
    if map50 is None:
        return False, "该模型没有 mAP50 指标（训练结果缺失），不能上线"
    if threshold is None:
        threshold = 0.5
    if float(map50) < float(threshold):
        return False, f"该模型 mAP50 {float(map50):.3f} 未达阈值 {float(threshold):.2f}，不能上线"
    return True, ""


def set_threshold(model_id: str, threshold: float) -> dict:
    """调整阈值并重新判定是否达标。"""
    _ensure()
    data = _read()
    for item in data["models"]:
        if item["id"] == model_id:
            item["threshold"] = float(threshold)
            map50 = item.get("map50")
            item["passed"] = 1 if (map50 is not None and float(map50) >= float(threshold)) else 0
            item["threshold_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _write(data)
            return item
    raise ValueError("模型不存在")


def activate(model_id: str) -> dict:
    """切换当前模型：写注册表 + 清缓存，下次推理自动加载新权重。"""
    global _model_cache, _current_id
    data = _read()
    entry = next((m for m in data["models"] if m["id"] == model_id), None)
    if not entry:
        raise ValueError("模型不存在")
    ok, reason = can_activate(entry)
    if not ok:
        raise PermissionError(reason)
    if not _resolve_path(entry["path"]).exists():
        raise ValueError("权重文件丢失")

    data["active"] = model_id
    _write(data)

    with _lock:
        _model_cache = None
        _current_id = None
    return entry


def active_model() -> Any:
    """返回当前激活的模型实例（懒加载 + 缓存）。"""
    global _model_cache, _current_id
    with _lock:
        data = _read()
        active_id = data.get("active")
        entry = next((m for m in data["models"] if m["id"] == active_id), None)
        path = _resolve_path(entry["path"]) if entry else settings.model_abs_path

        if _model_cache is None or _current_id != str(path):
            _model_cache = YOLO(str(path))
            _current_id = str(path)
        return _model_cache


def active_meta() -> dict:
    data = _read()
    entry = next((m for m in data["models"] if m["id"] == data.get("active")), None)
    if not entry:
        return {"id": None, "name": settings.MODEL_NAME, "class_num": 0}
    return entry

def update_entry(model_id: str, patch: dict) -> dict:
    """更新 registry 里某个模型的元数据（训练指标、阈值、是否达标）。"""
    _ensure()
    data = _read()
    for item in data["models"]:
        if item["id"] == model_id:
            item.update({k: v for k, v in (patch or {}).items() if k != "id"})
            _write(data)
            return item
    raise ValueError("模型不存在")
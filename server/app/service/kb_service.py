"""知识库入驻：上传文档 → 解析 → 切分 → 向量化 → 追加进现有向量库。

设计要点：
- 复用 rag.py 的向量库文件，追加而非重建，检索侧无需改动
- 切块 700 字 + 120 字重叠，按段落边界切，避免一句被劈开
- 每块 embedding 失败会单独重试一次，失败只丢该块并计数
"""
import hashlib
import json
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Iterable

import numpy as np
import requests

from app.core.config import settings

_lock = threading.Lock()
DOCS_FILE_NAME = "documents.json"
CHUNK_SIZE = 700
CHUNK_OVERLAP = 120
BATCH = 4
MAX_LEN = 800


# ---------- 解析 ----------
def parse_text(filename: str, content: bytes) -> str:
    """把上传文件转成纯文本。支持 txt / md / pdf / docx。"""
    suffix = Path(filename).suffix.lower()
    if suffix in (".txt", ".md", ".csv"):
        for enc in ("utf-8", "gbk", "utf-16"):
            try:
                return content.decode(enc)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="ignore")

    if suffix == ".pdf":
        try:
            import io

            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            return "\n\n".join((p.extract_text() or "") for p in reader.pages)
        except ImportError as exc:
            raise ValueError("缺少 pypdf 依赖，无法解析 PDF") from exc

    if suffix in (".docx", ".doc"):
        try:
            import io

            from docx import Document

            doc = Document(io.BytesIO(content))
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError as exc:
            raise ValueError("缺少 python-docx 依赖，无法解析 Word") from exc

    raise ValueError(f"不支持的文件类型：{suffix}")


# ---------- 切分 ----------
def split_chunks(text: str) -> list[str]:
    """按段落聚合到 CHUNK_SIZE，带重叠，尽量不在句子中间切。"""
    text = text.lstrip("\ufeff")
    text = re.sub(r"\r\n?", "\n", text).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    if not paras:
        return []

    chunks: list[str] = []
    buf = ""
    for para in paras:
        if len(buf) + len(para) + 1 <= CHUNK_SIZE:
            buf = f"{buf}\n{para}".strip()
            continue
        if buf:
            chunks.append(buf)
            buf = buf[-CHUNK_OVERLAP:] + "\n" + para
        else:
            # 单段就超长：硬切
            for i in range(0, len(para), CHUNK_SIZE - CHUNK_OVERLAP):
                chunks.append(para[i : i + CHUNK_SIZE])
            buf = ""
        while len(buf) > CHUNK_SIZE:
            chunks.append(buf[:CHUNK_SIZE])
            buf = buf[CHUNK_SIZE - CHUNK_OVERLAP :]
    if buf.strip():
        chunks.append(buf.strip())
    return [c for c in chunks if len(c) >= 40]


# ---------- 向量 ----------
def embed_batch(texts: list[str]) -> list[np.ndarray]:
    """批量 embedding；单条失败降级重试，仍失败则返回零向量占位。"""
    out: list[np.ndarray] = []
    for i in range(0, len(texts), BATCH):
        group = [t[:MAX_LEN] for t in texts[i : i + BATCH]]
        vectors = _embed_group(group)
        out.extend(vectors)
    return out


def _embed_group(group: list[str]) -> list[np.ndarray]:
    try:
        return _post_embed(group)
    except Exception:
        result = []
        for text in group:
            try:
                result.extend(_post_embed([text]))
            except Exception:
                result.append(np.zeros(1024, dtype=np.float32))
        return result


def _post_embed(group: list[str]) -> list[np.ndarray]:
    r = requests.post(
        f"{settings.RAG_BASE_URL}/embeddings",
        headers={
            "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": settings.RAG_EMBEDDING_MODEL, "input": group, "dimensions": 1024},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()["data"]
    vectors = []
    for item in data:
        v = np.array(item["embedding"], dtype=np.float32)
        norm = np.linalg.norm(v)
        vectors.append(v / norm if norm else v)
    return vectors


# ---------- 入库 ----------
def _vstore() -> Path:
    return settings.vstore_path


def _docs_file() -> Path:
    return _vstore() / DOCS_FILE_NAME


def list_documents() -> list[dict]:
    f = _docs_file()
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8"))


def _save_documents(docs: list[dict]) -> None:
    _docs_file().write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")


# 内置语料（UC IPM 抓取）的作物英文名 -> 中文
_CROP_ZH = {
    "apple": "苹果", "tomato": "番茄", "potato": "马铃薯", "grape": "葡萄",
    "strawberry": "草莓", "caneberries": "树莓", "blueberry": "蓝莓",
    "cherry": "樱桃", "peach": "桃", "peppers": "甜椒", "cucurbits": "瓜类",
    "corn": "玉米", "rice": "水稻",
}


def builtin_documents() -> list[dict]:
    """把内置语料（chunks 里没有 source 的那批）按 url 聚合成分档条目。

    这些是随项目一起构建的 UC IPM 资料，不在 documents.json 里，
    但用户看知识库时应该能看到它们。
    """
    chunks_file = _vstore() / "chunks_zh.json"
    if not chunks_file.exists():
        return []
    try:
        chunks = json.loads(chunks_file.read_text(encoding="utf-8"))
    except Exception:
        return []

    groups: dict[str, dict] = {}
    for c in chunks:
        if c.get("source"):
            continue  # 上传的文档已在 documents.json 里
        url = c.get("url") or c.get("title") or "unknown"
        g = groups.get(url)
        if g is None:
            g = groups[url] = {
                "id": "builtin:" + str(c.get("title") or url),
                "title": str(c.get("title") or url),
                "file": url,
                "url": c.get("url") or "",
                "crop": _CROP_ZH.get(str(c.get("crop") or ""), str(c.get("crop") or "内置")),
                "chars": 0,
                "chunk_count": 0,
                "added_at": "内置资料",
                "builtin": True,
            }
        g["chunk_count"] += 1
        g["chars"] += len(c.get("text") or "")
        # 同一 url 下可能有 "Comments" 这类小节标题，优先用更具体的主标题
        t = str(c.get("title") or "")
        if t and t.lower() not in ("comments", "unknown") and g["title"].lower() in ("comments", "unknown"):
            g["title"] = t

    out = list(groups.values())
    out.sort(key=lambda d: (d["crop"], d["title"]))
    return out


def all_documents() -> list[dict]:
    """上传文档（新→旧）+ 内置语料，供知识库列表展示。"""
    return list(reversed(list_documents())) + builtin_documents()


def stats() -> dict:
    """向量库现状：总块数 + 上传文档数 + 内置资料数。"""
    chunks_file = _vstore() / "chunks_zh.json"
    total = 0
    if chunks_file.exists():
        total = len(json.loads(chunks_file.read_text(encoding="utf-8")))
    docs = list_documents()
    builtin = builtin_documents()
    return {
        "chunks": total,
        "documents": len(docs),
        "builtin": len(builtin),
        "builtin_chunks": sum(d["chunk_count"] for d in builtin),
        "from_upload": sum(d.get("chunk_count", 0) for d in docs),
    }


def ingest(filename: str, content: bytes, crop: str = "", title: str = "") -> dict:
    """完整导入链路，返回本次结果。"""
    if not settings.DASHSCOPE_API_KEY:
        raise ValueError("未配置 DASHSCOPE_API_KEY，无法向量化")

    # 内容 hash 去重：同一个文件重复上传直接复用，不重复付 embedding 费用
    digest = hashlib.sha256(content).hexdigest()[:16]
    for d in list_documents():
        if d.get("hash") == digest:
            return {
                "doc_id": d["id"],
                "chunks_added": 0,
                "chunks_failed": 0,
                "total_chunks": stats()["chunks"],
                "title": d["title"],
                "duplicated": True,
            }

    text = parse_text(filename, content)
    if len(text) < 60:
        raise ValueError("解析出的正文太短，可能是扫描件或空文件")

    pieces = split_chunks(text)
    if not pieces:
        raise ValueError("切分后没有有效片段")

    with _lock:
        base = _vstore()
        chunks_file = base / "chunks_zh.json"
        vectors_file = base / "vectors_zh.npy"

        chunks = json.loads(chunks_file.read_text(encoding="utf-8")) if chunks_file.exists() else []
        matrix = np.load(vectors_file).astype(np.float32) if vectors_file.exists() else np.zeros((0, 1024), np.float32)

        doc_id = f"doc{int(time.time())}_{uuid.uuid4().hex[:4]}"
        doc_title = title or Path(filename).stem
        new_chunks = [
            {
                "id": f"{doc_id}-{i}",
                "crop": crop or "自定义",
                "title": doc_title,
                "text": piece,
                "source": filename,
                "url": "",
            }
            for i, piece in enumerate(pieces)
        ]

        vectors = embed_batch([c["text"] for c in new_chunks])
        valid = [i for i, v in enumerate(vectors) if np.any(v)]
        new_chunks = [new_chunks[i] for i in valid]
        new_matrix = np.stack([vectors[i] for i in valid]) if valid else np.zeros((0, 1024), np.float32)

        if len(chunks) == 0:
            merged_matrix = new_matrix
        else:
            merged_matrix = np.vstack([matrix, new_matrix])

        chunks.extend(new_chunks)
        chunks_file.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
        np.save(vectors_file, merged_matrix)

        docs = list_documents()
        docs.append(
            {
                "id": doc_id,
                "title": doc_title,
                "file": filename,
                "crop": crop or "自定义",
                "chars": len(text),
                "chunk_count": len(new_chunks),
                "failed": len(pieces) - len(new_chunks),
                "hash": digest,
                "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        _save_documents(docs)

        # 让 rag 下次检索重新读盘
        from app.service import rag

        rag._chunks = None
        rag._matrix = None

    return {
        "doc_id": doc_id,
        "chunks_added": len(new_chunks),
        "chunks_failed": len(pieces) - len(new_chunks),
        "total_chunks": len(chunks),
        "title": doc_title,
    }


def remove_document(doc_id: str) -> dict:
    """按文档删除其所有块，并重建向量矩阵。"""
    if str(doc_id).startswith("builtin:"):
        raise ValueError("内置资料随项目发布，不能删除")
    with _lock:
        base = _vstore()
        chunks_file = base / "chunks_zh.json"
        vectors_file = base / "vectors_zh.npy"

        chunks = json.loads(chunks_file.read_text(encoding="utf-8"))
        matrix = np.load(vectors_file).astype(np.float32)
        keep = [i for i, c in enumerate(chunks) if not str(c.get("id", "")).startswith(doc_id)]
        if len(keep) == len(chunks):
            raise ValueError("未找到该文档的片段")

        new_chunks = [chunks[i] for i in keep]
        new_matrix = matrix[keep] if keep else np.zeros((0, 1024), np.float32)
        chunks_file.write_text(json.dumps(new_chunks, ensure_ascii=False), encoding="utf-8")
        np.save(vectors_file, new_matrix)

        docs = [d for d in list_documents() if d["id"] != doc_id]
        _save_documents(docs)

        from app.service import rag

        rag._chunks = None
        rag._matrix = None

        return {"removed": doc_id, "chunks_left": len(new_chunks)}
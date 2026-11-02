"""向量检索：加载本地向量库，按余弦相似度召回相关农技资料。

索引由离线脚本生成（chunks_zh.json + vectors_zh.npy），这里只做查询。
"""
import json
import threading
from typing import Optional

import numpy as np
import requests

from app.core.config import settings

_lock = threading.Lock()
_chunks: Optional[list] = None
_matrix: Optional[np.ndarray] = None


def _load() -> tuple[list, np.ndarray]:
    """懒加载索引（首次调用时读盘，之后常驻内存）。"""
    global _chunks, _matrix
    with _lock:
        if _chunks is None or _matrix is None:
            base = settings.vstore_path
            _chunks = json.loads((base / "chunks_zh.json").read_text(encoding="utf-8"))
            m = np.load(base / "vectors_zh.npy").astype(np.float32)
            m = m / np.linalg.norm(m, axis=1, keepdims=True)
            _matrix = m
        return _chunks, _matrix


def _embed(text: str) -> np.ndarray:
    """把查询文本变成 1024 维向量。"""
    r = requests.post(
        f"{settings.RAG_BASE_URL}/embeddings",
        headers={
            "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.RAG_EMBEDDING_MODEL,
            "input": [text[:800]],
            "dimensions": 1024,
        },
        timeout=30,
    )
    r.raise_for_status()
    v = np.array(r.json()["data"][0]["embedding"], dtype=np.float32)
    return v / np.linalg.norm(v)


def retrieve(
    query: str,
    crop: Optional[str] = None,
    top_k: Optional[int] = None,
    title_hint: Optional[str] = None,
) -> list[dict]:
    """检索相关片段。

    Args:
        query: 检索语句（建议带上检测出的病害名，命中率会高很多）
        crop: 作物过滤（tomato / corn / potato ...），None 表示全库
        top_k: 返回条数
        title_hint: 标题关键词（如 rust / late-blight），命中者加权
    """
    if not settings.DASHSCOPE_API_KEY:
        return []
    chunks, matrix = _load()
    k = top_k or settings.RAG_TOP_K
    qv = _embed(query)

    if crop:
        idx = [i for i, c in enumerate(chunks) if c["crop"] == crop]
    else:
        idx = list(range(len(chunks)))
    if not idx:
        return []

    scores = matrix[idx] @ qv
    # 病害名精确命中加权：检测出的病名比语义相似更可信
    if title_hint:
        hint = title_hint.lower()
        for pos, i in enumerate(idx):
            if hint in chunks[i]["title"].lower():
                scores[pos] += 0.15

    order = np.argsort(scores)[::-1][:k]
    return [
        {
            "score": round(float(scores[i]), 4),
            "text": chunks[idx[i]]["text"],
            "title": chunks[idx[i]]["title"],
            "crop": chunks[idx[i]]["crop"],
            "url": chunks[idx[i]].get("url", ""),
        }
        for i in order
    ]


def build_context(hits: list[dict]) -> str:
    """把检索结果拼成给大模型的资料段。"""
    if not hits:
        return ""
    parts = []
    for i, h in enumerate(hits, 1):
        parts.append(f"【资料{i}】（作物：{h['crop']}／主题：{h['title']}）\n{h['text']}")
    return "\n\n---\n\n".join(parts)

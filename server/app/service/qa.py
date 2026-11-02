"""意图判断 + 问答生成。

意图判断：一次轻量调用，决定走不走检索、要不要联网。
生成：检测结果 + 检索资料 + 会话历史 → 流式回答；资料不足时开联网搜索兜底。
"""
import json
import re
from typing import AsyncIterator, Optional

import requests

from app.core.config import settings

SYSTEM_PROMPT = (
    "你是「禾鉴」农业植保助手，服务对象是种植户和农技人员。\n"
    "回答要求：\n"
    "1. 先给结论，再给依据，最后给可执行措施。\n"
    "2. 涉及用药必须说明：适用作物、常见剂型、稀释倍数、安全间隔期、轮换用药提醒。\n"
    "3. 资料里没有的内容，直说「资料里没有」，不要编造；有检测结果时，先把检测结论与资料对齐再说。\n"
    "4. 不要写「来源」「参考链接」「据某网页」这类出处说明，直接把信息讲清楚。\n"
    "5. 中文，短句分点，不用专业黑话；对方是种植户，不是研究员。\n"
    "6. 涉及天气、实时信息、具体网页内容时，先用工具查再回答；查不到就说查不到。"
)

INTENT_PROMPT = (
    "判断用户这句话属于哪类，只输出一个 JSON 对象，不要任何解释或代码块。\n"
    '格式：{"intent":"diagnosis|chat|other","crop":"作物中文名或空","symptom":"症状关键词或空","time_sensitive":true|false}\n'
    "定义：\n"
    "- diagnosis：在问作物病害的症状、原因、防治、用药\n"
    "- chat：打招呼、闲聊、感谢\n"
    "- other：与农业病虫害无关\n"
    "- time_sensitive：问题涉及最新、今年、当前、价格、天气、政策、新闻等时效信息\n"
)


def _chat(messages: list[dict], **extra) -> dict:
    payload = {
        "model": settings.RAG_QA_MODEL,
        "messages": messages,
        "temperature": 0,
        **extra,
    }
    r = requests.post(
        f"{settings.RAG_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def classify_intent(text: str, detection: Optional[dict] = None) -> dict:
    """判断意图。失败时默认按病害诊断处理（宁可多检索一次）。"""
    default = {"intent": "diagnosis", "crop": "", "symptom": "", "time_sensitive": False}
    if not text.strip():
        return default
    try:
        resp = _chat(
            [
                {"role": "system", "content": INTENT_PROMPT},
                {"role": "user", "content": text},
            ]
        )
        raw = resp["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(m.group(0)) if m else {}
        out = {**default, **{k: data.get(k, default[k]) for k in default}}
        if out["intent"] not in ("diagnosis", "chat", "other"):
            out["intent"] = "diagnosis"
        return out
    except Exception:
        return default


def build_messages(
    question: str,
    detection: Optional[dict],
    context: str,
    history: Optional[list[dict]] = None,
    use_search: bool = False,
    kg: str = "",
) -> list[dict]:
    """组装 messages：系统提示 + 历史 + 本轮（检测结果 + 资料 + 问题）。"""
    msgs: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in (history or [])[-settings.RAG_HISTORY_LIMIT:]:
        msgs.append({"role": h["role"], "content": h["content"]})

    blocks = []
    if detection and detection.get("class_name"):
        conf = detection.get("confidence")
        conf_txt = f"，置信度 {conf:.2f}" if isinstance(conf, float) else ""
        line = f"【检测结果】图片识别为：{detection['class_name']}{conf_txt}"
        if detection.get("severity"):
            ratio = detection.get("ratio") or 0
            line += f"；病斑占比 {ratio * 100:.1f}%，严重程度{detection['severity']}"
            if detection.get("risk"):
                line += f"，综合风险{detection['risk']}"
        blocks.append(line)
    if kg:
        blocks.append(f"【图谱关系】以下是从知识图谱中查到的一跳关系，可优先用于判断依据：\n{kg}")
    if context:
        blocks.append(f"【参考资料】\n{context}")
    if use_search:
        blocks.append("【联网搜索】已开启联网搜索，请结合查到的实时信息回答，不要说明信息来源。")
    elif not context:
        blocks.append("【参考资料】知识库中没有相关内容，请基于通用农技知识谨慎回答，并说明依据有限。")
    blocks.append(f"【用户问题】{question}")

    msgs.append({"role": "user", "content": "\n\n".join(blocks)})
    return msgs


def stream_answer(messages: list[dict], use_search: bool = False) -> AsyncIterator[str]:
    """流式生成；use_search=True 时开启联网搜索兜底。"""
    if not settings.DASHSCOPE_API_KEY:
        yield "（未配置 DASHSCOPE_API_KEY，无法生成回答）"
        return

    payload = {
        "model": settings.RAG_QA_MODEL,
        "messages": messages,
        "stream": True,
        "temperature": 0.3,
    }
    if use_search:
        payload["enable_search"] = True
        payload["search_options"] = {"forced_search": True}

    with requests.post(
        f"{settings.RAG_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
        stream=True,
    ) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith(b"data: "):
                continue
            chunk = line[6:].decode("utf-8")
            if chunk == "[DONE]":
                break
            try:
                delta = json.loads(chunk)["choices"][0]["delta"].get("content") or ""
            except (KeyError, IndexError, json.JSONDecodeError):
                continue
            if delta:
                yield delta


async def astream_answer(messages, tools=None, use_search=False, client_factory=None):
    """异步流式生成，产出事件字典：
        {"type": "token", "text": "..."}
        {"type": "tool_calls", "calls": [...]}
        {"type": "done"}

    用 httpx.AsyncClient 而不是 requests —— 同步读取会卡住事件循环，
    多人同时提问时第二个请求要排队等第一个吐完。
    """
    import httpx

    if not settings.DASHSCOPE_API_KEY:
        yield {"type": "error", "text": "未配置 DASHSCOPE_API_KEY"}
        return

    payload = {
        "model": settings.RAG_QA_MODEL,
        "messages": messages,
        "stream": True,
        "temperature": 0.3,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    if use_search:
        payload["enable_search"] = True
        payload["search_options"] = {"forced_search": True}

    headers = {
        "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }
    factory = client_factory or (lambda: httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=5.0)))

    # tool_calls 分片累积：OpenAI 兼容端点会按 index 逐片下发
    calls: dict[int, dict] = {}

    client = factory()
    async with client:
        async with client.stream(
            "POST", f"{settings.RAG_BASE_URL}/chat/completions", json=payload, headers=headers
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                chunk = line[6:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    delta = json.loads(chunk)["choices"][0]["delta"]
                except (KeyError, IndexError, json.JSONDecodeError):
                    continue

                for tc in delta.get("tool_calls") or []:
                    idx = tc.get("index", 0)
                    slot = calls.setdefault(idx, {"id": "", "type": "function",
                                                  "function": {"name": "", "arguments": ""}})
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["function"]["name"] += fn["name"]
                    if fn.get("arguments"):
                        slot["function"]["arguments"] += fn["arguments"]

                text = delta.get("content") or ""
                if text:
                    yield {"type": "token", "text": text}

    if calls:
        yield {"type": "tool_calls", "calls": [calls[k] for k in sorted(calls)]}
    yield {"type": "done"}
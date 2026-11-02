"""SSE（Server-Sent Events）帧封装。

【为什么单独抽出来】
  流式回答的每一段都要拼成 `id/event/data` 三段格式，格式错一个换行
  浏览器就不认。集中在一个文件里，测试也只用测这里。
"""
import json

# 事件名：前端按这些名字分发
EVENT_META = "meta"      # 会话 id、意图
EVENT_TOOL = "tool"      # 正在调用工具（前端显示"正在查询天气…"）
EVENT_TOKEN = "token"    # 增量文本
EVENT_PING = "ping"      # 心跳，防中间层超时断开
EVENT_DONE = "done"      # 结束
EVENT_ERROR = "error"    # 出错

# 必须带这几个头，否则 Nginx / 浏览器会攒够一批才吐
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def frame(event: str, data: dict, seq: int) -> str:
    """把一次事件拼成 SSE 帧。

    data 用 ensure_ascii=False，中文直接出，不用 \\uXXXX。
    """
    payload = json.dumps(data, ensure_ascii=False)
    return f"id: {seq}\nevent: {event}\ndata: {payload}\n\n"

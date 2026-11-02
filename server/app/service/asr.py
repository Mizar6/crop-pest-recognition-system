"""语音转文字：先把任意格式音频转成 16k 单声道 WAV，再调百炼 qwen3-asr-flash。

前端可以直接上传浏览器录的 webm/opus，这里用 ffmpeg 统一转码。
"""
import base64
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests

from app.core.config import settings

ASR_API = (
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
)
ASR_MODEL = "qwen3-asr-flash"


def ffmpeg_path() -> str | None:
    """定位 ffmpeg.exe（winget 装的不会自动进当前进程 PATH）。"""
    found = shutil.which("ffmpeg")
    if found:
        return found
    base = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    if base.exists():
        hit = next(base.rglob("ffmpeg.exe"), None)
        if hit:
            return str(hit)
    return None


def to_wav(data: bytes, suffix: str = ".webm") -> bytes:
    """任意音频字节 -> 16kHz 单声道 WAV 字节。失败原样返回。"""
    exe = ffmpeg_path()
    if not exe:
        return data
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"in{suffix or '.webm'}"
        dst = Path(tmp) / "out.wav"
        src.write_bytes(data)
        try:
            subprocess.run(
                [exe, "-y", "-i", str(src), "-ar", "16000", "-ac", "1", "-f", "wav", str(dst)],
                capture_output=True,
                timeout=60,
                check=True,
            )
            return dst.read_bytes()
        except Exception:
            return data


def transcribe_wav(data: bytes) -> str:
    """把 WAV 音频转成文字，失败返回空串。"""
    if not settings.DASHSCOPE_API_KEY or not data:
        return ""
    b64 = base64.b64encode(data).decode()
    try:
        r = requests.post(
            ASR_API,
            headers={
                "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": ASR_MODEL,
                "input": {
                    "messages": [
                        {"role": "user", "content": [{"audio": f"data:audio/wav;base64,{b64}"}]}
                    ]
                },
            },
            timeout=60,
        )
        r.raise_for_status()
        content = r.json()["output"]["choices"][0]["message"]["content"]
        if isinstance(content, str):
            return content.strip()
        parts = []
        for item in content or []:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
        return "".join(parts).strip()
    except Exception:
        return ""


def transcribe(data: bytes, suffix: str = ".webm") -> str:
    """对外入口：自动转码 + 识别。"""
    return transcribe_wav(to_wav(data, suffix))

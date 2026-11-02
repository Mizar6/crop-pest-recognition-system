"""文件落盘工具，统一写入 D:/uploads45。"""
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

from app.core.config import settings


def ensure_upload_dirs() -> None:
    """启动时创建上传根目录及子目录。"""
    root = Path(settings.UPLOAD_ROOT)
    for name in ("avatar", "models", "images", "videos", "results", "frames"):
        (root / name).mkdir(parents=True, exist_ok=True)


def abs_path(relative: Optional[str]) -> Optional[Path]:
    """相对路径转绝对路径。"""
    if not relative:
        return None
    return Path(settings.UPLOAD_ROOT) / relative.replace("\\", "/")


def save_upload(file: UploadFile, category: str, keep_name: Optional[str] = None) -> tuple[str, int]:
    """
    将上传文件保存到 uploads45/{category}/yyyyMMdd/uuid.ext。

    Args:
        file: FastAPI 上传文件
        category: 子目录，如 images、videos、avatar、models
        keep_name: 可选，强制使用该文件名（不含路径）
    Returns:
        (相对路径, 文件大小字节)
    """
    day = datetime.now().strftime("%Y%m%d")
    suffix = Path(file.filename or "file.bin").suffix.lower()
    filename = keep_name if keep_name else f"{uuid.uuid4().hex}{suffix}"
    rel_dir = f"{category}/{day}"
    dest_dir = Path(settings.UPLOAD_ROOT) / rel_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    size = 0
    with dest.open("wb") as f:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            f.write(chunk)
    relative = f"{rel_dir}/{filename}".replace("\\", "/")
    return relative, size


def save_bytes(data: bytes, category: str, suffix: str = ".jpg") -> str:
    """
    将二进制内容保存到指定分类目录。

    Args:
        data: 文件字节
        category: 子目录
        suffix: 扩展名
    Returns:
        相对路径
    """
    day = datetime.now().strftime("%Y%m%d")
    filename = f"{uuid.uuid4().hex}{suffix}"
    rel_dir = f"{category}/{day}"
    dest_dir = Path(settings.UPLOAD_ROOT) / rel_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(data)
    return f"{rel_dir}/{filename}".replace("\\", "/")


def public_url(relative: Optional[str]) -> Optional[str]:
    """拼接前端可访问的 /uploads 路径。"""
    if not relative:
        return None
    return "/uploads/" + relative.replace("\\", "/").lstrip("/")

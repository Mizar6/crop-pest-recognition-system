"""将 ORM 对象转为字典。"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.inspection import inspect


def to_dict(obj: Any, extra: Optional[dict] = None, exclude: Optional[list] = None) -> dict:
    """
    将 SQLAlchemy 模型实例转为普通字典。

    Args:
        obj: ORM 对象
        extra: 附加字段
        exclude: 需要排除的字段名
    """
    if obj is None:
        return extra or {}
    skip = set(exclude or [])
    data = {}
    for col in inspect(obj).mapper.column_attrs:
        if col.key in skip:
            continue
        value = getattr(obj, col.key)
        if isinstance(value, datetime):
            data[col.key] = value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(value, date):
            data[col.key] = value.strftime("%Y-%m-%d")
        elif isinstance(value, Decimal):
            data[col.key] = float(value)
        else:
            data[col.key] = value
    if extra:
        data.update(extra)
    return data

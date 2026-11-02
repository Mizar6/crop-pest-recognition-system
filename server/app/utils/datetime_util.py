"""日期时间格式常量与转换。"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any

DATE_FMT = "%Y-%m-%d"
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


def format_datetime(value: Any) -> Any:
    """
    将日期时间格式化为界面约定格式。

    Args:
        value: 原始值
    Returns:
        日期 -> 2026-11-02；日期时间 -> 2026-11-02 17:25:17
    """
    if isinstance(value, datetime):
        return value.strftime(DATETIME_FMT)
    if isinstance(value, date):
        return value.strftime(DATE_FMT)
    if isinstance(value, Decimal):
        return float(value)
    return value

"""统一接口响应。"""
from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.utils.datetime_util import format_datetime


def convert_datetimes(obj: Any) -> Any:
    """递归转换字典/列表中的日期时间字段。"""
    if isinstance(obj, list):
        return [convert_datetimes(i) for i in obj]
    if isinstance(obj, dict):
        return {k: convert_datetimes(v) for k, v in obj.items()}
    return format_datetime(obj)


def success(data: Any = None, msg: str = "操作成功") -> JSONResponse:
    """
    成功响应。

    Args:
        data: 业务数据
        msg: 提示信息
    """
    payload = {"code": 200, "msg": msg, "data": convert_datetimes(jsonable_encoder(data))}
    return JSONResponse(content=payload)


def fail(msg: str = "操作失败", code: int = 400, data: Any = None) -> JSONResponse:
    """
    失败响应。

    Args:
        msg: 错误提示
        code: 业务错误码
        data: 附加数据
    """
    payload = {"code": code, "msg": msg, "data": convert_datetimes(jsonable_encoder(data))}
    return JSONResponse(content=payload, status_code=200)


def page_data(items: list, total: int) -> dict:
    """组装分页数据结构。"""
    return {"list": items, "total": total}

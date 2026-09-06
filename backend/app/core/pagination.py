"""分页统一工具：强制 page_size 上限、白名单 sort 解析"""
from collections.abc import Mapping
from typing import Any, Optional

from sqlalchemy import asc, desc
from sqlalchemy.sql.elements import ColumnElement


MAX_PAGE_SIZE = 100


def normalize_page(page: Optional[int]) -> int:
    try:
        p = int(page) if page is not None else 1
    except (TypeError, ValueError):
        p = 1
    return max(p, 1)


def normalize_page_size(page_size: Optional[int]) -> int:
    try:
        ps = int(page_size) if page_size is not None else 20
    except (TypeError, ValueError):
        ps = 20
    return min(max(ps, 1), MAX_PAGE_SIZE)


def parse_sort(
    sort: Optional[str],
    allowed: Mapping[str, ColumnElement[Any]],
    default: tuple[str, str] = ("created_at", "desc"),
) -> list[ColumnElement[Any]]:
    """
    解析 sort 参数为 SQLAlchemy order_by 表达式列表。
    sort 格式: "field" 或 "-field"（- 表示降序），多个用逗号分隔。
    allowed: {"field_name": Model.column, ...} 白名单，防 SQL 注入。
    default: 默认 (field, direction)。
    返回: [order_expr, ...]
    """
    if not sort:
        field, direction = default
        col = allowed.get(field)
        if col is None:
            return []
        return [desc(col) if direction == "desc" else asc(col)]

    exprs: list[ColumnElement[Any]] = []
    for token in sort.split(","):
        token = token.strip()
        if not token:
            continue
        direction = "desc" if token.startswith("-") else "asc"
        field = token.lstrip("-+").strip()
        col = allowed.get(field)
        if col is None:
            continue  # 非白名单字段忽略
        exprs.append(desc(col) if direction == "desc" else asc(col))

    if not exprs:
        field, direction = default
        col = allowed.get(field)
        if col is not None:
            exprs.append(desc(col) if direction == "desc" else asc(col))
    return exprs


def offset_limit(page: int, page_size: int) -> tuple[int, int]:
    return (page - 1) * page_size, page_size

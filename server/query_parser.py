"""查询参数解析辅助 — handler.py 路由分发的轻量工具函数."""

from typing import List


def qbool(query: dict, key: str, default: bool = False) -> bool:
    """解析布尔型查询参数."""
    return query.get(key, str(int(default))) in ('1', 'true', 'True')


def qint(query: dict, key: str, default: int = 0) -> int:
    """解析整型查询参数."""
    try:
        return int(query.get(key, str(default)))
    except (ValueError, TypeError):
        return default


def qlist(query: dict, key: str, sep: str = ',') -> List[int]:
    """解析逗号分隔的整数列表."""
    raw = query.get(key, '')
    if not raw:
        return []
    try:
        return [int(x.strip()) for x in raw.split(sep) if x.strip().isdigit()]
    except (ValueError, TypeError):
        return []


def qstr(query: dict, key: str, default: str = '') -> str:
    """解析字符串查询参数."""
    return query.get(key, default)

def qfloat(query: dict, key: str, default: float = 0.0) -> float:
    """解析浮点查询参数."""
    try:
        return float(query.get(key, str(default)))
    except (ValueError, TypeError):
        return default

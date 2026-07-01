"""查询参数解析 — handler.py 使用的轻量工具."""

def qbool(query, key, default=False):
    return query.get(key, str(int(default))) in ('1', 'true', 'True')

def qint(query, key, default=0):
    try:
        return int(query.get(key, str(default)))
    except (ValueError, TypeError):
        return default

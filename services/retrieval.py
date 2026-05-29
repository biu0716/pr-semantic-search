"""
检索 service。

你的 src/search.py 本来就是干净的（不依赖 Streamlit），
这里只做一层很薄的转发，让 API 统一从 services 里取东西。
以后如果要加 reranker（之前聊到的检索质量优化），改 src/search.py 即可，
这里不用动。
"""

from src.search import search as _search


def search(query: str, k: int = 5) -> list[dict]:
    return _search(query, k)

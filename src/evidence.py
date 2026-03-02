# src/evidence.py
from __future__ import annotations
from typing import Any, Dict, List


def build_evidence_pack(
    results: List[Dict[str, Any]],
    query: str,
    max_evidence: int = 12,
    dedup: bool = True
) -> Dict[str, Any]:
    """
    把 search 返回的结果整理成 evidence_pack（证据包）。

    约定：results 里每一项至少包含：
    - chunk_id (str)
    - source (str) 例如文件名
    - score (float) 相似度/距离（你现在怎么返回就怎么塞）
    - text (str) chunk 内容

    如果你的 search 返回字段名不一样，先别急，后面我教你怎么对齐。
    """

    items = []
    seen = set()

    for r in results:
        text = (r.get("text") or "").strip()
        if not text:
            continue

        # 最小去重：用前 60 个字符做指纹（MVP 够用了）
        if dedup:
            fingerprint = text[:60]
            if fingerprint in seen:
                continue
            seen.add(fingerprint)

        items.append({
            "chunk_id": r.get("chunk_id"),
            "source": r.get("source"),
            "score": r.get("score"),
            "text": text
        })

        if len(items) >= max_evidence:
            break

    return {
        "query": query,
        "count": len(items),
        "items": items
    }
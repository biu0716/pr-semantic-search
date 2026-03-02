import json
import numpy as np
import faiss

from src.evidence import build_evidence_pack
from src.config import settings
from src.embedder import embed_texts


def search(query, k=5):
    index = faiss.read_index(settings.INDEX_PATH)

    with open(settings.META_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    q_vec = embed_texts([query])[0]
    q_vec = np.array([q_vec]).astype("float32")

    D, I = index.search(q_vec, k)

    results = []

    for score, idx in zip(D[0], I[0]):
        item = metadata[idx]

        results.append({
            "chunk_id": item.get("chunk_id", idx),
            "source": item.get("source", "unknown"),
            "text": item.get("text", ""),
            "score": float(score)
        })

    print("===== DEBUG: first result =====")
    print(results[0])

    # 🔥 构建 evidence_pack
    evidence_pack = build_evidence_pack(
        results,
        query=query,
        max_evidence=12,
        dedup=True
    )

    print("\n===== EVIDENCE PACK =====")
    print("count:", evidence_pack["count"])
    print("first item:", evidence_pack["items"][0])

    return evidence_pack


if __name__ == "__main__":
    while True:
        q = input("请输入查询内容：")
        evidence = search(q, 5)

        print("\n=== Evidence Items ===\n")

        for r in evidence["items"]:
            print("chunk_id:", r["chunk_id"])
            print("score:", r["score"])
            print("内容：", r["text"][:200])
            print("-" * 50)
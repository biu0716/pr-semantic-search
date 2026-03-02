from openai import OpenAI

client = OpenAI(
    api_key="sk-0f5875349bd24111b16e5f9d924c9702",
    base_url="https://api.deepseek.com"
)

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

    evidence_pack = build_evidence_pack(
        results,
        query=query,
        max_evidence=12,
        dedup=True
    )

    print("\n===== EVIDENCE PACK =====")
    print("count:", evidence_pack["count"])

    print("\n===== BUILDING CONTEXT =====")

    context_parts = []
    for item in evidence_pack["items"]:
        context_parts.append(
            f"[chunk_id={item['chunk_id']}]\n{item['text']}"
        )

    context = "\n\n".join(context_parts)

    print(context[:800])

    return evidence_pack

def ask_deepseek_to_summarize(user_query, searched_texts):
    context = "\n\n".join(searched_texts)

    system_prompt = """
你是一位企业级知识库问答助手。

严格规则：
1. 只能使用【参考资料】中的内容。
2. 不得补充任何未在资料中出现的产品参数、技术配置或数据。
3. 如果某信息未在资料中出现，必须写“资料未提及”。
4. 输出必须以“引用资料中的原句或概念”为基础。
5. 不得使用行业常识推测。
"""

    user_prompt = f"""
【参考资料】
{context}

【问题】
{user_query}

请基于资料回答，并在每个要点后标注引用的原句关键词。
"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    while True:
        q = input("请输入查询内容：")
        evidence = search(q, 5)

        # 打印检索到的 chunk_id
        print("\n=== 检索到的 chunk_ids ===")
        for item in evidence["items"]:
            print(item["chunk_id"])

        # 只传第一条给 LLM（用于验证是否乱编）
        texts = [evidence["items"][0]["text"]]

        print("\n=== 传入 LLM 的文本 ===")
        print(texts[0][:500])  # 只打印前500字符

        answer = ask_deepseek_to_summarize(q, texts)

        print("\n===== AI ANSWER =====\n")
        print(answer)

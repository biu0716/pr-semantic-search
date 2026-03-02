import json
import numpy as np
import faiss

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
    for idx in I[0]:
        results.append(metadata[idx])

    return results


if __name__ == "__main__":
    while True:
        q = input("请输入查询内容：")
        results = search(q, 3)

        print("\n=== 搜索结果 ===\n")

        for r in results:
            print("文件：", r["file"])
            print("片段：", r["text"][:200])
            print("-" * 50)

def ask_deepseek_to_summarize(user_query, searched_texts):
    """
    这个函数是“桥梁”：
    1. user_query: 你问的问题（比如：VLE传播重点是什么？）
    2. searched_texts: 你之前用 FAISS 搜出来的那些 docx 片段（通常是个列表）
    """
    
    # 把搜到的片段拼成一大段参考资料
    context = "\n".join(searched_texts)
    
    # 告诉 DeepSeek 它现在的身份
    system_prompt = "你是一个专业的公关(PR)顾问，请根据提供的参考资料回答问题。如果资料中没有提到，请诚实回答不知道。"
    
    # 告诉 DeepSeek 具体的任务
    user_prompt = f"参考资料如下：\n{context}\n\n我的问题是：{user_query}"
    
    # 正式调用 DeepSeek（这里用你已经配置好的环境变量）
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3  # 这个参数越低，AI越严谨，不会胡编乱造
    )
    
    return response.choices[0].message.content
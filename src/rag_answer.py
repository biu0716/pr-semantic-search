from openai import OpenAI
from src.search import search


client = OpenAI(
    api_key="668c9345b0664170b967322aad92ba31.CegvE6kJvsZYXYf5",
    base_url="https://open.bigmodel.cn/api/paas/v4/"
)


def answer(query):
    docs = search(query, 5)

    print("===== DEBUG: first result =====")
    print(docs[0] if docs else "No results")

    print("\n===== EVIDENCE PACK =====")
    print("count:", len(docs))

    context = "\n\n".join([d["text"] for d in docs])

    print("\n===== BUILDING CONTEXT =====")
    print(context[:2000])

    prompt = f"""
你是一名汽车品牌公关专家。

以下是梅赛德斯-奔驰车型资料：
{context}

用户问题：
{query}

请根据资料提炼：
1. 核心信息（3-4条）
2. 传播亮点
3. 可用于新闻稿的一段总结（100字以内）

只能根据资料回答，不要编造。
"""

    resp = client.chat.completions.create(
        model="glm-4-flash",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.4
    )

    return resp.choices[0].message.content


if __name__ == "__main__":
    while True:
        q = input("请输入问题：").strip()
        if not q:
            continue

        result = answer(q)

        print("\nAI回答：\n")
        print(result)
        print("\n" + "=" * 60 + "\n")
import requests
from src.config import settings


def embed_texts(texts):
    if not settings.EMBEDDING_API_KEY:
        raise RuntimeError("请先在 config.py 里填写 EMBEDDING_API_KEY")

    url = settings.EMBEDDING_BASE_URL + "/embeddings"

    headers = {
        "Authorization": f"Bearer {settings.EMBEDDING_API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "model": settings.EMBEDDING_MODEL,
        "input": texts
    }

    resp = requests.post(url, headers=headers, json=data, timeout=60)
    resp.raise_for_status()

    result = resp.json()

    vectors = []
    for item in result["data"]:
        vectors.append(item["embedding"])

    return vectors
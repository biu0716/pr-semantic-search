import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-small-zh-v1.5"

_model = None


def get_model():
    global _model
    if _model is not None:
        return _model

    # 先尝试只用本地缓存加载
    try:
        _model = SentenceTransformer(MODEL_NAME, local_files_only=True)
        print("✅ 已从本地缓存加载 embedding 模型")
        return _model
    except Exception as e:
        print("⚠️ 本地缓存加载失败，尝试联网加载...")
        print(f"   原因：{e}")

    # 如果本地缓存不完整，再联网加载
    _model = SentenceTransformer(MODEL_NAME)
    print("✅ 已联网加载 embedding 模型")
    return _model


def embed_texts(texts):
    model = get_model()
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False
    )
    return np.array(vectors, dtype="float32")
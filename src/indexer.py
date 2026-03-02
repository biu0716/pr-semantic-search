import json
from pathlib import Path

import numpy as np
import faiss

from src.config import settings
from src.loaders import read_docx
from src.chunker import chunk_text
from src.embedder import embed_texts


def build_index():
    root = Path(settings.ONEDRIVE_ROOT)

    all_chunks = []
    metadata = []

    print("🔍 扫描文件...")

    for p in root.rglob("*.docx"):
        if p.name.startswith("~$"):
            continue
        print("处理文件：", p)

        text = read_docx(p)
        chunks = chunk_text(text, 500, 80)

        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            metadata.append({
                "file": str(p),
                "chunk_id": i,
                "text": chunk
            })

    print("🧠 生成向量...")

    vectors = []
    batch_size = 16

    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i+batch_size]
        vecs = embed_texts(batch)
        vectors.extend(vecs)

    vectors = np.array(vectors).astype("float32")

    dim = vectors.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(vectors)

    Path("data").mkdir(exist_ok=True)

    faiss.write_index(index, settings.INDEX_PATH)

    with open(settings.META_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print("✅ 构建完成")
    print("向量数量：", len(vectors))


if __name__ == "__main__":
    build_index()
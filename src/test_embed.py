from src.embedder import embed_texts

vecs = embed_texts(["梅赛德斯-奔驰纯电VLE"])

print("向量数量：", len(vecs))
print("向量维度：", len(vecs[0]))
# PR Semantic Search - Development Log

---

## Day 01 - RAG v2 Stabilization

### 🎯 今日目标
- 验证RAG是否存在幻觉问题

### 🔧 今日完成
- 打印 chunk_id
- 控制单 chunk 传入 LLM
- 验证 hallucination 来源
- 冻结 RAG v2 稳定版本

### 🧠 技术理解提升
- 多 chunk context 会导致模型信息融合
- Hallucination 不一定是模型编造，可能来自检索混合
- Debug retrieval 比调 prompt 更重要

### 🚀 明日计划
- 优化 chunk 去重逻辑
- 打印并分析相似度 score
---
title: PR Agent
emoji: 📝
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# PR Agent · 汽车品牌传播提案工作台

一个面向汽车公关场景的 AI 工作台：给一句传播需求，自动产出「传播策略骨架 + 具体交付内容」，并支持稿件审校、术语规范化，以及基于知识库的语义检索。

> 本在线 Demo 运行在 **DEMO_MODE** 下，使用一套**完全虚构、脱敏**的示例品牌素材（「星航 NOVA」），不含任何真实客户资料。

## 它能做什么

- **写一份新提案**：两阶段生成——先出传播策略判断，再出新闻稿段落、传播方向、媒体标题、社媒文案，可逐段重写、整体优化、一键导出。
- **改一篇现有稿子**：审稿挑错 / 术语规范化 / 正式风格改写。
- **查资料、找素材**：语义召回 + 规则重排（车型匹配、文档类型、版本新鲜度、质量分），并展示每条结果的得分构成。

## 技术栈

Python · FastAPI · FAISS · sentence-transformers（bge-small-zh）· 规则化重排 · 原生前端

## 一个被修掉的真实问题

检索的车型识别原本用「子串包含」，导致 "CLA" 命中 "S-CLASS" 里的 c-l-a，把整批 S 级文档误判后打成 UNKNOWN——约占全库 35% 的内容因此搜不到。改为「带词边界的匹配」后，这些内容全部恢复，且无误伤。

## 本地运行

```bash
pip install -r requirements.txt
# 真实库（自己用）：
uvicorn app:app --reload --port 8000
# 演示模式（脱敏示例库 + 限流）：
DEMO_MODE=1 uvicorn app:app --port 8000
```

需在环境变量 `AIHUBMIX_API_KEY` 中提供 LLM key。

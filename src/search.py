import json
import os
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import faiss

from src.config import settings
from src.embedder import embed_texts

# DEMO_MODE=1 时，检索走脱敏示例库（data/sample/），用于线上演示；
# 不设置时走你的真实索引（data/index.faiss），本地自用不受影响。
DEMO_MODE = os.environ.get("DEMO_MODE") == "1"
SAMPLE_INDEX_PATH = Path("data/sample/index.faiss")
SAMPLE_META_PATH = Path("data/sample/meta.json")


# ==============================
# 车型识别规则
# 和 indexer.py 保持一致
# ==============================

MODEL_PATTERNS = [
    ("VISION V", "VISION_V"),
    ("VISION ICONIC", "VISION_ICONIC"),  # 新加
    ("VLE", "VLE"),
    ("GLS", "GLS"),
    ("GLE", "GLE"),
    ("GLC", "GLC"),        # 新加
    ("CLA", "CLA"),
    ("MAYBACH", "MAYBACH"),
    ("EQS", "EQS"),
    ("EQE", "EQE"),
    ("S-CLASS", "S_CLASS"),
    ("S级", "S_CLASS"),    # 新加
    # ---- 以下为脱敏 demo 用的虚构品牌「星航 NOVA」，不影响真实数据 ----
    ("NOVA S9", "NOVA_S9"), ("NOVA V9", "NOVA_V9"),
    ("NOVA X7", "NOVA_X7"), ("NOVA C3", "NOVA_C3"),
    ("S9", "NOVA_S9"), ("V9", "NOVA_V9"),
    ("X7", "NOVA_X7"), ("C3", "NOVA_C3"),
]


def model_pattern_hit(pattern: str, text_upper: str) -> bool:
    """
    带边界的车型匹配，和 indexer.py 里的同名函数保持一致。
    避免 "CLA" 命中 "S-CLASS" 里的 c-l-a 这类子串误伤。
    （理想情况下这个函数和 MODEL_PATTERNS 应该抽到一个共享模块，
      两边各写一份是历史遗留，等之后整理结构时再合并。）
    """
    p = pattern.upper()
    return re.search(rf"(?<![A-Za-z]){re.escape(p)}(?![A-Za-z])", text_upper) is not None


# ==============================
# 基础工具函数（和你原来一样，没动）
# ==============================

def load_index_and_metadata():
    if DEMO_MODE:
        index_path, meta_path = SAMPLE_INDEX_PATH, SAMPLE_META_PATH
    else:
        index_path, meta_path = settings.INDEX_PATH, settings.META_PATH
    index = faiss.read_index(str(index_path))
    with open(meta_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    return index, metadata


def infer_query_car_model(query: str) -> str | None:
    q_upper = query.upper()
    for pattern, label in MODEL_PATTERNS:
        if model_pattern_hit(pattern, q_upper):
            return label
    return None


def parse_date_safe(date_str: str | None):
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def compute_freshness_bonus(item_date, all_dates) -> float:
    if not item_date or not all_dates:
        return 0.0
    latest = max(all_dates)
    oldest = min(all_dates)
    if latest == oldest:
        return 0.03
    span_days = max((latest - oldest).days, 1)
    relative_pos = (item_date - oldest).days / span_days
    return round(0.05 * relative_pos, 4)


# ==============================
# 第一步：向量召回（和你原来一样，没动）
# ==============================

def retrieve_candidates(query: str, k: int):
    index, metadata = load_index_and_metadata()
    q_vec = embed_texts([query])[0]
    q_vec = np.array([q_vec]).astype("float32")
    faiss.normalize_L2(q_vec)
    D, I = index.search(q_vec, k)

    results = []
    for score, idx in zip(D[0], I[0]):
        if idx == -1:
            continue
        if idx >= len(metadata):
            continue
        item = metadata[idx].copy()
        item["semantic_score"] = float(score)
        results.append(item)

    return results


# ==============================
# 【新加】第一步半：硬过滤
# 只在 query 有明确车型时触发
# ==============================

def hard_filter_by_car_model(candidates: list, query_model: str) -> list:
    """
    当 query 明确包含车型（如"CLA传播亮点"）时，
    在 rerank 之前先过滤掉不相关的 chunk。

    保留规则：
    - 主车型 = query_model → 直接保留
    - 主车型 = UNKNOWN，且 related_models 里有 query_model → 降权保留
    - 主车型是别的车型 → 丢掉

    降级保护：
    - 如果过滤后不足 3 条，说明知识库里这个车型的内容太少，
      退回全部候选，避免返回空结果。
    """
    primary_match = []    # 主车型匹配
    related_match = []    # 通用文档里关联提到的

    for item in candidates:
        car_model = item.get("car_model", "UNKNOWN")
        related_models = item.get("related_models", [])  # 新 metadata 字段

        if car_model == query_model:
            primary_match.append(item)

        elif car_model == "UNKNOWN" and query_model in related_models:
            # 降权：把语义分打个折，让它排在主车型文档后面
            item = item.copy()
            item["semantic_score"] = item["semantic_score"] * 0.75
            related_match.append(item)

        # 其他车型：直接丢掉，不参与 rerank

    filtered = primary_match + related_match

    # 降级保护：结果太少就退回全部
    if len(filtered) < 3:
        print(f"⚠️ 硬过滤后结果不足3条（{len(filtered)}条），退回全部候选")
        return candidates

    print(f"✅ 硬过滤：{len(candidates)} → {len(filtered)} 条（主车型{len(primary_match)}条，关联{len(related_match)}条）")
    return filtered


# ==============================
# 第二步：规则型 rerank
# 主要改动：加了 score_breakdown，方便调试
# ==============================

def rerank_results(query: str, results: list[dict], final_k: int = 5) -> list[dict]:
    """
    rerank 逻辑和你原来基本一样。
    新增：score_breakdown 字段，记录每个维度的得分，
    方便你在终端或 Streamlit 里看"为什么这条排第一"。
    """
    if not results:
        return []

    query_model = infer_query_car_model(query)

    all_dates = []
    for item in results:
        dt = parse_date_safe(item.get("version_date"))
        if dt:
            all_dates.append(dt)

    reranked = []

    for item in results:
        semantic_score = float(item.get("semantic_score", 0.0))

        # 1) 车型匹配加分
        model_bonus = 0.0
        if query_model and item.get("car_model") == query_model:
            model_bonus = 0.12

        # 2) 正式稿 / 产品资料优先
        source_priority = int(item.get("source_priority", 0) or 0)
        doc_type_bonus = 0.04 * source_priority

        # 3) 更新版本加分
        freshness_bonus = compute_freshness_bonus(
            parse_date_safe(item.get("version_date")),
            all_dates
        )

        # 4) 文本质量加分
        quality_score = float(item.get("quality_score", 0.5) or 0.5)
        quality_bonus = round(0.06 * (quality_score - 0.5), 4)

        # 5) noisy 扣分
        noise_penalty = -0.08 if item.get("is_noisy") else 0.0

        # 汇总
        rerank_score = (
            semantic_score
            + model_bonus
            + doc_type_bonus
            + freshness_bonus
            + quality_bonus
            + noise_penalty
        )

        item["rerank_score"] = round(rerank_score, 6)

        # 【新加】分数拆解，调试用
        # 你可以在终端打印这个，也可以在 Streamlit 里展示给用户
        item["score_breakdown"] = {
            "语义分": round(semantic_score, 4),
            "车型匹配": model_bonus,
            "文档类型": round(doc_type_bonus, 4),
            "版本新鲜度": freshness_bonus,
            "质量加分": quality_bonus,
            "噪声惩罚": noise_penalty,
            "总分": round(rerank_score, 4),
        }

        reranked.append(item)

    reranked.sort(key=lambda x: x["rerank_score"], reverse=True)

    # 多样性控制（和你原来一样）
    final_results = []
    file_counter = {}
    group_counter = {}

    for item in reranked:
        file_name = item.get("file_name") or item.get("file", "")
        version_group = item.get("version_group", "")

        if file_counter.get(file_name, 0) >= 1:
            continue
        if version_group and group_counter.get(version_group, 0) >= 3:
            continue

        final_results.append(item)
        file_counter[file_name] = file_counter.get(file_name, 0) + 1
        if version_group:
            group_counter[version_group] = group_counter.get(version_group, 0) + 1

        if len(final_results) >= final_k:
            break

    return final_results


# ==============================
# 对外搜索函数
# 改动：在召回和 rerank 之间插入硬过滤
# ==============================

def search(query: str, k: int = 5) -> list[dict]:
    """
    完整流程：
    1. 向量召回（多取一些候选）
    2. 如果 query 有明确车型 → 硬过滤
    3. rerank
    4. 返回 Top K
    """
    candidate_k = max(k * 4, 20)  # 比原来多取一些，给硬过滤留余量
    candidates = retrieve_candidates(query, candidate_k)

    # 【新加】硬过滤：有明确车型才触发
    query_model = infer_query_car_model(query)
    if query_model:
        candidates = hard_filter_by_car_model(candidates, query_model)

    final_results = rerank_results(query, candidates, final_k=k)
    return final_results


# ==============================
# 本地调试入口
# 改动：打印 score_breakdown，方便你看每条结果的得分构成
# ==============================

if __name__ == "__main__":
      
    while True:
        q = input("请输入查询内容：").strip()
        if not q:
            continue

        results = search(q, 5)

        print("\n=== 搜索结果 ===\n")

        for i, r in enumerate(results, 1):
            print(f"【第{i}条】")
            print("文件：", r.get("file_name"))
            print("车型：", r.get("car_model"), "| 关联车型：", r.get("related_models", []))
            print("资料类型：", r.get("doc_type"))
            print("版本日期：", r.get("version_date"))

            # 打印分数拆解
            breakdown = r.get("score_breakdown", {})
            print("得分构成：")
            for k_name, v in breakdown.items():
                print(f"  {k_name}: {v}")

            print("片段：", r.get("text", ""))
            print("-" * 50)
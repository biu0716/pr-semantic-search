"""
精修 service。

包含两类逻辑：
1. refine_existing_result —— 对已生成的结果按用户补充要求再优化
2. run_refine_with_uploaded_text —— 对上传稿件做审稿 / 规范化 / 改写
逻辑与原 streamlit_app.py 完全一致。
"""

from src.pr_agent import call_llm
from services.terms import apply_extra_term_rules


def refine_existing_result(
    *,
    mode: str,
    current_result: str,
    instruction: str,
) -> str:
    if mode == "generate":
        prompt = f"""
你是一名服务汽车品牌的中国公关编辑。请基于用户补充要求，对已有结果做进一步优化。

【要求】
1. 保留原有整体结构，尤其保留：
- 【第一步｜传播策略骨架】
- 【第二步｜具体交付内容】
2. 第二步中的栏目标题尽量保持不变。
3. 不要新增没有依据的事实。
4. 优化方向只围绕用户补充要求展开。

【补充要求】
{instruction}

【当前结果】
{current_result}

请直接输出更新后的完整结果。
""".strip()
    else:
        prompt = f"""
你是一名服务汽车品牌的中国公关编辑。请基于用户补充要求，对已有处理结果做进一步优化。

【要求】
1. 保留原意，不新增事实。
2. 尽量保持现有结构。
3. 如果当前结果包含“问题清单 / 修改建议 / 参考改法”等结构，请尽量保留。
4. 只围绕用户补充要求优化表达。

【当前模式】
{mode}

【补充要求】
{instruction}

【当前结果】
{current_result}

请直接输出更新后的完整结果。
""".strip()

    return call_llm(prompt).strip()


def run_refine_with_uploaded_text(
    mode: str,
    source_text: str,
    instruction_text: str = "",
    extra_terms: dict[str, str] | None = None,
) -> str:
    extra_terms = extra_terms or {}
    source_text = apply_extra_term_rules(source_text, extra_terms)
    instruction_text = apply_extra_term_rules(instruction_text.strip(), extra_terms)

    mode_task_map = {
        "check": "请输出问题清单、修改建议与可参考改法。",
        "normalize": "请输出统一后的正式表达。",
        "rewrite": "请输出改写后的正式汽车 PR 风格文本。",
    }

    mode_rule_map = {
        "check": """
你是一名汽车品牌公关审稿编辑。
请基于上传稿件完成审稿，不要凭空补充稿件中没有的信息。
重点检查：
1. 品牌口径是否统一
2. 时间、事实、术语写法是否准确
3. 风险措辞是否需要收敛
4. 语气是否符合正式 PR 稿件
5. 结构与表达是否顺畅
""",
        "normalize": """
你是一名汽车品牌公关编辑。
请基于上传稿件做术语和表达规范化。
要求：
1. 优先统一品牌、产品、技术名词写法
2. 调整为更正式、更官方的表达
3. 尽量保留原意和原有结构
4. 不要新增稿件中没有的事实
""",
        "rewrite": """
你是一名汽车品牌公关编辑。
请基于上传稿件完成正式风格改写。
要求：
1. 保留原意，不新增事实
2. 语言更像正式汽车 PR 稿件
3. 语气更克制、更专业
4. 保持信息顺序尽量稳定
""",
    }

    extra_instruction_block = instruction_text if instruction_text else "无额外要求。"

    prompt = f"""
{mode_rule_map.get(mode, "")}

【额外个性化要求】
{extra_instruction_block}

【原稿内容】
{source_text}

【输出要求】
{mode_task_map.get(mode, "")}
""".strip()

    return call_llm(prompt)

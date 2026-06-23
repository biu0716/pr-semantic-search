"""
生成 service。

把原来 streamlit_app.py 里的两阶段生成 / 策略骨架 / 分段重写逻辑
原样搬过来，去掉 Streamlit 依赖。
LLM 调用仍然复用 src/pr_agent.py 里的函数。
"""

import inspect
import re

from src.pr_agent import (
    call_llm,
    clean_title_result,
    generate_core_pr,
    generate_pr,
    generate_titles,
    strip_titles_section,
)

from services.documents import build_uploaded_context
from services.terms import apply_extra_term_rules, build_terms_prompt_block


# ==============================
# 小工具
# ==============================

def call_with_supported_kwargs(func, *args, **kwargs):
    """只把目标函数签名里支持的 kwargs 传进去，避免 TypeError。"""
    sig = inspect.signature(func)
    supported_kwargs = {
        key: value for key, value in kwargs.items()
        if key in sig.parameters
    }
    return func(*args, **supported_kwargs)


# ==============================
# 第二步：基于上传资料生成
# ==============================

def generate_pr_from_uploaded_text(
    query: str,
    uploaded_text: str,
    source_name: str,
    extra_terms: dict[str, str] | None = None,
) -> str:
    extra_terms = extra_terms or {}

    query = apply_extra_term_rules(query, extra_terms)
    uploaded_text = apply_extra_term_rules(uploaded_text, extra_terms)

    context = build_uploaded_context(uploaded_text, source_name)
    terms_block = build_terms_prompt_block(extra_terms)

    core_prompt = f"""
你是一名服务汽车品牌的中国公关编辑，正在基于内部资料撰写传播提案内容。

请基于以下资料完成输出。

【重要要求】
1. 只能使用资料中明确出现的信息，不要补充资料中没有出现的配置、参数、功能和结论。
2. “传播方向”必须是传播切口，不要写成“空间/智能/豪华/操控”这类卖点分类。
3. 不要输出任何“媒体标题”内容。
4. 严格按照指定结构输出，不要增加新栏目。
5. 避免使用空泛AI套话。
6. 如涉及术语，请优先遵循术语表。

{terms_block}

【你只能输出以下四个部分，且必须按此顺序】
传播主题：
传播方向（3条）：
新闻稿段落：
社媒文案（3条）：

【参考资料】
{context}

【用户需求】
{query}
""".strip()

    title_prompt = f"""
你是一名中国汽车媒体编辑，请基于资料为一个汽车传播项目生成媒体标题。

【重要要求】
1. 只能使用资料中明确出现的信息。
2. 标题要更像传播选题，不要写成参数总结标题。
3. 如涉及术语，请优先遵循术语表。
4. 只允许输出编号标题，不要输出“传播主题”“媒体标题”“说明”等额外字段。

{terms_block}

【参考资料】
{context}

【用户需求】
{query}

请直接输出 5 个标题，每行一条，格式如下：
1.
2.
3.
4.
5.
""".strip()

    core_result = call_llm(core_prompt)
    core_result = strip_titles_section(core_result)

    title_result = call_llm(title_prompt)
    title_result = clean_title_result(title_result)

    final_result = f"{core_result}\n\n媒体标题（5条）：\n{title_result}"
    return final_result


# ==============================
# 第一步：策略骨架 prompt
# ==============================

def build_strategy_prompt(
    query: str,
    extra_terms: dict[str, str] | None = None,
    uploaded_text: str | None = None,
    source_name: str | None = None,
) -> str:
    extra_terms = extra_terms or {}
    query = apply_extra_term_rules(query, extra_terms)
    terms_block = build_terms_prompt_block(extra_terms)

    if uploaded_text and source_name:
        context_block = build_uploaded_context(
            apply_extra_term_rules(uploaded_text, extra_terms),
            source_name
        )
        source_rule = "可结合资料中的明确信息做传播判断，但不要补充资料中没有出现的事实。"
    else:
        context_block = "当前未上传参考资料。请仅基于用户需求完成传播判断，不要臆造具体配置、参数、功能和结论。"
        source_rule = "没有资料时，只做传播逻辑判断，不要写具体产品事实。"

    return f"""
你是一名服务汽车品牌的中国公关策略编辑。
现在不要直接写最终稿件，先完成传播策略判断。

【目标】
请先把这次任务的传播逻辑想清楚，再为后续生成具体交付内容做准备。

【重要要求】
1. 先做策略判断，不要直接输出完整新闻稿或媒体标题。
2. “传播方向”必须是传播切口，不要写成“空间/智能/豪华/操控”这类卖点分类。
3. 表达要像真实汽车 PR 提案前期判断，避免空泛AI套话。
4. {source_rule}
5. 如涉及术语，请优先遵循术语表。

{terms_block}

【参考信息】
{context_block}

【用户需求】
{query}

【请严格按以下结构输出】
任务理解：
传播对象判断：
核心传播命题：
传播方向建议（3条）：
不建议采用的表达：
写作提醒：
""".strip()


def generate_pr_from_brief_only(
    query: str,
    strategy_result: str,
    extra_terms: dict[str, str] | None = None,
) -> str:
    extra_terms = extra_terms or {}
    query = apply_extra_term_rules(query, extra_terms)
    terms_block = build_terms_prompt_block(extra_terms)

    prompt = f"""
你是一名服务汽车品牌的中国公关编辑，正在把用户 brief 转成可用的传播初稿。

当前没有上传产品资料，因此你必须只围绕【用户需求】和【策略骨架】写作。

【绝对禁止】
1. 禁止引用、借用或虚构任何用户没有提到的品牌、车型、参数、配置、功能、价格、上市时间。
2. 禁止出现与用户需求无关的车型名或品牌名。
3. 禁止把知识库示例中的车型、卖点或参数迁移到本次稿件。
4. 禁止使用“重新定义行业”“颠覆传统”“极致体验”等空泛或夸张表达。

【写作要求】
1. 如果缺少具体产品资料，新闻稿段落要写成框架性初稿，不要编造配置和参数。
2. 传播方向必须是传播切口，不要写成“空间/智能/豪华/操控”这类卖点分类。
3. 语言要像真实汽车 PR 初稿：克制、清楚、可交付。
4. 如涉及术语，请优先遵循术语表。

{terms_block}

【用户需求】
{query}

【策略骨架】
{strategy_result}

【你只能输出以下五个部分，且必须按此顺序】
传播主题：
传播方向（3条）：
导语：
新闻稿段落：
社媒文案（3条）：
""".strip()

    return call_llm(prompt).strip()


# ==============================
# 两阶段生成主流程
# ==============================

def generate_pr_two_stage(
    query: str,
    top_k: int = 5,
    extra_terms: dict[str, str] | None = None,
    uploaded_text: str | None = None,
    source_name: str | None = None,
) -> str:
    extra_terms = extra_terms or {}
    query = apply_extra_term_rules(query, extra_terms)

    strategy_prompt = build_strategy_prompt(
        query=query,
        extra_terms=extra_terms,
        uploaded_text=uploaded_text,
        source_name=source_name,
    )
    strategy_result = call_llm(strategy_prompt).strip()

    if uploaded_text and source_name:
        delivery_result = generate_pr_from_uploaded_text(
            query=query,
            uploaded_text=uploaded_text,
            source_name=source_name,
            extra_terms=extra_terms,
        )
    else:
        delivery_result = generate_pr_from_brief_only(
            query=query,
            strategy_result=strategy_result,
            extra_terms=extra_terms,
        )

    return f"""【第一步｜传播策略骨架】
{strategy_result}



【第二步｜具体交付内容】
{delivery_result}"""


# ==============================
# 结果解析 + 分段重写
# ==============================

GENERATE_SECTION_HEADERS = {
    "angles": "传播方向（3条）：",
    "titles": "媒体标题（5条）：",
    "social": "社媒文案（3条）：",
}

ALL_GENERATE_HEADERS = [
    "传播主题：",
    "传播方向（3条）：",
    "新闻稿段落：",
    "社媒文案（3条）：",
    "媒体标题（5条）：",
]


def split_two_stage_result(text: str) -> tuple[str | None, str | None]:
    text = text.strip()

    if "【第一步｜传播策略骨架】" not in text or "【第二步｜具体交付内容】" not in text:
        return None, text

    parts = text.split("【第二步｜具体交付内容】", 1)
    stage1_raw = parts[0].replace("【第一步｜传播策略骨架】", "").strip()
    stage2_raw = parts[1].strip()

    return stage1_raw, stage2_raw


def get_delivery_text(result_text: str) -> str:
    stage1, stage2 = split_two_stage_result(result_text)
    return (stage2 or result_text or "").strip()


def extract_section_content(text: str, header: str) -> str:
    joined = "|".join(re.escape(h) for h in ALL_GENERATE_HEADERS)
    pattern = rf"{re.escape(header)}\s*\n?(.*?)(?=\n(?:{joined})|\Z)"
    match = re.search(pattern, text, flags=re.DOTALL)
    return match.group(1).strip() if match else ""


def replace_section_content(text: str, header: str, new_content: str) -> str:
    joined = "|".join(re.escape(h) for h in ALL_GENERATE_HEADERS)
    pattern = rf"{re.escape(header)}\s*\n?(.*?)(?=\n(?:{joined})|\Z)"
    replacement = f"{header}\n{new_content.strip()}\n"
    if re.search(pattern, text, flags=re.DOTALL):
        return re.sub(pattern, replacement, text, count=1, flags=re.DOTALL).strip()
    return (text.rstrip() + "\n\n" + replacement).strip()


def regenerate_generate_section(
    *,
    section_key: str,
    query: str,
    current_result: str,
    top_k: int = 5,
    extra_terms: dict[str, str] | None = None,
    uploaded_text: str | None = None,
    source_name: str | None = None,
) -> str:
    header = GENERATE_SECTION_HEADERS[section_key]

    candidate_full = generate_pr_two_stage(
        query=query,
        top_k=top_k,
        extra_terms=extra_terms,
        uploaded_text=uploaded_text,
        source_name=source_name,
    )
    candidate_delivery = get_delivery_text(candidate_full)
    new_content = extract_section_content(candidate_delivery, header)

    if not new_content:
        raise ValueError("未能提取到对应内容，请重试。")

    current_stage1, current_delivery = split_two_stage_result(current_result)
    current_delivery = current_delivery or get_delivery_text(current_result)
    updated_delivery = replace_section_content(current_delivery, header, new_content)

    if current_stage1 is None:
        return updated_delivery

    return f"""【第一步｜传播策略骨架】
{current_stage1}



【第二步｜具体交付内容】
{updated_delivery}"""

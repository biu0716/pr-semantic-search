import argparse
import os
import sys
import json
import re
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI

from src.search import search
from src.rules.pr_rules import normalize_text
from src.rules.mb_terms import MB_CN_TO_EN, MB_EN_TO_CN, MB_MEDIA_CN_TO_EN

load_dotenv()

def _join_retrieved_chunks(retrieved_chunks: List[Any], max_chars: int = 6000) -> str:
    parts = []
    total = 0

    for i, chunk in enumerate(retrieved_chunks, start=1):
        if isinstance(chunk, str):
            text = chunk
            source = f"chunk_{i}"
        elif isinstance(chunk, dict):
            text = chunk.get("text", "") or chunk.get("content", "")
            source = chunk.get("source", f"chunk_{i}")
        else:
            text = getattr(chunk, "text", "") or getattr(chunk, "content", "")
            source = getattr(chunk, "source", f"chunk_{i}")

        text = (text or "").strip()
        if not text:
            continue

        piece = f"[来源{i}: {source}]\n{text}\n"
        if total + len(piece) > max_chars:
            break

        parts.append(piece)
        total += len(piece)

    return "\n".join(parts)


# ==============================
# Config
# ==============================

AIHUBMIX_BASE_URL = "https://aihubmix.com/v1"
MODEL_NAME = os.getenv("AIHUBMIX_MODEL", "gpt-5.3-chat-latest")
API_KEY = os.getenv("AIHUBMIX_API_KEY")


# ==============================
# LLM Client
# ==============================

def _extract_json_block(text: str) -> Dict[str, Any]:
    """
    尝试从模型返回文本中提取 JSON。
    兼容：
    1. 纯 JSON
    2. ```json ... ``` 包裹
    3. 文本中夹着 JSON
    """
    text = text.strip()

    # 情况1：直接就是 JSON
    try:
        return json.loads(text)
    except Exception:
        pass

    # 情况2：代码块里的 JSON
    fenced_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced_match:
        candidate = fenced_match.group(1).strip()
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # 情况3：提取第一个 {...}
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        candidate = brace_match.group(0).strip()
        try:
            return json.loads(candidate)
        except Exception:
            pass

    raise ValueError(f"无法从模型输出中解析 JSON：\n{text[:1000]}")


def get_client() -> OpenAI:
    if not API_KEY:
        raise RuntimeError(
            "未检测到 AIHUBMIX_API_KEY 环境变量。\n"
            "请先执行：\n"
            'export AIHUBMIX_API_KEY="你的key"'
        )

    return OpenAI(
        base_url=AIHUBMIX_BASE_URL,
        api_key=API_KEY,
    )


client = get_client()


def call_llm(prompt: str) -> str:
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "developer",
                "content": (
                    "你是一名经验丰富的中国汽车品牌公关编辑，"
                    "擅长传播提案、媒体标题撰写、新闻稿表达优化、品牌术语规范化。"
                    "请始终使用中文输出。"
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        max_completion_tokens=1500,
    )

    return resp.choices[0].message.content or ""


# ==============================
# Helpers
# ==============================

def apply_model_name_rules(text: str) -> str:
    # 车型名规范化：将简称统一为品牌标准写法。
    # 这里留空字典作为可扩展点——实际规则应来自上传的术语表，
    # 不在代码里硬编码任何具体客户的车型名。
    replacements: dict[str, str] = {}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def safe_search(query: str, top_k: int) -> list[dict[str, Any]]:
    """
    兼容不同 search() 返回结构：
    - [{'text': '...'}, ...]
    - [{'chunk': '...'}, ...]
    - [{'content': '...'}, ...]
    """
    docs = search(query, top_k)

    if not isinstance(docs, list):
        raise ValueError("search() 返回结果不是 list，请检查 src/search.py")

    normalized_docs: list[dict[str, Any]] = []
    for d in docs:
        if not isinstance(d, dict):
            continue

        text = d.get("text") or d.get("chunk") or d.get("content") or ""
        source = d.get("source") or d.get("file") or d.get("path") or ""

        normalized_docs.append({
            "text": text,
            "source": source,
        })

    return normalized_docs

def apply_mb_term_rules(text: str) -> str:
    for en_term, zh_term in MB_EN_TO_CN.items():
        if en_term and zh_term:
            text = text.replace(en_term, zh_term)
    return text

def build_context(docs: list[dict[str, Any]]) -> str:
    if not docs:
        return "未检索到相关资料。"

    blocks = []
    for i, d in enumerate(docs, start=1):
        text = d.get("text", "").strip()
        source = d.get("source", "").strip()

        if source:
            block = f"[资料{i} | 来源: {source}]\n{text}"
        else:
            block = f"[资料{i}]\n{text}"

        blocks.append(block)

    return "\n\n".join(blocks)


def strip_titles_section(text: str) -> str:
    """
    防止 generate_core_pr() 偷偷输出“媒体标题”栏目。
    """
    stop_markers = [
        "\n媒体标题：",
        "\n媒体标题（5条）：",
        "\n标题：",
        "\n标题建议：",
    ]

    cut_pos = len(text)
    for marker in stop_markers:
        pos = text.find(marker)
        if pos != -1:
            cut_pos = min(cut_pos, pos)

    return text[:cut_pos].strip()


# ==============================
# Title Generator
# ==============================

def clean_title_result(text: str) -> str:
    lines = text.splitlines()
    cleaned = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith("传播主题"):
            continue

        if stripped in {"媒体标题：", "媒体标题（5条）："}:
            continue

        cleaned.append(line)

    return "\n".join(cleaned).strip()


def _call_llm_json(prompt: str) -> Dict[str, Any]:
    raw_text = call_llm(prompt)
    return _extract_json_block(raw_text)

# ==============================
# Core PR Generator
# ==============================

def build_fact_sheet(query: str, retrieved_chunks: List[Any]) -> Dict[str, Any]:
    retrieved_context = _join_retrieved_chunks(retrieved_chunks)

    prompt = f"""
你现在不要写新闻稿，不要写标题。
你只做一件事：从资料里提取“明确出现的信息”，整理成 JSON。

要求：
1. 只提取资料里明确出现的信息，不要补充常识，不要猜。
2. 如果资料里没有，就返回空列表。
3. 除了 JSON，不要输出任何解释。

用户需求：
{query}

检索资料：
{retrieved_context}

请严格输出下面这个 JSON 结构：
{{
  "official_names": [],
  "confirmed_facts": [],
  "brand_phrases": [],
  "scenes": [],
  "tech_points": []
}}
"""

    fact_sheet = _call_llm_json(prompt)

    for key in ["official_names", "confirmed_facts", "brand_phrases", "scenes", "tech_points"]:
        if key not in fact_sheet or not isinstance(fact_sheet[key], list):
            fact_sheet[key] = []

    return fact_sheet

def generate_angles(query: str, fact_sheet: Dict[str, Any]) -> Dict[str, Any]:
    fact_sheet_text = json.dumps(fact_sheet, ensure_ascii=False, indent=2)

    prompt = f"""
你现在不要写新闻稿正文。
你只做一件事：基于 fact sheet，提炼传播主题和传播切口。

要求：
1. 不要写成“设计、空间、智能”这种卖点分类。
2. 要更像传播角度、传播切口。
3. 只能使用 fact sheet 里的信息，不要补充。
4. 除了 JSON，不要输出任何解释。

用户需求：
{query}

fact sheet:
{fact_sheet_text}

注意：如果用户需求里有明确数量要求（如“三个传播主题”），main_theme 必须输出对应数量的主题，用换行分隔，每条一个独立主题，angles 条数也必须和用户要求一致。
请严格输出下面这个 JSON 结构：
{{
  "main_theme": "",
  "angles": [
    {{
      "name": "",
      "why_it_works": ""
    }},
    {{
      "name": "",
      "why_it_works": ""
    }},
    {{
      "name": "",
      "why_it_works": ""
    }}
  ],
  "recommended_angle": ""
}}
"""

    angles = _call_llm_json(prompt)

    if "main_theme" not in angles or not isinstance(angles["main_theme"], str):
        angles["main_theme"] = ""

    if "angles" not in angles or not isinstance(angles["angles"], list):
        angles["angles"] = []

    if "recommended_angle" not in angles or not isinstance(angles["recommended_angle"], str):
        angles["recommended_angle"] = ""

    return angles

def generate_titles(query: str, fact_sheet: Dict[str, Any], angles: Dict[str, Any]) -> Dict[str, Any]:
    fact_sheet_text = json.dumps(fact_sheet, ensure_ascii=False, indent=2)
    angles_text = json.dumps(angles, ensure_ascii=False, indent=2)

    prompt = f"""
你现在不要写正文。
你只做一件事：基于 fact sheet 和传播切口，生成更像汽车传播稿的标题。

要求：
1. 标题不是资料摘要，不是参数罗列。
2. 标题要简洁，有传播感。
3. 不要写“全面升级”“焕新而来”“重新定义”这种很空的话。
4. 每个标题只聚焦一个点。
5. 只能使用 fact sheet 和 angles 里的信息，不要补充。
6. 除了 JSON，不要输出任何解释。

用户需求：
{query}

fact sheet:
{fact_sheet_text}

传播切口：
{angles_text}

请严格输出下面这个 JSON 结构：
{{
  "titles": [
    {{
      "title": "",
      "type": "场景型"
    }},
    {{
      "title": "",
      "type": "品牌价值型"
    }},
    {{
      "title": "",
      "type": "媒体选题型"
    }},
    {{
      "title": "",
      "type": "技术价值型"
    }}
  ]
}}
"""

    titles = _call_llm_json(prompt)

    if "titles" not in titles or not isinstance(titles["titles"], list):
        titles["titles"] = []

    return titles

def generate_paragraphs(query: str, fact_sheet: Dict[str, Any], angles: Dict[str, Any]) -> Dict[str, Any]:
    fact_sheet_text = json.dumps(fact_sheet, ensure_ascii=False, indent=2)
    angles_text = json.dumps(angles, ensure_ascii=False, indent=2)

    prompt = f"""
你现在只做一件事：基于 fact sheet 和传播切口，生成简洁的传播文案。

要求：
1. 只使用 fact sheet 和 angles 里的信息，不要补充资料外内容。
2. 不要写得像汽车评测稿，不要写成参数说明书。
3. 除非用户明确要求技术稿，否则不要集中罗列数字、续航、电耗、补能、转弯直径等参数。
4. 优先写“这个车适合什么场景、传递什么价值、带来什么体验”，而不是罗列配置。
5. 每段最多只允许出现 1 个具体技术点或 1 组数据。
6. 语言要更像汽车公关传播稿，而不是媒体测评稿。
7. 不要堆砌“全面升级”“焕新而来”“重新定义”这类空话。
8. 除了 JSON，不要输出任何解释。
9. 正文要有传播感，但保持克制，不要像发布会口号。

用户需求：
{query}

fact sheet:
{fact_sheet_text}

传播切口：
{angles_text}

请严格输出下面这个 JSON 结构：
{{
  "lead": "",
  "body_paragraphs": [
    "",
    ""
  ],
  "social_copies": [
    "",
    ""
  ]
}}
"""

    paragraphs = _call_llm_json(prompt)

    if "lead" not in paragraphs or not isinstance(paragraphs["lead"], str):
        paragraphs["lead"] = ""

    if "body_paragraphs" not in paragraphs or not isinstance(paragraphs["body_paragraphs"], list):
        paragraphs["body_paragraphs"] = []

    if "social_copies" not in paragraphs or not isinstance(paragraphs["social_copies"], list):
        paragraphs["social_copies"] = []

    return paragraphs

def self_check_generated_output(
    query: str,
    fact_sheet: Dict[str, Any],
    angles: Dict[str, Any],
    titles: Dict[str, Any],
    paragraphs: Dict[str, Any],
) -> Dict[str, Any]:
    fact_sheet_text = json.dumps(fact_sheet, ensure_ascii=False, indent=2)
    angles_text = json.dumps(angles, ensure_ascii=False, indent=2)
    titles_text = json.dumps(titles, ensure_ascii=False, indent=2)
    paragraphs_text = json.dumps(paragraphs, ensure_ascii=False, indent=2)

    prompt = f"""
你是一名汽车公关审稿助手。请检查下面这批生成内容是否有问题。

检查重点：
1. 有没有超出资料明确内容的地方
2. 标题是否太像总结句、资讯稿、参数罗列
3. 正文是否像评测稿，不像PR稿
4. 有没有明显空泛套话
5. 除了 JSON，不要输出任何解释

用户需求：
{query}

fact sheet:
{fact_sheet_text}

angles:
{angles_text}

titles:
{titles_text}

paragraphs:
{paragraphs_text}

请严格输出下面这个 JSON 结构：
{{
  "needs_revision": false,
  "issues": [
    {{
      "type": "",
      "detail": ""
    }}
  ],
  "revision_advice": [
    ""
  ]
}}
"""

    check_result = _call_llm_json(prompt)

    if "needs_revision" not in check_result or not isinstance(check_result["needs_revision"], bool):
        check_result["needs_revision"] = False

    if "issues" not in check_result or not isinstance(check_result["issues"], list):
        check_result["issues"] = []

    if "revision_advice" not in check_result or not isinstance(check_result["revision_advice"], list):
        check_result["revision_advice"] = []

    return check_result


def postprocess_generate_result(result: Dict[str, Any]) -> Dict[str, Any]:
    banned_title_prefixes = ["如何", "看", "为什么"]
    banned_phrases = ["沉浸式", "私人影院", "重新定义", "无限可能"]
    technical_title_keywords = [
        "转弯直径", "后轮转向", "续航", "补能", "电耗", "kWh", "公里", "度"
    ]

    titles = result.get("titles", {}).get("titles", [])
    cleaned_titles = []
    for item in titles:
        title = item.get("title", "").strip()

        if "？" in title or title.startswith(tuple(banned_title_prefixes)):
            continue

        if sum(1 for kw in technical_title_keywords if kw in title) >= 2:
            continue

        for p in banned_phrases:
            title = title.replace(p, "")

        item["title"] = title.strip("：:，, ")
        if item["title"]:
            cleaned_titles.append(item)

    result["titles"]["titles"] = cleaned_titles[:4]

    paragraphs = result.get("paragraphs", {})
    lead = paragraphs.get("lead", "")
    body_paragraphs = paragraphs.get("body_paragraphs", [])
    social_copies = paragraphs.get("social_copies", [])

    def clean_text(text: str) -> str:
        for p in banned_phrases:
            text = text.replace(p, "")
        return text.strip()

    paragraphs["lead"] = clean_text(lead)
    paragraphs["body_paragraphs"] = [clean_text(x) for x in body_paragraphs]
    paragraphs["social_copies"] = [clean_text(x) for x in social_copies]

    result["paragraphs"] = paragraphs
    return result

def run_generate_pipeline(query: str, retrieved_chunks: List[Any]) -> Dict[str, Any]:
    fact_sheet = build_fact_sheet(query, retrieved_chunks)
    angles = generate_angles(query, fact_sheet)
    titles = generate_titles(query, fact_sheet, angles)
    paragraphs = generate_paragraphs(query, fact_sheet, angles)
    check_result = self_check_generated_output(
        query=query,
        fact_sheet=fact_sheet,
        angles=angles,
        titles=titles,
        paragraphs=paragraphs,
    )

    result = {
        "fact_sheet": fact_sheet,
        "angles": angles,
        "titles": titles,
        "paragraphs": paragraphs,
        "check_result": check_result,
    }

    result = postprocess_generate_result(result)
    return result

def format_generate_pipeline_result(result: Dict[str, Any]) -> str:
    lines = []

    angles = result.get("angles", {})
    titles = result.get("titles", {})
    paragraphs = result.get("paragraphs", {})
    check_result = result.get("check_result", {})

    lines.append("【传播主题】")
    main_theme = angles.get("main_theme", "")
    # 支持多个主题，每条一行
    for i, theme in enumerate(main_theme.strip().splitlines(),1):
        theme = theme.strip()
        if theme:
            lines.append(f"{i}. {theme}")
    lines.append("")

    lines.append("【传播切口】")
    for item in angles.get("angles", []):
        name = item.get("name", "")
        why = item.get("why_it_works", "")
        lines.append(f"- {name}：{why}")
    lines.append("")

    lines.append("【标题】")
    for item in titles.get("titles", []):
        title = item.get("title", "")
        tp = item.get("type", "")
        lines.append(f"- [{tp}] {title}")
    lines.append("")

    lines.append("【传播导语】")
    lines.append(paragraphs.get("lead", ""))
    lines.append("")

    lines.append("【正文】")
    for p in paragraphs.get("body_paragraphs", []):
        lines.append(p)
        lines.append("")

    lines.append("【社媒短文案】")
    for s in paragraphs.get("social_copies", []):
        lines.append(f"- {s}")
    lines.append("")

    lines.append("【自检】")
    lines.append(f"- 是否建议修订：{'是' if check_result.get('needs_revision') else '否'}")
    for issue in check_result.get("issues", []):
        lines.append(f"- {issue.get('type', '')}：{issue.get('detail', '')}")

    return "\n".join(lines)


def generate_core_pr(query: str, context: str) -> str:
    prompt = f"""
你是一名服务汽车品牌的中国公关编辑，正在基于内部资料撰写传播提案内容。

请基于以下资料完成输出。

【重要要求】
1. 只能使用资料中明确出现的信息，不要补充资料中没有出现的配置、参数、功能和结论。
2. “传播方向”必须是传播切口，不要写成“空间/智能/豪华/操控”这类卖点分类。
3. 不要输出任何“媒体标题”内容。
4. 不要输出“传播主题”之外的额外栏目。
5. 严格按照指定结构输出，不要增加新栏目。
6. 避免使用空泛AI套话，例如：
   - 引领未来
   - 重新定义
   - 开启新纪元
   - 完美融合
   - 颠覆行业
7. 语言要像真实公关内部讨论稿，具体、自然、可传播。
8. 尽量突出场景、对象、人群、出行方式、体验场景，而不是只罗列功能点。
9. 新闻稿段落必须基于资料，不要编造。
10. 社媒文案每条聚焦一个明确场景。

【你只能输出以下四个部分，且必须按此顺序】
传播主题：
传播方向（3条）：
新闻稿段落：
社媒文案（3条）：

【禁止输出】
- 媒体标题
- 标题建议
- 额外总结
- 说明文字

【传播方向写法要求】
每条都必须包含：
1. 一个切口标题
2. 一句解释

示例格式：
1. 切口标题
一句解释

【参考资料】
{context}

【用户需求】
{query}
""".strip()

    return call_llm(prompt)


# 用户需求 → 需要跑哪些步骤的映射
# 关键词匹配，命中哪些就跑哪些
DELIVERABLE_KEYWORDS = {
    "angles":     ["传播主题", "传播方向", "传播切口", "传播角度", "主题"],
    "titles":     ["标题", "媒体标题", "题目"],
    "lead":       ["导语", "开头", "引言"],
    "body":       ["正文", "新闻稿", "稿件", "段落"],
    "social":     ["社媒", "文案", "微博", "小红书", "朋友圈"],
}

def detect_deliverables(query: str) -> set[str]:
    """
    从 query 里识别用户想要什么。
    没有明确指定时，返回全部。
    """
    query_lower = query.lower()
    matched = set()

    for key, keywords in DELIVERABLE_KEYWORDS.items():
        for kw in keywords:
            if kw in query_lower:
                matched.add(key)
                break

    # 没有命中任何关键词 → 全部输出
    if not matched:
        matched = set(DELIVERABLE_KEYWORDS.keys())

    # 有标题/导语/正文/社媒，必须先有 angles（传播主题是基础）
    if matched & {"titles", "lead", "body", "social"}:
        matched.add("angles")

    return matched


def generate_pr(query: str, top_k: int = 5) -> str:
    retrieved_chunks = safe_search(query, top_k)
    deliverables = detect_deliverables(query)

    # 第一步：fact sheet 是所有后续步骤的基础，必须跑
    fact_sheet = build_fact_sheet(query, retrieved_chunks)

    # 第二步：angles（传播主题+切口），几乎所有情况都需要
    angles = generate_angles(query, fact_sheet) if "angles" in deliverables else {}

    # 第三步：按需并行跑剩余步骤
    from concurrent.futures import ThreadPoolExecutor

    titles_result = {}
    paragraphs_result = {}

    def run_titles():
        return generate_titles(query, fact_sheet, angles)

    def run_paragraphs():
        return generate_paragraphs(query, fact_sheet, angles)

    need_titles = "titles" in deliverables
    need_paragraphs = bool(deliverables & {"lead", "body", "social"})

    if need_titles and need_paragraphs:
        with ThreadPoolExecutor(max_workers=2) as executor:
            f_titles = executor.submit(run_titles)
            f_paragraphs = executor.submit(run_paragraphs)
            titles_result = f_titles.result()
            paragraphs_result = f_paragraphs.result()
    elif need_titles:
        titles_result = run_titles()
    elif need_paragraphs:
        paragraphs_result = run_paragraphs()

    # 第四步：按需格式化输出，只输出用户要的部分
    lines = []

    if "angles" in deliverables:
        lines.append("【传播主题】")
        lines.append(angles.get("main_theme", ""))
        lines.append("")

        # 只有用户明确要传播方向/切口时才输出
        if deliverables & {"angles"} and any(
            kw in query for kw in ["传播方向", "传播切口", "传播角度", "切口"]
        ):
            lines.append("【传播切口】")
            for item in angles.get("angles", []):
                name = item.get("name", "")
                why = item.get("why_it_works", "")
                lines.append(f"- {name}：{why}")
            lines.append("")

    if "titles" in deliverables and titles_result:
        lines.append("【标题】")
        for item in titles_result.get("titles", []):
            title = item.get("title", "")
            tp = item.get("type", "")
            lines.append(f"- [{tp}] {title}")
        lines.append("")

    if paragraphs_result:
        lead = paragraphs_result.get("lead", "")
        body = paragraphs_result.get("body_paragraphs", [])
        social = paragraphs_result.get("social_copies", [])

        if "lead" in deliverables and lead:
            lines.append("【传播导语】")
            lines.append(lead)
            lines.append("")

        if "body" in deliverables and body:
            lines.append("【正文】")
            for p in body:
                lines.append(p)
                lines.append("")

        if "social" in deliverables and social:
            lines.append("【社媒短文案】")
            for s in social:
                lines.append(f"- {s}")
            lines.append("")

    return "\n".join(lines).strip()

# ==============================
# Mode: check
# ==============================

def check_text(text: str) -> str:
    prompt = f"""
你是一名服务汽车品牌的中国公关编辑，请从“汽车公关审稿”的角度检查以下文本，并给出明确、可执行的修改建议。

【检查维度】
1. 错别字
2. 病句、不通顺、语序不自然
3. 不符合中国表达习惯或有翻译腔
4. 品牌名称、车型名称、技术术语、时间表达是否规范
5. 过于口语化，不适合正式 PR 文稿
6. 标点、数字、时间、空格、大小写、括号等格式问题
7. AI 味太重、表达空泛
8. 是否存在过于绝对、过满、缺乏依据的表述
9. 是否存在资料外扩写、把推测写成事实的风险
10. 是否更像卖点罗列，缺少传播切口
11. 是否存在传播或宣传风险措辞，例如：
   - 最
   - 唯一
   - 首个
   - 第一
   - 全面领先
   - 重新定义
   - 颠覆
12. 是否有品牌口径不统一、命名不统一、时间/时区写法不规范的问题
13. 车型名、技术术语是否符合品牌术语表的标准写法（若已提供术语表）

【特别要求】
- 不仅指出“错误”，也指出“在 PR 写作里值得注意的小点”
- 如果句子本身语法没错，但从汽车公关写作角度看不够稳妥，也请指出
- 如果内容已经基本没问题，也请给出 1-3 条“可进一步优化的小建议”
- 请尽量像一个有经验的公关同事在帮忙看稿，而不是只做语法检查
- 如涉及品牌、车型、技术术语，请优先按品牌官方写法（以术语表为准）和更稳妥的 PR 语气提出建议
- 如出现“德国时间”“中国时间”等口语说法，请优先提示是否应改为更正式的时区表达，例如“欧洲中部时间（CET）”“北京时间（UTC+8）”

【输出要求】
如果发现问题，请按以下格式逐条列出：

问题类型：
原句：
问题说明：
修改建议：

最后请单独增加一个部分：

PR写作提醒：
- ...
- ...
- ...

如果整体没有明显问题，也请明确写：
“未发现明显问题”

然后再补充“PR写作提醒”。

【待检查文本】
{text}
""".strip()

    return call_llm(prompt)

# ==============================
# Mode: normalize
# ==============================

def normalize_pr(text: str) -> str:
    normalized = normalize_text(text)
    normalized = apply_model_name_rules(normalized)
    normalized = apply_mb_term_rules(normalized)

    prompt = f"""
你是一名汽车品牌公关编辑。

下面这段文本已经过一轮基础术语替换，请继续做“口语 → 正式书面表达”的规范化处理。

【要求】
1. 保持原意不变
2. 改成更适合汽车公关稿、活动方案、沟通邮件中的正式表达
3. 优先使用准确、规范、书面的说法
4. 避免口语化、随意化表达
5. 只输出最终优化后的版本，不要解释
6. 车型名、技术术语请按品牌术语表的标准写法（若已提供术语表）。

【文本】
{normalized}
""".strip()

    return call_llm(prompt)


# ==============================
# Mode: rewrite
# ==============================

def rewrite_text(text: str) -> str:
    text = apply_model_name_rules(text)
    prompt = f"""
你是一名汽车品牌公关编辑。

请将下面这段文字改写为更符合中国汽车品牌公关语境的表达。

【改写要求】
1. 保持原意不变
2. 提升书面感、准确性和规范性
3. 避免口语化表达
4. 避免空泛 AI 腔
5. 如果原文明显不够像正式 PR 表达，请改得更专业
6. 只输出改写后的最终版本，不要解释
7. 如提及 VLE，统一写作“全新纯电VLE”，不要仅写”VLE”。

【原文】
{text}
""".strip()

    return call_llm(prompt)


# ==============================
# CLI
# ==============================

def main() -> None:
    parser = argparse.ArgumentParser(description="PR Agent for automotive PR tasks")

    parser.add_argument(
        "--mode",
        required=True,
        choices=["generate", "check", "normalize", "rewrite"],
        help="运行模式：generate / check / normalize / rewrite",
    )
    parser.add_argument("--query", help="generate 模式下的用户需求")
    parser.add_argument("--text", help="check / normalize / rewrite 模式下的输入文本")
    parser.add_argument("--top_k", type=int, default=5, help="generate 模式下检索条数，默认 5")

    args = parser.parse_args()

    try:
        if args.mode == "generate":
            if not args.query:
                raise ValueError("generate 模式必须提供 --query")
            result = generate_pr(args.query, args.top_k)

        elif args.mode == "check":
            if not args.text:
                raise ValueError("check 模式必须提供 --text")
            result = check_text(args.text)

        elif args.mode == "normalize":
            if not args.text:
                raise ValueError("normalize 模式必须提供 --text")
            result = normalize_pr(args.text)

        elif args.mode == "rewrite":
            if not args.text:
                raise ValueError("rewrite 模式必须提供 --text")
            result = rewrite_text(args.text)

        else:
            raise ValueError(f"未知 mode: {args.mode}")

        print(result)

    except Exception as e:
        print(f"运行失败：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
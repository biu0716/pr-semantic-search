"""
术语表 service。

逻辑和原来 streamlit_app.py 里完全一致，
唯一改动：parse_terms_table 接收 (file_bytes, filename) 而不是 UploadedFile。
"""

import re
from io import BytesIO
from pathlib import Path

import pandas as pd


def normalize_column_name(name: str) -> str:
    return (
        str(name)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )


def parse_terms_table(file_bytes: bytes, filename: str) -> dict[str, str]:
    suffix = Path(filename).suffix.lower()
    buffer = BytesIO(file_bytes)

    if suffix == ".csv":
        df = pd.read_csv(buffer)
    elif suffix in [".xlsx", ".xls"]:
        df = pd.read_excel(buffer)
    else:
        raise ValueError("术语表仅支持 csv / xlsx / xls")

    if df.empty:
        raise ValueError("术语表为空")

    df = df.dropna(how="all").copy()
    df.columns = [str(col).strip() for col in df.columns]

    normalized_columns = {
        normalize_column_name(col): col for col in df.columns
    }

    source_aliases = ["错误写法", "原写法", "原词", "术语", "待替换", "before", "source", "from"]
    target_aliases = ["标准写法", "规范写法", "官方写法", "目标写法", "替换后", "after", "target", "to"]

    source_col = None
    target_col = None

    for alias in source_aliases:
        if normalize_column_name(alias) in normalized_columns:
            source_col = normalized_columns[normalize_column_name(alias)]
            break

    for alias in target_aliases:
        if normalize_column_name(alias) in normalized_columns:
            target_col = normalized_columns[normalize_column_name(alias)]
            break

    if source_col is None or target_col is None:
        if len(df.columns) >= 2:
            source_col = df.columns[0]
            target_col = df.columns[1]
        else:
            raise ValueError("术语表至少需要两列：原写法 / 标准写法")

    rules: dict[str, str] = {}
    for _, row in df[[source_col, target_col]].dropna().iterrows():
        raw_source = str(row[source_col]).strip()
        raw_target = str(row[target_col]).strip()

        if raw_source and raw_target:
            rules[raw_source] = raw_target

    if not rules:
        raise ValueError("术语表中没有可用规则")

    return rules


def apply_extra_term_rules(text: str, extra_terms: dict[str, str] | None = None) -> str:
    extra_terms = extra_terms or {}
    if not text or not extra_terms:
        return text

    updated_text = text
    for raw_source, raw_target in extra_terms.items():
        if not raw_source:
            continue
        updated_text = re.sub(re.escape(raw_source), raw_target, updated_text)

    return updated_text


def build_terms_prompt_block(extra_terms: dict[str, str] | None = None) -> str:
    extra_terms = extra_terms or {}
    if not extra_terms:
        return "【术语表】\n当前未上传术语表。"

    lines = ["【术语表】", "如涉及以下写法，请优先遵循："]
    for raw_source, raw_target in extra_terms.items():
        lines.append(f"- {raw_source} → {raw_target}")

    return "\n".join(lines)

import json
import re
from datetime import datetime
from pathlib import Path

import faiss
import numpy as np

from src.config import settings
from src.loaders import read_docx
from src.chunker import chunk_text
from src.embedder import embed_texts


# ==============================
# 基础配置
# ==============================

CHUNK_SIZE = 1200

# 是否跳过“明显很脏”的 chunk
SKIP_NOISY_CHUNKS = True

# 质量分低于这个阈值，且被判断为 noisy，就不入主索引
NOISY_THRESHOLD = 0.45


# ==============================
# 规则字典
# ==============================

DOC_TYPE_PRIORITY = {
    # rerank会用到
    "official_pr": 3,
    # 正式新闻稿最优先
    "product_material": 2,
    # 产品资料其次
    "subtitle": 1,
    "meeting_note": 1,
    "other": 0,
}

DOC_TYPE_CN = {
    "official_pr": "正式新闻稿",
    "product_material": "产品资料",
    "subtitle": "字幕稿",
    "meeting_note": "会议纪要",
    "other": "其他资料",
}

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
    判断车型代号是否真的出现在文本里（带边界）。

    为什么不用简单的 `pattern in text`：
    "CLA" 这种三字母代号会命中 "S-CLASS" 里的 c-l-a，
    把 S 级文档误判成 CLA，进而被打成 UNKNOWN。
    这里要求英文代号的前后都不是英文字母，
    所以 "S-CLASS" 里的 "CLA" 不再算命中，
    而 "奔驰CLA"、"CLA 260" 这类真正的 CLA 照常识别。
    中文代号（如 S级）前后不会紧挨英文字母，匹配不受影响。
    """
    p = pattern.upper()
    return re.search(rf"(?<![A-Za-z]){re.escape(p)}(?![A-Za-z])", text_upper) is not None


# ==============================
# 读取文件
# ==============================

def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")
# 把txt文件读成字符串

def collect_target_files(root: Path) -> list[Path]:
    """
    默认扫描目录下所有 .docx / .txt 文件。
    """
    docx_files = sorted(root.rglob("*.docx"))
    txt_files = sorted(root.rglob("*.txt"))
    return docx_files + txt_files


def read_file(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix == ".docx":
        return read_docx(path)

    if suffix == ".txt":
        return read_text_file(path)

    raise ValueError(f"不支持的文件类型：{suffix}")


# ==============================
# metadata 提取
# ==============================

def infer_car_model(file_path: Path, text: str) -> tuple[str, list[str]]:
    """
    返回 (主车型, 关联车型列表)。

    主车型判断优先级：
    1. 非ref文档：看路径（文件夹部分，不含文件名）
    2. ref文档：看文件名
    3. 以上都找不到：看文件名（非ref也试一次）
    4. 还找不到：返回 UNKNOWN

    正文里顺带提到的其他车型 → 进 related_models，不影响主车型。

    为什么这样改：
    原来的逻辑用 str(file_path) 找车型，会把正文路径和文件名混在一起，
    更大的问题是：没有 related_models，搜索层无法区分
    "这个文档是关于CLA的" 和 "这个文档里顺带提到了CLA"。
    """
    file_name_upper = file_path.name.upper()
    path_parts_upper = [part.upper() for part in file_path.parts]

    is_ref_doc = "REF" in path_parts_upper

    def get_hits(text_to_check: str) -> list[str]:
        hits = []
        for pattern, label in MODEL_PATTERNS:
            if model_pattern_hit(pattern, text_to_check):
                hits.append(label)
        return list(dict.fromkeys(hits))  # 去重，保留顺序

    def find_related(primary: str) -> list[str]:
        """从正文里找所有车型，排除主车型，作为关联车型。"""
        if not text:
            return []
        text_upper = text.upper()
        related = []
        for pattern, label in MODEL_PATTERNS:
            if label == primary:
                continue
            if model_pattern_hit(pattern, text_upper):
                related.append(label)
        return list(dict.fromkeys(related))

    # -------- ref 文档：只看文件名 --------
    if is_ref_doc:
        file_hits = get_hits(file_name_upper)
        if len(file_hits) == 1:
            return file_hits[0], find_related(file_hits[0])
        # 文件名里有多个车型 or 没有 → UNKNOWN
        return "UNKNOWN", []

    # -------- 非ref文档：先看路径中的文件夹部分（不含文件名）--------
    # 只取文件夹部分，避免文件名里的车型污染路径判断
    folder_parts = path_parts_upper[:-1]  # 去掉最后一个（文件名）
    folder_text = " ".join(folder_parts)
    folder_hits = get_hits(folder_text)

    if len(folder_hits) == 1:
        return folder_hits[0], find_related(folder_hits[0])

    # 文件夹里有多个车型（例如：/CLA/EQS对比/），返回UNKNOWN
    if len(folder_hits) > 1:
        return "UNKNOWN", []

    # -------- 文件夹里没找到，再看文件名 --------
    file_hits = get_hits(file_name_upper)
    if len(file_hits) == 1:
        return file_hits[0], find_related(file_hits[0])

    return "UNKNOWN", []


def infer_doc_type(file_path: Path) -> str:
    """
    资料类型判断优先级：
    1. 先看路径（更可靠）
    2. 再看文件名
    """
    path_text = str(file_path).lower()
    file_name = file_path.name.lower()

    # ---------- 1) 路径优先 ----------
    # 会议录音 / 转写结果 优先判成会议纪要类
    if "会议录音" in path_text or "转写结果" in path_text or "transcript" in path_text:
        return "meeting_note"

    # 修改建议类，不属于正式新闻稿
    # 如果你暂时不想单独建 review_note 类型，就先归到 other
    if "修改建议" in path_text or "comment" in file_name or "comments" in file_name:
        return "other"

    # 字幕稿
    if "字幕" in path_text or "subtitle" in path_text:
        return "subtitle"

    # 产品资料
    if "产品资料" in path_text or "product" in path_text:
        return "product_material"

    # ---------- 2) 再看文件名 ----------
    if "字幕" in file_name or "subtitle" in file_name:
        return "subtitle"

    if "产品资料" in file_name or "product" in file_name:
        return "product_material"

    if "纪要" in file_name or "meeting" in file_name:
        return "meeting_note"

    if "新闻稿" in file_name or "press" in file_name:
        return "official_pr"

    return "other"


def get_source_priority(doc_type: str) -> int:
# 根据资料类型，返回一个优先级分数
    return DOC_TYPE_PRIORITY.get(doc_type, 0)


def extract_version_label(file_name: str) -> str:
    """
    从文件名里提取版本标签，比如 v4 / final / draft / BI / CN
    """
    lower_name = file_name.lower()

    labels = []

    match_v = re.search(r"\bv\d+\b", lower_name)
    if match_v:
        labels.append(match_v.group(0))

    if "final" in lower_name or "终版" in file_name or "最终" in file_name:
        labels.append("final")

    if "draft" in lower_name or "草稿" in file_name:
        labels.append("draft")

    if re.search(r"\bbi\b", lower_name):
        labels.append("BI")

    if re.search(r"\bcn\b", lower_name) or "中文" in file_name:
        labels.append("CN")

    return "|".join(labels) if labels else ""


def extract_version_date(path: Path) -> str:
    """
    优先从文件名提日期。
    支持：
    - 20260309
    - 2026-03-09
    - 0309（默认补文件修改年份）
    如果文件名里没有，就退回文件修改时间。
    """
    file_name = path.stem

    # 先找 8 位或带分隔符的完整日期
    match_full = re.search(r"(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)", file_name)
    if match_full:
        year, month, day = match_full.groups()
        return f"{year}-{month}-{day}"

    # 再找 4 位月日，例如 0309
    match_md = re.search(r"(?<!\d)(0[1-9]|1[0-2])([0-2]\d|3[01])(?!\d)", file_name)
    if match_md:
        month, day = match_md.groups()
        year = datetime.fromtimestamp(path.stat().st_mtime).year
        return f"{year}-{month}-{day}"

    # 最后退回文件修改时间
    dt = datetime.fromtimestamp(path.stat().st_mtime)
    return dt.strftime("%Y-%m-%d")


def infer_version_group(file_name: str, car_model: str, doc_type: str) -> str:
    """
    给“同主题资料”做一个最小归组。
    先用简单规则，不追求特别智能。
    """
    lower_name = file_name.lower()

    if "首秀" in file_name or "world premiere" in lower_name or "premiere" in lower_name:
        group = "world_premiere"
    elif "车展" in file_name or "auto show" in lower_name:
        group = "auto_show"
    elif "上市" in file_name or "发布" in file_name or "launch" in lower_name:
        group = "launch"
    else:
        group = doc_type

    if car_model != "UNKNOWN":
        return f"{car_model.lower()}_{group}"

    return group


# ==============================
# 文本质量判断
# ==============================

def estimate_quality_score(text: str) -> float:
    """
    一个很轻的启发式质量分：
    1. 越脏、越碎、越重复，分越低
    2. 先做 alpha 版，不追求特别精确
    """
    score = 1.0
    text = text or ""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    total_lines = max(len(lines), 1)
    total_chars = max(len(text), 1)

    short_line_ratio = sum(1 for line in lines if len(line) <= 6) / total_lines
    repeated_line_ratio = 1 - len(set(lines)) / total_lines
    line_break_ratio = text.count("\n") / total_chars

    weird_chars = re.findall(r"[�□■◆▌▍▎▏¤�]", text)
    weird_char_ratio = len(weird_chars) / total_chars

    if len(text) < 80:
        score -= 0.10

    if line_break_ratio > 0.04:
        score -= 0.10

    if short_line_ratio > 0.35:
        score -= 0.15

    if repeated_line_ratio > 0.18:
        score -= 0.20

    if weird_char_ratio > 0.005:
        score -= 0.25

    if re.search(r"(.)\1{7,}", text):
        score -= 0.10

    score = max(0.0, min(score, 1.0))
    return round(score, 2)


def is_noisy_chunk(text: str, quality_score: float) -> bool:
    """
    先用简单规则判断是否是明显 noisy 的 chunk
    """
    if quality_score < 0.60:
        return True

    if text.count("\n") > 18 and len(text) < 500:
        return True

    return False


# ==============================
# embedding 文本构造
# ==============================

def build_chunk_for_embedding(
    chunk: str,
    *,
    file_name: str,
    car_model: str,
    doc_type: str,
    version_group: str,
) -> str:
    """
    不再只拼原始文件名；
    先拼更干净的业务标签，再拼文件名和正文。
    """
    prefix_parts = []

    if car_model != "UNKNOWN":
        prefix_parts.append(f"车型：{car_model}")

    prefix_parts.append(f"资料类型：{DOC_TYPE_CN.get(doc_type, '其他资料')}")

    if version_group:
        prefix_parts.append(f"主题组：{version_group}")

    prefix_parts.append(f"文件名：{file_name}")

    prefix = "\n".join(prefix_parts)
    return f"{prefix}\n\n{chunk}"


# ==============================
# 主流程
# ==============================

def build_index(root=None, index_path=None, meta_path=None):
    root = Path(root) if root else Path(settings.ONEDRIVE_ROOT)
    index_path = Path(index_path) if index_path else Path(settings.INDEX_PATH)
    meta_path = Path(meta_path) if meta_path else Path(settings.META_PATH)

    if not root.exists():
        raise RuntimeError(f"知识库目录不存在：{root}")

    target_files = collect_target_files(root)

    if not target_files:
        raise RuntimeError(f"目录下未找到可处理文件：{root}")

    all_chunks = []
    # 存的是要拿去做embedding的文本
    metadata = []
    # 存的是每个chunk的说明书

    skipped_empty_files = 0
    skipped_unreadable_files = 0
    skipped_noisy_chunks = 0

    print("🔍 开始扫描目录...")
    print(f"目录：{root}")
    print(f"发现文件数：{len(target_files)}")

    for p in target_files:
    # 遍历每个文件
        print("处理文件：", p)

        try:
            text = read_file(p)
            # 读取文件
        except Exception as e:
            print(f"⚠️ 跳过无法读取的文件：{p}")
            print(f"   原因：{e}")
            skipped_unreadable_files += 1
            continue

        text = text.strip()
        if not text:
            print(f"⚠️ 文件内容为空，跳过：{p}")
            skipped_empty_files += 1
            continue
        # 先提取文件级信息
        # 这些信息后面会复制到这个文件切出来的每个chunk上
        file_name = p.name
        car_model, related_models = infer_car_model(p, text)
        doc_type = infer_doc_type(p)
        source_priority = get_source_priority(doc_type)
        version_date = extract_version_date(p)
        version_label = extract_version_label(file_name)
        version_group = infer_version_group(file_name, car_model, doc_type)

        chunks = chunk_text(text, CHUNK_SIZE)
        # 把长文本切成1200左右一段一段

        if not chunks:
            print(f"⚠️ 未切出有效 chunk，跳过：{p}")
            continue

        print(f"  生成 chunk 数：{len(chunks)}")
        print(f"  车型：{car_model} | 资料类型：{doc_type} | 版本日期：{version_date}")

        for i, chunk in enumerate(chunks):
        # 对每个chunk做4件事：
            # 第一步：打质量分
            quality_score = estimate_quality_score(chunk)
            noisy = is_noisy_chunk(chunk, quality_score)

            # 第二步：太脏就跳过
            if SKIP_NOISY_CHUNKS and noisy and quality_score <= NOISY_THRESHOLD:
                skipped_noisy_chunks += 1
                continue

            # 第三步：构造embedding文本
            tagged_chunk = build_chunk_for_embedding(
                chunk,
                file_name=file_name,
                car_model=car_model,
                doc_type=doc_type,
                version_group=version_group,
            )

            all_chunks.append(tagged_chunk)

            metadata.append({
            # 第四步：存metadata
                "file": str(p),
                "file_name": file_name,
                "chunk_id": i,
                "text": chunk,
                "car_model": car_model,
                "related_models": related_models,
                "doc_type": doc_type,
                "source_priority": source_priority,
                "version_date": version_date,
                "version_label": version_label,
                "version_group": version_group,
                "quality_score": quality_score,
                "is_noisy": noisy,
            })

    print("总 chunk 数：", len(all_chunks))
    print("跳过的空文件数：", skipped_empty_files)
    print("跳过的不可读文件数：", skipped_unreadable_files)
    print("跳过的 noisy chunk 数：", skipped_noisy_chunks)

    if len(all_chunks) == 0:
        raise RuntimeError("没有扫描到任何可用 chunk，请检查文件路径或文档内容。")

    print("🧠 开始生成向量...")

    vectors = []
    batch_size = 16

    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        print(f"embedding 进度：{i + 1}/{len(all_chunks)}")
        vecs = embed_texts(batch)
        vectors.extend(vecs)
        # 把所有chunk分批送去做embedding

    vectors = np.array(vectors, dtype="float32")

    dim = vectors.shape[1]
    faiss.normalize_L2(vectors)
    # 向量归一化：把所有文档向量长度统一成1.这样后面用IndexFlatIP检索时，更接近按cosine similarity排序。

    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.parent.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(index_path))

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print("✅ 构建完成")
    print("向量数量：", len(vectors))
    print("索引文件：", index_path)
    print("元数据文件：", meta_path)


if __name__ == "__main__":
    build_index()
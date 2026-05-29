import re


def clean_text(text: str) -> str:
    """
    文本清洗：
    1. 统一换行符
    2. 去掉每行首尾空格
    3. 【新加】过滤掉明显是噪声的行
    4. 压缩连续空行
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = []
    for line in text.split("\n"):
        line = line.strip()

        # 【新加】过滤纯数字行
        # docx 里图片ID、对象编号通常是一串纯数字，没有任何意义
        # 例如：1454156985、20231009
        # 判断标准：整行只有数字（允许夹空格），且长度超过5位
        if re.fullmatch(r"[\d\s]{5,}", line):
            continue

        # 【新加】过滤明显是乱码/特殊符号的行
        # 整行几乎全是非中文非字母的奇怪字符
        if line and len(line) <= 10:
            useful_chars = re.findall(r"[\u4e00-\u9fff\w]", line)
            if len(useful_chars) == 0:
                continue

        lines.append(line)

    text = "\n".join(lines)

    # 连续3个以上换行，压成2个
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def split_into_paragraphs(text: str) -> list[str]:
    """
    改动：在按空行切段之前，先把【】段落标记转成空行。
    这样"【安全很靠谱】..."、"【智能很能打】..."这类结构
    就会被识别成独立段落，不会再变成一整块。
    """
    # 【改动】把【xxx】前面插一个空行，让它成为段落分隔符
    # 例如：...安全细节【智能很能打】...
    # 变成：...安全细节\n\n【智能很能打】...
    text = re.sub(r"(?<!\n)【", "\n\n【", text)

    # 同理，其他常见的结构标记也处理一下
    # 比如 "一、" "二、" "三、" 这类章节号
    text = re.sub(r"(?<!\n)([一二三四五六七八九十]+、)", r"\n\n\1", text)

    raw_paragraphs = re.split(r"\n\s*\n", text)

    paragraphs = []
    for para in raw_paragraphs:
        para = para.strip()
        if not para:
            continue

        lines = [line.strip() for line in para.split("\n") if line.strip()]

        if not lines:
            continue

        merged = lines[0]
        for line in lines[1:]:
            last_char = merged[-1] if merged else ""
            first_char = line[0] if line else ""
            is_cjk_boundary = (
                "\u4e00" <= last_char <= "\u9fff" or
                "\u4e00" <= first_char <= "\u9fff"
            )
            if is_cjk_boundary:
                merged += line
            else:
                merged += " " + line

        if merged:
            paragraphs.append(merged)

    return paragraphs


def split_into_sentences(text: str) -> list[str]:
    """
    按句号、问号、感叹号、分号简单分句。
    （和你原来一样，没有改动）
    """
    text = text.strip()
    if not text:
        return []

    parts = re.findall(r".+?(?:[。！？!?；;]|$)", text)
    sentences = [p.strip() for p in parts if p.strip()]
    return sentences


def chunk_text(text: str, max_chars: int = 1000, overlap: int = 0) -> list[str]:
    """
    彻底重写组装逻辑：
    - 内层：按句子切好的 unit 已经保证末尾是句子边界
    - 外层：只合并，不硬切，chunk 永远在句子边界结束
    """
    text = clean_text(text)
    paragraphs = split_into_paragraphs(text)

    if not paragraphs:
        return []

    # 第一步：把所有段落切成以句子边界结尾的 unit
    units = []

    for para in paragraphs:
        if len(para) <= max_chars:
            units.append(para)
            continue

        sentences = split_into_sentences(para)

        if not sentences:
            # 没有句子边界：按长度硬切，这是唯一允许硬切的地方
            for i in range(0, len(para), max_chars):
                units.append(para[i:i + max_chars])
            continue

        current = ""
        for sent in sentences:
            if len(current) + len(sent) <= max_chars:
                current += sent
            else:
                if current:
                    units.append(current.strip())  # 末尾一定是句子边界 ✓
                if len(sent) > max_chars:
                    # 单句本身超长：硬切，没有更好的办法
                    for i in range(0, len(sent), max_chars):
                        units.append(sent[i:i + max_chars])
                    current = ""
                else:
                    current = sent
        if current.strip():
            units.append(current.strip())

    # 第二步：合并 unit，但绝不跨 unit 硬切
    # 每个 unit 已经在句子边界结尾，合并后 chunk 也在句子边界结尾
    chunks = []
    current_chunk = ""

    for unit in units:
        if not current_chunk:
            current_chunk = unit
        elif len(current_chunk) + len(unit) <= max_chars:
            current_chunk += unit
        else:
            # 装不下了，保存当前 chunk（末尾是句子边界）
            chunks.append(current_chunk.strip())
            current_chunk = unit  # 新 chunk 从这个 unit 开始

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


"""
文档读取 service。

和原来 streamlit_app.py 里的 read_uploaded_text 逻辑完全一致，
唯一改动：不再接收 Streamlit 的 UploadedFile 对象，
改成接收 (file_bytes, filename)，这样任何前端都能调用。
"""

from io import BytesIO
from pathlib import Path

from docx import Document


def read_uploaded_text(file_bytes: bytes, filename: str) -> str:
    """把上传的 txt / docx 读成纯文本。"""
    suffix = Path(filename).suffix.lower()

    if suffix == ".txt":
        for encoding in ["utf-8", "utf-8-sig", "gb18030", "gbk"]:
            try:
                return file_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("txt 文件编码无法识别，建议保存为 UTF-8 后重试")

    if suffix == ".docx":
        doc = Document(BytesIO(file_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)

    raise ValueError("暂不支持的文件类型，仅支持 txt / docx")


def build_uploaded_context(text: str, source_name: str) -> str:
    text = text.strip()
    if not text:
        return "未读取到上传资料内容。"
    return f"[上传资料 | 来源: {source_name}]\n{text}"

import os
from docx import Document
from PyPDF2 import PdfReader
from tqdm import tqdm

# ====== 你的PR资料路径 ======
KNOWLEDGE_PATH = "/Users/biu/OneDrive/PR_Knowledge"

# ====== 过滤无用文件夹关键词 ======
EXCLUDE_KEYWORDS = [
    "old",
    "ref",
    "录音",
    "报销",
    "字体",
    "图片",
    "模板",
    "速记"
]

def should_exclude(path):
    for keyword in EXCLUDE_KEYWORDS:
        if keyword in path:
            return True
    return False

def read_docx(path):
    try:
        doc = Document(path)
        return "\n".join([p.text for p in doc.paragraphs])
    except:
        return ""

def read_pdf(path):
    try:
        reader = PdfReader(path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except:
        return ""

def collect_documents():
    documents = []
    for root, dirs, files in os.walk(KNOWLEDGE_PATH):
        if should_exclude(root):
            continue

        for file in files:
            full_path = os.path.join(root, file)

            if should_exclude(full_path):
                continue

            if file.endswith(".docx"):
                text = read_docx(full_path)
            elif file.endswith(".pdf"):
                text = read_pdf(full_path)
            else:
                continue

            if text.strip():
                documents.append({
                    "path": full_path,
                    "content": text
                })

    return documents


if __name__ == "__main__":
    print("开始扫描PR资料库...")
    docs = collect_documents()
    print(f"共读取 {len(docs)} 份文档")
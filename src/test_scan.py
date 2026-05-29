from src.config import settings
from src.loaders import read_docx
from src.chunker import chunk_text
from pathlib import Path

root = Path(settings.ONEDRIVE_ROOT)

print("扫描目录：", root)

for p in root.rglob("*.docx"):
    print("\n发现文件：", p)

    text = read_docx(p)
    print("原始长度：", len(text))

    chunks = chunk_text(text, 800, 120)
    print("切块数量：", len(chunks))

    print("\n第一块前200字：")
    print(chunks[0][:200])
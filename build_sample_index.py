"""
构建「脱敏示例索引」。

它会扫描 data/sample_docs/ 里的虚构品牌素材，
生成示例索引到 data/sample/index.faiss 和 data/sample/meta.json，
不会动你的真实索引（data/index.faiss）。

用法（在项目根目录、激活了 .venv311 之后）：
    python build_sample_index.py
"""

from pathlib import Path
from src.indexer import build_index

ROOT = Path("data/sample_docs")
INDEX = Path("data/sample/index.faiss")
META = Path("data/sample/meta.json")

if __name__ == "__main__":
    print("📦 正在构建脱敏示例索引（不影响你的真实索引）...")
    build_index(root=ROOT, index_path=INDEX, meta_path=META)
    print("\n🎉 示例索引已生成：")
    print("   ", INDEX)
    print("   ", META)
    print("提示：线上 demo 会用这套示例索引；你的真实索引仍在 data/index.faiss 不变。")

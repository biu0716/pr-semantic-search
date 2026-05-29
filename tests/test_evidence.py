# test_evidence.py
from src.evidence import build_evidence_pack

dummy_results = [
    {"chunk_id": "c1", "source": "a.docx", "score": 0.91, "text": "这是第一段内容……" * 5},
    {"chunk_id": "c2", "source": "b.docx", "score": 0.88, "text": "这是第二段内容……" * 5},
    {"chunk_id": "c3", "source": "a.docx", "score": 0.87, "text": "这是第一段内容……" * 5},  # 故意重复
]

pack = build_evidence_pack(dummy_results, query="VLE 中国市场传播重点", max_evidence=12, dedup=True)
print(pack)
import os
from dataclasses import dataclass

@dataclass
class Settings:
    ONEDRIVE_ROOT: str = r"C:\Users\biu\OneDrive\PR_Knowledge"

    EMBEDDING_BASE_URL: str = "https://api.openai.com/v1"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    INDEX_PATH: str = os.path.join("data", "index.faiss")
    META_PATH: str = os.path.join("data", "meta.jsonl")

    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 120

settings = Settings()
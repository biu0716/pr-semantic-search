import os
from dataclasses import dataclass

@dataclass
class Settings:
    ONEDRIVE_ROOT: str = r"C:\Users\biu\OneDrive\PR_Knowledge"

    EMBEDDING_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    EMBEDDING_API_KEY: str = "668c9345b0664170b967322aad92ba31.CegvE6kJvsZYXYf5"
    EMBEDDING_MODEL: str = "embedding-2"

    # 👇 把这两行加上
    INDEX_PATH: str = os.path.join("data", "index.faiss")
    META_PATH: str = os.path.join("data", "meta.json")

settings = Settings()
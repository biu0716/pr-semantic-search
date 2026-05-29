import os
from pathlib import Path
from dataclasses import dataclass, field

# =========================
# 基础路径
# =========================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# 你现在固定使用的知识库目录
DEFAULT_ONEDRIVE_ROOT = "/Users/biu/Library/CloudStorage/OneDrive-个人/知识库"

# =========================
# Provider 配置
# =========================
ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
OPENAI_BASE_URL = "https://api.openai.com/v1"
AIHUBMIX_BASE_URL = "https://aihubmix.com/v1"

DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", "aihubmix").lower()

DEFAULT_ZHIPU_CHAT_MODEL = "glm-4-flash"
DEFAULT_OPENAI_CHAT_MODEL = "gpt-5-mini"
DEFAULT_AIHUBMIX_CHAT_MODEL = "gpt-5.3-chat-latest"

DEFAULT_ZHIPU_EMBEDDING_MODEL = "embedding-3"
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_LOCAL_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"

# =========================
# Key 获取
# =========================
def get_zhipu_api_key() -> str:
    api_key = os.getenv("ZHIPU_API_KEY") or os.getenv("ZAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "未读取到智谱 API Key。\n"
            "请先执行：\n"
            "export ZHIPU_API_KEY='你的key'"
        )
    return api_key

def get_openai_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "未读取到 OpenAI API Key。\n"
            "请先执行：\n"
            "export OPENAI_API_KEY='你的key'"
        )
    return api_key

def get_aihubmix_api_key() -> str:
    api_key = os.getenv("AIHUBMIX_API_KEY")
    if not api_key:
        raise RuntimeError(
            "未读取到 AIHubMix API Key。\n"
            "请先执行：\n"
            "export AIHUBMIX_API_KEY='你的key'"
        )
    return api_key

# =========================
# Provider / Model
# =========================
def get_provider() -> str:
    provider = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).lower()
    if provider not in {"zhipu", "openai", "aihubmix"}:
        raise RuntimeError(
            f"不支持的 LLM_PROVIDER: {provider}，请使用 zhipu / openai / aihubmix"
        )
    return provider

def get_api_key(provider: str | None = None) -> str:
    provider = provider or get_provider()

    if provider == "zhipu":
        return get_zhipu_api_key()
    if provider == "openai":
        return get_openai_api_key()
    if provider == "aihubmix":
        return get_aihubmix_api_key()

    raise RuntimeError(f"未知 provider: {provider}")

def get_base_url(provider: str | None = None) -> str:
    provider = provider or get_provider()

    if provider == "zhipu":
        return ZHIPU_BASE_URL
    if provider == "openai":
        return OPENAI_BASE_URL
    if provider == "aihubmix":
        return AIHUBMIX_BASE_URL

    raise RuntimeError(f"未知 provider: {provider}")

def get_chat_model(provider: str | None = None) -> str:
    provider = provider or get_provider()

    env_model = os.getenv("CHAT_MODEL") or os.getenv("AIHUBMIX_MODEL")
    if env_model:
        return env_model

    if provider == "zhipu":
        return DEFAULT_ZHIPU_CHAT_MODEL
    if provider == "openai":
        return DEFAULT_OPENAI_CHAT_MODEL
    if provider == "aihubmix":
        return DEFAULT_AIHUBMIX_CHAT_MODEL

    raise RuntimeError(f"未知 provider: {provider}")

def get_embedding_provider() -> str:
    return os.getenv("EMBEDDING_PROVIDER", "local").lower()

def get_embedding_model(provider: str | None = None) -> str:
    provider = provider or get_embedding_provider()

    env_model = os.getenv("EMBEDDING_MODEL")
    if env_model:
        return env_model

    if provider == "local":
        return DEFAULT_LOCAL_EMBEDDING_MODEL
    if provider == "zhipu":
        return DEFAULT_ZHIPU_EMBEDDING_MODEL
    if provider == "openai":
        return DEFAULT_OPENAI_EMBEDDING_MODEL

    raise RuntimeError(f"未知 embedding provider: {provider}")

def get_embedding_api_key(provider: str | None = None) -> str:
    provider = provider or get_embedding_provider()

    if provider == "local":
        return ""
    if provider == "zhipu":
        return get_zhipu_api_key()
    if provider == "openai":
        return get_openai_api_key()

    raise RuntimeError(f"未知 embedding provider: {provider}")

def get_embedding_base_url(provider: str | None = None) -> str:
    provider = provider or get_embedding_provider()

    if provider == "local":
        return ""
    if provider == "zhipu":
        return ZHIPU_BASE_URL
    if provider == "openai":
        return OPENAI_BASE_URL

    raise RuntimeError(f"未知 embedding provider: {provider}")

# =========================
# Settings
# =========================
@dataclass
class Settings:
    PROJECT_ROOT: Path = PROJECT_ROOT
    DATA_DIR: Path = DATA_DIR

    # 知识库目录
    ONEDRIVE_ROOT: str = os.getenv("ONEDRIVE_ROOT", DEFAULT_ONEDRIVE_ROOT)

    # 索引文件
    INDEX_PATH: Path = DATA_DIR / "index.faiss"
    META_PATH: Path = DATA_DIR / "meta.json"

    # Chat / LLM
    LLM_PROVIDER: str = field(default_factory=get_provider)
    CHAT_API_KEY: str = field(default_factory=lambda: get_api_key(get_provider()))
    CHAT_BASE_URL: str = field(default_factory=lambda: get_base_url(get_provider()))
    CHAT_MODEL: str = field(default_factory=lambda: get_chat_model(get_provider()))

    # Embedding
    EMBEDDING_PROVIDER: str = field(default_factory=get_embedding_provider)
    EMBEDDING_API_KEY: str = field(default_factory=lambda: get_embedding_api_key(get_embedding_provider()))
    EMBEDDING_BASE_URL: str = field(default_factory=lambda: get_embedding_base_url(get_embedding_provider()))
    EMBEDDING_MODEL: str = field(default_factory=lambda: get_embedding_model(get_embedding_provider()))

settings = Settings()
"""
ChromaDB persistent client configuration for Fortinet RAG.

ChromaDB 持久化客户端配置，用于 Fortinet RAG 文档向量存储。

Provides:
    - get_embedding_function(): Create embedding function based on config
    - get_chroma_collection(): Get or create a ChromaDB collection
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from gns3_copilot.log_config import setup_logger
from gns3_copilot.utils.app_config import get_config

if TYPE_CHECKING:
    import chromadb

logger = setup_logger("rag.chroma_store")

# Default ChromaDB storage path relative to project root
_DEFAULT_CHROMA_DIR = "data/chroma_db"


def _resolve_chroma_path() -> str:
    """Resolve the ChromaDB persistent storage path.

    解析 ChromaDB 持久化存储路径。
    优先使用 RAG_CHROMA_PATH 配置，否则使用默认路径 data/chroma_db。

    Returns:
        Absolute path to the ChromaDB storage directory.
    """
    configured_path = get_config("RAG_CHROMA_PATH", "")
    if configured_path:
        return os.path.abspath(configured_path)

    # Default: data/chroma_db relative to project root (where pyproject.toml lives)
    project_root = Path(__file__).resolve().parents[3]
    return str(project_root / _DEFAULT_CHROMA_DIR)


def get_embedding_function() -> Any:
    """Create an embedding function based on RAG configuration.

    根据 RAG 配置创建嵌入函数。
    支持 openai 和 huggingface 两种提供商。

    Returns:
        A LangChain-compatible embedding function instance.

    Raises:
        ValueError: If the configured provider is not supported.
    """
    provider = get_config("RAG_EMBEDDING_PROVIDER", "openai").lower()
    model = get_config("RAG_EMBEDDING_MODEL", "text-embedding-3-small")

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings  # type: ignore[import-untyped]

        api_key = get_config("RAG_EMBEDDING_API_KEY", "") or get_config(
            "MODEL_API_KEY", ""
        )
        base_url = get_config("RAG_EMBEDDING_BASE_URL", "") or get_config(
            "BASE_URL", ""
        )

        kwargs: dict[str, Any] = {"model": model}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url

        logger.info("Creating OpenAI embedding function: model=%s", model)
        return OpenAIEmbeddings(**kwargs)

    if provider == "huggingface":
        from langchain_huggingface import (  # type: ignore[import-untyped]
            HuggingFaceEmbeddings,
        )

        logger.info("Creating HuggingFace embedding function: model=%s", model)
        return HuggingFaceEmbeddings(model_name=model)

    raise ValueError(
        f"Unsupported RAG_EMBEDDING_PROVIDER: '{provider}'. "
        "Supported: 'openai', 'huggingface'."
    )


def get_chroma_collection(
    collection_name: str | None = None,
) -> chromadb.Collection:
    """Get or create a ChromaDB collection with persistent storage.

    获取或创建 ChromaDB 持久化集合。

    Args:
        collection_name: Override collection name. Defaults to RAG_COLLECTION_NAME config.

    Returns:
        A ChromaDB Collection object.
    """
    import chromadb  # type: ignore[import-untyped]

    name = collection_name or get_config("RAG_COLLECTION_NAME", "fortinet_docs")
    chroma_path = _resolve_chroma_path()

    logger.info(
        "Opening ChromaDB collection: name=%s, path=%s",
        name,
        chroma_path,
    )

    os.makedirs(chroma_path, exist_ok=True)
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_or_create_collection(name=name)

    logger.info(
        "ChromaDB collection ready: %s (count=%d)", name, collection.count()
    )
    return collection

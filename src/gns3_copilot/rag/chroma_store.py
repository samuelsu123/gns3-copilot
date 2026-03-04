"""ChromaDB helper functions for Fortinet documentation collections."""

from __future__ import annotations

import os
import re
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.errors import NotFoundError

from gns3_copilot.log_config import setup_logger
from gns3_copilot.rag.embeddings_factory import EmbeddingProfile
from gns3_copilot.utils import get_config

logger = setup_logger("rag_chroma_store")

_SAFE_TOKEN_RE = re.compile(r"[^a-z0-9_\-]+")


def _safe_token(value: str) -> str:
    token = _SAFE_TOKEN_RE.sub("_", str(value or "").strip().lower())
    return token.strip("_") or "unknown"


def get_chroma_persist_dir() -> str:
    """Return configured Chroma persistence directory."""
    configured = get_config("RAG_CHROMA_DIR", "data/chroma")
    path = str(configured or "data/chroma").strip() or "data/chroma"
    os.makedirs(path, exist_ok=True)
    return path


def build_collection_name(
    product: str,
    version: str,
    embedding_profile: EmbeddingProfile,
) -> str:
    """Build deterministic collection name with embedding profile suffix."""
    return (
        "fortinet__"
        f"{_safe_token(product)}__"
        f"{_safe_token(version)}__"
        f"{_safe_token(embedding_profile.backend)}__"
        f"{embedding_profile.model_hash}"
    )


def get_client(persist_dir: str | None = None) -> chromadb.PersistentClient:
    """Create a persistent Chroma client."""
    return chromadb.PersistentClient(path=persist_dir or get_chroma_persist_dir())


def get_or_create_collection(
    product: str,
    version: str,
    embedding_profile: EmbeddingProfile,
    recreate: bool = False,
    persist_dir: str | None = None,
) -> tuple[Collection, str]:
    """Get or create a Fortinet collection."""
    client = get_client(persist_dir)
    collection_name = build_collection_name(product, version, embedding_profile)

    if recreate:
        try:
            client.delete_collection(collection_name)
            logger.info("Deleted existing Chroma collection: %s", collection_name)
        except NotFoundError:
            pass

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={
            "vendor": "fortinet",
            "product": str(product),
            "version": str(version),
            "embedding_backend": embedding_profile.backend,
            "embedding_model": embedding_profile.model,
            "hnsw:space": "cosine",
        },
    )
    return collection, collection_name


def get_collection_if_exists(
    product: str,
    version: str,
    embedding_profile: EmbeddingProfile,
    persist_dir: str | None = None,
) -> tuple[Collection | None, str]:
    """Return existing collection or None if it has not been created yet."""
    client = get_client(persist_dir)
    collection_name = build_collection_name(product, version, embedding_profile)
    try:
        return client.get_collection(collection_name), collection_name
    except NotFoundError:
        return None, collection_name


def upsert_batches(
    collection: Collection,
    ids: list[str],
    documents: list[str],
    metadatas: list[dict[str, Any]],
    embeddings: list[list[float]],
    batch_size: int = 256,
) -> int:
    """Write records into Chroma in fixed-size batches."""
    total = len(ids)
    written = 0

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        collection.upsert(
            ids=ids[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
            embeddings=embeddings[start:end],
        )
        written += end - start

    return written

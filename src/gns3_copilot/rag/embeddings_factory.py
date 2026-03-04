"""Embedding adapter factory for ChromaDB-based RAG."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from langchain_openai import OpenAIEmbeddings

from gns3_copilot.log_config import setup_logger
from gns3_copilot.utils import get_config

logger = setup_logger("rag_embeddings")

SUPPORTED_EMBEDDING_BACKENDS = {"openai", "local"}


class EmbeddingAdapter(Protocol):
    """Common interface used by ingest/retrieval code."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""

    def embed_query(self, text: str) -> list[float]:
        """Embed a query string."""


@dataclass(frozen=True)
class EmbeddingProfile:
    """Resolved embedding configuration profile."""

    backend: str
    model: str
    model_hash: str


class LocalSentenceTransformerEmbeddings:
    """Thin wrapper exposing langchain-like embedding methods."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = _load_sentence_transformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        vector = self._model.encode([text], normalize_embeddings=True)[0]
        return vector.tolist()


def normalize_embedding_backend(backend: str | None) -> str:
    """Normalize configured backend and fallback safely."""
    value = str(backend or "openai").strip().lower()
    if value in SUPPORTED_EMBEDDING_BACKENDS:
        return value
    logger.warning(
        "Unsupported EMBEDDING_BACKEND '%s'; fallback to 'openai'", backend
    )
    return "openai"


def _short_model_hash(backend: str, model_name: str) -> str:
    raw = f"{backend}:{model_name}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:10]


@lru_cache(maxsize=4)
def _load_sentence_transformer(model_name: str):
    from sentence_transformers import SentenceTransformer

    logger.info("Loading local sentence-transformer model: %s", model_name)
    return SentenceTransformer(model_name)


def get_embedding_profile(backend_override: str | None = None) -> EmbeddingProfile:
    """Return normalized backend/model profile used for collection naming."""
    backend = normalize_embedding_backend(
        backend_override or get_config("EMBEDDING_BACKEND", "openai")
    )

    if backend == "local":
        model_name = get_config("EMBEDDING_LOCAL_MODEL", "BAAI/bge-m3")
    else:
        model_name = get_config("EMBEDDING_OPENAI_MODEL", "text-embedding-3-small")

    model_name = str(model_name or "").strip() or "text-embedding-3-small"
    return EmbeddingProfile(
        backend=backend,
        model=model_name,
        model_hash=_short_model_hash(backend, model_name),
    )


def create_embedding_adapter(
    backend_override: str | None = None,
) -> EmbeddingAdapter:
    """Create an embedding adapter based on app config."""
    profile = get_embedding_profile(backend_override=backend_override)

    if profile.backend == "local":
        return LocalSentenceTransformerEmbeddings(profile.model)

    api_key = get_config("MODEL_API_KEY", "")
    base_url = get_config("BASE_URL", "")
    kwargs: dict[str, str] = {"model": profile.model}
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url

    return OpenAIEmbeddings(**kwargs)

"""Document retrieval helpers for Fortinet ChromaDB collections."""

from __future__ import annotations

from typing import Any

from gns3_copilot.log_config import setup_logger
from gns3_copilot.rag.chroma_store import get_collection_if_exists
from gns3_copilot.rag.embeddings_factory import create_embedding_adapter, get_embedding_profile
from gns3_copilot.utils import get_config

logger = setup_logger("rag_retrieval")


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_citation(metadata: dict[str, Any]) -> str:
    source_file = str(metadata.get("source_file", "unknown_source"))
    page_start = metadata.get("page_start")
    page_end = metadata.get("page_end")
    section_title = str(metadata.get("section_title", "")).strip()

    if page_start and page_end and page_start != page_end:
        page_part = f"p{page_start}-{page_end}"
    elif page_start:
        page_part = f"p{page_start}"
    else:
        page_part = "p?"

    if section_title:
        return f"{source_file} {page_part} | {section_title}"
    return f"{source_file} {page_part}"


def search_fortinet_docs(
    query: str,
    product: str,
    version: str,
    top_k: int | None = None,
    min_similarity: float | None = None,
    embedding_backend: str | None = None,
    persist_dir: str | None = None,
) -> dict[str, Any]:
    """Search Fortinet documentation and return normalized hit payload."""
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return {
            "query": query,
            "product": product,
            "version": version,
            "no_evidence": True,
            "reason": "empty_query",
            "hits": [],
        }

    top_k_value = max(1, _safe_int(top_k, _safe_int(get_config("RAG_TOP_K", "6"), 6)))
    min_similarity_value = _safe_float(
        min_similarity,
        _safe_float(get_config("RAG_MIN_SIMILARITY", "0.25"), 0.25),
    )

    profile = get_embedding_profile(backend_override=embedding_backend)
    collection, collection_name = get_collection_if_exists(
        product=product,
        version=version,
        embedding_profile=profile,
        persist_dir=persist_dir,
    )

    if collection is None:
        return {
            "query": normalized_query,
            "product": product,
            "version": version,
            "no_evidence": True,
            "reason": "collection_not_found",
            "collection_name": collection_name,
            "hits": [],
        }

    embedding_adapter = create_embedding_adapter(backend_override=profile.backend)
    query_embedding = embedding_adapter.embed_query(normalized_query)
    raw = collection.query(
        query_embeddings=[query_embedding],
        n_results=max(top_k_value * 2, top_k_value),
        include=["documents", "metadatas", "distances"],
    )

    docs = (raw.get("documents") or [[]])[0]
    metas = (raw.get("metadatas") or [[]])[0]
    distances = (raw.get("distances") or [[]])[0]

    hits: list[dict[str, Any]] = []
    for index, document in enumerate(docs):
        metadata = metas[index] if index < len(metas) and isinstance(metas[index], dict) else {}
        distance = distances[index] if index < len(distances) else None

        similarity = None
        if isinstance(distance, (int, float)):
            similarity = max(0.0, min(1.0, 1.0 - float(distance)))

        if similarity is not None and similarity < min_similarity_value:
            continue

        snippet = str(document or "").strip()
        if len(snippet) > 500:
            snippet = snippet[:500].rstrip() + "..."

        hits.append(
            {
                "rank": len(hits) + 1,
                "score": similarity,
                "snippet": snippet,
                "citation": _build_citation(metadata),
                "metadata": metadata,
            }
        )
        if len(hits) >= top_k_value:
            break

    return {
        "query": normalized_query,
        "product": product,
        "version": version,
        "embedding_backend": profile.backend,
        "embedding_model": profile.model,
        "collection_name": collection_name,
        "top_k": top_k_value,
        "min_similarity": min_similarity_value,
        "no_evidence": len(hits) == 0,
        "hits": hits,
    }

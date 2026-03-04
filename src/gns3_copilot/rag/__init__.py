"""RAG utilities for Fortinet/FortiGate documentation retrieval."""

from gns3_copilot.rag.embeddings_factory import (
    EmbeddingProfile,
    create_embedding_adapter,
    get_embedding_profile,
    normalize_embedding_backend,
)
from gns3_copilot.rag.ingest import (
    build_chunk_payload,
    ingest_pdf_to_chroma,
    read_pdf_pages,
    split_text_into_chunks,
)
from gns3_copilot.rag.retrieval import search_fortinet_docs

__all__ = [
    "EmbeddingProfile",
    "create_embedding_adapter",
    "get_embedding_profile",
    "normalize_embedding_backend",
    "split_text_into_chunks",
    "read_pdf_pages",
    "build_chunk_payload",
    "ingest_pdf_to_chroma",
    "search_fortinet_docs",
]

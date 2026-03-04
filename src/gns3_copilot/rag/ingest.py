"""PDF ingest utilities for Fortinet documentation RAG."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from gns3_copilot.log_config import setup_logger
from gns3_copilot.rag.chroma_store import get_or_create_collection, upsert_batches
from gns3_copilot.rag.embeddings_factory import create_embedding_adapter, get_embedding_profile

logger = setup_logger("rag_ingest")


def split_text_into_chunks(
    text: str,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
    min_chunk_chars: int = 80,
) -> list[str]:
    """Split text by fixed character windows with overlap."""
    clean = " ".join(str(text or "").split())
    if not clean:
        return []

    if chunk_overlap >= chunk_size:
        chunk_overlap = max(0, chunk_size // 4)

    chunks: list[str] = []
    start = 0
    step = max(1, chunk_size - chunk_overlap)

    while start < len(clean):
        end = min(len(clean), start + chunk_size)
        chunk = clean[start:end].strip()
        if len(chunk) >= min_chunk_chars:
            chunks.append(chunk)
        start += step

    return chunks


def _guess_section_title(page_text: str) -> str:
    for line in str(page_text or "").splitlines():
        candidate = " ".join(line.split()).strip()
        if 3 <= len(candidate) <= 120:
            return candidate
    return ""


def read_pdf_pages(pdf_path: str) -> list[tuple[int, str]]:
    """Extract per-page text from PDF, keeping 1-based page numbers."""
    reader = PdfReader(pdf_path)
    pages: list[tuple[int, str]] = []

    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        normalized = "\n".join(line.rstrip() for line in text.splitlines())
        if normalized.strip():
            pages.append((index, normalized))

    return pages


def build_chunk_payload(
    pages: list[tuple[int, str]],
    source_file: str,
    vendor: str,
    product: str,
    version: str,
    doc_type: str,
    language: str,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
    min_chunk_chars: int = 80,
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Build ids/documents/metadatas payload from extracted pages."""
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []

    global_chunk_index = 0
    source_basename = os.path.basename(source_file)

    for page_number, page_text in pages:
        section_title = _guess_section_title(page_text)
        chunks = split_text_into_chunks(
            page_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            min_chunk_chars=min_chunk_chars,
        )

        for local_chunk_index, chunk in enumerate(chunks):
            ids.append(
                (
                    f"{product}:{version}:{source_basename}:"
                    f"p{page_number}:c{local_chunk_index}"
                )
            )
            documents.append(chunk)
            metadatas.append(
                {
                    "vendor": vendor,
                    "product": product,
                    "version": version,
                    "doc_type": doc_type,
                    "language": language,
                    "source_file": source_basename,
                    "page_start": page_number,
                    "page_end": page_number,
                    "section_title": section_title,
                    "chunk_index": global_chunk_index,
                }
            )
            global_chunk_index += 1

    return ids, documents, metadatas


def ingest_pdf_to_chroma(
    pdf_path: str,
    product: str,
    version: str,
    doc_type: str = "admin-guide",
    language: str = "en",
    vendor: str = "fortinet",
    recreate: bool = False,
    batch_size: int = 256,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
    min_chunk_chars: int = 80,
    embedding_backend: str | None = None,
    persist_dir: str | None = None,
) -> dict[str, Any]:
    """Ingest a PDF document into ChromaDB and return statistics."""
    pdf = Path(pdf_path)
    if not pdf.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf}")

    pages = read_pdf_pages(str(pdf))
    ids, documents, metadatas = build_chunk_payload(
        pages=pages,
        source_file=pdf.name,
        vendor=vendor,
        product=product,
        version=version,
        doc_type=doc_type,
        language=language,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        min_chunk_chars=min_chunk_chars,
    )

    profile = get_embedding_profile(backend_override=embedding_backend)
    embedding_adapter = create_embedding_adapter(backend_override=profile.backend)
    collection, collection_name = get_or_create_collection(
        product=product,
        version=version,
        embedding_profile=profile,
        recreate=recreate,
        persist_dir=persist_dir,
    )

    total_written = 0
    for start in range(0, len(documents), batch_size):
        end = min(start + batch_size, len(documents))
        batch_docs = documents[start:end]
        batch_ids = ids[start:end]
        batch_meta = metadatas[start:end]
        batch_embeddings = embedding_adapter.embed_documents(batch_docs)
        total_written += upsert_batches(
            collection=collection,
            ids=batch_ids,
            documents=batch_docs,
            metadatas=batch_meta,
            embeddings=batch_embeddings,
            batch_size=batch_size,
        )

    summary = {
        "pdf_path": str(pdf),
        "source_file": pdf.name,
        "vendor": vendor,
        "product": product,
        "version": version,
        "doc_type": doc_type,
        "language": language,
        "embedding_backend": profile.backend,
        "embedding_model": profile.model,
        "collection_name": collection_name,
        "total_pages_with_text": len(pages),
        "total_chunks": len(documents),
        "total_written": total_written,
        "recreate": recreate,
    }
    logger.info("PDF ingest summary: %s", summary)
    return summary

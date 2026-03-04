"""Tests for PDF ingest helpers in gns3_copilot.rag.ingest."""

from __future__ import annotations

from pathlib import Path

from gns3_copilot.rag.embeddings_factory import EmbeddingProfile
from gns3_copilot.rag.ingest import (
    build_chunk_payload,
    ingest_pdf_to_chroma,
    split_text_into_chunks,
)


class _FakeEmbeddingAdapter:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class _FakeCollection:
    def __init__(self) -> None:
        self.rows = 0

    def upsert(self, ids, documents, metadatas, embeddings) -> None:
        assert len(ids) == len(documents) == len(metadatas) == len(embeddings)
        self.rows += len(ids)


def test_split_text_into_chunks_applies_overlap() -> None:
    text = "A" * 300
    chunks = split_text_into_chunks(text, chunk_size=120, chunk_overlap=20, min_chunk_chars=10)

    assert len(chunks) >= 3
    assert all(len(item) <= 120 for item in chunks)
    assert chunks[0][-20:] == chunks[1][:20]


def test_build_chunk_payload_contains_required_metadata() -> None:
    pages = [
        (1, "Section One\nThis is the first page with enough content to split into chunks."),
        (2, "Section Two\nThis is the second page."),
    ]
    ids, docs, metadatas = build_chunk_payload(
        pages=pages,
        source_file="FortiGate_7.6.6_Admin_Guide.pdf",
        vendor="fortinet",
        product="fortigate",
        version="7.6.6",
        doc_type="admin-guide",
        language="en",
        chunk_size=80,
        chunk_overlap=10,
        min_chunk_chars=20,
    )

    assert ids
    assert docs
    assert metadatas
    assert len(ids) == len(docs) == len(metadatas)

    sample = metadatas[0]
    assert sample["vendor"] == "fortinet"
    assert sample["product"] == "fortigate"
    assert sample["version"] == "7.6.6"
    assert sample["doc_type"] == "admin-guide"
    assert sample["source_file"] == "FortiGate_7.6.6_Admin_Guide.pdf"
    assert "page_start" in sample
    assert "page_end" in sample
    assert "section_title" in sample
    assert "chunk_index" in sample


def test_ingest_pdf_to_chroma_returns_stats(monkeypatch, tmp_path: Path) -> None:
    pdf_path = tmp_path / "fortigate.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake")

    fake_collection = _FakeCollection()

    monkeypatch.setattr(
        "gns3_copilot.rag.ingest.read_pdf_pages",
        lambda _path: [(1, "Section\nThis is a test page with valid content for chunking.")],
    )
    monkeypatch.setattr(
        "gns3_copilot.rag.ingest.get_embedding_profile",
        lambda backend_override=None: EmbeddingProfile(
            backend="openai", model="text-embedding-3-small", model_hash="abc123"
        ),
    )
    monkeypatch.setattr(
        "gns3_copilot.rag.ingest.create_embedding_adapter",
        lambda backend_override=None: _FakeEmbeddingAdapter(),
    )
    monkeypatch.setattr(
        "gns3_copilot.rag.ingest.get_or_create_collection",
        lambda **kwargs: (fake_collection, "fortinet__fortigate__7_6_6__openai__abc123"),
    )

    summary = ingest_pdf_to_chroma(
        pdf_path=str(pdf_path),
        product="fortigate",
        version="7.6.6",
        recreate=True,
        chunk_size=120,
        chunk_overlap=20,
        min_chunk_chars=10,
        batch_size=8,
    )

    assert summary["source_file"] == "fortigate.pdf"
    assert summary["product"] == "fortigate"
    assert summary["version"] == "7.6.6"
    assert summary["total_pages_with_text"] == 1
    assert summary["total_chunks"] >= 1
    assert summary["total_written"] == summary["total_chunks"]
    assert fake_collection.rows == summary["total_chunks"]

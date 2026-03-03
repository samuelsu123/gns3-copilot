"""Tests for rag.ingest module."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from gns3_copilot.rag.ingest import (
    _compute_chunk_id,
    detect_doc_type,
)


class TestDetectDocType:
    """Tests for detect_doc_type."""

    def test_cli_reference_detected(self):
        assert detect_doc_type("/docs/FortiOS_CLI_Reference.pdf") == "cli_reference"

    def test_cli_in_name_detected(self):
        assert detect_doc_type("fortios-cli-guide.md") == "cli_reference"

    def test_reference_in_name_detected(self):
        assert detect_doc_type("reference_manual.txt") == "cli_reference"

    def test_config_guide_default(self):
        assert detect_doc_type("admin_guide.pdf") == "config_guide"

    def test_config_guide_for_generic(self):
        assert detect_doc_type("fortios-7.4-handbook.md") == "config_guide"


class TestComputeChunkId:
    """Tests for _compute_chunk_id."""

    def test_deterministic(self):
        """Same inputs produce same ID."""
        id1 = _compute_chunk_id("file.md", 0, "content")
        id2 = _compute_chunk_id("file.md", 0, "content")
        assert id1 == id2

    def test_different_content_different_id(self):
        """Different content produces different ID."""
        id1 = _compute_chunk_id("file.md", 0, "content A")
        id2 = _compute_chunk_id("file.md", 0, "content B")
        assert id1 != id2

    def test_different_index_different_id(self):
        """Different chunk index produces different ID."""
        id1 = _compute_chunk_id("file.md", 0, "content")
        id2 = _compute_chunk_id("file.md", 1, "content")
        assert id1 != id2

    def test_returns_hex_string(self):
        """ID is a valid hex string (SHA-256 = 64 hex chars)."""
        chunk_id = _compute_chunk_id("file.md", 0, "content")
        assert len(chunk_id) == 64
        int(chunk_id, 16)  # Should not raise


class TestSplitText:
    """Tests for _split_text."""

    def _make_mock_splitter(self, return_value):
        """Create a mock RecursiveCharacterTextSplitter."""
        mock_splitter = MagicMock()
        mock_splitter.split_text.return_value = return_value
        return mock_splitter

    def test_splits_short_text(self):
        """Short text returns single chunk."""
        mock_splitter = self._make_mock_splitter(["hello world"])
        mock_module = MagicMock()
        mock_module.RecursiveCharacterTextSplitter.return_value = mock_splitter

        with patch.dict("sys.modules", {"langchain_text_splitters": mock_module}):
            from gns3_copilot.rag.ingest import _split_text

            chunks = _split_text("hello world", 100, 10, ["\n\n"])
            assert len(chunks) == 1
            assert chunks[0] == "hello world"

    def test_splits_long_text(self):
        """Long text is split into multiple chunks."""
        mock_splitter = self._make_mock_splitter(["chunk1", "chunk2", "chunk3"])
        mock_module = MagicMock()
        mock_module.RecursiveCharacterTextSplitter.return_value = mock_splitter

        with patch.dict("sys.modules", {"langchain_text_splitters": mock_module}):
            from gns3_copilot.rag.ingest import _split_text

            text = "A" * 500 + "\n\n" + "B" * 500
            chunks = _split_text(text, 200, 50, ["\n\n"])
            assert len(chunks) > 1


class TestIngestDocuments:
    """Tests for ingest_documents."""

    def _patch_split_text(self):
        """Return a patch that mocks _split_text to return simple chunks."""
        def fake_split(text, chunk_size, chunk_overlap, separators):
            # Simple splitting for tests
            if len(text) <= chunk_size:
                return [text]
            chunks = []
            for i in range(0, len(text), chunk_size - chunk_overlap):
                chunk = text[i : i + chunk_size]
                if chunk:
                    chunks.append(chunk)
            return chunks if chunks else [text]

        return patch("gns3_copilot.rag.ingest._split_text", side_effect=fake_split)

    def test_dry_run_no_writes(self):
        """Dry run mode counts chunks but doesn't write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test_guide.md")
            with open(test_file, "w") as f:
                f.write("# FortiGate Configuration\n\n" + "Some content. " * 100)

            with patch(
                "gns3_copilot.rag.ingest.get_config",
                side_effect=lambda k, d="": {
                    "RAG_GUIDE_CHUNK_SIZE": "200",
                    "RAG_GUIDE_CHUNK_OVERLAP": "50",
                }.get(k, d),
            ), self._patch_split_text():
                from gns3_copilot.rag.ingest import ingest_documents

                result = ingest_documents(tmpdir, dry_run=True)

            assert result["total_files"] == 1
            assert result["total_chunks"] > 0
            assert result["new_chunks"] == result["total_chunks"]
            assert result["skipped_chunks"] == 0

    def test_empty_directory(self):
        """Empty directory returns zeros."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from gns3_copilot.rag.ingest import ingest_documents

            result = ingest_documents(tmpdir, dry_run=True)
            assert result["total_files"] == 0
            assert result["total_chunks"] == 0

    def test_nonexistent_path_raises(self):
        """Non-existent path raises FileNotFoundError."""
        from gns3_copilot.rag.ingest import ingest_documents

        with pytest.raises(FileNotFoundError):
            ingest_documents("/nonexistent/path/12345", dry_run=True)

    def test_single_file_ingestion(self):
        """Single file can be ingested directly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "cli_reference.txt")
            with open(test_file, "w") as f:
                f.write(
                    "config system interface\nedit port2\n"
                    "set ip 10.0.0.1/24\nnext\nend\n"
                )

            with patch(
                "gns3_copilot.rag.ingest.get_config",
                side_effect=lambda k, d="": {
                    "RAG_CLI_CHUNK_SIZE": "800",
                    "RAG_CLI_CHUNK_OVERLAP": "100",
                }.get(k, d),
            ), self._patch_split_text():
                from gns3_copilot.rag.ingest import ingest_documents

                result = ingest_documents(test_file, dry_run=True)

            assert result["total_files"] == 1
            assert result["total_chunks"] >= 1

    def test_doc_type_override(self):
        """Explicit doc_type overrides auto-detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # File name suggests config_guide but we override to cli_reference
            test_file = os.path.join(tmpdir, "admin_guide.txt")
            with open(test_file, "w") as f:
                f.write("Some text content\n" * 50)

            with patch(
                "gns3_copilot.rag.ingest.get_config",
                side_effect=lambda k, d="": {
                    "RAG_CLI_CHUNK_SIZE": "100",
                    "RAG_CLI_CHUNK_OVERLAP": "20",
                }.get(k, d),
            ), self._patch_split_text():
                from gns3_copilot.rag.ingest import ingest_documents

                result = ingest_documents(
                    test_file, doc_type="cli_reference", dry_run=True
                )

            assert result["total_files"] == 1

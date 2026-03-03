"""
Document ingestion pipeline for Fortinet RAG.

文档摄取管道：将 Fortinet 官方文档分块并存入 ChromaDB 向量数据库。

Supports PDF, Markdown, HTML, and TXT formats with two chunking strategies:
- cli_reference: smaller chunks (800 chars) with FortiOS CLI structure markers
- config_guide: larger chunks (1500 chars) with Markdown heading separators
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from gns3_copilot.log_config import setup_logger
from gns3_copilot.utils.app_config import get_config

logger = setup_logger("rag.ingest")

# Supported file extensions
SUPPORTED_EXTENSIONS = {".pdf", ".md", ".html", ".htm", ".txt"}

# FortiOS CLI structure markers used as separators for CLI reference docs
_CLI_SEPARATORS = [
    "\nconfig ",
    "\nend\n",
    "\nedit ",
    "\nnext\n",
    "\n### ",
    "\n## ",
    "\n# ",
    "\n\n",
]

# Markdown heading separators for config guide docs
_GUIDE_SEPARATORS = [
    "\n# ",
    "\n## ",
    "\n### ",
    "\n#### ",
    "\n\n",
]


def detect_doc_type(file_path: str) -> str:
    """Detect document type from filename.

    根据文件名自动检测文档类型。
    文件名包含 'cli' 或 'reference' 视为 CLI 参考文档，否则为配置指南。

    Args:
        file_path: Path to the document file.

    Returns:
        'cli_reference' or 'config_guide'.
    """
    name_lower = Path(file_path).stem.lower()
    if "cli" in name_lower or "reference" in name_lower:
        return "cli_reference"
    return "config_guide"


def _get_chunk_params(doc_type: str) -> tuple[int, int, list[str]]:
    """Get chunking parameters for a document type.

    Args:
        doc_type: 'cli_reference' or 'config_guide'.

    Returns:
        Tuple of (chunk_size, chunk_overlap, separators).
    """
    if doc_type == "cli_reference":
        chunk_size = int(get_config("RAG_CLI_CHUNK_SIZE", "800"))
        chunk_overlap = int(get_config("RAG_CLI_CHUNK_OVERLAP", "100"))
        return chunk_size, chunk_overlap, _CLI_SEPARATORS
    else:
        chunk_size = int(get_config("RAG_GUIDE_CHUNK_SIZE", "1500"))
        chunk_overlap = int(get_config("RAG_GUIDE_CHUNK_OVERLAP", "200"))
        return chunk_size, chunk_overlap, _GUIDE_SEPARATORS


def _compute_chunk_id(source: str, chunk_index: int, content: str) -> str:
    """Compute a deterministic chunk ID based on content hash.

    基于 SHA-256 的 chunk_id 去重，摄取脚本可重复运行。

    Args:
        source: Source file path.
        chunk_index: Index of the chunk within the document.
        content: The chunk text content.

    Returns:
        A hex digest string as the chunk ID.
    """
    raw = f"{source}::{chunk_index}::{content}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_document(file_path: str) -> str:
    """Load document content from a file.

    Args:
        file_path: Path to the document file.

    Returns:
        The text content of the document.

    Raises:
        ValueError: If the file extension is not supported.
    """
    ext = Path(file_path).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file extension: '{ext}'. "
            f"Supported: {SUPPORTED_EXTENSIONS}"
        )

    if ext == ".pdf":
        from langchain_community.document_loaders import (  # type: ignore[import-untyped]
            PyPDFLoader,
        )

        loader = PyPDFLoader(file_path)
        pages = loader.load()
        return "\n\n".join(page.page_content for page in pages)

    if ext in (".html", ".htm"):
        from langchain_community.document_loaders import (  # type: ignore[import-untyped]
            BSHTMLLoader,
        )

        loader = BSHTMLLoader(file_path)
        docs = loader.load()
        return "\n\n".join(doc.page_content for doc in docs)

    # .md and .txt: read as plain text
    with open(file_path, encoding="utf-8") as f:
        return f.read()


def _split_text(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    separators: list[str],
) -> list[str]:
    """Split text into chunks using RecursiveCharacterTextSplitter.

    Args:
        text: The text to split.
        chunk_size: Maximum chunk size in characters.
        chunk_overlap: Overlap between consecutive chunks.
        separators: Ordered list of separators to try.

    Returns:
        List of text chunks.
    """
    from langchain_text_splitters import (  # type: ignore[import-untyped]
        RecursiveCharacterTextSplitter,
    )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
        keep_separator=True,
    )
    return splitter.split_text(text)


def ingest_documents(
    docs_path: str,
    doc_type: str | None = None,
    dry_run: bool = False,
    collection_name: str | None = None,
) -> dict[str, Any]:
    """Ingest documents from a directory or single file into ChromaDB.

    将文档从目录或单个文件摄取到 ChromaDB 向量数据库。

    Args:
        docs_path: Path to a directory of documents or a single file.
        doc_type: Override document type ('cli_reference' or 'config_guide').
            If None, auto-detected from filename.
        dry_run: If True, only report what would be ingested without writing.
        collection_name: Override ChromaDB collection name.

    Returns:
        Summary dict with keys: total_files, total_chunks, new_chunks, skipped_chunks.
    """
    from gns3_copilot.rag.chroma_store import (
        get_chroma_collection,
        get_embedding_function,
    )

    path = Path(docs_path)
    if path.is_file():
        files = [str(path)]
    elif path.is_dir():
        files = sorted(
            str(f)
            for f in path.rglob("*")
            if f.suffix.lower() in SUPPORTED_EXTENSIONS
        )
    else:
        raise FileNotFoundError(f"Path not found: {docs_path}")

    if not files:
        logger.warning("No supported files found in %s", docs_path)
        return {
            "total_files": 0,
            "total_chunks": 0,
            "new_chunks": 0,
            "skipped_chunks": 0,
        }

    logger.info("Found %d files to ingest from %s", len(files), docs_path)

    # Prepare all chunks
    all_chunks: list[dict[str, Any]] = []
    for file_path in files:
        file_doc_type = doc_type or detect_doc_type(file_path)
        chunk_size, chunk_overlap, separators = _get_chunk_params(file_doc_type)

        logger.info(
            "Processing %s (type=%s, chunk_size=%d)",
            file_path,
            file_doc_type,
            chunk_size,
        )

        text = _load_document(file_path)
        chunks = _split_text(text, chunk_size, chunk_overlap, separators)

        for idx, chunk_text in enumerate(chunks):
            chunk_id = _compute_chunk_id(file_path, idx, chunk_text)
            all_chunks.append(
                {
                    "id": chunk_id,
                    "text": chunk_text,
                    "metadata": {
                        "source": os.path.basename(file_path),
                        "doc_type": file_doc_type,
                        "chunk_index": idx,
                    },
                }
            )

    logger.info("Total chunks prepared: %d", len(all_chunks))

    if dry_run:
        logger.info("Dry run mode — no data written to ChromaDB")
        return {
            "total_files": len(files),
            "total_chunks": len(all_chunks),
            "new_chunks": len(all_chunks),
            "skipped_chunks": 0,
        }

    # Get collection and check for existing chunks (deduplication)
    collection = get_chroma_collection(collection_name)
    embedding_fn = get_embedding_function()

    existing_ids = set()
    if collection.count() > 0:
        # Fetch existing IDs in batches
        chunk_ids = [c["id"] for c in all_chunks]
        batch_size = 100
        for i in range(0, len(chunk_ids), batch_size):
            batch = chunk_ids[i : i + batch_size]
            result = collection.get(ids=batch)
            if result and result["ids"]:
                existing_ids.update(result["ids"])

    new_chunks = [c for c in all_chunks if c["id"] not in existing_ids]
    skipped = len(all_chunks) - len(new_chunks)

    if skipped > 0:
        logger.info("Skipping %d existing chunks (deduplication)", skipped)

    if new_chunks:
        # Embed and upsert in batches
        batch_size = 50
        for i in range(0, len(new_chunks), batch_size):
            batch = new_chunks[i : i + batch_size]
            texts = [c["text"] for c in batch]
            ids = [c["id"] for c in batch]
            metadatas = [c["metadata"] for c in batch]

            embeddings = embedding_fn.embed_documents(texts)
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
            logger.info(
                "Upserted batch %d-%d of %d",
                i + 1,
                min(i + batch_size, len(new_chunks)),
                len(new_chunks),
            )

    logger.info(
        "Ingestion complete: %d files, %d total chunks, %d new, %d skipped",
        len(files),
        len(all_chunks),
        len(new_chunks),
        skipped,
    )

    return {
        "total_files": len(files),
        "total_chunks": len(all_chunks),
        "new_chunks": len(new_chunks),
        "skipped_chunks": skipped,
    }

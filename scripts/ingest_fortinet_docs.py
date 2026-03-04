#!/usr/bin/env python3
"""CLI tool for ingesting Fortinet PDF documentation into ChromaDB."""

from __future__ import annotations

import argparse
import json
import sys

from gns3_copilot.rag import ingest_pdf_to_chroma


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest a Fortinet PDF into ChromaDB for RAG retrieval"
    )
    parser.add_argument("--pdf", required=True, help="Path to PDF file")
    parser.add_argument("--product", default="fortigate", help="Product name")
    parser.add_argument("--version", default="7.6.6", help="Product version")
    parser.add_argument("--doc-type", default="admin-guide", help="Document type")
    parser.add_argument("--language", default="en", help="Document language")
    parser.add_argument("--vendor", default="fortinet", help="Vendor name")
    parser.add_argument(
        "--embedding-backend",
        choices=["openai", "local"],
        default=None,
        help="Embedding backend override",
    )
    parser.add_argument("--persist-dir", default=None, help="ChromaDB persist directory")
    parser.add_argument(
        "--batch-size", type=int, default=256, help="Embedding/upsert batch size"
    )
    parser.add_argument("--chunk-size", type=int, default=1200, help="Chunk size in chars")
    parser.add_argument(
        "--chunk-overlap", type=int, default=200, help="Chunk overlap in chars"
    )
    parser.add_argument(
        "--min-chunk-chars", type=int, default=80, help="Minimum chunk length"
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate target collection before ingest",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        summary = ingest_pdf_to_chroma(
            pdf_path=args.pdf,
            product=args.product,
            version=args.version,
            doc_type=args.doc_type,
            language=args.language,
            vendor=args.vendor,
            recreate=args.recreate,
            batch_size=args.batch_size,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            min_chunk_chars=args.min_chunk_chars,
            embedding_backend=args.embedding_backend,
            persist_dir=args.persist_dir,
        )
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1

    print(json.dumps({"status": "ok", "summary": summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

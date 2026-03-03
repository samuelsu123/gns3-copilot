#!/usr/bin/env python3
"""
Fortinet document ingestion CLI script.

离线导入 Fortinet 官方文档到 ChromaDB 向量数据库。

Usage:
    python scripts/ingest_fortinet_docs.py /path/to/fortinet/docs
    python scripts/ingest_fortinet_docs.py /path/to/docs --doc-type cli_reference
    python scripts/ingest_fortinet_docs.py /path/to/docs --dry-run
    python scripts/ingest_fortinet_docs.py /path/to/docs --collection my_collection
"""

import argparse
import sys
from pathlib import Path

# Add project src to path so we can import gns3_copilot modules
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest Fortinet documents into ChromaDB vector database."
    )
    parser.add_argument(
        "docs_path",
        help="Path to a directory of documents or a single file.",
    )
    parser.add_argument(
        "--doc-type",
        choices=["cli_reference", "config_guide"],
        default=None,
        help=(
            "Override document type. If not specified, auto-detected "
            "from filename (files containing 'cli' or 'reference' → cli_reference)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be ingested without writing to ChromaDB.",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="Override ChromaDB collection name (default: from config).",
    )

    args = parser.parse_args()

    # Validate path
    docs_path = Path(args.docs_path)
    if not docs_path.exists():
        print(f"Error: Path not found: {docs_path}", file=sys.stderr)
        sys.exit(1)

    # Initialize config database so get_config works
    from gns3_copilot.utils.app_config import init_config

    init_config()

    from gns3_copilot.rag.ingest import ingest_documents

    print(f"Ingesting documents from: {docs_path}")
    if args.doc_type:
        print(f"Document type override: {args.doc_type}")
    if args.dry_run:
        print("DRY RUN — no data will be written")

    result = ingest_documents(
        docs_path=str(docs_path),
        doc_type=args.doc_type,
        dry_run=args.dry_run,
        collection_name=args.collection,
    )

    print("\n--- Ingestion Summary ---")
    print(f"  Files processed:  {result['total_files']}")
    print(f"  Total chunks:     {result['total_chunks']}")
    print(f"  New chunks added: {result['new_chunks']}")
    print(f"  Skipped (dedup):  {result['skipped_chunks']}")


if __name__ == "__main__":
    main()

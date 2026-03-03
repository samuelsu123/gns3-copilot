"""
Fortinet RAG (Retrieval-Augmented Generation) module.

Provides ChromaDB-based vector storage and document ingestion pipeline
for Fortinet/FortiOS official documentation.

RAG 模块：基于 ChromaDB 的向量存储和文档摄取管道，
用于 Fortinet/FortiOS 官方文档检索增强生成。
"""

from gns3_copilot.rag.chroma_store import get_chroma_collection, get_embedding_function
from gns3_copilot.rag.ingest import ingest_documents

__all__ = [
    "get_chroma_collection",
    "get_embedding_function",
    "ingest_documents",
]

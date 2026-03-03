"""
Fortinet knowledge base RAG retrieval tool.

RAG 检索工具：从 ChromaDB 向量数据库检索 Fortinet 官方文档片段，
辅助 LLM 生成更准确的 FortiOS 配置命令。

The tool is a no-op when RAG_ENABLED is False.
"""

from __future__ import annotations

from typing import Any

from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun

from gns3_copilot.log_config import setup_tool_logger
from gns3_copilot.utils.app_config import get_config

logger = setup_tool_logger("fortinet_rag_tool")


class FortinetKnowledgeBaseTool(BaseTool):
    """LangChain tool to search the Fortinet knowledge base via ChromaDB.

    Searches indexed Fortinet/FortiOS documentation (CLI references,
    configuration guides) and returns relevant document chunks with
    source metadata and relevance scores.

    When RAG_ENABLED is False, returns an informational message
    without error.

    Input:
        A natural language query string describing the FortiOS
        configuration topic or CLI syntax to look up.
        Example: "FortiOS static route config syntax"

    Output:
        A dict containing a list of relevant document chunks,
        each with content, source, doc_type, and distance score.
    """

    name: str = "search_fortinet_knowledge_base"
    description: str = (
        "Search the Fortinet/FortiOS official documentation knowledge base. "
        "Use this tool when you need to look up FortiOS CLI syntax, "
        "configuration best practices, or command references. "
        "Input: a natural language query describing what you need. "
        "Output: relevant documentation chunks with source metadata."
    )

    def _run(
        self,
        query: str = "",
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> dict[str, Any]:
        """Search the Fortinet knowledge base.

        Args:
            query: Natural language search query.
            run_manager: LangChain run manager (unused).

        Returns:
            Dict with 'results' list or 'message' if RAG is disabled.
        """
        # Check RAG feature toggle
        rag_enabled = get_config("RAG_ENABLED", "False").lower() == "true"
        if not rag_enabled:
            logger.info("RAG is disabled (RAG_ENABLED=False)")
            return {
                "message": (
                    "Fortinet knowledge base search is not enabled. "
                    "Set RAG_ENABLED=True and ingest documents to use this tool."
                )
            }

        if not query or not query.strip():
            logger.warning("Empty query received")
            return {"results": [], "message": "Empty query. Please provide a search term."}

        try:
            # Lazy imports to avoid startup delay
            from gns3_copilot.rag.chroma_store import (
                get_chroma_collection,
                get_embedding_function,
            )

            top_k = int(get_config("RAG_TOP_K", "5"))
            collection = get_chroma_collection()
            embedding_fn = get_embedding_function()

            # Check if collection has any documents
            if collection.count() == 0:
                logger.warning("ChromaDB collection is empty")
                return {
                    "results": [],
                    "message": (
                        "Knowledge base is empty. "
                        "Run the ingestion script to add Fortinet documents."
                    ),
                }

            # Embed query and search
            query_embedding = embedding_fn.embed_query(query)
            search_results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

            # Format results
            results: list[dict[str, Any]] = []
            if search_results and search_results["documents"]:
                docs = search_results["documents"][0]
                metadatas = search_results["metadatas"][0] if search_results["metadatas"] else [{}] * len(docs)
                distances = search_results["distances"][0] if search_results["distances"] else [0.0] * len(docs)

                for doc, meta, dist in zip(docs, metadatas, distances):
                    results.append(
                        {
                            "content": doc,
                            "source": meta.get("source", "unknown"),
                            "doc_type": meta.get("doc_type", "unknown"),
                            "distance": round(dist, 4),
                        }
                    )

            logger.info(
                "RAG search completed: query='%s', results=%d",
                query[:80],
                len(results),
            )
            return {"results": results}

        except Exception as e:
            logger.error("RAG search failed: %s", e)
            return {"error": f"Knowledge base search failed: {str(e)}"}

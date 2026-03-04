"""Fortinet documentation search tool backed by ChromaDB."""

from __future__ import annotations

import json
from typing import Any

from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun

from gns3_copilot.log_config import setup_tool_logger
from gns3_copilot.rag import search_fortinet_docs
from gns3_copilot.utils import get_config

logger = setup_tool_logger("fortinet_doc_search")


class FortinetDocSearchTool(BaseTool):
    """Search Fortinet/FortiGate docs stored in ChromaDB."""

    name: str = "fortinet_doc_search"
    description: str = """
    Search Fortinet documentation chunks from ChromaDB.

    Input can be a JSON object/string with keys:
      - query (required): question text
      - product (optional): defaults to configured RAG_DEFAULT_PRODUCT (fortigate)
      - version (optional): defaults to configured RAG_DEFAULT_VERSION (7.6.6)
      - top_k (optional): defaults to configured RAG_TOP_K

    Example:
      {
        "query": "How to configure firewall policy from LAN to WAN?",
        "product": "fortigate",
        "version": "7.6.6",
        "top_k": 6
      }

    Returns:
      {
        "no_evidence": bool,
        "hits": [
          {
            "rank": 1,
            "score": 0.86,
            "snippet": "...",
            "citation": "FortiGate_7.6.6_Admin_Guide.pdf p123",
            "metadata": {...}
          }
        ]
      }
    """

    def _run(
        self,
        tool_input: str | bytes | dict[str, Any] | list[Any],
        run_manager: CallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        del run_manager
        try:
            payload = self._parse_tool_input(tool_input)
        except ValueError as exc:
            return {
                "query": "",
                "product": get_config("RAG_DEFAULT_PRODUCT", "fortigate"),
                "version": get_config("RAG_DEFAULT_VERSION", "7.6.6"),
                "no_evidence": True,
                "reason": f"invalid_input: {exc}",
                "hits": [],
            }

        rag_enabled = str(get_config("RAG_ENABLED", "False")).strip().lower() in {
            "true",
            "1",
            "yes",
            "on",
        }
        if not rag_enabled:
            return {
                "query": str(payload.get("query", "")).strip(),
                "product": str(payload.get("product", "fortigate")),
                "version": str(payload.get("version", "7.6.6")),
                "no_evidence": True,
                "reason": "rag_disabled",
                "hits": [],
            }

        query = str(payload.get("query", "")).strip()
        product = str(
            payload.get("product") or get_config("RAG_DEFAULT_PRODUCT", "fortigate")
        ).strip()
        version = str(
            payload.get("version") or get_config("RAG_DEFAULT_VERSION", "7.6.6")
        ).strip()

        top_k_raw = payload.get("top_k", get_config("RAG_TOP_K", "6"))
        try:
            top_k = int(top_k_raw)
        except (TypeError, ValueError):
            top_k = 6

        if not query:
            return {
                "query": query,
                "product": product,
                "version": version,
                "no_evidence": True,
                "reason": "empty_query",
                "hits": [],
            }

        try:
            result = search_fortinet_docs(
                query=query,
                product=product,
                version=version,
                top_k=top_k,
            )
            logger.info(
                "fortinet_doc_search query='%s' product=%s version=%s hits=%s",
                query,
                product,
                version,
                len(result.get("hits", [])),
            )
            return result
        except Exception as exc:  # pragma: no cover
            logger.exception("fortinet_doc_search failed")
            return {
                "query": query,
                "product": product,
                "version": version,
                "no_evidence": True,
                "reason": f"search_error: {exc}",
                "hits": [],
            }

    def _parse_tool_input(
        self, tool_input: str | bytes | dict[str, Any] | list[Any]
    ) -> dict[str, Any]:
        if isinstance(tool_input, dict):
            return tool_input

        if isinstance(tool_input, list):
            raise ValueError("Expected JSON object, got list")

        if isinstance(tool_input, (str, bytes, bytearray)):
            raw_text = (
                tool_input.decode("utf-8", errors="replace")
                if isinstance(tool_input, (bytes, bytearray))
                else tool_input
            )
            raw_text = str(raw_text).strip()
            if not raw_text:
                return {}

            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON: {exc}") from exc

            if not isinstance(parsed, dict):
                raise ValueError("Expected JSON object")
            return parsed

        raise ValueError(f"Unsupported input type: {type(tool_input).__name__}")

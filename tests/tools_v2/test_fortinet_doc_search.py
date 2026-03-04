"""Tests for FortinetDocSearchTool."""

from __future__ import annotations

from gns3_copilot.tools_v2.fortinet_doc_search import FortinetDocSearchTool


def test_fortinet_doc_search_returns_hits(monkeypatch) -> None:
    monkeypatch.setattr(
        "gns3_copilot.tools_v2.fortinet_doc_search.get_config",
        lambda key, default="": {
            "RAG_ENABLED": "True",
            "RAG_DEFAULT_PRODUCT": "fortigate",
            "RAG_DEFAULT_VERSION": "7.6.6",
            "RAG_TOP_K": "6",
        }.get(key, default),
    )
    monkeypatch.setattr(
        "gns3_copilot.tools_v2.fortinet_doc_search.search_fortinet_docs",
        lambda **kwargs: {
            "query": kwargs["query"],
            "product": kwargs["product"],
            "version": kwargs["version"],
            "no_evidence": False,
            "hits": [
                {
                    "rank": 1,
                    "score": 0.88,
                    "snippet": "sample",
                    "citation": "FortiGate_7.6.6_Admin_Guide.pdf p123",
                    "metadata": {"page_start": 123},
                }
            ],
        },
    )

    tool = FortinetDocSearchTool()
    result = tool._run({"query": "how to configure policy"})

    assert result["no_evidence"] is False
    assert len(result["hits"]) == 1
    assert "citation" in result["hits"][0]


def test_fortinet_doc_search_returns_disabled_when_rag_off(monkeypatch) -> None:
    monkeypatch.setattr(
        "gns3_copilot.tools_v2.fortinet_doc_search.get_config",
        lambda key, default="": {
            "RAG_ENABLED": "False",
            "RAG_DEFAULT_PRODUCT": "fortigate",
            "RAG_DEFAULT_VERSION": "7.6.6",
        }.get(key, default),
    )

    tool = FortinetDocSearchTool()
    result = tool._run({"query": "policy"})

    assert result["no_evidence"] is True
    assert result["reason"] == "rag_disabled"


def test_fortinet_doc_search_supports_json_string_input(monkeypatch) -> None:
    monkeypatch.setattr(
        "gns3_copilot.tools_v2.fortinet_doc_search.get_config",
        lambda key, default="": {
            "RAG_ENABLED": "True",
            "RAG_DEFAULT_PRODUCT": "fortigate",
            "RAG_DEFAULT_VERSION": "7.6.6",
            "RAG_TOP_K": "6",
        }.get(key, default),
    )
    monkeypatch.setattr(
        "gns3_copilot.tools_v2.fortinet_doc_search.search_fortinet_docs",
        lambda **kwargs: {
            "query": kwargs["query"],
            "product": kwargs["product"],
            "version": kwargs["version"],
            "no_evidence": True,
            "hits": [],
        },
    )

    tool = FortinetDocSearchTool()
    result = tool._run('{"query":"policy", "product":"fortigate", "version":"7.6.6"}')

    assert result["query"] == "policy"
    assert result["product"] == "fortigate"
    assert result["version"] == "7.6.6"

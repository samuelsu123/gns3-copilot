"""Tests for tools_v2.fortinet_rag_tool module."""

from unittest.mock import MagicMock, patch

from gns3_copilot.tools_v2.fortinet_rag_tool import FortinetKnowledgeBaseTool


class TestFortinetKnowledgeBaseTool:
    """Tests for FortinetKnowledgeBaseTool."""

    def setup_method(self):
        self.tool = FortinetKnowledgeBaseTool()

    def test_tool_name(self):
        assert self.tool.name == "search_fortinet_knowledge_base"

    @patch("gns3_copilot.tools_v2.fortinet_rag_tool.get_config")
    def test_rag_disabled_returns_message(self, mock_get_config):
        """When RAG_ENABLED=False, returns informational message."""
        mock_get_config.return_value = "False"

        result = self.tool._run("static route syntax")
        assert "message" in result
        assert "not enabled" in result["message"]

    @patch("gns3_copilot.tools_v2.fortinet_rag_tool.get_config")
    def test_empty_query(self, mock_get_config):
        """Empty query returns empty results with message."""
        mock_get_config.side_effect = lambda k, d="": {
            "RAG_ENABLED": "True",
        }.get(k, d)

        result = self.tool._run("")
        assert "message" in result
        assert "Empty query" in result["message"]

    @patch("gns3_copilot.tools_v2.fortinet_rag_tool.get_config")
    def test_whitespace_query(self, mock_get_config):
        """Whitespace-only query returns empty results."""
        mock_get_config.side_effect = lambda k, d="": {
            "RAG_ENABLED": "True",
        }.get(k, d)

        result = self.tool._run("   ")
        assert "message" in result

    @patch("gns3_copilot.tools_v2.fortinet_rag_tool.get_config")
    def test_successful_search(self, mock_get_config):
        """Successful search returns formatted results."""
        mock_get_config.side_effect = lambda k, d="": {
            "RAG_ENABLED": "True",
            "RAG_TOP_K": "3",
        }.get(k, d)

        mock_collection = MagicMock()
        mock_collection.count.return_value = 10
        mock_collection.query.return_value = {
            "documents": [["doc1 content", "doc2 content"]],
            "metadatas": [[
                {"source": "cli_ref.pdf", "doc_type": "cli_reference"},
                {"source": "guide.md", "doc_type": "config_guide"},
            ]],
            "distances": [[0.1234, 0.5678]],
        }

        mock_embedding_fn = MagicMock()
        mock_embedding_fn.embed_query.return_value = [0.1] * 128

        with patch(
            "gns3_copilot.rag.chroma_store.get_chroma_collection",
            return_value=mock_collection,
        ), patch(
            "gns3_copilot.rag.chroma_store.get_embedding_function",
            return_value=mock_embedding_fn,
        ):
            result = self.tool._run("static route config")

        assert "results" in result
        assert len(result["results"]) == 2
        assert result["results"][0]["content"] == "doc1 content"
        assert result["results"][0]["source"] == "cli_ref.pdf"
        assert result["results"][0]["distance"] == 0.1234

    @patch("gns3_copilot.tools_v2.fortinet_rag_tool.get_config")
    def test_empty_collection(self, mock_get_config):
        """Empty collection returns message about ingestion."""
        mock_get_config.side_effect = lambda k, d="": {
            "RAG_ENABLED": "True",
            "RAG_TOP_K": "5",
        }.get(k, d)

        mock_collection = MagicMock()
        mock_collection.count.return_value = 0

        mock_embedding_fn = MagicMock()

        with patch(
            "gns3_copilot.rag.chroma_store.get_chroma_collection",
            return_value=mock_collection,
        ), patch(
            "gns3_copilot.rag.chroma_store.get_embedding_function",
            return_value=mock_embedding_fn,
        ):
            result = self.tool._run("some query")

        assert "message" in result
        assert "empty" in result["message"].lower()

    @patch("gns3_copilot.tools_v2.fortinet_rag_tool.get_config")
    def test_exception_handling(self, mock_get_config):
        """Exceptions are caught and returned as error dict."""
        mock_get_config.side_effect = lambda k, d="": {
            "RAG_ENABLED": "True",
            "RAG_TOP_K": "5",
        }.get(k, d)

        with patch(
            "gns3_copilot.rag.chroma_store.get_chroma_collection",
            side_effect=RuntimeError("Connection failed"),
        ):
            result = self.tool._run("some query")

        assert "error" in result
        assert "Connection failed" in result["error"]

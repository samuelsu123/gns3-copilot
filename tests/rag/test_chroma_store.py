"""Tests for rag.chroma_store module."""

from unittest.mock import MagicMock, patch

import pytest


class TestResolveChromaPath:
    """Tests for _resolve_chroma_path."""

    @patch("gns3_copilot.rag.chroma_store.get_config")
    def test_uses_configured_path(self, mock_get_config):
        """When RAG_CHROMA_PATH is set, use that path."""
        mock_get_config.return_value = "/custom/chroma/path"

        from gns3_copilot.rag.chroma_store import _resolve_chroma_path

        result = _resolve_chroma_path()
        assert "/custom/chroma/path" in result

    @patch("gns3_copilot.rag.chroma_store.get_config")
    def test_uses_default_path_when_empty(self, mock_get_config):
        """When RAG_CHROMA_PATH is empty, use default data/chroma_db."""
        mock_get_config.return_value = ""

        from gns3_copilot.rag.chroma_store import _resolve_chroma_path

        result = _resolve_chroma_path()
        assert result.endswith("data/chroma_db")


class TestGetEmbeddingFunction:
    """Tests for get_embedding_function."""

    @patch("gns3_copilot.rag.chroma_store.get_config")
    def test_openai_provider(self, mock_get_config):
        """OpenAI provider creates OpenAIEmbeddings."""

        def config_side_effect(key, default=""):
            mapping = {
                "RAG_EMBEDDING_PROVIDER": "openai",
                "RAG_EMBEDDING_MODEL": "text-embedding-3-small",
                "RAG_EMBEDDING_API_KEY": "test-key",
                "RAG_EMBEDDING_BASE_URL": "",
                "MODEL_API_KEY": "",
                "BASE_URL": "",
            }
            return mapping.get(key, default)

        mock_get_config.side_effect = config_side_effect

        mock_embeddings_cls = MagicMock()
        mock_langchain_openai = MagicMock()
        mock_langchain_openai.OpenAIEmbeddings = mock_embeddings_cls

        with patch.dict("sys.modules", {"langchain_openai": mock_langchain_openai}):
            from gns3_copilot.rag.chroma_store import get_embedding_function

            get_embedding_function()
            mock_embeddings_cls.assert_called_once()

    @patch("gns3_copilot.rag.chroma_store.get_config")
    def test_unsupported_provider_raises(self, mock_get_config):
        """Unsupported provider raises ValueError."""

        def config_side_effect(key, default=""):
            if key == "RAG_EMBEDDING_PROVIDER":
                return "unsupported_provider"
            return default

        mock_get_config.side_effect = config_side_effect

        from gns3_copilot.rag.chroma_store import get_embedding_function

        with pytest.raises(ValueError, match="Unsupported RAG_EMBEDDING_PROVIDER"):
            get_embedding_function()


class TestGetChromaCollection:
    """Tests for get_chroma_collection."""

    @patch("gns3_copilot.rag.chroma_store._resolve_chroma_path", return_value="/tmp/test_chroma")
    @patch("gns3_copilot.rag.chroma_store.get_config")
    def test_creates_collection(self, mock_get_config, mock_resolve_path):
        """Creates or gets a ChromaDB collection."""
        mock_get_config.return_value = "test_collection"

        mock_collection = MagicMock()
        mock_collection.count.return_value = 0

        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection

        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.return_value = mock_client

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            from gns3_copilot.rag.chroma_store import get_chroma_collection

            result = get_chroma_collection("my_collection")

            mock_chromadb.PersistentClient.assert_called_once_with(
                path="/tmp/test_chroma"
            )
            mock_client.get_or_create_collection.assert_called_once_with(
                name="my_collection"
            )
            assert result == mock_collection

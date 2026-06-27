# demo/api/tests/test_vectorstore.py
import pytest
from unittest.mock import patch, MagicMock
from vectorstore import get_vectorstore, collection_exists, delete_collection


def test_get_vectorstore_returns_chroma():
    with patch("vectorstore.chromadb.PersistentClient"), \
         patch("vectorstore.OpenAIEmbeddings"), \
         patch("vectorstore.Chroma") as mock_chroma:
        mock_chroma.return_value = MagicMock()
        vs = get_vectorstore("test_collection")
        mock_chroma.assert_called_once()
        assert vs is not None


def test_collection_exists_true():
    with patch("vectorstore.chromadb.PersistentClient") as mock_client:
        mock_client.return_value.get_collection.return_value = MagicMock()
        assert collection_exists("existing_collection") is True


def test_collection_exists_false():
    with patch("vectorstore.chromadb.PersistentClient") as mock_client:
        mock_client.return_value.get_collection.side_effect = Exception("not found")
        assert collection_exists("missing_collection") is False


def test_delete_collection_no_error_if_missing():
    with patch("vectorstore.chromadb.PersistentClient") as mock_client:
        mock_client.return_value.delete_collection.side_effect = Exception("not found")
        delete_collection("missing")  # should not raise

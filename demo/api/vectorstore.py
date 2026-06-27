# demo/api/vectorstore.py
from pathlib import Path
import chromadb
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

CHROMA_PATH = Path(__file__).parent / "chroma_db"
CHROMA_PATH.mkdir(exist_ok=True)


def get_vectorstore(collection_name: str = "groentech_kb") -> Chroma:
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    return Chroma(
        client=client,
        collection_name=collection_name,
        embedding_function=embeddings,
    )


def collection_exists(collection_name: str) -> bool:
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    try:
        client.get_collection(collection_name)
        return True
    except Exception:
        return False


def delete_collection(collection_name: str) -> None:
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

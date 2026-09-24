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


def delete_expired_uploads(max_age_seconds: int) -> list[str]:
    """Delete upload_* collections whose first chunk is older than max_age_seconds.

    Returns the names that were deleted. Same rule as tools/cleanup_uploads.py,
    but callable from the API itself so the "deleted after 1 hour" promise
    holds without an external cron job.
    """
    import time

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    deleted: list[str] = []
    now = time.time()
    for entry in client.list_collections():
        # chromadb versions differ: Collection objects or plain names
        name = getattr(entry, "name", entry)
        if not isinstance(name, str) or not name.startswith("upload_"):
            continue
        try:
            metadatas = client.get_collection(name).peek(limit=1).get("metadatas") or []
            uploaded_at = (metadatas[0] or {}).get("uploaded_at", 0) if metadatas else 0
            # no timestamp (empty or foreign collection) counts as expired
            if now - float(uploaded_at) > max_age_seconds:
                client.delete_collection(name)
                deleted.append(name)
        except Exception:
            continue
    return deleted

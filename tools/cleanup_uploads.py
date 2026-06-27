# tools/cleanup_uploads.py
"""
Usage: python tools/cleanup_uploads.py
Deletes uploaded ChromaDB collections older than 1 hour.
Run manually or via cron/n8n.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "demo" / "api"))

from dotenv import load_dotenv
load_dotenv()

import chromadb
from vectorstore import CHROMA_PATH

MAX_AGE_SECONDS = 3600


def cleanup() -> int:
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collections = client.list_collections()
    deleted = 0

    for collection in collections:
        if not collection.name.startswith("upload_"):
            continue
        try:
            sample = collection.peek(limit=1)
            metadatas = sample.get("metadatas", [])
            if not metadatas:
                continue
            uploaded_at = metadatas[0].get("uploaded_at", 0)
            age = time.time() - uploaded_at
            if age > MAX_AGE_SECONDS:
                client.delete_collection(collection.name)
                print(f"Deleted {collection.name} (age: {age/60:.1f} min)")
                deleted += 1
        except Exception as e:
            print(f"Error processing {collection.name}: {e}")

    print(f"Cleanup complete. Deleted {deleted} collection(s).")
    return deleted


if __name__ == "__main__":
    cleanup()

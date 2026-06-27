# tools/ingest_documents.py
"""
Usage: python tools/ingest_documents.py
Run from project root. Loads GroenTech KB into ChromaDB.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "demo" / "api"))

from dotenv import load_dotenv
load_dotenv()

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from vectorstore import get_vectorstore, collection_exists

KB_PATH = Path("demo/api/data/groentech_kb")
COLLECTION_NAME = "groentech_kb"


def ingest() -> int:
    if collection_exists(COLLECTION_NAME):
        print(f"Collection '{COLLECTION_NAME}' already exists. Skipping ingestion.")
        print("To re-ingest, delete demo/api/chroma_db/ first.")
        return 0

    print(f"Loading documents from {KB_PATH}...")
    loader = DirectoryLoader(
        str(KB_PATH),
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    )
    docs = loader.load()
    print(f"Loaded {len(docs)} documents.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        separators=["\n## ", "\n### ", "\n", " "],
    )
    chunks = splitter.split_documents(docs)

    for chunk in chunks:
        source = Path(chunk.metadata.get("source", "onbekend")).name
        chunk.metadata["source"] = source

    print(f"Split into {len(chunks)} chunks. Ingesting into ChromaDB...")
    vs = get_vectorstore(COLLECTION_NAME)
    vs.add_documents(chunks)
    print(f"Done. {len(chunks)} chunks stored in '{COLLECTION_NAME}'.")
    return len(chunks)


if __name__ == "__main__":
    count = ingest()
    sys.exit(0 if count >= 0 else 1)

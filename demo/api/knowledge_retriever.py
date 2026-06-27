# demo/api/knowledge_retriever.py
from langchain_core.documents import Document
from models import RetrievedKnowledge, PipelineState
from vectorstore import get_vectorstore


def retrieve_knowledge(state: PipelineState) -> dict:
    vs = get_vectorstore(state["collection_name"])
    query = state["customer_message"]
    results: list[Document] = vs.similarity_search(query, k=3)

    if not results:
        return {
            "knowledge": RetrievedKnowledge(
                passages=[],
                sources=[],
                query_used=query,
            )
        }

    return {
        "knowledge": RetrievedKnowledge(
            passages=[doc.page_content for doc in results],
            sources=[doc.metadata.get("source", "onbekend") for doc in results],
            query_used=query,
        )
    }

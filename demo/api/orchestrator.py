# demo/api/orchestrator.py
from langgraph.graph import StateGraph, END
from models import PipelineState
from intent_classifier import classify_intent
from knowledge_retriever import retrieve_knowledge
from response_drafter import draft_response
from quality_checker import check_quality

FALLBACK = (
    "Dank u voor uw bericht. Wij hebben helaas geen specifieke informatie "
    "beschikbaar om uw vraag direct te beantwoorden. "
    "Een van onze medewerkers neemt zo spoedig mogelijk contact met u op."
)


def _should_retry_or_finalize(state: PipelineState) -> str:
    quality = state.get("quality")
    retry_count = state.get("retry_count", 0)
    if quality and not quality.passed and retry_count < 2:
        return "retry"
    return "finalize"


def _finalize(state: PipelineState) -> dict:
    quality = state.get("quality")
    draft = state.get("draft")
    if quality and quality.passed and draft:
        return {"final_response": draft.response}
    return {"final_response": FALLBACK}


def build_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("retrieve_knowledge", retrieve_knowledge)
    graph.add_node("draft_response", draft_response)
    graph.add_node("check_quality", check_quality)
    graph.add_node("finalize", _finalize)

    graph.set_entry_point("classify_intent")
    graph.add_edge("classify_intent", "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "draft_response")
    graph.add_edge("draft_response", "check_quality")
    graph.add_conditional_edges(
        "check_quality",
        _should_retry_or_finalize,
        {"retry": "draft_response", "finalize": "finalize"},
    )
    graph.add_edge("finalize", END)
    return graph.compile()


pipeline = build_graph()

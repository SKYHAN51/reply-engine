# demo/api/tests/test_agents.py
import pytest
from unittest.mock import patch, MagicMock
from models import (
    ClassifiedIntent, IntentType, RetrievedKnowledge,
    DraftedResponse, QualityCheckResult, PipelineState,
)

BASE_STATE: PipelineState = {
    "customer_message": "Wat zijn jullie openingstijden?",
    "collection_name": "groentech_kb",
    "intent": None,
    "knowledge": None,
    "draft": None,
    "quality": None,
    "retry_count": 0,
    "final_response": None,
    "error": None,
}


def test_classify_intent_returns_intent():
    mock_result = ClassifiedIntent(
        intent=IntentType.INFO,
        confidence=0.95,
        reasoning="Openingstijdenvraag",
    )
    with patch("intent_classifier._make_chain") as mock_chain_factory:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_result
        mock_chain_factory.return_value = mock_chain

        from intent_classifier import classify_intent
        result = classify_intent(BASE_STATE)

    assert "intent" in result
    assert result["intent"].intent == IntentType.INFO


def test_retrieve_knowledge_returns_passages():
    mock_doc1 = MagicMock()
    mock_doc1.page_content = "Openingstijden: ma-vr 08:30-17:30"
    mock_doc1.metadata = {"source": "contact.md"}

    mock_doc2 = MagicMock()
    mock_doc2.page_content = "Zaterdag gesloten"
    mock_doc2.metadata = {"source": "contact.md"}

    with patch("knowledge_retriever.get_vectorstore") as mock_vs_factory:
        mock_vs = MagicMock()
        mock_vs.similarity_search.return_value = [mock_doc1, mock_doc2]
        mock_vs_factory.return_value = mock_vs

        from knowledge_retriever import retrieve_knowledge
        result = retrieve_knowledge(BASE_STATE)

    assert "knowledge" in result
    assert len(result["knowledge"].passages) == 2
    assert result["knowledge"].sources == ["contact.md", "contact.md"]


def test_draft_response_returns_text():
    state_with_knowledge = {
        **BASE_STATE,
        "knowledge": RetrievedKnowledge(
            passages=["Openingstijden ma-vr 08:30-17:30"],
            sources=["contact.md"],
            query_used="openingstijden",
        ),
    }
    mock_result = DraftedResponse(response="Geachte klant, onze openingstijden zijn ma-vr 08:30-17:30.")

    with patch("response_drafter._make_chain") as mock_chain_factory:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_result
        mock_chain_factory.return_value = mock_chain

        from response_drafter import draft_response
        result = draft_response(state_with_knowledge)

    assert "draft" in result
    assert "openingstijden" in result["draft"].response.lower()


def test_quality_checker_passes_good_response():
    state_with_draft = {
        **BASE_STATE,
        "knowledge": RetrievedKnowledge(
            passages=["Openingstijden ma-vr 08:30-17:30"],
            sources=["contact.md"],
            query_used="openingstijden",
        ),
        "draft": DraftedResponse(response="Onze openingstijden zijn ma-vr 08:30-17:30."),
    }
    mock_result = QualityCheckResult(
        passed=True,
        hallucination_detected=False,
        confidence_score=0.95,
    )

    with patch("quality_checker._make_chain") as mock_chain_factory:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_result
        mock_chain_factory.return_value = mock_chain

        from quality_checker import check_quality
        result = check_quality(state_with_draft)

    assert result["quality"].passed is True
    assert result["retry_count"] == 0


def test_quality_checker_increments_retry_on_fail():
    state_with_draft = {
        **BASE_STATE,
        "knowledge": RetrievedKnowledge(passages=[], sources=[], query_used=""),
        "draft": DraftedResponse(response="Wij bieden gratis levering aan."),
    }
    mock_result = QualityCheckResult(
        passed=False,
        hallucination_detected=True,
        confidence_score=0.3,
        issues=["Gratis levering niet vermeld in kennisbank"],
    )

    with patch("quality_checker._make_chain") as mock_chain_factory:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_result
        mock_chain_factory.return_value = mock_chain

        from quality_checker import check_quality
        result = check_quality(state_with_draft)

    assert result["quality"].passed is False
    assert result["retry_count"] == 1

# demo/api/tests/test_orchestrator.py
import pytest
from unittest.mock import patch, MagicMock
from models import (
    ClassifiedIntent, IntentType, RetrievedKnowledge,
    DraftedResponse, QualityCheckResult, PipelineState,
)

MOCK_INTENT = ClassifiedIntent(intent=IntentType.INFO, confidence=0.9, reasoning="test")
MOCK_KNOWLEDGE = RetrievedKnowledge(passages=["Openingstijden ma-vr"], sources=["contact.md"], query_used="q")
MOCK_DRAFT = DraftedResponse(response="Geachte klant, openingstijden zijn ma-vr.")
MOCK_QUALITY_PASS = QualityCheckResult(passed=True, hallucination_detected=False, confidence_score=0.95)


def test_pipeline_returns_final_response():
    with patch("intent_classifier._make_chain") as m1, \
         patch("knowledge_retriever.get_vectorstore") as m2, \
         patch("response_drafter._make_chain") as m3, \
         patch("quality_checker._make_chain") as m4:

        m1.return_value = MagicMock(**{"invoke.return_value": MOCK_INTENT})
        mock_vs = MagicMock()
        mock_vs.similarity_search.return_value = [
            MagicMock(page_content="Openingstijden ma-vr", metadata={"source": "contact.md"})
        ]
        m2.return_value = mock_vs
        m3.return_value = MagicMock(**{"invoke.return_value": MOCK_DRAFT})
        m4.return_value = MagicMock(**{"invoke.return_value": MOCK_QUALITY_PASS})

        from orchestrator import pipeline
        initial_state: PipelineState = {
            "customer_message": "Wat zijn jullie openingstijden?",
            "collection_name": "groentech_kb",
            "intent": None, "knowledge": None, "draft": None, "quality": None,
            "retry_count": 0, "final_response": None, "error": None,
        }
        result = pipeline.invoke(initial_state)

    assert result["final_response"] is not None
    assert len(result["final_response"]) > 10


def test_pipeline_fallback_on_quality_fail():
    mock_quality_fail = QualityCheckResult(
        passed=False, hallucination_detected=True, confidence_score=0.2, issues=["hallucination"]
    )
    with patch("intent_classifier._make_chain") as m1, \
         patch("knowledge_retriever.get_vectorstore") as m2, \
         patch("response_drafter._make_chain") as m3, \
         patch("quality_checker._make_chain") as m4:

        m1.return_value = MagicMock(**{"invoke.return_value": MOCK_INTENT})
        mock_vs = MagicMock()
        mock_vs.similarity_search.return_value = []
        m2.return_value = mock_vs
        m3.return_value = MagicMock(**{"invoke.return_value": MOCK_DRAFT})
        m4.return_value = MagicMock(**{"invoke.return_value": mock_quality_fail})

        from orchestrator import pipeline
        initial_state: PipelineState = {
            "customer_message": "test",
            "collection_name": "groentech_kb",
            "intent": None, "knowledge": None, "draft": None, "quality": None,
            "retry_count": 0, "final_response": None, "error": None,
        }
        result = pipeline.invoke(initial_state)

    assert result["final_response"] is not None

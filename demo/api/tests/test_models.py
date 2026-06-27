# demo/api/tests/test_models.py
import pytest
from models import (
    IntentType, ClassifiedIntent, RetrievedKnowledge,
    DraftedResponse, QualityCheckResult, PipelineState,
    ProcessRequest, UploadResponse,
)


def test_intent_type_values():
    assert IntentType.INFO == "info"
    assert IntentType.KLACHT == "klacht"
    assert IntentType.COMMERCIEEL == "commercieel"
    assert IntentType.ONBEKEND == "onbekend"


def test_classified_intent_valid():
    intent = ClassifiedIntent(intent="info", confidence=0.95, reasoning="test")
    assert intent.intent == IntentType.INFO
    assert intent.confidence == 0.95


def test_classified_intent_confidence_bounds():
    with pytest.raises(Exception):
        ClassifiedIntent(intent="info", confidence=1.5, reasoning="test")


def test_retrieved_knowledge():
    k = RetrievedKnowledge(
        passages=["passage 1", "passage 2"],
        sources=["doc.md", "doc2.md"],
        query_used="test query",
    )
    assert len(k.passages) == 2


def test_quality_check_result_defaults():
    q = QualityCheckResult(
        passed=True,
        hallucination_detected=False,
        confidence_score=0.9,
    )
    assert q.issues == []


def test_pipeline_state_is_typed_dict():
    state: PipelineState = {
        "customer_message": "test",
        "collection_name": "groentech_kb",
        "intent": None,
        "knowledge": None,
        "draft": None,
        "quality": None,
        "retry_count": 0,
        "final_response": None,
        "error": None,
    }
    assert state["customer_message"] == "test"


def test_process_request_default_collection():
    req = ProcessRequest(message="hallo")
    assert req.collection_name == "groentech_kb"

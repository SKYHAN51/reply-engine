# demo/api/models.py
from enum import Enum
from typing import Optional, TypedDict
from pydantic import BaseModel, Field


class IntentType(str, Enum):
    INFO = "info"
    KLACHT = "klacht"
    COMMERCIEEL = "commercieel"
    ONBEKEND = "onbekend"


class ClassifiedIntent(BaseModel):
    intent: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class RetrievedKnowledge(BaseModel):
    passages: list[str]
    sources: list[str]
    query_used: str


class DraftedResponse(BaseModel):
    response: str


class QualityCheckResult(BaseModel):
    passed: bool
    hallucination_detected: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    issues: list[str] = []


class PipelineState(TypedDict):
    customer_message: str
    collection_name: str
    intent: Optional[ClassifiedIntent]
    knowledge: Optional[RetrievedKnowledge]
    draft: Optional[DraftedResponse]
    quality: Optional[QualityCheckResult]
    retry_count: int
    final_response: Optional[str]
    error: Optional[str]


class ProcessRequest(BaseModel):
    message: str
    collection_name: str = "groentech_kb"


class UploadResponse(BaseModel):
    collection_name: str
    document_name: str
    chunk_count: int
    message: str

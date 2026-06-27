# demo/api/tests/test_api.py
import pytest
import json
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_health_endpoint():
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_process_endpoint_streams_events():
    async def mock_astream(*args, **kwargs):
        yield {"classify_intent": {"intent": MagicMock(intent="info", confidence=0.9)}}
        yield {"retrieve_knowledge": {"knowledge": MagicMock(sources=["contact.md"], passages=["test"])}}
        yield {"draft_response": {"draft": MagicMock(response="Test antwoord.")}}
        yield {"check_quality": {"quality": MagicMock(passed=True, confidence_score=0.95)}}
        yield {"finalize": {"final_response": "Test antwoord."}}

    with patch("main.pipeline") as mock_pipeline:
        mock_pipeline.astream = mock_astream
        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/process",
                json={"message": "Test vraag", "collection_name": "groentech_kb"},
            )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    events = [
        json.loads(line[6:])
        for line in response.text.split("\n\n")
        if line.startswith("data: ") and line.strip() != "data: [DONE]"
    ]
    assert len(events) >= 1


@pytest.mark.asyncio
async def test_upload_rejects_non_pdf():
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_rejects_oversized_file():
    from main import app
    big_content = b"%PDF-1.4 " + b"x" * (2 * 1024 * 1024 + 1)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/upload",
            files={"file": ("big.pdf", big_content, "application/pdf")},
        )
    assert response.status_code == 400
    assert "groot" in response.json()["detail"]

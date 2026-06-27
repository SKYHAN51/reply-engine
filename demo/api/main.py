# demo/api/main.py
import json
import time
import uuid
import tempfile
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from models import PipelineState, ProcessRequest, UploadResponse
from orchestrator import pipeline
from vectorstore import get_vectorstore

app = FastAPI(title="Reply Engine API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STEP_LABELS = {
    "classify_intent": "Intentie herkend",
    "retrieve_knowledge": "Kennisbank doorzocht",
    "draft_response": "Antwoord opgesteld",
    "check_quality": "Kwaliteitscheck",
    "finalize": "Klaar",
}


def _extract_step_data(node_name: str, state: dict) -> dict:
    if node_name == "classify_intent" and state.get("intent"):
        intent = state["intent"]
        return {
            "intent": str(getattr(intent, "intent", intent)),
            "confidence": getattr(intent, "confidence", None),
        }
    if node_name == "retrieve_knowledge" and state.get("knowledge"):
        k = state["knowledge"]
        return {
            "sources": getattr(k, "sources", []),
            "passages": getattr(k, "passages", [])[:3],
        }
    if node_name == "check_quality" and state.get("quality"):
        q = state["quality"]
        return {
            "confidence_score": getattr(q, "confidence_score", 0.0),
            "passed": getattr(q, "passed", False),
        }
    if node_name == "finalize" and state.get("final_response"):
        quality = state.get("quality")
        return {
            "response": state["final_response"],
            "confidence_score": getattr(quality, "confidence_score", 0.9) if quality else 0.9,
        }
    return {}


async def _stream_pipeline(message: str, collection_name: str) -> AsyncGenerator[str, None]:
    start = time.time()
    initial_state: PipelineState = {
        "customer_message": message,
        "collection_name": collection_name,
        "intent": None, "knowledge": None, "draft": None, "quality": None,
        "retry_count": 0, "final_response": None, "error": None,
    }
    try:
        async for chunk in pipeline.astream(initial_state, stream_mode="updates"):
            for node_name, node_state in chunk.items():
                elapsed = int((time.time() - start) * 1000)
                event = {
                    "step": STEP_LABELS.get(node_name, node_name),
                    "node": node_name,
                    "status": "done",
                    "elapsed_ms": elapsed,
                    "data": _extract_step_data(node_name, node_state),
                }
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'step': 'Fout', 'node': 'error', 'status': 'error', 'elapsed_ms': 0, 'data': {'message': str(exc)}})}\n\n"
    yield "data: [DONE]\n\n"


@app.post("/process")
async def process_message(request: ProcessRequest):
    return StreamingResponse(
        _stream_pipeline(request.message, request.collection_name),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Alleen PDF bestanden worden ondersteund.")
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Bestand te groot. Maximaal 2MB.")

    collection_name = f"upload_{uuid.uuid4().hex[:8]}"

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        from langchain_community.document_loaders import PyPDFLoader
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        docs = PyPDFLoader(str(tmp_path)).load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
        chunks = splitter.split_documents(docs)

        for chunk in chunks:
            chunk.metadata["source"] = file.filename
            chunk.metadata["uploaded_at"] = time.time()

        vs = get_vectorstore(collection_name)
        vs.add_documents(chunks)
    finally:
        tmp_path.unlink(missing_ok=True)

    return UploadResponse(
        collection_name=collection_name,
        document_name=file.filename,
        chunk_count=len(chunks),
        message="Document geladen. U kunt nu maximaal 5 vragen stellen.",
    )


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}

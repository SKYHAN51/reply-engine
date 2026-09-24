# demo/api/main.py
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
import tempfile
from collections import deque
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from models import PipelineState, ProcessRequest, UploadResponse
from orchestrator import pipeline
from vectorstore import collection_exists, delete_expired_uploads, get_vectorstore

logger = logging.getLogger("reply-engine")

DEFAULT_COLLECTION = "groentech_kb"
_COLLECTION_RE = re.compile(r"^upload_[0-9a-f]{32}$")
# Geheim om upload-tokens te ondertekenen; val terug op een per-proces geheim (uploads leven max 1u).
_UPLOAD_TOKEN_SECRET = os.environ.get("UPLOAD_TOKEN_SECRET") or secrets.token_hex(32)

# Globaal plafond op dure LLM-verwerking (kostenbescherming tegen IP-rotatie).
_PROCESS_MAX_PER_HOUR = int(os.environ.get("PROCESS_MAX_PER_HOUR", "150"))
_process_times: deque[float] = deque()

_MAX_UPLOAD_BYTES = 2 * 1024 * 1024
# multipart framing on top of the file itself
_MAX_UPLOAD_REQUEST_BYTES = _MAX_UPLOAD_BYTES + 256 * 1024
_UPLOAD_TTL_SECONDS = 3600
_MAX_QUESTIONS_PER_UPLOAD = 5
_question_counts: dict[str, int] = {}
_last_cleanup = 0.0

_ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    "ALLOWED_ORIGINS",
    "https://reply-engine-beta.vercel.app,https://skyhan.app,http://localhost:8000",
).split(",") if o.strip()]


def _sign_collection(name: str) -> str:
    return hmac.new(_UPLOAD_TOKEN_SECRET.encode(), name.encode(), hashlib.sha256).hexdigest()


def _process_budget_ok() -> bool:
    now = time.time()
    while _process_times and now - _process_times[0] > 3600:
        _process_times.popleft()
    if len(_process_times) >= _PROCESS_MAX_PER_HOUR:
        return False
    _process_times.append(now)
    return True


def _client_ip(request: Request) -> str:
    # Behind Render's proxy request.client.host is the proxy for every
    # visitor, which put everyone in one shared rate-limit bucket. Use the
    # entry the proxy appended (rightmost X-Forwarded-For); the ones to its
    # left are whatever the client sent.
    forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    return forwarded[-1] if forwarded else get_remote_address(request)


def _cleanup_expired_uploads() -> None:
    """Deletes uploads older than the TTL, at most every 5 minutes."""
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < 300:
        return
    _last_cleanup = now
    try:
        for name in delete_expired_uploads(_UPLOAD_TTL_SECONDS):
            _question_counts.pop(name, None)
    except Exception:
        logger.exception("Opschonen van uploads mislukt")


limiter = Limiter(key_func=_client_ip)
app = FastAPI(title="Reply Engine API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Registered before CORS so CORS stays the outermost layer and these early
# rejections still carry CORS headers. Starlette has already buffered the
# whole multipart body by the time the /upload handler runs, so the size
# check has to happen here, on the declared length, before any of it is read.
@app.middleware("http")
async def _limit_upload_size(request: Request, call_next):
    if request.method == "POST" and request.url.path == "/upload":
        length = request.headers.get("content-length")
        if length is None:
            return JSONResponse({"detail": "Content-Length vereist."}, status_code=411)
        if not length.isdigit() or int(length) > _MAX_UPLOAD_REQUEST_BYTES:
            return JSONResponse({"detail": "Bestand te groot. Maximaal 2MB."}, status_code=413)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
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
    except Exception:
        logger.exception("Pipeline verwerking mislukt")
        err_event = {
            "step": "Fout", "node": "error", "status": "error", "elapsed_ms": 0,
            "data": {"message": "Er ging iets mis bij het verwerken van uw vraag."},
        }
        yield f"data: {json.dumps(err_event, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@app.post("/process")
@limiter.limit("10/minute")
async def process_message(request: Request, body: ProcessRequest):
    collection = body.collection_name
    _cleanup_expired_uploads()
    if collection == DEFAULT_COLLECTION:
        pass
    elif _COLLECTION_RE.match(collection):
        expected = _sign_collection(collection)
        if not body.collection_token or not hmac.compare_digest(body.collection_token, expected):
            raise HTTPException(status_code=403, detail="Geen toegang tot dit document.")
        # Without this, querying an expired (deleted) upload would silently
        # recreate it as an empty collection.
        if not collection_exists(collection):
            raise HTTPException(status_code=410, detail="Document verlopen. Upload het opnieuw.")
        # The page promised 5 questions per upload; this was only enforced in the browser.
        used = _question_counts.get(collection, 0)
        if used >= _MAX_QUESTIONS_PER_UPLOAD:
            raise HTTPException(status_code=429, detail="Maximum van 5 vragen per upload bereikt.")
        _question_counts[collection] = used + 1
    else:
        raise HTTPException(status_code=400, detail="Ongeldige collectie.")

    if not _process_budget_ok():
        raise HTTPException(status_code=429, detail="Demo tijdelijk overbelast. Probeer het later opnieuw.")

    return StreamingResponse(
        _stream_pipeline(body.message, collection),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/upload", response_model=UploadResponse)
@limiter.limit("5/minute")
async def upload_document(request: Request, file: UploadFile = File(...)):
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Alleen PDF bestanden worden ondersteund.")
    _cleanup_expired_uploads()
    content = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Bestand te groot. Maximaal 2MB.")
    if content[:5] != b"%PDF-":
        raise HTTPException(status_code=400, detail="Bestand is geen geldige PDF.")

    collection_name = f"upload_{secrets.token_hex(16)}"

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        from langchain_community.document_loaders import PyPDFLoader
        from langchain_text_splitters import RecursiveCharacterTextSplitter

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
        collection_token=_sign_collection(collection_name),
        document_name=filename,
        chunk_count=len(chunks),
        message="Document geladen. U kunt nu maximaal 5 vragen stellen.",
    )


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}

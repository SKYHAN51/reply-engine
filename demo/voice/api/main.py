from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models import FaqRequest, FaqResponse
from vapi_handler import get_faq

app = FastAPI(title="Voice Receptionist API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/vapi/faq", response_model=FaqResponse)
async def faq_endpoint(request: FaqRequest) -> FaqResponse:
    return get_faq(request)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "voice-receptionist"}

import hmac
import logging
import os
import time
from collections import deque

from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from models import (
    FaqRequest, FaqResponse,
    CheckAvailabilityRequest, CheckAvailabilityResponse,
    BookAppointmentRequest, BookAppointmentResponse,
)
from vapi_handler import get_faq, check_availability, book_appointment
from sms import send_sms_confirmation

logger = logging.getLogger("voice-api")

# Gedeeld geheim dat VAPI meestuurt als `X-Vapi-Secret` header (server.secret in de assistant config).
_VAPI_SECRET = os.environ.get("VAPI_SERVER_SECRET", "")
# Deze endpoints zijn server-to-server webhooks; standaard geen browser-origins toegestaan.
_ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]

# Globaal SMS-plafond (kosten- en misbruikbescherming), onafhankelijk van per-IP limiet.
_SMS_MAX_PER_HOUR = int(os.environ.get("SMS_MAX_PER_HOUR", "40"))
_sms_times: deque[float] = deque()


def _sms_budget_ok() -> bool:
    now = time.time()
    while _sms_times and now - _sms_times[0] > 3600:
        _sms_times.popleft()
    if len(_sms_times) >= _SMS_MAX_PER_HOUR:
        return False
    _sms_times.append(now)
    return True


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Voice Receptionist API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["POST"],
    allow_headers=["*"],
)


async def verify_vapi_secret(x_vapi_secret: str = Header(default="")) -> None:
    """Weiger elk verzoek zonder geldig gedeeld geheim (fail closed)."""
    if not _VAPI_SECRET:
        logger.error("VAPI_SERVER_SECRET is niet geconfigureerd — /vapi endpoints geblokkeerd.")
        raise HTTPException(status_code=503, detail="Server authenticatie niet geconfigureerd.")
    if not hmac.compare_digest(x_vapi_secret, _VAPI_SECRET):
        raise HTTPException(status_code=401, detail="Ongeldige of ontbrekende authenticatie.")


@app.post("/vapi/faq", response_model=FaqResponse, dependencies=[Depends(verify_vapi_secret)])
@limiter.limit("30/minute")
async def faq_endpoint(request: Request, body: FaqRequest) -> FaqResponse:
    return get_faq(body)


@app.post("/vapi/check-availability", response_model=CheckAvailabilityResponse,
          dependencies=[Depends(verify_vapi_secret)])
@limiter.limit("30/minute")
async def check_availability_endpoint(request: Request, body: CheckAvailabilityRequest) -> CheckAvailabilityResponse:
    return check_availability(body)


@app.post("/vapi/book-appointment", response_model=BookAppointmentResponse,
          dependencies=[Depends(verify_vapi_secret)])
@limiter.limit("10/minute")
async def book_appointment_endpoint(request: Request, body: BookAppointmentRequest) -> BookAppointmentResponse:
    result = book_appointment(body)
    if _sms_budget_ok():
        try:
            await send_sms_confirmation(body.naam, body.telefoon, body.datum, body.tijdstip)
        except Exception:
            logger.exception("SMS verzending mislukt")
    else:
        logger.warning("SMS-plafond bereikt (%s/uur) — bevestigings-SMS overgeslagen.", _SMS_MAX_PER_HOUR)
    return result


@app.post("/vapi/webhook", dependencies=[Depends(verify_vapi_secret)])
async def vapi_webhook(request: Request):
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "voice-receptionist"}

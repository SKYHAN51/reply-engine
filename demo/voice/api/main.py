from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from models import (
    FaqRequest, FaqResponse,
    CheckAvailabilityRequest, CheckAvailabilityResponse,
    BookAppointmentRequest, BookAppointmentResponse,
)
from vapi_handler import get_faq, check_availability, book_appointment
from sms import send_sms_confirmation

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


@app.post("/vapi/check-availability", response_model=CheckAvailabilityResponse)
async def check_availability_endpoint(request: CheckAvailabilityRequest) -> CheckAvailabilityResponse:
    return check_availability(request)


@app.post("/vapi/book-appointment", response_model=BookAppointmentResponse)
async def book_appointment_endpoint(request: BookAppointmentRequest) -> BookAppointmentResponse:
    result = book_appointment(request)
    await send_sms_confirmation(request.naam, request.telefoon, request.datum, request.tijdstip)
    return result


@app.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "voice-receptionist"}

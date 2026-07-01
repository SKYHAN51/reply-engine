from supabase import create_client
import os
from dotenv import load_dotenv
from pathlib import Path
from models import (
    FaqRequest, FaqResponse,
    CheckAvailabilityRequest, CheckAvailabilityResponse,
    BookAppointmentRequest, BookAppointmentResponse,
)

load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

FAQ_KENNISBANK = {
    "tarieven": "Onze voorrijkosten zijn €95. Het uurtarief is €65 exclusief BTW. Na 20:00 geldt een spoedtarief van €150.",
    "werkgebied": "Wij werken in Gelderland, Utrecht en Overijssel.",
    "services": "Wij lossen lekkages, verstoppingen, cv-ketel problemen, toilet- en kraanreparaties op.",
    "openingstijden": "Wij zijn bereikbaar van maandag tot vrijdag van 08:00 tot 18:00. Spoedgevallen 24 uur per dag, 7 dagen per week.",
    "spoed": "Voor spoedgevallen na 20:00 rekenen wij €150 voorrijkosten. Bel ons en wij zijn er zo snel mogelijk.",
}

DEFAULT_ANTWOORD = "Wij zijn Snelservice Installatie, een loodgietersbedrijf in Gelderland. Waarmee kan ik u helpen?"


def get_faq(request: FaqRequest) -> FaqResponse:
    antwoord = FAQ_KENNISBANK.get(request.categorie.lower(), DEFAULT_ANTWOORD)
    return FaqResponse(antwoord=antwoord)


def check_availability(request: CheckAvailabilityRequest) -> CheckAvailabilityResponse:
    tijdslot_full = request.tijdstip if len(request.tijdstip) == 8 else f"{request.tijdstip}:00"

    exact = (
        supabase.table("availability")
        .select("*")
        .eq("dag", request.datum)
        .eq("tijdslot", tijdslot_full)
        .eq("beschikbaar", True)
        .execute()
    )
    beschikbaar = len(exact.data) > 0

    alts = (
        supabase.table("availability")
        .select("tijdslot")
        .eq("dag", request.datum)
        .eq("beschikbaar", True)
        .limit(4)
        .execute()
    )
    alternatieven = [
        r["tijdslot"][:5]
        for r in alts.data
        if r["tijdslot"][:5] != request.tijdstip[:5]
    ][:2]

    return CheckAvailabilityResponse(beschikbaar=beschikbaar, alternatieven=alternatieven)


def book_appointment(request: BookAppointmentRequest) -> BookAppointmentResponse:
    tijdslot_full = request.tijdstip if len(request.tijdstip) == 8 else f"{request.tijdstip}:00"

    result = (
        supabase.table("appointments")
        .insert({
            "naam": request.naam,
            "telefoon": request.telefoon,
            "datum": request.datum,
            "tijdstip": tijdslot_full,
            "probleem": request.probleem,
            "status": "gepland",
        })
        .execute()
    )
    afspraak_id = result.data[0]["id"]

    supabase.table("availability").update({"beschikbaar": False}).eq("dag", request.datum).eq("tijdslot", tijdslot_full).execute()

    return BookAppointmentResponse(bevestigd=True, afspraak_id=afspraak_id)

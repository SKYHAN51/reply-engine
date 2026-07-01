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

from pydantic import BaseModel


class FaqRequest(BaseModel):
    categorie: str


class FaqResponse(BaseModel):
    antwoord: str


class CheckAvailabilityRequest(BaseModel):
    datum: str
    tijdstip: str


class CheckAvailabilityResponse(BaseModel):
    beschikbaar: bool
    alternatieven: list[str]


class BookAppointmentRequest(BaseModel):
    naam: str
    telefoon: str
    datum: str
    tijdstip: str
    probleem: str


class BookAppointmentResponse(BaseModel):
    bevestigd: bool
    afspraak_id: str

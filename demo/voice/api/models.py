import re

from pydantic import BaseModel, field_validator

# E.164: optioneel '+', geen leidende 0, 8-15 cijfers totaal.
_PHONE_RE = re.compile(r"^\+?[1-9]\d{7,14}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$")


def _clean_text(value: str, *, veld: str, max_len: int) -> str:
    """Strip, lengte-check en weiger control chars / newlines (SMS/webhook injectie)."""
    if not isinstance(value, str):
        raise ValueError(f"{veld} moet tekst zijn")
    value = value.strip()
    if not value:
        raise ValueError(f"{veld} mag niet leeg zijn")
    if len(value) > max_len:
        raise ValueError(f"{veld} is te lang (max {max_len})")
    if any(ord(c) < 32 for c in value):
        raise ValueError(f"{veld} bevat ongeldige tekens")
    return value


class FaqRequest(BaseModel):
    categorie: str

    @field_validator("categorie")
    @classmethod
    def _v_categorie(cls, v: str) -> str:
        return _clean_text(v, veld="categorie", max_len=40)


class FaqResponse(BaseModel):
    antwoord: str


class CheckAvailabilityRequest(BaseModel):
    datum: str
    tijdstip: str

    @field_validator("datum")
    @classmethod
    def _v_datum(cls, v: str) -> str:
        v = v.strip()
        if not _DATE_RE.match(v):
            raise ValueError("datum moet YYYY-MM-DD zijn")
        return v

    @field_validator("tijdstip")
    @classmethod
    def _v_tijdstip(cls, v: str) -> str:
        v = v.strip()
        if not _TIME_RE.match(v):
            raise ValueError("tijdstip moet HH:MM zijn")
        return v


class CheckAvailabilityResponse(BaseModel):
    beschikbaar: bool
    alternatieven: list[str]


class BookAppointmentRequest(BaseModel):
    naam: str
    telefoon: str
    datum: str
    tijdstip: str
    probleem: str

    @field_validator("naam")
    @classmethod
    def _v_naam(cls, v: str) -> str:
        return _clean_text(v, veld="naam", max_len=100)

    @field_validator("probleem")
    @classmethod
    def _v_probleem(cls, v: str) -> str:
        return _clean_text(v, veld="probleem", max_len=500)

    @field_validator("telefoon")
    @classmethod
    def _v_telefoon(cls, v: str) -> str:
        v = v.strip().replace(" ", "").replace("-", "")
        if not _PHONE_RE.match(v):
            raise ValueError("telefoon moet een geldig telefoonnummer zijn")
        return v

    @field_validator("datum")
    @classmethod
    def _v_datum(cls, v: str) -> str:
        v = v.strip()
        if not _DATE_RE.match(v):
            raise ValueError("datum moet YYYY-MM-DD zijn")
        return v

    @field_validator("tijdstip")
    @classmethod
    def _v_tijdstip(cls, v: str) -> str:
        v = v.strip()
        if not _TIME_RE.match(v):
            raise ValueError("tijdstip moet HH:MM zijn")
        return v


class BookAppointmentResponse(BaseModel):
    bevestigd: bool
    afspraak_id: str

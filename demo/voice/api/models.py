import re

from pydantic import BaseModel, field_validator

# Alleen Nederlandse mobiele nummers (06…, +316…, 00316…): de bevestiging
# gaat per SMS, en het oude open E.164-patroon liet de publieke demo SMS'en
# naar willekeurige (dure) buitenlandse nummers — SMS-pumping. Het weigerde
# bovendien juist het gewone Nederlandse formaat 06…, want dat begint met 0.
_NL_MOBILE_RE = re.compile(r"^(?:\+31|0031|0)6(\d{8})$")
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
        match = _NL_MOBILE_RE.match(v)
        if not match:
            raise ValueError("telefoon moet een Nederlands mobiel nummer zijn (06…)")
        return "+316" + match.group(1)

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
    # None wanneer het tijdslot niet (meer) vrij was
    afspraak_id: str | None = None

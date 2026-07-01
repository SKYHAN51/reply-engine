# Voice Receptionist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bouw een AI Voice Receptionist voor Snelservice Installatie BV — een loodgietersbedrijf — dat via een browser web call FAQ beantwoordt, afspraken boekt, SMS stuurt en alles logt in Supabase.

**Architecture:** VAPI beheert het spraakgesprek (STT, GPT-4o, Dutch TTS). Bij elke actie roept VAPI een FastAPI endpoint aan. FastAPI regelt de business logic, schrijft naar Supabase en triggert n8n voor SMS. De frontend is een standalone HTML-pagina met de VAPI web widget.

**Tech Stack:** VAPI (voice), FastAPI (API), Supabase (database), n8n (SMS), Vercel (frontend), Render (API), Tailwind CSS (UI)

## Global Constraints

- Python 3.11
- FastAPI >= 0.115.0
- supabase-py >= 2.0.0
- httpx >= 0.27.0
- Alles in het Nederlands (AI-stem, SMS, UI)
- Geen Twilio nodig voor demo — VAPI web call via browser
- Consistent met Reply Engine stijl (donkere UI, Tailwind)

---

## Bestandsstructuur

```
Newsletters Demo/
├── demo/
│   └── voice/
│       ├── index.html              ← demo pagina (Tailwind + VAPI widget)
│       └── api/
│           ├── main.py             ← FastAPI app + endpoints
│           ├── vapi_handler.py     ← FAQ, availability, booking logica
│           ├── sms.py              ← n8n webhook trigger
│           └── models.py           ← Pydantic schemas
├── tools/
│   └── seed_availability.py        ← vul Supabase met demo-slots
└── workflows/
    └── voice_receptionist.md       ← SOP (bestaand patroon volgen)
```

---

### Task 1: Supabase tabellen + seed data

**Files:**
- Create: `tools/seed_availability.py`

**Interfaces:**
- Produces: Supabase tabellen `appointments` en `availability` met demo-slots voor de komende 14 werkdagen

- [ ] **Stap 1: Maak tabellen aan in Supabase dashboard**

Ga naar Supabase → SQL Editor → voer uit:

```sql
create table appointments (
  id uuid primary key default gen_random_uuid(),
  created_at timestamp with time zone default now(),
  naam text not null,
  telefoon text not null,
  datum date not null,
  tijdstip time not null,
  probleem text not null,
  status text default 'gepland'
);

create table availability (
  id uuid primary key default gen_random_uuid(),
  dag date not null,
  tijdslot time not null,
  beschikbaar boolean default true
);
```

- [ ] **Stap 2: Schrijf seed script**

Maak `tools/seed_availability.py`:

```python
from supabase import create_client
import os
from dotenv import load_dotenv
from datetime import date, timedelta
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

slots = ["09:00:00", "10:00:00", "11:00:00", "13:00:00", "14:00:00", "15:00:00", "16:00:00"]
today = date.today()

rows = []
for i in range(1, 15):
    dag = today + timedelta(days=i)
    if dag.weekday() < 5:
        for tijdslot in slots:
            rows.append({"dag": dag.isoformat(), "tijdslot": tijdslot, "beschikbaar": True})

supabase.table("availability").insert(rows).execute()
print(f"Seeded {len(rows)} slots.")
```

- [ ] **Stap 3: Voer seed script uit**

```bash
cd "C:\Users\skayh\Desktop\Newsletters Demo"
python tools/seed_availability.py
```

Verwacht: `Seeded 70 slots.` (of vergelijkbaar)

- [ ] **Stap 4: Verifieer in Supabase dashboard**

Ga naar Table Editor → `availability` → controleer dat er rijen zijn met `beschikbaar: true`

- [ ] **Stap 5: Commit**

```bash
git add tools/seed_availability.py
git commit -m "feat: add supabase tables and seed script for voice receptionist"
```

---

### Task 2: FastAPI models + FAQ endpoint

**Files:**
- Create: `demo/voice/api/models.py`
- Create: `demo/voice/api/vapi_handler.py`
- Create: `demo/voice/api/main.py`

**Interfaces:**
- Consumes: `SUPABASE_URL`, `SUPABASE_KEY` uit `.env`
- Produces:
  - `POST /vapi/faq` → `FaqResponse(antwoord: str)`
  - `GET /health` → `{"status": "healthy"}`

- [ ] **Stap 1: Schrijf models.py**

Maak `demo/voice/api/models.py`:

```python
from pydantic import BaseModel
from typing import Optional


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
```

- [ ] **Stap 2: Schrijf vapi_handler.py (FAQ gedeelte)**

Maak `demo/voice/api/vapi_handler.py`:

```python
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
```

- [ ] **Stap 3: Schrijf main.py met FAQ endpoint**

Maak `demo/voice/api/main.py`:

```python
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
```

- [ ] **Stap 4: Test FAQ endpoint**

```bash
cd "C:\Users\skayh\Desktop\Newsletters Demo\demo\voice\api"
pip install fastapi uvicorn supabase python-dotenv httpx
uvicorn main:app --reload --port 8001
```

In een nieuw terminal:

```bash
curl -X POST http://localhost:8001/vapi/faq \
  -H "Content-Type: application/json" \
  -d '{"categorie": "tarieven"}'
```

Verwacht:
```json
{"antwoord": "Onze voorrijkosten zijn €95. Het uurtarief is €65 exclusief BTW. Na 20:00 geldt een spoedtarief van €150."}
```

- [ ] **Stap 5: Commit**

```bash
git add demo/voice/api/models.py demo/voice/api/vapi_handler.py demo/voice/api/main.py
git commit -m "feat: add fastapi skeleton and faq endpoint for voice receptionist"
```

---

### Task 3: Availability + booking endpoints

**Files:**
- Modify: `demo/voice/api/vapi_handler.py` — voeg availability en booking logica toe
- Modify: `demo/voice/api/main.py` — voeg 2 endpoints toe
- Create: `demo/voice/api/sms.py`

**Interfaces:**
- Consumes: `vapi_handler.get_faq`, Supabase tabellen `appointments` en `availability`
- Produces:
  - `POST /vapi/check-availability` → `CheckAvailabilityResponse`
  - `POST /vapi/book-appointment` → `BookAppointmentResponse` + SMS trigger

- [ ] **Stap 1: Voeg availability logica toe aan vapi_handler.py**

Voeg toe onderaan `demo/voice/api/vapi_handler.py`:

```python
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
```

- [ ] **Stap 2: Schrijf sms.py**

Maak `demo/voice/api/sms.py`:

```python
import httpx
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

N8N_SMS_WEBHOOK = os.environ.get("N8N_SMS_WEBHOOK_URL", "")


async def send_sms_confirmation(naam: str, telefoon: str, datum: str, tijdstip: str) -> None:
    if not N8N_SMS_WEBHOOK:
        print(f"[SMS] Webhook niet geconfigureerd. Zou SMS sturen naar {telefoon}")
        return

    bericht = (
        f"Bevestiging Snelservice Installatie: "
        f"afspraak op {datum} om {tijdstip[:5]}. "
        f"Vragen? Bel 026-1234567."
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(N8N_SMS_WEBHOOK, json={
            "naam": naam,
            "telefoon": telefoon,
            "bericht": bericht,
        })
```

- [ ] **Stap 3: Voeg endpoints toe aan main.py**

Vervang de volledige inhoud van `demo/voice/api/main.py`:

```python
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
```

- [ ] **Stap 4: Test availability endpoint**

```bash
curl -X POST http://localhost:8001/vapi/check-availability \
  -H "Content-Type: application/json" \
  -d '{"datum": "2026-07-08", "tijdstip": "10:00"}'
```

Verwacht:
```json
{"beschikbaar": true, "alternatieven": ["09:00", "11:00"]}
```

- [ ] **Stap 5: Test booking endpoint**

```bash
curl -X POST http://localhost:8001/vapi/book-appointment \
  -H "Content-Type: application/json" \
  -d '{"naam": "Jan de Vries", "telefoon": "0612345678", "datum": "2026-07-08", "tijdstip": "10:00", "probleem": "lekkende kraan"}'
```

Verwacht:
```json
{"bevestigd": true, "afspraak_id": "<uuid>"}
```

Controleer in Supabase → `appointments` → rij aangemaakt. `availability` → slot op `beschikbaar: false`.

- [ ] **Stap 6: Commit**

```bash
git add demo/voice/api/vapi_handler.py demo/voice/api/main.py demo/voice/api/sms.py
git commit -m "feat: add availability check, booking endpoint and sms trigger"
```

---

### Task 4: n8n SMS workflow

**Files:**
- n8n workflow (in skyhan.app n8n instance)

**Interfaces:**
- Consumes: Webhook POST met `{naam, telefoon, bericht}`
- Produces: SMS via MessageBird naar klant + `N8N_SMS_WEBHOOK_URL` voor in `.env`

- [ ] **Stap 1: Maak n8n workflow aan**

Ga naar n8n op skyhan.app:

1. Nieuw workflow → naam: "Voice Receptionist — SMS Bevestiging"
2. Voeg toe: **Webhook** node
   - Method: POST
   - Path: `voice-sms-confirmation`
   - Response mode: Immediately
3. Voeg toe: **MessageBird** node (of **HTTP Request** als fallback)
   - Bij MessageBird: To = `{{$json.telefoon}}`, Body = `{{$json.bericht}}`
   - Bij HTTP Request (Twilio fallback): zie stap 2
4. Activeer workflow → kopieer webhook URL

- [ ] **Stap 2: Alternatief zonder MessageBird (HTTP Request naar Twilio of log)**

Als MessageBird niet beschikbaar is, gebruik een HTTP Request node die naar een logging endpoint stuurt of gebruik Twilio:

```
URL: https://api.twilio.com/2010-04-01/Accounts/{{$env.TWILIO_SID}}/Messages.json
Method: POST
Authentication: Basic Auth (TWILIO_SID / TWILIO_TOKEN)
Body: To={{$json.telefoon}}&From=+31...&Body={{$json.bericht}}
```

Voor de **demo** is een console.log (Set node die output toont) ook voldoende — het gaat om het aantonen van de flow.

- [ ] **Stap 3: Voeg webhook URL toe aan .env**

Voeg toe aan `.env`:
```
N8N_SMS_WEBHOOK_URL=https://skyhan.app/webhook/voice-sms-confirmation
```

- [ ] **Stap 4: Test webhook**

```bash
curl -X POST https://skyhan.app/webhook/voice-sms-confirmation \
  -H "Content-Type: application/json" \
  -d '{"naam": "Test", "telefoon": "0612345678", "bericht": "Bevestiging test afspraak."}'
```

Verwacht: HTTP 200, SMS of log in n8n execution history.

- [ ] **Stap 5: Commit**

```bash
git add .env
git commit -m "feat: configure n8n sms webhook for voice receptionist"
```

---

### Task 5: VAPI assistant aanmaken

**Files:**
- Create: `tools/create_vapi_assistant.py`

**Interfaces:**
- Consumes: `VAPI_PRIVATE_KEY`, FastAPI URL (Render na deploy, of localhost voor test)
- Produces: `VAPI_ASSISTANT_ID` en `VAPI_PUBLIC_KEY` voor in `.env`

- [ ] **Stap 1: Maak VAPI account aan**

Ga naar vapi.ai → Sign up → kopieer:
- **Public Key** (voor frontend)
- **Private Key** (voor server-side)

Voeg toe aan `.env`:
```
VAPI_PUBLIC_KEY=pk_...
VAPI_PRIVATE_KEY=sk_...
```

- [ ] **Stap 2: Schrijf create_vapi_assistant.py**

Maak `tools/create_vapi_assistant.py`:

```python
import httpx
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

VAPI_KEY = os.environ["VAPI_PRIVATE_KEY"]
API_BASE = os.environ.get("VOICE_API_URL", "http://localhost:8001")

assistant = {
    "name": "Snelservice Receptionist",
    "model": {
        "provider": "openai",
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Je bent de AI-receptionist van Snelservice Installatie BV, "
                    "een loodgietersbedrijf in Gelderland. "
                    "Je spreekt altijd Nederlands. Je bent professioneel, vriendelijk en to-the-point. "
                    "Je kunt: vragen beantwoorden over tarieven, werkgebied en services, "
                    "beschikbaarheid checken en afspraken inplannen. "
                    "Houd antwoorden kort (maximaal 2 zinnen). Stel één vraag tegelijk. "
                    "Begin het gesprek altijd met: "
                    "'Goedendag, u spreekt met Snelservice Installatie. Waarmee kan ik u helpen?'"
                ),
            }
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_faq",
                    "description": "Beantwoord een vraag over tarieven, werkgebied, services of openingstijden",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "categorie": {
                                "type": "string",
                                "enum": ["tarieven", "werkgebied", "services", "openingstijden", "spoed"],
                                "description": "De categorie van de vraag",
                            }
                        },
                        "required": ["categorie"],
                    },
                },
                "server": {"url": f"{API_BASE}/vapi/faq"},
            },
            {
                "type": "function",
                "function": {
                    "name": "check_availability",
                    "description": "Controleer of een tijdslot beschikbaar is",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "datum": {"type": "string", "description": "Datum in YYYY-MM-DD formaat"},
                            "tijdstip": {"type": "string", "description": "Tijdstip in HH:MM formaat"},
                        },
                        "required": ["datum", "tijdstip"],
                    },
                },
                "server": {"url": f"{API_BASE}/vapi/check-availability"},
            },
            {
                "type": "function",
                "function": {
                    "name": "book_appointment",
                    "description": "Boek een afspraak na bevestiging van naam, telefoonnummer, datum, tijdstip en probleem",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "naam": {"type": "string"},
                            "telefoon": {"type": "string"},
                            "datum": {"type": "string", "description": "YYYY-MM-DD"},
                            "tijdstip": {"type": "string", "description": "HH:MM"},
                            "probleem": {"type": "string"},
                        },
                        "required": ["naam", "telefoon", "datum", "tijdstip", "probleem"],
                    },
                },
                "server": {"url": f"{API_BASE}/vapi/book-appointment"},
            },
        ],
    },
    "voice": {
        "provider": "openai",
        "voiceId": "alloy",
    },
    "firstMessage": "Goedendag, u spreekt met Snelservice Installatie. Waarmee kan ik u helpen?",
    "endCallMessage": "Bedankt voor uw oproep. Fijne dag verder!",
    "silenceTimeoutSeconds": 20,
    "maxDurationSeconds": 300,
}

response = httpx.post(
    "https://api.vapi.ai/assistant",
    headers={"Authorization": f"Bearer {VAPI_KEY}"},
    json=assistant,
    timeout=30.0,
)
data = response.json()
print(f"Assistant ID: {data['id']}")
print(f"Voeg toe aan .env: VAPI_ASSISTANT_ID={data['id']}")
```

- [ ] **Stap 3: Voer script uit**

```bash
python tools/create_vapi_assistant.py
```

Verwacht:
```
Assistant ID: asst_xxxxxxxx
Voeg toe aan .env: VAPI_ASSISTANT_ID=asst_xxxxxxxx
```

- [ ] **Stap 4: Voeg toe aan .env**

```
VAPI_ASSISTANT_ID=asst_xxxxxxxx
VOICE_API_URL=http://localhost:8001
```

- [ ] **Stap 5: Commit**

```bash
git add tools/create_vapi_assistant.py .env
git commit -m "feat: add vapi assistant creation script for voice receptionist"
```

---

### Task 6: Frontend demo pagina

**Files:**
- Create: `demo/voice/index.html`

**Interfaces:**
- Consumes: `VAPI_PUBLIC_KEY`, `VAPI_ASSISTANT_ID` (hardcoded in HTML na deploy)
- Produces: Werkende demo pagina met web call knop, live transcript en booking card

- [ ] **Stap 1: Schrijf index.html**

Maak `demo/voice/index.html`:

```html
<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Voice Receptionist — Snelservice Installatie</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    :root {
      --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
    }
    body { background: #0a0a0b; color: #f5f5f5; font-family: 'Inter', system-ui, sans-serif; }
    .pulse { animation: pulse 2s infinite; }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }
    .fade-in {
      animation: fadeIn 0.4s var(--ease-out) both;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .call-btn {
      transition: transform 160ms var(--ease-out), box-shadow 160ms var(--ease-out);
    }
    .call-btn:hover { transform: scale(1.02); }
    .call-btn:active { transform: scale(0.97); }
  </style>
</head>
<body class="min-h-screen flex flex-col">

  <!-- Header -->
  <header class="border-b border-white/10 px-6 py-4">
    <div class="max-w-4xl mx-auto flex items-center justify-between">
      <span class="text-sm font-mono text-white/40">skyhan.app / voice-receptionist</span>
      <a href="https://skyhan.app" class="text-sm text-white/40 hover:text-white transition-colors">← Portfolio</a>
    </div>
  </header>

  <!-- Main -->
  <main class="flex-1 max-w-4xl mx-auto w-full px-6 py-16">

    <!-- Hero -->
    <div class="mb-12">
      <div class="text-xs font-mono uppercase tracking-widest text-white/30 mb-4">Project C · Voice AI</div>
      <h1 class="text-4xl font-bold mb-4 leading-tight">
        AI Voice Receptionist
      </h1>
      <p class="text-lg text-white/60 max-w-xl">
        Nooit meer een gemiste oproep. Deze AI-receptionist neemt op, beantwoordt vragen
        en boekt afspraken — 24/7, in het Nederlands.
      </p>
    </div>

    <!-- Demo card -->
    <div class="bg-white/5 border border-white/10 rounded-2xl p-8 mb-8">
      <div class="flex items-center gap-3 mb-6">
        <div class="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center text-lg">🔧</div>
        <div>
          <div class="font-semibold">Snelservice Installatie BV</div>
          <div class="text-sm text-white/40">Loodgietersbedrijf · Gelderland</div>
        </div>
        <div class="ml-auto">
          <span id="status-badge" class="text-xs font-mono px-2 py-1 rounded-full bg-green-500/10 text-green-400">
            ● Beschikbaar
          </span>
        </div>
      </div>

      <!-- Call button -->
      <div id="call-section" class="text-center py-4">
        <button
          id="call-btn"
          onclick="startCall()"
          class="call-btn bg-white text-black font-semibold px-8 py-4 rounded-xl text-base"
        >
          📞 Bel Snelservice Installatie
        </button>
        <p class="text-xs text-white/30 mt-3">Microfoon vereist · Gratis · Geen app nodig</p>
      </div>

      <!-- Active call UI (hidden by default) -->
      <div id="active-call" class="hidden">
        <div class="flex items-center justify-center gap-3 mb-6">
          <div class="w-3 h-3 rounded-full bg-red-500 pulse"></div>
          <span class="text-sm font-mono text-white/60">Gesprek actief...</span>
          <span id="call-timer" class="text-sm font-mono text-white/40">0:00</span>
        </div>

        <!-- Transcript -->
        <div id="transcript" class="bg-black/30 rounded-xl p-4 mb-4 min-h-32 max-h-64 overflow-y-auto space-y-3">
          <p class="text-white/30 text-sm text-center">Transcript verschijnt hier...</p>
        </div>

        <!-- End call -->
        <div class="text-center">
          <button
            onclick="endCall()"
            class="call-btn bg-red-500/20 text-red-400 border border-red-500/30 font-medium px-6 py-3 rounded-xl text-sm"
          >
            ✕ Gesprek beëindigen
          </button>
        </div>
      </div>
    </div>

    <!-- Booking card (hidden by default) -->
    <div id="booking-card" class="hidden fade-in bg-green-500/10 border border-green-500/30 rounded-2xl p-6 mb-8">
      <div class="flex items-center gap-3 mb-4">
        <div class="text-2xl">✅</div>
        <div>
          <div class="font-semibold text-green-400">Afspraak bevestigd</div>
          <div class="text-sm text-white/40">SMS bevestiging verstuurd</div>
        </div>
      </div>
      <div id="booking-details" class="space-y-2 text-sm text-white/70"></div>
    </div>

    <!-- Stack -->
    <div class="flex gap-2 flex-wrap mb-12">
      <span class="text-xs font-mono px-3 py-1 rounded-full bg-white/5 border border-white/10 text-white/50">VAPI</span>
      <span class="text-xs font-mono px-3 py-1 rounded-full bg-white/5 border border-white/10 text-white/50">FastAPI</span>
      <span class="text-xs font-mono px-3 py-1 rounded-full bg-white/5 border border-white/10 text-white/50">GPT-4o</span>
      <span class="text-xs font-mono px-3 py-1 rounded-full bg-white/5 border border-white/10 text-white/50">Supabase</span>
      <span class="text-xs font-mono px-3 py-1 rounded-full bg-white/5 border border-white/10 text-white/50">n8n</span>
    </div>

    <!-- CTA -->
    <div class="border border-white/10 rounded-2xl p-6 text-center">
      <p class="text-white/60 mb-4">Wil je dit voor jouw bedrijf?</p>
      <a
        href="mailto:skayhan0@gmail.com?subject=Voice Receptionist interesse"
        class="inline-block bg-white text-black font-semibold px-6 py-3 rounded-xl text-sm hover:bg-white/90 transition-colors"
      >
        Neem contact op →
      </a>
    </div>

  </main>

  <!-- VAPI SDK -->
  <script>
    // Vapi configuratie — vervang na deploy
    const VAPI_PUBLIC_KEY = "JOUW_VAPI_PUBLIC_KEY";
    const VAPI_ASSISTANT_ID = "JOUW_VAPI_ASSISTANT_ID";

    let vapi = null;
    let timerInterval = null;
    let secondsElapsed = 0;
    let lastBooking = null;

    async function loadVapi() {
      const { default: Vapi } = await import("https://cdn.jsdelivr.net/npm/@vapi-ai/web@latest/dist/vapi.js");
      vapi = new Vapi(VAPI_PUBLIC_KEY);

      vapi.on("call-start", () => {
        document.getElementById("call-section").classList.add("hidden");
        document.getElementById("active-call").classList.remove("hidden");
        document.getElementById("status-badge").textContent = "● Verbonden";
        document.getElementById("status-badge").className = "text-xs font-mono px-2 py-1 rounded-full bg-red-500/10 text-red-400";
        startTimer();
      });

      vapi.on("call-end", () => {
        document.getElementById("active-call").classList.add("hidden");
        document.getElementById("call-section").classList.remove("hidden");
        document.getElementById("status-badge").textContent = "● Beschikbaar";
        document.getElementById("status-badge").className = "text-xs font-mono px-2 py-1 rounded-full bg-green-500/10 text-green-400";
        stopTimer();
        if (lastBooking) showBookingCard(lastBooking);
      });

      vapi.on("message", (msg) => {
        if (msg.type === "transcript") {
          addTranscriptLine(msg.role, msg.transcript);
        }
        if (msg.type === "tool-calls") {
          const toolCall = msg.toolCallList?.[0];
          if (toolCall?.function?.name === "book_appointment") {
            lastBooking = JSON.parse(toolCall.function.arguments || "{}");
          }
        }
      });
    }

    async function startCall() {
      if (!vapi) await loadVapi();
      document.getElementById("transcript").innerHTML = "";
      lastBooking = null;
      await vapi.start(VAPI_ASSISTANT_ID);
    }

    function endCall() {
      if (vapi) vapi.stop();
    }

    function addTranscriptLine(role, text) {
      const container = document.getElementById("transcript");
      const isFirst = container.querySelector("p.text-white\\/30");
      if (isFirst) isFirst.remove();

      const line = document.createElement("div");
      line.className = `flex gap-2 ${role === "assistant" ? "" : "flex-row-reverse"}`;
      line.innerHTML = `
        <div class="max-w-xs px-3 py-2 rounded-xl text-sm ${
          role === "assistant"
            ? "bg-white/10 text-white/80"
            : "bg-blue-500/20 text-blue-200"
        }">
          <span class="text-xs font-mono opacity-50 block mb-1">${role === "assistant" ? "AI" : "Klant"}</span>
          ${text}
        </div>
      `;
      container.appendChild(line);
      container.scrollTop = container.scrollHeight;
    }

    function showBookingCard(booking) {
      const card = document.getElementById("booking-card");
      const details = document.getElementById("booking-details");
      details.innerHTML = `
        <div class="grid grid-cols-2 gap-2">
          <span class="text-white/40">Naam</span><span>${booking.naam || "—"}</span>
          <span class="text-white/40">Datum</span><span>${booking.datum || "—"}</span>
          <span class="text-white/40">Tijdstip</span><span>${booking.tijdstip || "—"}</span>
          <span class="text-white/40">Probleem</span><span>${booking.probleem || "—"}</span>
        </div>
      `;
      card.classList.remove("hidden");
    }

    function startTimer() {
      secondsElapsed = 0;
      timerInterval = setInterval(() => {
        secondsElapsed++;
        const min = Math.floor(secondsElapsed / 60);
        const sec = secondsElapsed % 60;
        document.getElementById("call-timer").textContent = `${min}:${sec.toString().padStart(2, "0")}`;
      }, 1000);
    }

    function stopTimer() {
      clearInterval(timerInterval);
    }
  </script>

</body>
</html>
```

- [ ] **Stap 2: Vervang VAPI keys in index.html**

Na het aanmaken van de VAPI assistant (Task 5), vervang in `index.html`:
```javascript
const VAPI_PUBLIC_KEY = "pk_xxxxxxxxxxxxxxxx";
const VAPI_ASSISTANT_ID = "asst_xxxxxxxxxxxxxxxx";
```

- [ ] **Stap 3: Test lokaal**

Open `demo/voice/index.html` direct in de browser (file://). Klik "Bel Snelservice Installatie". Zorg dat microfoontoegang is toegestaan.

Controleer:
- AI neemt op in het Nederlands
- Transcript verschijnt in real-time
- FAQ vragen worden beantwoord
- Afspraak boeken werkt (API moet draaien op localhost:8001)

- [ ] **Stap 4: Commit**

```bash
git add demo/voice/index.html
git commit -m "feat: add voice receptionist demo frontend with vapi web widget"
```

---

### Task 7: Deploy naar Render + Vercel

**Files:**
- Create: `demo/voice/api/Dockerfile`
- Create: `demo/voice/api/requirements.txt`

**Interfaces:**
- Consumes: Alle vorige tasks
- Produces: Live URL's voor API (Render) en frontend (Vercel) + update VAPI_ASSISTANT_ID met Render URL

- [ ] **Stap 1: Schrijf requirements.txt**

Maak `demo/voice/api/requirements.txt`:

```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
supabase>=2.0.0
python-dotenv>=1.0.0
httpx>=0.27.0
pydantic>=2.9.0
```

- [ ] **Stap 2: Schrijf Dockerfile**

Maak `demo/voice/api/Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
```

- [ ] **Stap 3: Commit voor deploy**

```bash
git add demo/voice/api/requirements.txt demo/voice/api/Dockerfile
git commit -m "feat: add dockerfile and requirements for voice receptionist api"
git push
```

- [ ] **Stap 4: Deploy API naar Render**

1. Ga naar render.com → New Web Service
2. Connect GitHub repo
3. Root Directory: `demo/voice/api`
4. Runtime: Docker
5. Environment variables toevoegen:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `N8N_SMS_WEBHOOK_URL`
6. Deploy → kopieer URL (bijv. `https://voice-receptionist-xxxx.onrender.com`)

- [ ] **Stap 5: Update VAPI assistant met Render URL**

Voeg toe aan `.env`:
```
VOICE_API_URL=https://voice-receptionist-xxxx.onrender.com
```

Voer opnieuw uit (update bestaande assistant):

```bash
python tools/create_vapi_assistant.py
```

Of update handmatig in VAPI dashboard → Tools → server URLs aanpassen naar Render URL.

- [ ] **Stap 6: Update index.html VAPI keys + deploy naar Vercel**

Vervang in `demo/voice/index.html` de VAPI keys met de echte waarden, dan:

```bash
cd "C:\Users\skayh\Desktop\Newsletters Demo\demo\voice"
vercel deploy --prod
vercel alias set <deployment-url> voice-receptionist.vercel.app
```

- [ ] **Stap 7: End-to-end test**

1. Open de Vercel URL in de browser
2. Klik "Bel Snelservice Installatie"
3. Vraag: "Wat zijn jullie spoedtarieven?" → AI antwoordt correct
4. Maak afspraak: geef naam, telefoonnummer, datum en probleem
5. Controleer Supabase → `appointments` → rij aangemaakt
6. Controleer n8n execution history → SMS workflow getriggerd

- [ ] **Stap 8: Finale commit**

```bash
git add .
git commit -m "feat: voice receptionist fully deployed on render + vercel"
git push
```

---

## Environment Variables Overzicht

| Variable | Waar vandaan |
|---|---|
| `SUPABASE_URL` | Supabase dashboard → Settings → API |
| `SUPABASE_KEY` | Supabase dashboard → Settings → API (anon key) |
| `N8N_SMS_WEBHOOK_URL` | n8n workflow webhook URL |
| `VAPI_PUBLIC_KEY` | vapi.ai → Account → API Keys |
| `VAPI_PRIVATE_KEY` | vapi.ai → Account → API Keys |
| `VAPI_ASSISTANT_ID` | Output van create_vapi_assistant.py |
| `VOICE_API_URL` | Render deploy URL |

---

## Kosten na Deploy

| Bron | Kosten |
|---|---|
| VAPI | $10 gratis credit → ~150 demo minuten |
| Render | Gratis tier |
| Vercel | Gratis tier |
| Supabase | Gratis tier |
| **Totaal** | **€0** |

# AI Voice Receptionist — Design Spec
**Datum:** 2026-06-30
**Project:** C van 3 (Voice AI voor lokale dienstverleners)
**Doel:** Inbound leads via skyhan.app + LinkedIn. Lokale bedrijven zien de demo, willen het zelf, nemen contact op.

---

## Probleemstelling

Nederlandse lokale dienstverleners (loodgieters, HVAC, kappers, tandartsen) missen dagelijks 20-40% van hun inkomende telefoontjes. Elke gemiste oproep is een gemiste opdracht. Ze weten dat AI dit kan oplossen — maar ze weten niet hoe, en ze kunnen het niet zelf bouwen.

Dit project is de demo die die kloof overbrugt: een werkend AI-receptionist dat bezoekers zelf kunnen uitproberen via de browser.

---

## Demo Bedrijf

**Snelservice Installatie BV** (fictief loodgietersbedrijf)

**Kennisbank:**
- Voorrijkosten: €95
- Arbeid: €65 per uur
- Spoedtarief na 20:00: €150
- Werkgebied: Gelderland, Utrecht, Overijssel
- Services: lekkages, verstoppingen, cv-ketel onderhoud, toilet, kraan

---

## Wat het Doet

Een AI-receptionist die inkomende telefoontjes afhandelt via de browser:

1. **FAQ beantwoorden** — tarieven, werkgebied, openingstijden, services
2. **Afspraak inplannen** — beschikbaarheid checken, datum/tijdstip boeken
3. **SMS-bevestiging sturen** — automatisch naar de klant na boeking
4. **Loggen in Supabase** — elke afspraak opgeslagen met naam, telefoon, probleem, tijdstip

---

## Demo Ervaring (Wat een Bezoeker Ziet)

### Stap 1 — Landing page
Professionele, donkere UI op `skyhan.app/projects/voice-receptionist`. Uitleg van het concept in 2 zinnen. Geen tutorial-look.

### Stap 2 — Web call
Bezoeker klikt "Bel Snelservice Installatie". Browser vraagt microfoontoegang. VAPI web widget opent direct — geen app, geen telefoon nodig.

AI neemt op in het Nederlands:
> *"Goedendag, u spreekt met Snelservice Installatie. Waarmee kan ik u helpen?"*

### Stap 3 — Gesprek
Live transcript verschijnt op de pagina terwijl het gesprek plaatsvindt. Bezoeker ziet wat de AI zegt en hoort het tegelijk.

**Scenario A — FAQ:**
> Klant: "Wat zijn jullie spoedtarieven?"
> AI: "Na 20:00 rekenen wij een spoedtarief van €150 exclusief BTW. Wilt u een afspraak inplannen?"

**Scenario B — Boeking:**
> AI vraagt: naam → telefoonnummer → datum en tijdstip → aard van het probleem
> AI: "Ik heb uw afspraak ingepland voor dinsdag 8 juli om 10:00. U ontvangt dadelijk een SMS-bevestiging."

### Stap 4 — Booking card
Direct na de boeking verschijnt een kaart op de pagina met de afspraakdetails. SMS-bevestiging verstuurd.

### Stap 5 — CTA
> "Wil je dit voor jouw bedrijf? → Neem contact op"

---

## Architectuur

```
Browser (skyhan.app)
    └── VAPI Web Widget
            ├── STT — spraak naar tekst (real-time)
            ├── GPT-4o — gespreksintelligentie
            ├── Dutch TTS — tekst naar stem
            └── Function calls → FastAPI (Render)
                    │
                    ├── POST /vapi/faq
                    │       └── Geeft antwoord uit kennisbank
                    │
                    ├── POST /vapi/check-availability
                    │       └── Checkt beschikbare slots in Supabase
                    │
                    └── POST /vapi/book-appointment
                            ├── Schrijft afspraak naar Supabase
                            └── Triggert n8n webhook → SMS
```

---

## Tech Stack

| Laag | Technologie | Reden |
|---|---|---|
| Voice platform | VAPI | Industrie-standaard, gratis $10 credit, Dutch TTS, web call support |
| LLM | GPT-4o | Snel, natuurlijk Nederlands, function calling |
| STT | VAPI ingebouwd | Real-time, geen extra setup |
| TTS | VAPI Dutch voice | Klinkt natuurlijk in het Nederlands |
| API | FastAPI (Render) | Consistent met Reply Engine, al ingericht |
| Database | Supabase | Al in gebruik, gratis tier |
| SMS | n8n (skyhan.app) | Al ingericht, MessageBird/Twilio node |
| Frontend | Tailwind CSS + Vanilla JS | Consistent met Reply Engine demo |
| Deployment | Vercel (frontend) + Render (API) | Al ingericht, geen extra kosten |

---

## Supabase Schema

### `appointments`
```
id            UUID (primary key)
created_at    TIMESTAMP
naam          TEXT
telefoon      TEXT
datum         DATE
tijdstip      TIME
probleem      TEXT
status        TEXT (gepland / bevestigd / geannuleerd)
```

### `availability`
```
id            UUID
dag           DATE
tijdslot      TIME
beschikbaar   BOOLEAN
```

---

## VAPI Assistant Configuratie

### System prompt (kern)
```
Je bent de AI-receptionist van Snelservice Installatie BV, een loodgietersbedrijf 
in Gelderland. Je spreekt altijd Nederlands. Je bent professioneel, vriendelijk 
en to-the-point.

Je kunt:
1. Vragen beantwoorden over tarieven, werkgebied en services
2. Beschikbaarheid checken
3. Afspraken inplannen

Je belt NOOIT terug — je maakt direct een afspraak of beantwoordt de vraag.
Houd antwoorden kort (max 2 zinnen). Stel één vraag tegelijk.
```

### Functions
- `check_availability(datum, tijdstip)` → POST /vapi/check-availability
- `book_appointment(naam, telefoon, datum, tijdstip, probleem)` → POST /vapi/book-appointment
- `get_faq(categorie)` → POST /vapi/faq

---

## FastAPI Endpoints

### POST /vapi/faq
Input: `{ "categorie": "tarieven" }`
Output: `{ "antwoord": "Onze voorrijkosten zijn €95..." }`

### POST /vapi/check-availability
Input: `{ "datum": "2026-07-08", "tijdstip": "10:00" }`
Output: `{ "beschikbaar": true, "alternatieven": ["09:00", "14:00"] }`

### POST /vapi/book-appointment
Input: `{ "naam": "Jan de Vries", "telefoon": "0612345678", "datum": "2026-07-08", "tijdstip": "10:00", "probleem": "lekkende kraan" }`
Output: `{ "bevestigd": true, "afspraak_id": "uuid" }`
Side effect: triggert n8n webhook → SMS naar klant

### POST /vapi/webhook (VAPI events)
Ontvangt call events van VAPI (start, end, transcript). Logt naar Supabase.

---

## n8n SMS Workflow

1. Webhook trigger (van FastAPI /book-appointment)
2. Bouw SMS-tekst:
   > "Bevestiging Snelservice Installatie: afspraak op [datum] om [tijdstip]. Vragen? Bel 026-1234567."
3. Verstuur via MessageBird node
4. Log status naar Supabase

---

## Foutafhandeling

| Scenario | Gedrag |
|---|---|
| Tijdslot niet beschikbaar | AI biedt 2 alternatieven aan |
| VAPI function call faalt | AI zegt "Ik verbind u door" — graceful fallback |
| SMS mislukt | Afspraak wordt alsnog opgeslagen, SMS-fout gelogd |
| Microfoon geweigerd | Duidelijke foutmelding op pagina |
| Geen reactie >10 seconden | AI vraagt "Bent u er nog?" — na 20s gesprek beëindigd |

---

## Bestandsstructuur

```
Newsletters Demo/
├── demo/
│   ├── voice/
│   │   ├── index.html              ← demo pagina (Tailwind)
│   │   └── api/
│   │       ├── main.py             ← FastAPI app
│   │       ├── vapi_handler.py     ← VAPI function call logica
│   │       ├── sms.py              ← n8n webhook trigger
│   │       └── models.py           ← Pydantic schemas
├── workflows/
│   └── voice_receptionist.md       ← SOP voor dit systeem
└── tools/
    └── seed_availability.py        ← vul Supabase met demo-slots
```

---

## Kosten Schatting

| Gebruik | Kosten |
|---|---|
| Demo gesprek (~3 min) | ~€0.15 |
| VAPI gratis credit ($10) | ~60-70 demo gesprekken |
| 100 bezoekers/maand die demo proberen | ~€15 |
| Productie voor klant (200 calls/mnd á 4 min) | ~€80-120/mnd infra |
| Klant betaalt | €500-2.000/mnd |

---

## skyhan.app Integratie

- **URL:** `skyhan.app/projects/voice-receptionist`
- **Portfolio card:** titel, 1-zin beschrijving, stack-iconen, [Demo] [GitHub] [Contact]
- **Demo pagina:** probleem → live web call → booking card → CTA

---

## LinkedIn Post Strategie

**Hook:**
> *"Ik belde een loodgietersbedrijf om 23:00. De AI nam op in het Nederlands, vertelde me de spoedtarieven en boekte mijn afspraak. De SMS-bevestiging kwam 8 seconden later. Dit bouwde ik in één week."*

**Body:** wat het doet (1 zin) + hoe het werkt (3 bullets) + link naar live demo

**CTA:** "Demo live op skyhan.app. Wil je dit voor jouw bedrijf? Reageer of DM me."

---

## Succescriteria

- Web call start binnen 2 seconden na klikken
- AI antwoordt binnen 1.5 seconden na spreken
- Boeking voltooid in <2 minuten gesprek
- SMS arriveert binnen 10 seconden na boeking
- Werkt op desktop + mobiel (Chrome, Safari)
- CTA leidt tot minimaal 1 inbound contactverzoek binnen 2 weken na LinkedIn post

---

## Project C is Deel 3 van 3

Na Voice Receptionist is de trilogie compleet:
- **Project A:** Bedrijfsdocument Brain (nog te bouwen)
- **Project B:** Reply Engine ✅ Live
- **Project C:** Voice Receptionist (dit project)

Elk project toont een ander kanaal: email → document Q&A → telefoon.

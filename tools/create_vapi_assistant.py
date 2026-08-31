import httpx
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

VAPI_KEY = os.environ["VAPI_PRIVATE_KEY"]
API_BASE = os.environ.get("VOICE_API_URL", "http://localhost:8001")
# Gedeeld geheim: VAPI stuurt dit als `X-Vapi-Secret` header bij elke tool-call,
# de API weigert verzoeken zonder geldig geheim.
SERVER_SECRET = os.environ["VAPI_SERVER_SECRET"]

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
                "server": {"url": f"{API_BASE}/vapi/faq", "secret": SERVER_SECRET},
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
                "server": {"url": f"{API_BASE}/vapi/check-availability", "secret": SERVER_SECRET},
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
                "server": {"url": f"{API_BASE}/vapi/book-appointment", "secret": SERVER_SECRET},
            },
        ],
    },
    "transcriber": {
        "provider": "deepgram",
        "model": "nova-2",
        "language": "nl",
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
response.raise_for_status()
data = response.json()
print(f"Assistant ID: {data['id']}")
print(f"Voeg toe aan .env: VAPI_ASSISTANT_ID={data['id']}")

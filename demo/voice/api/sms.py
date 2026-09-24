import httpx
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

N8N_SMS_WEBHOOK = os.environ.get("N8N_SMS_WEBHOOK_URL", "")


async def send_sms_confirmation(naam: str, telefoon: str, datum: str, tijdstip: str) -> None:
    if not N8N_SMS_WEBHOOK:
        print(f"[SMS] Webhook niet geconfigureerd. Zou SMS sturen naar …{telefoon[-2:]}")  # geen volledig nummer in logs
        return

    # Demo: het bedrijf is fictief. Geen verzonnen terugbelnummer — 026 is
    # een echt Arnhems netnummer en het nummer kan van iemand anders zijn.
    bericht = (
        f"DEMO skyhan.app: afspraak bij Snelservice Installatie (fictief) "
        f"op {datum} om {tijdstip[:5]}. Dit is een demonstratie, er komt geen monteur."
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(N8N_SMS_WEBHOOK, json={
            "naam": naam,
            "telefoon": telefoon,
            "bericht": bericht,
        })

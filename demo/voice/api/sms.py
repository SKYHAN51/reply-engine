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

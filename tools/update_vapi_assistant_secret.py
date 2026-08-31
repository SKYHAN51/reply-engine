import httpx
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

VAPI_KEY = os.environ["VAPI_PRIVATE_KEY"]
ASSISTANT_ID = os.environ["VAPI_ASSISTANT_ID"]
API_BASE = os.environ.get("VOICE_API_URL", "http://localhost:8001")
SERVER_SECRET = os.environ["VAPI_SERVER_SECRET"]

response = httpx.get(
    f"https://api.vapi.ai/assistant/{ASSISTANT_ID}",
    headers={"Authorization": f"Bearer {VAPI_KEY}"},
    timeout=30.0,
)
response.raise_for_status()
assistant = response.json()

tools = assistant["model"]["tools"]
for tool in tools:
    endpoint = tool["server"]["url"].rsplit("/", 1)[-1]
    tool["server"] = {"url": f"{API_BASE}/vapi/{endpoint}", "secret": SERVER_SECRET}

patch_response = httpx.patch(
    f"https://api.vapi.ai/assistant/{ASSISTANT_ID}",
    headers={"Authorization": f"Bearer {VAPI_KEY}"},
    json={"model": {**assistant["model"], "tools": tools}},
    timeout=30.0,
)
patch_response.raise_for_status()
updated = patch_response.json()
secrets_set = [t["server"].get("secret") is not None for t in updated["model"]["tools"]]
print(f"Assistant {ASSISTANT_ID} updated. Tools with secret set: {sum(secrets_set)}/{len(secrets_set)}")

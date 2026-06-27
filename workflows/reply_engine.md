# Workflow: Reply Engine

## Objective
Run the AI inbox agent demo for visitors on skyhan.app/projects/reply-engine.
Convert inbound interest into client contacts.

## Inputs Required
- OPENAI_API_KEY (in .env and Railway environment)
- GroenTech KB documents in demo/api/data/groentech_kb/

## Setup (First Time)
1. `pip install -r requirements.txt`
2. `python tools/ingest_documents.py`
3. `cd demo/api && uvicorn main:app --reload`

## Production Deployment
1. Push to GitHub
2. Railway deploys automatically via Dockerfile
3. Frontend: `vercel deploy demo/ --prod`

## Adding a New Client Knowledge Base
1. Create `demo/api/data/<client_kb>/` with markdown files
2. Run `python tools/ingest_documents.py` (update KB_PATH and COLLECTION_NAME)
3. Use `collection_name=<client_kb>` in API calls

## Cleanup Uploads
Run periodically to remove old uploads:
```
python tools/cleanup_uploads.py
```

## Known Constraints
- Upload limit: 2MB PDF, max 5 queries per session
- OpenAI rate limits: GPT-4o-mini has 500 RPM on tier 1
- ChromaDB is local — if Railway container restarts, volume persists via Docker volume

## Edge Cases
- No relevant passages found → fallback response (no hallucination)
- Quality check fails twice → fallback response
- Upload > 2MB → 400 error in UI, no LLM call

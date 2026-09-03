# ZorgNotitie Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone portfolio demo that turns a short spoken care
observation into a human-reviewed, structured ZPRT-style care log entry, with
deterministic (non-AI-scored) attention flags — for Dutch home care
(wijkverpleging) administrative burden.

**Architecture:** Next.js frontend never talks to Supabase directly — every
read/write goes through a FastAPI backend that holds the only Supabase
`service_role` key. This is a deliberate simplification (no per-user auth is
needed for a synthetic-data demo) and it also means RLS can deny `anon` and
`authenticated` entirely from day one, avoiding the exact class of exposure
found and fixed in this repo's Supabase RLS incident (2026-09-01). AI
(Whisper + an LLM) only ever produces a *draft*; a human must explicitly save
before anything becomes a final record or a visible alert.

**Tech Stack:** Next.js 14 (App Router) + TypeScript + Tailwind (frontend),
FastAPI + Pydantic + pytest (backend), Supabase/Postgres (new standalone
project), OpenAI Whisper (STT) + OpenAI chat completions with structured
output (extraction), Vercel (frontend) + Render (backend).

**Spec:** `docs/superpowers/specs/2026-09-03-zorgnotitie-design.md`

## Global Constraints

- No real patient data, real names, BSN, addresses, or medication records — synthetic demo data only, everywhere, always.
- No medical scoring, diagnosis, triage, or automatic escalation, anywhere in the codebase or copy.
- The LLM extraction output is written ONLY to `extraction_json` — the human-approved final fields (`actual_care_summary`, `deviation_detected`, `deviation_reason`, `mood_observation`, `mood_changed`, `behaviour_observation`, `behaviour_changed`) are set only by the explicit save action, never auto-populated as "final."
- Alerts are created only inside the same transaction as an explicit save (`review_status` transitioning to `reviewed`) — never before.
- Audio files are deleted immediately after the STT call returns (success or failure) — never persisted.
- The manager dashboard endpoint queries only rows where `review_status = 'reviewed'`.
- `extraction_json` and the human-approved fields are separate columns — never merged or overwritten into each other.
- Every new piece of logic gets a failing test first, then the minimal code to pass it (TDD), matching the pattern already used in this repo's `demo/api` (Reply Engine) and `demo/voice/api` (Voice Receptionist) test suites.
- Alert copy is always "Aandachtspunt voor beoordeling" — never language implying AI made a health judgment.
- Every visible page/screen shows: "Demo met synthetische gegevens; geen medisch hulpmiddel; geen klinische besluitvorming."

---

## Phase 0: Repository Setup

### Task 0.1: Create the repository and Python backend skeleton

**Files:**
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\app\__init__.py`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\app\config.py`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\requirements.txt`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\.env.example`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\pytest.ini`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\.gitignore`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\README.md`

**Interfaces:**
- Produces: `app.config.Settings` — a Pydantic settings object with fields `supabase_url: str`, `supabase_service_role_key: str`, `openai_api_key: str`, loaded from environment variables, importable as `from app.config import get_settings`.

- [ ] **Step 1: Create the directory structure**

Run:
```bash
mkdir -p "C:/Users/skayh/Desktop/zorgnotitie/backend/app/routes"
mkdir -p "C:/Users/skayh/Desktop/zorgnotitie/backend/tests"
mkdir -p "C:/Users/skayh/Desktop/zorgnotitie/supabase/migrations"
mkdir -p "C:/Users/skayh/Desktop/zorgnotitie/frontend"
cd "C:/Users/skayh/Desktop/zorgnotitie" && git init
```

- [ ] **Step 2: Write `.gitignore`**

```
# Python
__pycache__/
*.pyc
.venv/
.pytest_cache/

# Node
node_modules/
.next/
frontend/.env.local

# Env
.env
backend/.env

# OS
.DS_Store
```

- [ ] **Step 3: Write `backend/requirements.txt`**

```
fastapi==0.141.1
uvicorn==0.52.4
pydantic==2.13.5
pydantic-settings==2.15.0
supabase==2.31.0
openai==3.6.0
python-dotenv==1.2.3
pytest==9.1.1
pytest-asyncio==1.4.0
httpx==0.28.1
python-multipart==0.0.32
```

(Versions match the already-verified pins in this repo's root `requirements.txt` and `demo/voice/api/requirements.txt` where the same packages overlap.)

- [ ] **Step 4: Write `backend/pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 5: Write `backend/.env.example`**

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
OPENAI_API_KEY=sk-...
```

- [ ] **Step 6: Write `backend/app/config.py`**

```python
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_role_key: str
    openai_api_key: str

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 7: Create `backend/app/__init__.py`** (empty file, makes `app` a package)

- [ ] **Step 8: Write `README.md`**

```markdown
# ZorgNotitie

Portfolio demo: a spoken care observation becomes a human-reviewed, structured
ZPRT-style care log entry, with deterministic attention flags.

**Not a medical device. Uses synthetic data only. Makes no clinical decisions.**

See `docs/` in the Newsletters Demo repo for the full design spec and plan:
`docs/superpowers/specs/2026-09-03-zorgnotitie-design.md`

## Stack
- Frontend: Next.js + TypeScript + Tailwind (`frontend/`)
- Backend: FastAPI (`backend/`)
- Database: Supabase (Postgres + RLS)
```

- [ ] **Step 9: Commit**

```bash
cd "C:/Users/skayh/Desktop/zorgnotitie"
git add .
git commit -m "chore: initial repository structure"
```

---

## Phase 1: Database

### Task 1.1: Write the initial Supabase migration

**Files:**
- Create: `C:\Users\skayh\Desktop\zorgnotitie\supabase\migrations\0001_initial_schema.sql`

**Interfaces:**
- Produces: tables `demo_clients`, `zorgmomenten`, `alerts`, `processing_events`, `audit_log` exactly as named, with the columns listed below — later tasks (1.2 seed data, 2.x backend code) depend on these exact names and types.

- [ ] **Step 1: Write the migration SQL**

```sql
-- ============================================================
-- ZorgNotitie — Initial Schema
-- Standalone Supabase project. No connection to any other
-- project's tables. RLS locked to service_role only — the
-- FastAPI backend is the sole writer/reader; the frontend never
-- talks to Supabase directly.
-- ============================================================

CREATE TABLE demo_clients (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  display_name TEXT NOT NULL,
  care_plan_summary TEXT NOT NULL,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE zorgmomenten (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  demo_client_id UUID REFERENCES demo_clients(id) ON DELETE CASCADE,
  planned_care_summary TEXT NOT NULL,
  audio_status TEXT NOT NULL DEFAULT 'pending'
    CHECK (audio_status IN ('pending', 'transcribing', 'transcribed', 'failed')),
  transcript TEXT,
  extraction_json JSONB,
  actual_care_summary TEXT,
  deviation_detected BOOLEAN,
  deviation_reason TEXT,
  mood_observation TEXT,
  mood_changed BOOLEAN,
  behaviour_observation TEXT,
  behaviour_changed BOOLEAN,
  review_status TEXT NOT NULL DEFAULT 'processing'
    CHECK (review_status IN ('processing', 'draft', 'needs_review', 'reviewed', 'failed')),
  reviewed_by TEXT,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  zorgmoment_id UUID REFERENCES zorgmomenten(id) ON DELETE CASCADE,
  alert_type TEXT NOT NULL
    CHECK (alert_type IN ('care_deviation', 'mood_change', 'behaviour_change')),
  reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'acknowledged', 'resolved')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  acknowledged_at TIMESTAMPTZ,
  resolved_at TIMESTAMPTZ
);

CREATE TABLE processing_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  zorgmoment_id UUID REFERENCES zorgmomenten(id) ON DELETE CASCADE,
  stage TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('started', 'succeeded', 'failed')),
  error_code TEXT,
  error_message_safe TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  zorgmoment_id UUID REFERENCES zorgmomenten(id) ON DELETE CASCADE,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('ai', 'human')),
  event_type TEXT NOT NULL,
  before_json JSONB,
  after_json JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_zorgmomenten_review_status ON zorgmomenten(review_status);
CREATE INDEX idx_zorgmomenten_client ON zorgmomenten(demo_client_id, created_at DESC);
CREATE INDEX idx_alerts_zorgmoment ON alerts(zorgmoment_id);
CREATE INDEX idx_alerts_status ON alerts(status);
CREATE INDEX idx_processing_events_zorgmoment ON processing_events(zorgmoment_id, created_at);

-- ============================================================
-- RLS: service_role only. anon/authenticated get nothing — the
-- frontend has no direct Supabase credentials at all.
-- ============================================================
ALTER TABLE demo_clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE zorgmomenten ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON demo_clients FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON zorgmomenten FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON alerts FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON processing_events FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON audit_log FOR ALL TO service_role USING (true);
```

- [ ] **Step 2: Run it in the new Supabase project's SQL Editor**

This requires a new Supabase project to exist first. Tell the user: "Create a
new Supabase project (e.g. named `zorgnotitie`), then paste this migration
into its SQL Editor and run it. Once done, give me the project URL and
service_role key so I can write `backend/.env`." Do not proceed to Task 1.2
until this is confirmed done and the credentials are in `backend/.env`
(gitignored, never committed).

- [ ] **Step 3: Commit the migration file**

```bash
cd "C:/Users/skayh/Desktop/zorgnotitie"
git add supabase/migrations/0001_initial_schema.sql
git commit -m "feat: initial database schema with service_role-only RLS"
```

### Task 1.2: Seed demo data

**Files:**
- Create: `C:\Users\skayh\Desktop\zorgnotitie\supabase\migrations\0002_seed_demo_clients.sql`

**Interfaces:**
- Produces: 3 rows in `demo_clients`, one of which (`Mevrouw De Vries`) exactly matches the spec's grounding example — later tasks (frontend client selector, demo walkthrough) depend on this row existing with this exact `display_name` and `care_plan_summary`.

- [ ] **Step 1: Write the seed SQL**

```sql
INSERT INTO demo_clients (display_name, care_plan_summary) VALUES
(
  'Mevrouw De Vries',
  'Ochtendzorg: hulp bij wassen en aankleden, medicatieherinnering en ontbijtvoorbereiding.'
),
(
  'Meneer Bakker',
  'Avondzorg: hulp bij aankleden voor de nacht, medicatie toedienen, controle bloeddruk.'
),
(
  'Mevrouw Jansen',
  'Middagzorg: wondverzorging been, hulp bij lopen naar woonkamer, korte wandeling indien mogelijk.'
);
```

- [ ] **Step 2: Run it in the Supabase SQL Editor** (same project as Task 1.1)

- [ ] **Step 3: Verify via a direct REST call**

Run (after `backend/.env` is filled in from Task 1.1 Step 2):
```bash
cd "C:/Users/skayh/Desktop/zorgnotitie/backend"
python -c "
from dotenv import load_dotenv
load_dotenv()
import os, urllib.request, json
url = os.environ['SUPABASE_URL'] + '/rest/v1/demo_clients?select=display_name'
req = urllib.request.Request(url, headers={
    'apikey': os.environ['SUPABASE_SERVICE_ROLE_KEY'],
    'Authorization': 'Bearer ' + os.environ['SUPABASE_SERVICE_ROLE_KEY'],
})
print(json.loads(urllib.request.urlopen(req).read()))
"
```
Expected: a list of 3 dicts including `{'display_name': 'Mevrouw De Vries'}`.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/0002_seed_demo_clients.sql
git commit -m "feat: seed 3 synthetic demo clients"
```

---

## Phase 2: Backend Domain Layer (extraction schema + deterministic alert engine)

### Task 2.1: Pydantic extraction schema + validation tests

**Files:**
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\app\schemas.py`
- Test: `C:\Users\skayh\Desktop\zorgnotitie\backend\tests\test_schemas.py`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\tests\__init__.py` (empty)

**Interfaces:**
- Produces: `app.schemas.ExtractionDraft` (Pydantic model with fields `actual_care_summary: str`, `deviation_detected: bool`, `deviation_reason: str | None`, `mood_observation: str`, `mood_changed: bool`, `behaviour_observation: str`, `behaviour_changed: bool`), and `app.schemas.validate_extraction(raw: dict) -> ExtractionDraft` which raises `pydantic.ValidationError` on malformed input. Task 2.2 (alert engine) and Task 4.x (extraction service) both import `ExtractionDraft`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_schemas.py
import pytest
from pydantic import ValidationError
from app.schemas import ExtractionDraft, validate_extraction


def test_valid_extraction_parses():
    raw = {
        "actual_care_summary": "Aankleden met extra hulp; douchen niet uitgevoerd.",
        "deviation_detected": True,
        "deviation_reason": "Cliënt voelde zich moe en weigerde douchen",
        "mood_observation": "veranderd: stiller dan normaal",
        "mood_changed": True,
        "behaviour_observation": "verminderde eetlust",
        "behaviour_changed": True,
    }
    draft = validate_extraction(raw)
    assert isinstance(draft, ExtractionDraft)
    assert draft.deviation_detected is True
    assert draft.mood_changed is True


def test_missing_required_field_raises():
    raw = {
        "actual_care_summary": "Aankleden gelukt.",
        "deviation_detected": False,
        # deviation_reason omitted — allowed to be None, so this alone should NOT fail.
        # mood_observation intentionally omitted to trigger the failure.
        "mood_changed": False,
        "behaviour_observation": "geen bijzonderheden",
        "behaviour_changed": False,
    }
    with pytest.raises(ValidationError):
        validate_extraction(raw)


def test_wrong_type_raises():
    raw = {
        "actual_care_summary": "Aankleden gelukt.",
        "deviation_detected": "yes",  # must be bool, not str
        "deviation_reason": None,
        "mood_observation": "geen verandering",
        "mood_changed": False,
        "behaviour_observation": "geen bijzonderheden",
        "behaviour_changed": False,
    }
    with pytest.raises(ValidationError):
        validate_extraction(raw)


def test_deviation_false_allows_null_reason():
    raw = {
        "actual_care_summary": "Alles volgens plan uitgevoerd.",
        "deviation_detected": False,
        "deviation_reason": None,
        "mood_observation": "geen verandering",
        "mood_changed": False,
        "behaviour_observation": "geen bijzonderheden",
        "behaviour_changed": False,
    }
    draft = validate_extraction(raw)
    assert draft.deviation_reason is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:/Users/skayh/Desktop/zorgnotitie/backend" && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt && .venv/Scripts/pytest tests/test_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas'` (or similar import error).

- [ ] **Step 3: Write the implementation**

```python
# backend/app/schemas.py
from typing import Optional
from pydantic import BaseModel


class ExtractionDraft(BaseModel):
    actual_care_summary: str
    deviation_detected: bool
    deviation_reason: Optional[str] = None
    mood_observation: str
    mood_changed: bool
    behaviour_observation: str
    behaviour_changed: bool


def validate_extraction(raw: dict) -> ExtractionDraft:
    """Validate the LLM's raw JSON proposal against the fixed schema.
    Raises pydantic.ValidationError on any malformed or missing field —
    callers must not silently pass through invalid extraction output."""
    return ExtractionDraft(**raw)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/pytest tests/test_schemas.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/tests/test_schemas.py backend/tests/__init__.py
git commit -m "feat: extraction schema with strict validation"
```

### Task 2.2: Deterministic alert engine + tests

**Files:**
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\app\alerts.py`
- Test: `C:\Users\skayh\Desktop\zorgnotitie\backend\tests\test_alerts.py`

**Interfaces:**
- Consumes: `app.schemas.ExtractionDraft` (from Task 2.1)
- Produces: `app.alerts.determine_alerts(draft: ExtractionDraft) -> list[dict]`, where each dict is `{"alert_type": str, "reason": str}` — Task 5.x (save endpoint, which commits alerts to the DB) calls this function.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_alerts.py
from app.schemas import ExtractionDraft
from app.alerts import determine_alerts


def _draft(**overrides):
    base = dict(
        actual_care_summary="Alles volgens plan.",
        deviation_detected=False,
        deviation_reason=None,
        mood_observation="geen verandering",
        mood_changed=False,
        behaviour_observation="geen bijzonderheden",
        behaviour_changed=False,
    )
    base.update(overrides)
    return ExtractionDraft(**base)


def test_no_triggers_produces_no_alerts():
    alerts = determine_alerts(_draft())
    assert alerts == []


def test_deviation_produces_care_deviation_alert():
    draft = _draft(deviation_detected=True, deviation_reason="Cliënt weigerde douchen")
    alerts = determine_alerts(draft)
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "care_deviation"
    assert alerts[0]["reason"] == "Cliënt weigerde douchen"


def test_mood_changed_produces_mood_change_alert():
    draft = _draft(mood_changed=True, mood_observation="stiller dan normaal")
    alerts = determine_alerts(draft)
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "mood_change"
    assert alerts[0]["reason"] == "stiller dan normaal"


def test_behaviour_changed_produces_behaviour_change_alert():
    draft = _draft(behaviour_changed=True, behaviour_observation="verminderde eetlust")
    alerts = determine_alerts(draft)
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "behaviour_change"
    assert alerts[0]["reason"] == "verminderde eetlust"


def test_all_three_triggers_produce_three_alerts():
    draft = _draft(
        deviation_detected=True, deviation_reason="reden",
        mood_changed=True, mood_observation="stemming",
        behaviour_changed=True, behaviour_observation="gedrag",
    )
    alerts = determine_alerts(draft)
    types = {a["alert_type"] for a in alerts}
    assert types == {"care_deviation", "mood_change", "behaviour_change"}


def test_alert_reason_never_contains_risk_language():
    """Copy guarantee from the spec: never phrase an alert as a clinical
    risk finding. This test guards the reason text pass-through — the
    caller (save endpoint) is responsible for the alert_type -> display
    label mapping, but the raw reason must never be rewritten to add
    risk/diagnosis language."""
    draft = _draft(deviation_detected=True, deviation_reason="Cliënt voelde zich moe")
    alerts = determine_alerts(draft)
    for a in alerts:
        assert "risico" not in a["reason"].lower()
        assert "diagnose" not in a["reason"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/pytest tests/test_alerts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.alerts'`.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/alerts.py
from app.schemas import ExtractionDraft


def determine_alerts(draft: ExtractionDraft) -> list[dict]:
    """Deterministic, rule-based attention flags. No AI scoring, no
    severity levels, no clinical judgment — each rule reads one explicit
    boolean field the caregiver has reviewed and approved. This function
    is pure: given the same draft, it always returns the same alerts."""
    alerts: list[dict] = []

    if draft.deviation_detected:
        alerts.append({
            "alert_type": "care_deviation",
            "reason": draft.deviation_reason or "Afwijking van planning gemeld",
        })
    if draft.mood_changed:
        alerts.append({
            "alert_type": "mood_change",
            "reason": draft.mood_observation,
        })
    if draft.behaviour_changed:
        alerts.append({
            "alert_type": "behaviour_change",
            "reason": draft.behaviour_observation,
        })

    return alerts
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/pytest tests/test_alerts.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/alerts.py backend/tests/test_alerts.py
git commit -m "feat: deterministic alert engine"
```

### Task 2.3: Supabase client + processing_events logger

**Files:**
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\app\db.py`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\app\events.py`
- Test: `C:\Users\skayh\Desktop\zorgnotitie\backend\tests\test_events.py`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\tests\conftest.py`

**Interfaces:**
- Consumes: `app.config.get_settings` (Task 0.1)
- Produces: `app.db.get_client() -> supabase.Client`; `app.events.log_event(client, zorgmoment_id: str, stage: str, status: str, error_code: str | None = None, error_message_safe: str | None = None) -> None`. Later tasks (STT, extraction, save endpoint) call `log_event` at each pipeline stage.

- [ ] **Step 1: Write `backend/tests/conftest.py`** (shared fixture: a fake Supabase client double, so tests don't hit the network)

```python
# backend/tests/conftest.py
import pytest


class FakeTable:
    def __init__(self, store: dict, name: str):
        self._store = store.setdefault(name, [])

    def insert(self, row: dict):
        self._store.append(row)
        return self

    def execute(self):
        return type("Result", (), {"data": list(self._store)})()


class FakeSupabaseClient:
    """Minimal stand-in for supabase.Client — records inserted rows
    per table in memory so tests can assert on them without a real
    Supabase project."""
    def __init__(self):
        self._data: dict = {}

    def table(self, name: str):
        return FakeTable(self._data, name)


@pytest.fixture
def fake_supabase():
    return FakeSupabaseClient()
```

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_events.py
from app.events import log_event


def test_log_event_inserts_a_row(fake_supabase):
    log_event(
        fake_supabase,
        zorgmoment_id="abc-123",
        stage="stt",
        status="succeeded",
    )
    rows = fake_supabase.table("processing_events").execute().data
    assert len(rows) == 1
    assert rows[0]["zorgmoment_id"] == "abc-123"
    assert rows[0]["stage"] == "stt"
    assert rows[0]["status"] == "succeeded"
    assert rows[0]["error_code"] is None


def test_log_event_records_error_fields(fake_supabase):
    log_event(
        fake_supabase,
        zorgmoment_id="abc-123",
        stage="extraction",
        status="failed",
        error_code="invalid_json",
        error_message_safe="Extraction output did not match the required schema.",
    )
    rows = fake_supabase.table("processing_events").execute().data
    assert rows[0]["status"] == "failed"
    assert rows[0]["error_code"] == "invalid_json"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/pytest tests/test_events.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.events'`.

- [ ] **Step 4: Write `backend/app/db.py`**

```python
# backend/app/db.py
from functools import lru_cache
from supabase import create_client, Client
from app.config import get_settings


@lru_cache
def get_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
```

- [ ] **Step 5: Write `backend/app/events.py`**

```python
# backend/app/events.py
from typing import Optional


def log_event(
    client,
    zorgmoment_id: str,
    stage: str,
    status: str,
    error_code: Optional[str] = None,
    error_message_safe: Optional[str] = None,
) -> None:
    """Write one traceability row for a pipeline stage. Called at the
    start and end of every stage (stt, extraction, save) so failures are
    diagnosable from the database, never only from logs."""
    client.table("processing_events").insert({
        "zorgmoment_id": zorgmoment_id,
        "stage": stage,
        "status": status,
        "error_code": error_code,
        "error_message_safe": error_message_safe,
    }).execute()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/pytest tests/test_events.py -v`
Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/app/db.py backend/app/events.py backend/tests/test_events.py backend/tests/conftest.py
git commit -m "feat: Supabase client and processing_events logger"
```

---

## Phase 3: Speech-to-Text + Recording Flow

### Task 3.1: STT provider abstraction + tests

**Files:**
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\app\stt.py`
- Test: `C:\Users\skayh\Desktop\zorgnotitie\backend\tests\test_stt.py`

**Interfaces:**
- Produces: `app.stt.transcribe(audio_bytes: bytes, filename: str) -> str` — raises `app.stt.TranscriptionError` on failure. Task 3.2 (recording endpoint) calls this and handles `TranscriptionError`.

- [ ] **Step 1: Write the failing test** (mocks the OpenAI client — no real API calls in tests)

```python
# backend/tests/test_stt.py
from unittest.mock import patch, MagicMock
import pytest
from app.stt import transcribe, TranscriptionError


def test_transcribe_returns_text_on_success():
    fake_response = MagicMock()
    fake_response.text = "Mevrouw De Vries wilde vandaag niet douchen."
    with patch("app.stt._client") as mock_client:
        mock_client.audio.transcriptions.create.return_value = fake_response
        result = transcribe(b"fake-audio-bytes", "note.webm")
    assert result == "Mevrouw De Vries wilde vandaag niet douchen."


def test_transcribe_raises_on_empty_result():
    fake_response = MagicMock()
    fake_response.text = "   "
    with patch("app.stt._client") as mock_client:
        mock_client.audio.transcriptions.create.return_value = fake_response
        with pytest.raises(TranscriptionError):
            transcribe(b"fake-audio-bytes", "note.webm")


def test_transcribe_raises_on_api_error():
    with patch("app.stt._client") as mock_client:
        mock_client.audio.transcriptions.create.side_effect = Exception("timeout")
        with pytest.raises(TranscriptionError):
            transcribe(b"fake-audio-bytes", "note.webm")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/pytest tests/test_stt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.stt'`.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/stt.py
import io
from openai import OpenAI
from app.config import get_settings


class TranscriptionError(Exception):
    """Raised when speech-to-text fails or returns unusable output.
    Callers must surface this as a retry-able error, never fall back
    to an empty or guessed transcript."""


_client = OpenAI(api_key=get_settings().openai_api_key)


def transcribe(audio_bytes: bytes, filename: str) -> str:
    try:
        buf = io.BytesIO(audio_bytes)
        buf.name = filename
        response = _client.audio.transcriptions.create(
            model="whisper-1",
            file=buf,
        )
    except Exception as exc:
        raise TranscriptionError(f"STT call failed: {exc}") from exc

    text = (response.text or "").strip()
    if not text:
        raise TranscriptionError("STT returned an empty transcript.")
    return text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/pytest tests/test_stt.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/stt.py backend/tests/test_stt.py
git commit -m "feat: Whisper STT wrapper with explicit failure handling"
```

### Task 3.2: Recording endpoint — upload, transcribe, delete audio, create zorgmoment

**Files:**
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\app\routes\__init__.py` (empty)
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\app\routes\zorgmomenten.py`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\app\main.py`
- Test: `C:\Users\skayh\Desktop\zorgnotitie\backend\tests\test_routes_record.py`

**Interfaces:**
- Consumes: `app.stt.transcribe`/`TranscriptionError` (Task 3.1), `app.db.get_client` (Task 2.3), `app.events.log_event` (Task 2.3)
- Produces: `POST /zorgmomenten/{id}/record` — accepts a demo_client_id (path uses a pre-created zorgmoment id created by a separate `POST /zorgmomenten` call). Task 4.x (extraction endpoint) is called next in the same flow, from the frontend, as a separate step — this task does NOT call extraction; it only gets the transcript persisted and `audio_status` updated.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_routes_record.py
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_create_zorgmoment_returns_id_and_processing_status(fake_supabase):
    with patch("app.routes.zorgmomenten.get_client", return_value=fake_supabase):
        fake_supabase.table("demo_clients").insert({
            "id": "client-1", "display_name": "Mevrouw De Vries",
            "care_plan_summary": "Ochtendzorg.",
        }).execute()
        response = client.post("/zorgmomenten", json={
            "demo_client_id": "client-1",
            "planned_care_summary": "Ochtendzorg.",
        })
    assert response.status_code == 201
    body = response.json()
    assert body["review_status"] == "processing"
    assert "id" in body


def test_record_endpoint_transcribes_and_updates_status(fake_supabase):
    with patch("app.routes.zorgmomenten.get_client", return_value=fake_supabase), \
         patch("app.routes.zorgmomenten.transcribe", return_value="Testnotitie."):
        create_resp = client.post("/zorgmomenten", json={
            "demo_client_id": "client-1",
            "planned_care_summary": "Ochtendzorg.",
        })
        zm_id = create_resp.json()["id"]
        response = client.post(
            f"/zorgmomenten/{zm_id}/record",
            files={"audio": ("note.webm", b"fake-bytes", "audio/webm")},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["audio_status"] == "transcribed"
    assert body["transcript"] == "Testnotitie."


def test_record_endpoint_surfaces_stt_failure(fake_supabase):
    from app.stt import TranscriptionError
    with patch("app.routes.zorgmomenten.get_client", return_value=fake_supabase), \
         patch("app.routes.zorgmomenten.transcribe", side_effect=TranscriptionError("timeout")):
        create_resp = client.post("/zorgmomenten", json={
            "demo_client_id": "client-1",
            "planned_care_summary": "Ochtendzorg.",
        })
        zm_id = create_resp.json()["id"]
        response = client.post(
            f"/zorgmomenten/{zm_id}/record",
            files={"audio": ("note.webm", b"fake-bytes", "audio/webm")},
        )
    assert response.status_code == 422
    assert response.json()["audio_status"] == "failed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/pytest tests/test_routes_record.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 3: Write `backend/app/routes/zorgmomenten.py`**

```python
# backend/app/routes/zorgmomenten.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from app.db import get_client
from app.stt import transcribe, TranscriptionError
from app.events import log_event

router = APIRouter()


class CreateZorgmomentRequest(BaseModel):
    demo_client_id: str
    planned_care_summary: str


@router.post("/zorgmomenten", status_code=201)
def create_zorgmoment(body: CreateZorgmomentRequest):
    client = get_client()
    result = client.table("zorgmomenten").insert({
        "demo_client_id": body.demo_client_id,
        "planned_care_summary": body.planned_care_summary,
        "audio_status": "pending",
        "review_status": "processing",
    }).execute()
    return result.data[0] if hasattr(result, "data") and result.data else {
        "id": "unknown", "review_status": "processing"
    }


@router.post("/zorgmomenten/{zorgmoment_id}/record")
async def record_audio(zorgmoment_id: str, audio: UploadFile = File(...)):
    client = get_client()
    audio_bytes = await audio.read()

    log_event(client, zorgmoment_id, "stt", "started")
    try:
        transcript = transcribe(audio_bytes, audio.filename or "note.webm")
    except TranscriptionError as exc:
        log_event(client, zorgmoment_id, "stt", "failed", error_code="stt_failed",
                   error_message_safe=str(exc))
        client.table("zorgmomenten").insert({
            "id": zorgmoment_id, "audio_status": "failed",
        }).execute()
        raise HTTPException(status_code=422, detail={
            "audio_status": "failed",
            "message": "Transcriptie mislukt. Probeer het opnieuw.",
        })
    finally:
        # Audio is never persisted — it only ever existed in this
        # request's memory and is discarded when this function returns.
        del audio_bytes

    log_event(client, zorgmoment_id, "stt", "succeeded")
    client.table("zorgmomenten").insert({
        "id": zorgmoment_id, "audio_status": "transcribed", "transcript": transcript,
    }).execute()
    return {"id": zorgmoment_id, "audio_status": "transcribed", "transcript": transcript}
```

- [ ] **Step 4: Write `backend/app/main.py`**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.zorgmomenten import router as zorgmomenten_router

app = FastAPI(title="ZorgNotitie API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # tighten to the deployed frontend origin in Phase 7
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(zorgmomenten_router)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "zorgnotitie"}
```

Note: the `test_routes_record.py` tests above use `fake_supabase.table(...).insert(...).execute()`
which appends rather than upserts — this is sufficient for these unit tests
(they only check the shape of the response), but the real Supabase client's
`.insert()` on an existing `id` will fail on the primary key constraint. This
is intentionally deferred: Task 5.1 replaces these raw `.insert()` calls with
proper `.update()` calls using real Supabase syntax once the full write path
is built end-to-end. Flag this explicitly in the Task 5.1 write-up so it
isn't missed.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/pytest tests/test_routes_record.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/ backend/app/main.py backend/tests/test_routes_record.py
git commit -m "feat: zorgmoment creation and recording endpoints"
```

### Task 3.3: Next.js frontend scaffold + Opnemen (recording) page

**Files:**
- Create: `C:\Users\skayh\Desktop\zorgnotitie\frontend\package.json`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\frontend\tsconfig.json`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\frontend\next.config.js`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\frontend\tailwind.config.ts`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\frontend\postcss.config.js`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\frontend\app\layout.tsx`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\frontend\app\globals.css`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\frontend\app\page.tsx`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\frontend\lib\api.ts`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\frontend\.env.local.example`

**Interfaces:**
- Produces: `lib/api.ts` exports `createZorgmoment`, `uploadRecording` — Task 4.4 (review page) and Task 5.2 (dashboard page) add further exports to this same file.

This task has no backend tests (frontend scaffolding); manual verification
step replaces the test-run steps.

- [ ] **Step 1: Write `frontend/package.json`**

```json
{
  "name": "zorgnotitie-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "15.5.4",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "typescript": "5.9.2",
    "@types/node": "22.10.5",
    "@types/react": "18.3.18",
    "@types/react-dom": "18.3.5",
    "tailwindcss": "3.4.17",
    "postcss": "8.5.1",
    "autoprefixer": "10.4.20"
  }
}
```

- [ ] **Step 2: Write `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "baseUrl": ".",
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Write `frontend/next.config.js`**

```js
/** @type {import('next').NextConfig} */
module.exports = { reactStrictMode: true };
```

- [ ] **Step 4: Write `frontend/tailwind.config.ts`**

```ts
import type { Config } from "tailwindcss";
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
} satisfies Config;
```

- [ ] **Step 5: Write `frontend/postcss.config.js`**

```js
module.exports = { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

- [ ] **Step 6: Write `frontend/app/globals.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 7: Write `frontend/.env.local.example`**

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 8: Write `frontend/app/layout.tsx`**

```tsx
import "./globals.css";

export const metadata = {
  title: "ZorgNotitie",
  description: "Demo met synthetische gegevens. Geen medisch hulpmiddel. Geen klinische besluitvorming.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="nl">
      <body className="bg-slate-50 min-h-screen">
        <div className="bg-amber-100 text-amber-900 text-sm text-center py-2 px-4">
          Demo met synthetische gegevens. Geen medisch hulpmiddel. Geen klinische besluitvorming.
        </div>
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 9: Write `frontend/lib/api.ts`**

```ts
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface DemoClient {
  id: string;
  display_name: string;
  care_plan_summary: string;
}

export async function createZorgmoment(demoClientId: string, plannedCareSummary: string) {
  const res = await fetch(`${API_URL}/zorgmomenten`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ demo_client_id: demoClientId, planned_care_summary: plannedCareSummary }),
  });
  if (!res.ok) throw new Error("Kon zorgmoment niet aanmaken.");
  return res.json();
}

export async function uploadRecording(zorgmomentId: string, audioBlob: Blob) {
  const formData = new FormData();
  formData.append("audio", audioBlob, "note.webm");
  const res = await fetch(`${API_URL}/zorgmomenten/${zorgmomentId}/record`, {
    method: "POST",
    body: formData,
  });
  const body = await res.json();
  if (!res.ok) {
    throw new Error(body.detail?.message || "Transcriptie mislukt. Probeer het opnieuw.");
  }
  return body;
}
```

- [ ] **Step 10: Write `frontend/app/page.tsx`** (Opnemen page)

```tsx
"use client";

import { useState, useRef } from "react";
import { createZorgmoment, uploadRecording } from "@/lib/api";

const DEMO_CLIENTS = [
  { id: "client-1", display_name: "Mevrouw De Vries", care_plan_summary: "Ochtendzorg: hulp bij wassen en aankleden, medicatieherinnering en ontbijtvoorbereiding." },
  { id: "client-2", display_name: "Meneer Bakker", care_plan_summary: "Avondzorg: hulp bij aankleden voor de nacht, medicatie toedienen, controle bloeddruk." },
  { id: "client-3", display_name: "Mevrouw Jansen", care_plan_summary: "Middagzorg: wondverzorging been, hulp bij lopen naar woonkamer, korte wandeling indien mogelijk." },
];
// Note: replace this hardcoded list with a GET /demo-clients call once
// Task 5.2's dashboard endpoints exist — tracked as a follow-up, not
// blocking this page's core recording flow.

type Status = "idle" | "recording" | "uploading" | "transcribed" | "error";

export default function OpnemenPage() {
  const [selectedClient, setSelectedClient] = useState(DEMO_CLIENTS[0]);
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [zorgmomentId, setZorgmomentId] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  async function startRecording() {
    setErrorMessage("");
    const zm = await createZorgmoment(selectedClient.id, selectedClient.care_plan_summary);
    setZorgmomentId(zm.id);

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    chunksRef.current = [];
    recorder.ondataavailable = (e) => chunksRef.current.push(e.data);
    recorder.start();
    mediaRecorderRef.current = recorder;
    setStatus("recording");
  }

  async function stopRecording() {
    const recorder = mediaRecorderRef.current;
    if (!recorder || !zorgmomentId) return;

    setStatus("uploading");
    recorder.stop();
    recorder.onstop = async () => {
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      try {
        await uploadRecording(zorgmomentId, blob);
        setStatus("transcribed");
      } catch (err) {
        setErrorMessage(err instanceof Error ? err.message : "Onbekende fout.");
        setStatus("error");
      }
    };
  }

  return (
    <main className="max-w-xl mx-auto p-6">
      <h1 className="text-2xl font-semibold mb-4">Opnemen</h1>

      <label className="block mb-2 text-sm font-medium">Cliënt</label>
      <select
        className="border rounded p-2 w-full mb-4"
        value={selectedClient.id}
        onChange={(e) => setSelectedClient(DEMO_CLIENTS.find((c) => c.id === e.target.value)!)}
        disabled={status === "recording" || status === "uploading"}
      >
        {DEMO_CLIENTS.map((c) => (
          <option key={c.id} value={c.id}>{c.display_name}</option>
        ))}
      </select>

      <div className="bg-white border rounded p-3 mb-4 text-sm text-slate-600">
        <strong>Geplande zorg:</strong> {selectedClient.care_plan_summary}
      </div>

      {status === "idle" && (
        <button onClick={startRecording} className="bg-slate-900 text-white px-4 py-2 rounded">
          Start opname
        </button>
      )}
      {status === "recording" && (
        <button onClick={stopRecording} className="bg-red-600 text-white px-4 py-2 rounded">
          Stop opname
        </button>
      )}
      {status === "uploading" && <p>Bezig met transcriberen…</p>}
      {status === "transcribed" && (
        <div>
          <p className="text-green-700 mb-2">Transcriptie gelukt.</p>
          <a href={`/review/${zorgmomentId}`} className="underline text-slate-900">
            Ga naar controleren en opslaan →
          </a>
        </div>
      )}
      {status === "error" && (
        <div>
          <p className="text-red-700 mb-2">{errorMessage}</p>
          <button onClick={() => setStatus("idle")} className="bg-slate-900 text-white px-4 py-2 rounded">
            Opnieuw proberen
          </button>
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 11: Manual verification**

Run:
```bash
cd "C:/Users/skayh/Desktop/zorgnotitie/frontend"
npm install
npm run dev
```
Open `http://localhost:3000` — expect the Opnemen page to render with the
client selector and disclaimer banner. Full record→transcribe verification
happens once the backend is also running (Task 3.2's server started via
`uvicorn app.main:app --reload` from `backend/`), which is a manual
end-to-end check, not a unit test — record it as a manual QA note in the
Phase 6 fixtures task rather than re-verifying here.

- [ ] **Step 12: Commit**

```bash
cd "C:/Users/skayh/Desktop/zorgnotitie"
git add frontend/
git commit -m "feat: Next.js scaffold and Opnemen recording page"
```

---

## Phase 4: Extraction + Review/Save Flow

### Task 4.1: Extraction service (LLM call wrapper)

**Files:**
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\app\extraction.py`
- Test: `C:\Users\skayh\Desktop\zorgnotitie\backend\tests\test_extraction.py`

**Interfaces:**
- Consumes: `app.schemas.ExtractionDraft`, `validate_extraction` (Task 2.1)
- Produces: `app.extraction.extract(transcript: str, planned_care_summary: str) -> ExtractionDraft` — raises `app.extraction.ExtractionError` on failure. Task 4.2 (extraction endpoint) calls this.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_extraction.py
import json
from unittest.mock import patch, MagicMock
import pytest
from app.extraction import extract, ExtractionError

VALID_JSON = json.dumps({
    "actual_care_summary": "Aankleden met extra hulp; douchen niet uitgevoerd.",
    "deviation_detected": True,
    "deviation_reason": "Cliënt voelde zich moe",
    "mood_observation": "stiller dan normaal",
    "mood_changed": True,
    "behaviour_observation": "verminderde eetlust",
    "behaviour_changed": True,
})


def _mock_completion(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


def test_extract_returns_validated_draft():
    with patch("app.extraction._client") as mock_client:
        mock_client.chat.completions.create.return_value = _mock_completion(VALID_JSON)
        draft = extract("transcript hier", "geplande zorg hier")
    assert draft.deviation_detected is True
    assert draft.mood_changed is True


def test_extract_raises_on_invalid_json():
    with patch("app.extraction._client") as mock_client:
        mock_client.chat.completions.create.return_value = _mock_completion("dit is geen json")
        with pytest.raises(ExtractionError):
            extract("transcript hier", "geplande zorg hier")


def test_extract_raises_on_schema_mismatch():
    bad_json = json.dumps({"actual_care_summary": "iets", "deviation_detected": "niet een boolean"})
    with patch("app.extraction._client") as mock_client:
        mock_client.chat.completions.create.return_value = _mock_completion(bad_json)
        with pytest.raises(ExtractionError):
            extract("transcript hier", "geplande zorg hier")


def test_extract_raises_on_api_error():
    with patch("app.extraction._client") as mock_client:
        mock_client.chat.completions.create.side_effect = Exception("rate limited")
        with pytest.raises(ExtractionError):
            extract("transcript hier", "geplande zorg hier")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/pytest tests/test_extraction.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.extraction'`.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/extraction.py
import json
from openai import OpenAI
from pydantic import ValidationError
from app.config import get_settings
from app.schemas import ExtractionDraft, validate_extraction

_client = OpenAI(api_key=get_settings().openai_api_key)

_SYSTEM_PROMPT = """Je bent een assistent die gesproken zorgobservaties omzet \
in een gestructureerd concept volgens de Z=P=R,T-methodiek (Zorgplan=Planning=\
Realisatie, tenzij). Je output is UITSLUITEND een JSON-object met exact deze \
velden, geen extra tekst eromheen:
{
  "actual_care_summary": string — wat er werkelijk is gebeurd tijdens het zorgmoment,
  "deviation_detected": boolean — week de uitgevoerde zorg af van de planning,
  "deviation_reason": string of null — reden voor de afwijking, alleen indien deviation_detected true is,
  "mood_observation": string — korte beschrijving van de stemming van de cliënt,
  "mood_changed": boolean — was er een merkbare verandering in stemming,
  "behaviour_observation": string — korte beschrijving van gedrag/gedragsverandering,
  "behaviour_changed": boolean — was er een merkbare gedragsverandering
}
Je doet een voorstel, geen definitieve beoordeling. Gebruik geen medische \
diagnoses, risicoscores of urgentieclassificaties."""


class ExtractionError(Exception):
    """Raised when the LLM's output can't be parsed or doesn't match the
    schema. Callers must surface this as a retry-able error, never guess
    at a structured draft from malformed output."""


def extract(transcript: str, planned_care_summary: str) -> ExtractionDraft:
    try:
        response = _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"Geplande zorg: {planned_care_summary}\n\n"
                    f"Gesproken observatie (transcript): {transcript}"
                )},
            ],
            response_format={"type": "json_object"},
        )
        raw_content = response.choices[0].message.content
    except Exception as exc:
        raise ExtractionError(f"Extraction API call failed: {exc}") from exc

    try:
        raw = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"Extraction output was not valid JSON: {exc}") from exc

    try:
        return validate_extraction(raw)
    except ValidationError as exc:
        raise ExtractionError(f"Extraction output did not match the schema: {exc}") from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/pytest tests/test_extraction.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/extraction.py backend/tests/test_extraction.py
git commit -m "feat: LLM extraction service with strict JSON schema enforcement"
```

### Task 4.2: Extraction endpoint

**Files:**
- Modify: `C:\Users\skayh\Desktop\zorgnotitie\backend\app\routes\zorgmomenten.py`
- Test: `C:\Users\skayh\Desktop\zorgnotitie\backend\tests\test_routes_extract.py`

**Interfaces:**
- Consumes: `app.extraction.extract`/`ExtractionError` (Task 4.1)
- Produces: `POST /zorgmomenten/{id}/extract` returning `{"id", "review_status": "needs_review", "extraction_json": {...}}`. Task 4.4 (review page) calls this right after `uploadRecording` succeeds.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_routes_extract.py
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.schemas import ExtractionDraft
from app.extraction import ExtractionError

client = TestClient(app)

VALID_DRAFT = ExtractionDraft(
    actual_care_summary="Aankleden met extra hulp; douchen niet uitgevoerd.",
    deviation_detected=True,
    deviation_reason="Cliënt voelde zich moe",
    mood_observation="stiller dan normaal",
    mood_changed=True,
    behaviour_observation="verminderde eetlust",
    behaviour_changed=True,
)


def test_extract_endpoint_returns_draft(fake_supabase):
    fake_supabase.table("zorgmomenten").insert({
        "id": "zm-1", "transcript": "iets gezegd", "planned_care_summary": "Ochtendzorg.",
    }).execute()
    with patch("app.routes.zorgmomenten.get_client", return_value=fake_supabase), \
         patch("app.routes.zorgmomenten.extract", return_value=VALID_DRAFT):
        response = client.post("/zorgmomenten/zm-1/extract")
    assert response.status_code == 200
    body = response.json()
    assert body["review_status"] == "needs_review"
    assert body["extraction_json"]["deviation_detected"] is True


def test_extract_endpoint_surfaces_extraction_failure(fake_supabase):
    fake_supabase.table("zorgmomenten").insert({
        "id": "zm-1", "transcript": "iets gezegd", "planned_care_summary": "Ochtendzorg.",
    }).execute()
    with patch("app.routes.zorgmomenten.get_client", return_value=fake_supabase), \
         patch("app.routes.zorgmomenten.extract", side_effect=ExtractionError("bad json")):
        response = client.post("/zorgmomenten/zm-1/extract")
    assert response.status_code == 422
    assert response.json()["review_status"] == "failed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/pytest tests/test_routes_extract.py -v`
Expected: FAIL with `AttributeError` (no `/extract` route yet) or 404.

- [ ] **Step 3: Add the endpoint to `backend/app/routes/zorgmomenten.py`**

Add these imports at the top of the file:
```python
from app.extraction import extract, ExtractionError
```

Append this route to the file:
```python
@router.post("/zorgmomenten/{zorgmoment_id}/extract")
def extract_zorgmoment(zorgmoment_id: str):
    client = get_client()
    existing = client.table("zorgmomenten").execute().data
    row = next((r for r in existing if r.get("id") == zorgmoment_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Zorgmoment niet gevonden.")

    log_event(client, zorgmoment_id, "extraction", "started")
    try:
        draft = extract(row["transcript"], row["planned_care_summary"])
    except ExtractionError as exc:
        log_event(client, zorgmoment_id, "extraction", "failed",
                   error_code="extraction_failed", error_message_safe=str(exc))
        client.table("zorgmomenten").insert({
            "id": zorgmoment_id, "review_status": "failed",
        }).execute()
        raise HTTPException(status_code=422, detail={
            "review_status": "failed",
            "message": "Kon geen gestructureerd concept maken. Probeer het opnieuw.",
        })

    log_event(client, zorgmoment_id, "extraction", "succeeded")
    extraction_json = draft.model_dump()
    client.table("zorgmomenten").insert({
        "id": zorgmoment_id,
        "review_status": "needs_review",
        "extraction_json": extraction_json,
    }).execute()
    return {"id": zorgmoment_id, "review_status": "needs_review", "extraction_json": extraction_json}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/pytest tests/test_routes_extract.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/zorgmomenten.py backend/tests/test_routes_extract.py
git commit -m "feat: extraction endpoint"
```

### Task 4.3: Save endpoint — the only place final fields, alerts, and audit_log are written

**Files:**
- Modify: `C:\Users\skayh\Desktop\zorgnotitie\backend\app\routes\zorgmomenten.py`
- Test: `C:\Users\skayh\Desktop\zorgnotitie\backend\tests\test_routes_save.py`

**Interfaces:**
- Consumes: `app.alerts.determine_alerts` (Task 2.2), `app.schemas.ExtractionDraft` (Task 2.1)
- Produces: `POST /zorgmomenten/{id}/save` — this is the ONLY endpoint that writes to the final `zorgmomenten` fields, `alerts`, and `audit_log`. Task 5.x (dashboard) reads only rows this endpoint has written.

This is the task that enforces the plan's most important global constraint —
review it carefully against `Global Constraints` above before moving on.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_routes_save.py
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _seed_needs_review_zorgmoment(fake_supabase, **extraction_overrides):
    extraction_json = {
        "actual_care_summary": "Aankleden met extra hulp; douchen niet uitgevoerd.",
        "deviation_detected": True,
        "deviation_reason": "Cliënt voelde zich moe",
        "mood_observation": "stiller dan normaal",
        "mood_changed": True,
        "behaviour_observation": "verminderde eetlust",
        "behaviour_changed": True,
    }
    extraction_json.update(extraction_overrides)
    fake_supabase.table("zorgmomenten").insert({
        "id": "zm-1", "review_status": "needs_review", "extraction_json": extraction_json,
    }).execute()
    return extraction_json


def test_save_writes_final_fields_from_human_approved_body(fake_supabase):
    _seed_needs_review_zorgmoment(fake_supabase)
    with patch("app.routes.zorgmomenten.get_client", return_value=fake_supabase):
        response = client.post("/zorgmomenten/zm-1/save", json={
            "actual_care_summary": "Aankleden met extra hulp; douchen niet uitgevoerd (bevestigd).",
            "deviation_detected": True,
            "deviation_reason": "Cliënt voelde zich moe",
            "mood_observation": "stiller dan normaal",
            "mood_changed": True,
            "behaviour_observation": "verminderde eetlust",
            "behaviour_changed": True,
            "reviewed_by": "demo-zorgmedewerker",
        })
    assert response.status_code == 200
    saved_rows = [r for r in fake_supabase.table("zorgmomenten").execute().data if r.get("review_status") == "reviewed"]
    assert len(saved_rows) == 1
    assert saved_rows[0]["actual_care_summary"].endswith("(bevestigd).")


def test_save_creates_alerts_matching_final_fields(fake_supabase):
    _seed_needs_review_zorgmoment(fake_supabase)
    with patch("app.routes.zorgmomenten.get_client", return_value=fake_supabase):
        client.post("/zorgmomenten/zm-1/save", json={
            "actual_care_summary": "iets",
            "deviation_detected": True, "deviation_reason": "reden",
            "mood_observation": "stemming", "mood_changed": True,
            "behaviour_observation": "gedrag", "behaviour_changed": True,
            "reviewed_by": "demo-zorgmedewerker",
        })
    alert_rows = fake_supabase.table("alerts").execute().data
    types = {a["alert_type"] for a in alert_rows}
    assert types == {"care_deviation", "mood_change", "behaviour_change"}


def test_save_writes_audit_log_with_before_and_after(fake_supabase):
    original = _seed_needs_review_zorgmoment(fake_supabase)
    with patch("app.routes.zorgmomenten.get_client", return_value=fake_supabase):
        client.post("/zorgmomenten/zm-1/save", json={
            "actual_care_summary": "GEWIJZIGD door zorgmedewerker",
            "deviation_detected": True, "deviation_reason": "reden",
            "mood_observation": "stemming", "mood_changed": True,
            "behaviour_observation": "gedrag", "behaviour_changed": True,
            "reviewed_by": "demo-zorgmedewerker",
        })
    audit_rows = fake_supabase.table("audit_log").execute().data
    assert len(audit_rows) == 1
    assert audit_rows[0]["before_json"]["actual_care_summary"] == original["actual_care_summary"]
    assert audit_rows[0]["after_json"]["actual_care_summary"] == "GEWIJZIGD door zorgmedewerker"
    assert audit_rows[0]["actor_type"] == "human"


def test_save_when_caregiver_clears_a_flagged_field_creates_no_alert_for_it(fake_supabase):
    """The caregiver can override the AI's proposed booleans during review —
    if they correct mood_changed to false, no mood_change alert is created,
    even though the AI's original draft had it true."""
    _seed_needs_review_zorgmoment(fake_supabase, mood_changed=True)
    with patch("app.routes.zorgmomenten.get_client", return_value=fake_supabase):
        client.post("/zorgmomenten/zm-1/save", json={
            "actual_care_summary": "iets",
            "deviation_detected": False, "deviation_reason": None,
            "mood_observation": "geen verandering na overleg", "mood_changed": False,
            "behaviour_observation": "geen bijzonderheden", "behaviour_changed": False,
            "reviewed_by": "demo-zorgmedewerker",
        })
    alert_rows = fake_supabase.table("alerts").execute().data
    assert alert_rows == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/pytest tests/test_routes_save.py -v`
Expected: FAIL (404, no `/save` route yet).

- [ ] **Step 3: Add the endpoint to `backend/app/routes/zorgmomenten.py`**

Add this import at the top:
```python
from typing import Optional
from app.alerts import determine_alerts
from app.schemas import ExtractionDraft
```

Append this model and route:
```python
class SaveZorgmomentRequest(BaseModel):
    actual_care_summary: str
    deviation_detected: bool
    deviation_reason: Optional[str] = None
    mood_observation: str
    mood_changed: bool
    behaviour_observation: str
    behaviour_changed: bool
    reviewed_by: str


@router.post("/zorgmomenten/{zorgmoment_id}/save")
def save_zorgmoment(zorgmoment_id: str, body: SaveZorgmomentRequest):
    client = get_client()
    existing = client.table("zorgmomenten").execute().data
    row = next((r for r in existing if r.get("id") == zorgmoment_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Zorgmoment niet gevonden.")
    if row.get("review_status") != "needs_review":
        raise HTTPException(status_code=409, detail="Dit zorgmoment is niet klaar om op te slaan.")

    before_json = row.get("extraction_json")
    after_json = body.model_dump()

    # This is the ONLY place final fields are written — always from the
    # human-approved request body, never copied from extraction_json.
    client.table("zorgmomenten").insert({
        "id": zorgmoment_id,
        "review_status": "reviewed",
        "reviewed_by": body.reviewed_by,
        **after_json,
    }).execute()

    client.table("audit_log").insert({
        "zorgmoment_id": zorgmoment_id,
        "actor_type": "human",
        "event_type": "review_saved",
        "before_json": before_json,
        "after_json": after_json,
    }).execute()

    draft = ExtractionDraft(**after_json_without_reviewer(after_json))
    for alert in determine_alerts(draft):
        client.table("alerts").insert({
            "zorgmoment_id": zorgmoment_id,
            "alert_type": alert["alert_type"],
            "reason": alert["reason"],
        }).execute()

    return {"id": zorgmoment_id, "review_status": "reviewed"}


def after_json_without_reviewer(after_json: dict) -> dict:
    """ExtractionDraft doesn't have a reviewed_by field — strip it before
    constructing the draft used for alert determination."""
    return {k: v for k, v in after_json.items() if k != "reviewed_by"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/pytest tests/test_routes_save.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run the full backend test suite to confirm nothing regressed**

Run: `.venv/Scripts/pytest -v`
Expected: all tests across all files pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/zorgmomenten.py backend/tests/test_routes_save.py
git commit -m "feat: save endpoint — the sole writer of final fields, alerts, and audit_log"
```

### Task 4.4: Controleren en opslaan (review) page

**Files:**
- Modify: `C:\Users\skayh\Desktop\zorgnotitie\frontend\lib\api.ts`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\frontend\app\review\[id]\page.tsx`

**Interfaces:**
- Consumes: `POST /zorgmomenten/{id}/extract` (Task 4.2), `POST /zorgmomenten/{id}/save` (Task 4.3)

- [ ] **Step 1: Add to `frontend/lib/api.ts`**

```ts
export interface ExtractionDraft {
  actual_care_summary: string;
  deviation_detected: boolean;
  deviation_reason: string | null;
  mood_observation: string;
  mood_changed: boolean;
  behaviour_observation: string;
  behaviour_changed: boolean;
}

export async function extractZorgmoment(zorgmomentId: string): Promise<{ extraction_json: ExtractionDraft }> {
  const res = await fetch(`${API_URL}/zorgmomenten/${zorgmomentId}/extract`, { method: "POST" });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail?.message || "Extractie mislukt.");
  return body;
}

export async function saveZorgmoment(zorgmomentId: string, draft: ExtractionDraft, reviewedBy: string) {
  const res = await fetch(`${API_URL}/zorgmomenten/${zorgmomentId}/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...draft, reviewed_by: reviewedBy }),
  });
  if (!res.ok) throw new Error("Opslaan mislukt.");
  return res.json();
}
```

- [ ] **Step 2: Write `frontend/app/review/[id]/page.tsx`**

```tsx
"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { extractZorgmoment, saveZorgmoment, ExtractionDraft } from "@/lib/api";

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [draft, setDraft] = useState<ExtractionDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    extractZorgmoment(id)
      .then((res) => setDraft(res.extraction_json))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  function updateField<K extends keyof ExtractionDraft>(key: K, value: ExtractionDraft[K]) {
    if (!draft) return;
    setDraft({ ...draft, [key]: value });
  }

  async function handleSave() {
    if (!draft) return;
    setSaving(true);
    setError("");
    try {
      await saveZorgmoment(id, draft, "demo-zorgmedewerker");
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Opslaan mislukt.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <main className="max-w-xl mx-auto p-6">Bezig met concept maken…</main>;
  if (error && !draft) return <main className="max-w-xl mx-auto p-6 text-red-700">{error}</main>;
  if (!draft) return null;

  return (
    <main className="max-w-xl mx-auto p-6">
      <h1 className="text-2xl font-semibold mb-2">Controleren en opslaan</h1>
      <p className="text-sm text-slate-600 mb-4">
        AI doet een voorstel. Jij controleert en beslist.
      </p>

      <label className="block text-sm font-medium mt-4">Uitgevoerde zorg</label>
      <textarea
        className="border rounded p-2 w-full"
        value={draft.actual_care_summary}
        onChange={(e) => updateField("actual_care_summary", e.target.value)}
      />

      <label className="flex items-center gap-2 mt-4">
        <input
          type="checkbox"
          checked={draft.deviation_detected}
          onChange={(e) => updateField("deviation_detected", e.target.checked)}
        />
        Afwijking van planning
      </label>
      {draft.deviation_detected && (
        <input
          className="border rounded p-2 w-full mt-2"
          value={draft.deviation_reason ?? ""}
          onChange={(e) => updateField("deviation_reason", e.target.value)}
          placeholder="Reden voor afwijking"
        />
      )}

      <label className="block text-sm font-medium mt-4">Stemming</label>
      <input
        className="border rounded p-2 w-full"
        value={draft.mood_observation}
        onChange={(e) => updateField("mood_observation", e.target.value)}
      />
      <label className="flex items-center gap-2 mt-2">
        <input
          type="checkbox"
          checked={draft.mood_changed}
          onChange={(e) => updateField("mood_changed", e.target.checked)}
        />
        Stemming afwijkend van normaal
      </label>

      <label className="block text-sm font-medium mt-4">Gedrag</label>
      <input
        className="border rounded p-2 w-full"
        value={draft.behaviour_observation}
        onChange={(e) => updateField("behaviour_observation", e.target.value)}
      />
      <label className="flex items-center gap-2 mt-2">
        <input
          type="checkbox"
          checked={draft.behaviour_changed}
          onChange={(e) => updateField("behaviour_changed", e.target.checked)}
        />
        Gedrag afwijkend van normaal
      </label>

      {error && <p className="text-red-700 mt-4">{error}</p>}

      <button
        onClick={handleSave}
        disabled={saving}
        className="bg-slate-900 text-white px-4 py-2 rounded mt-6"
      >
        {saving ? "Bezig met opslaan…" : "Opslaan"}
      </button>
    </main>
  );
}
```

- [ ] **Step 3: Manual verification**

With backend running (`uvicorn app.main:app --reload` from `backend/`, venv
activated) and frontend running (`npm run dev` from `frontend/`): record a
note on the Opnemen page, follow the link to `/review/<id>`, confirm the
draft renders, edit a field, click Opslaan, confirm redirect to `/dashboard`
(will 404 until Task 5.2 — expected at this point in the plan).

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api.ts frontend/app/review/
git commit -m "feat: Controleren en opslaan review page"
```

---

## Phase 5: Dashboard + Audit Detail View

### Task 5.1: Dashboard endpoint (reviewed-only) + alert detail

**Files:**
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\app\routes\dashboard.py`
- Modify: `C:\Users\skayh\Desktop\zorgnotitie\backend\app\main.py`
- Test: `C:\Users\skayh\Desktop\zorgnotitie\backend\tests\test_routes_dashboard.py`

**Interfaces:**
- Produces: `GET /dashboard/zorgmomenten` (only `review_status = 'reviewed'` rows), `GET /dashboard/zorgmomenten/{id}` (detail incl. `extraction_json` vs. final fields and `audit_log` rows), `GET /dashboard/alerts?status=open`. Task 5.2 (dashboard page) calls all three.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_routes_dashboard.py
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_dashboard_list_excludes_unreviewed_rows(fake_supabase):
    fake_supabase.table("zorgmomenten").insert({"id": "zm-1", "review_status": "reviewed", "actual_care_summary": "a"}).execute()
    fake_supabase.table("zorgmomenten").insert({"id": "zm-2", "review_status": "needs_review", "actual_care_summary": "b"}).execute()
    fake_supabase.table("zorgmomenten").insert({"id": "zm-3", "review_status": "failed"}).execute()
    with patch("app.routes.dashboard.get_client", return_value=fake_supabase):
        response = client.get("/dashboard/zorgmomenten")
    ids = [r["id"] for r in response.json()]
    assert ids == ["zm-1"]


def test_dashboard_detail_includes_audit_log(fake_supabase):
    fake_supabase.table("zorgmomenten").insert({"id": "zm-1", "review_status": "reviewed"}).execute()
    fake_supabase.table("audit_log").insert({"zorgmoment_id": "zm-1", "actor_type": "human", "event_type": "review_saved"}).execute()
    with patch("app.routes.dashboard.get_client", return_value=fake_supabase):
        response = client.get("/dashboard/zorgmomenten/zm-1")
    assert response.status_code == 200
    assert len(response.json()["audit_log"]) == 1


def test_open_alerts_endpoint_filters_by_status(fake_supabase):
    fake_supabase.table("alerts").insert({"id": "a1", "zorgmoment_id": "zm-1", "alert_type": "mood_change", "status": "open"}).execute()
    fake_supabase.table("alerts").insert({"id": "a2", "zorgmoment_id": "zm-1", "alert_type": "care_deviation", "status": "resolved"}).execute()
    with patch("app.routes.dashboard.get_client", return_value=fake_supabase):
        response = client.get("/dashboard/alerts?status=open")
    ids = [a["id"] for a in response.json()]
    assert ids == ["a1"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/pytest tests/test_routes_dashboard.py -v`
Expected: FAIL (404, module doesn't exist).

- [ ] **Step 3: Write `backend/app/routes/dashboard.py`**

```python
# backend/app/routes/dashboard.py
from fastapi import APIRouter, HTTPException, Query
from app.db import get_client

router = APIRouter(prefix="/dashboard")


@router.get("/zorgmomenten")
def list_reviewed_zorgmomenten():
    client = get_client()
    all_rows = client.table("zorgmomenten").execute().data
    return [r for r in all_rows if r.get("review_status") == "reviewed"]


@router.get("/zorgmomenten/{zorgmoment_id}")
def get_zorgmoment_detail(zorgmoment_id: str):
    client = get_client()
    all_rows = client.table("zorgmomenten").execute().data
    row = next((r for r in all_rows if r.get("id") == zorgmoment_id), None)
    if row is None or row.get("review_status") != "reviewed":
        raise HTTPException(status_code=404, detail="Zorgmoment niet gevonden.")

    audit_rows = [
        a for a in client.table("audit_log").execute().data
        if a.get("zorgmoment_id") == zorgmoment_id
    ]
    alert_rows = [
        a for a in client.table("alerts").execute().data
        if a.get("zorgmoment_id") == zorgmoment_id
    ]
    return {**row, "audit_log": audit_rows, "alerts": alert_rows}


@router.get("/alerts")
def list_alerts(status: str = Query(default="open")):
    client = get_client()
    all_rows = client.table("alerts").execute().data
    return [a for a in all_rows if a.get("status") == status]
```

- [ ] **Step 4: Wire the router into `backend/app/main.py`**

Add this import:
```python
from app.routes.dashboard import router as dashboard_router
```
Add this line after `app.include_router(zorgmomenten_router)`:
```python
app.include_router(dashboard_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/pytest tests/test_routes_dashboard.py -v`
Expected: 3 passed.

- [ ] **Step 6: Run the full backend suite**

Run: `.venv/Scripts/pytest -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/dashboard.py backend/app/main.py backend/tests/test_routes_dashboard.py
git commit -m "feat: dashboard endpoints — reviewed-only, with audit and alert detail"
```

### Task 5.2: Teamoverzicht (dashboard) page

**Files:**
- Modify: `C:\Users\skayh\Desktop\zorgnotitie\frontend\lib\api.ts`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\frontend\app\dashboard\page.tsx`
- Create: `C:\Users\skayh\Desktop\zorgnotitie\frontend\app\dashboard\[id]\page.tsx`

**Interfaces:**
- Consumes: `GET /dashboard/zorgmomenten`, `GET /dashboard/zorgmomenten/{id}`, `GET /dashboard/alerts` (Task 5.1)

- [ ] **Step 1: Add to `frontend/lib/api.ts`**

```ts
export async function listReviewedZorgmomenten() {
  const res = await fetch(`${API_URL}/dashboard/zorgmomenten`);
  if (!res.ok) throw new Error("Kon overzicht niet laden.");
  return res.json();
}

export async function getZorgmomentDetail(id: string) {
  const res = await fetch(`${API_URL}/dashboard/zorgmomenten/${id}`);
  if (!res.ok) throw new Error("Kon detail niet laden.");
  return res.json();
}

export async function listOpenAlerts() {
  const res = await fetch(`${API_URL}/dashboard/alerts?status=open`);
  if (!res.ok) throw new Error("Kon aandachtspunten niet laden.");
  return res.json();
}
```

- [ ] **Step 2: Write `frontend/app/dashboard/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listReviewedZorgmomenten, listOpenAlerts } from "@/lib/api";

const ALERT_LABELS: Record<string, string> = {
  care_deviation: "Afwijking van planning",
  mood_change: "Verandering in stemming",
  behaviour_change: "Verandering in gedrag",
};

export default function DashboardPage() {
  const [zorgmomenten, setZorgmomenten] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([listReviewedZorgmomenten(), listOpenAlerts()])
      .then(([zm, al]) => {
        setZorgmomenten(zm);
        setAlerts(al);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <main className="max-w-3xl mx-auto p-6">Laden…</main>;

  return (
    <main className="max-w-3xl mx-auto p-6">
      <h1 className="text-2xl font-semibold mb-4">Teamoverzicht</h1>

      {alerts.length > 0 && (
        <section className="mb-6">
          <h2 className="text-lg font-medium mb-2">Open aandachtspunten</h2>
          <ul className="space-y-2">
            {alerts.map((a) => (
              <li key={a.id} className="bg-amber-50 border border-amber-200 rounded p-3">
                <span className="font-medium">{ALERT_LABELS[a.alert_type] ?? a.alert_type}</span>
                {" — "}
                <span className="text-sm text-slate-700">{a.reason}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h2 className="text-lg font-medium mb-2">Zorgmomenten</h2>
        <ul className="space-y-2">
          {zorgmomenten.map((zm) => (
            <li key={zm.id} className="border rounded p-3">
              <Link href={`/dashboard/${zm.id}`} className="underline">
                {zm.actual_care_summary?.slice(0, 80) ?? "(geen samenvatting)"}
              </Link>
            </li>
          ))}
          {zorgmomenten.length === 0 && <p className="text-slate-500">Nog geen opgeslagen zorgmomenten.</p>}
        </ul>
      </section>
    </main>
  );
}
```

- [ ] **Step 3: Write `frontend/app/dashboard/[id]/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getZorgmomentDetail } from "@/lib/api";

export default function ZorgmomentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<any>(null);

  useEffect(() => {
    getZorgmomentDetail(id).then(setDetail);
  }, [id]);

  if (!detail) return <main className="max-w-2xl mx-auto p-6">Laden…</main>;

  return (
    <main className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-semibold mb-4">Zorgmoment detail</h1>

      <section className="mb-6">
        <h2 className="text-lg font-medium mb-2">Definitieve, door mens goedgekeurde versie</h2>
        <p><strong>Uitgevoerde zorg:</strong> {detail.actual_care_summary}</p>
        <p><strong>Afwijking:</strong> {detail.deviation_detected ? detail.deviation_reason : "Geen"}</p>
        <p><strong>Stemming:</strong> {detail.mood_observation}</p>
        <p><strong>Gedrag:</strong> {detail.behaviour_observation}</p>
        <p className="text-sm text-slate-500 mt-2">Beoordeeld door: {detail.reviewed_by}</p>
      </section>

      <section className="mb-6">
        <h2 className="text-lg font-medium mb-2">Aandachtspunten</h2>
        {detail.alerts?.length ? (
          <ul className="space-y-1">
            {detail.alerts.map((a: any) => (
              <li key={a.id}>{a.alert_type}: {a.reason}</li>
            ))}
          </ul>
        ) : (
          <p className="text-slate-500">Geen aandachtspunten.</p>
        )}
      </section>

      <section>
        <h2 className="text-lg font-medium mb-2">Audit — AI-voorstel vs. definitieve versie</h2>
        {detail.audit_log?.map((entry: any) => (
          <div key={entry.id} className="border rounded p-3 mb-2 text-sm">
            <p className="font-medium mb-1">AI-voorstel:</p>
            <pre className="bg-slate-50 p-2 rounded overflow-x-auto">{JSON.stringify(entry.before_json, null, 2)}</pre>
            <p className="font-medium mb-1 mt-2">Definitieve versie (mens):</p>
            <pre className="bg-slate-50 p-2 rounded overflow-x-auto">{JSON.stringify(entry.after_json, null, 2)}</pre>
          </div>
        ))}
      </section>
    </main>
  );
}
```

- [ ] **Step 4: Manual verification**

With both servers running, complete a full record → review → save cycle,
then visit `/dashboard` and confirm the saved zorgmoment and any alert
appear, and its detail page shows the AI proposal vs. final version.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api.ts frontend/app/dashboard/
git commit -m "feat: Teamoverzicht dashboard and zorgmoment detail page"
```

---

## Phase 6: Failure Handling, Duplicate-Alert Prevention, End-to-End Fixtures

### Task 6.1: Duplicate-alert prevention on re-save

**Files:**
- Modify: `C:\Users\skayh\Desktop\zorgnotitie\backend\app\routes\zorgmomenten.py`
- Test: `C:\Users\skayh\Desktop\zorgnotitie\backend\tests\test_routes_save.py` (add to existing file)

**Interfaces:**
- Modifies the save endpoint from Task 4.3 to be idempotent against re-saves of an already-`reviewed` zorgmoment.

- [ ] **Step 1: Write the failing test** (append to `backend/tests/test_routes_save.py`)

```python
def test_resaving_an_already_reviewed_zorgmoment_is_rejected(fake_supabase):
    """A zorgmoment can only move from needs_review -> reviewed once.
    This prevents duplicate alerts if a caregiver double-clicks Save or
    the client retries a slow request."""
    fake_supabase.table("zorgmomenten").insert({
        "id": "zm-1", "review_status": "reviewed",
    }).execute()
    with patch("app.routes.zorgmomenten.get_client", return_value=fake_supabase):
        response = client.post("/zorgmomenten/zm-1/save", json={
            "actual_care_summary": "iets",
            "deviation_detected": True, "deviation_reason": "reden",
            "mood_observation": "stemming", "mood_changed": True,
            "behaviour_observation": "gedrag", "behaviour_changed": True,
            "reviewed_by": "demo-zorgmedewerker",
        })
    assert response.status_code == 409
    alert_rows = fake_supabase.table("alerts").execute().data
    assert alert_rows == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/pytest tests/test_routes_save.py -v`

This test actually already passes given Task 4.3's existing guard
(`if row.get("review_status") != "needs_review"`) — run it to confirm that
guard truly covers this case rather than assuming. If it fails, the guard
needs fixing before continuing; if it passes, this test still stays in the
suite as a regression guard and no implementation change is needed for this
task. Note this outcome explicitly rather than silently skipping the
implementation step.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_routes_save.py
git commit -m "test: guard against duplicate alerts on zorgmoment re-save"
```

### Task 6.2: End-to-end demo fixture script

**Files:**
- Create: `C:\Users\skayh\Desktop\zorgnotitie\backend\scripts\demo_walkthrough.py`

**Interfaces:**
- A standalone script exercising the real (not faked) Supabase project + real OpenAI calls, to be run manually against the live backend before recording the demo video in Phase 7.

- [ ] **Step 1: Write the script**

```python
# backend/scripts/demo_walkthrough.py
"""Manual end-to-end smoke script — run against a live backend
(uvicorn app.main:app --reload) with real Supabase + OpenAI credentials.
Not part of the pytest suite: this hits real APIs and costs real tokens."""
import requests

BASE = "http://localhost:8000"

def main():
    health = requests.get(f"{BASE}/health").json()
    print("Health:", health)
    assert health["status"] == "healthy"

    create = requests.post(f"{BASE}/zorgmomenten", json={
        "demo_client_id": "REPLACE_WITH_REAL_DEMO_CLIENT_ID",
        "planned_care_summary": "Ochtendzorg: hulp bij wassen en aankleden, medicatieherinnering en ontbijtvoorbereiding.",
    })
    zm_id = create.json()["id"]
    print("Created zorgmoment:", zm_id)

    print("Manually record and upload audio via the frontend for this ID, then run:")
    print(f"  requests.post('{BASE}/zorgmomenten/{zm_id}/extract')")
    print("to continue this walkthrough.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it manually** (not an automated test — this is a documented manual QA step)

Run: `cd "C:/Users/skayh/Desktop/zorgnotitie/backend" && .venv/Scripts/python scripts/demo_walkthrough.py`
Requires: the real demo Supabase project's `demo_clients.id` for "Mevrouw De
Vries" substituted in, and `uvicorn app.main:app --reload` running in another
terminal with real `.env` credentials loaded.

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/demo_walkthrough.py
git commit -m "chore: add manual end-to-end demo walkthrough script"
```

---

## Phase 7: Deployment and LinkedIn Prep

### Task 7.1: Deploy backend to Render

- [ ] **Step 1:** Push the repo to a new GitHub repository (ask the user for
  the account/org to create it under — do not assume `skyhan51` without
  confirming, since this is a new standalone project).
- [ ] **Step 2:** In Render, create a new Web Service from the repo, root
  directory `backend/`, build command `pip install -r requirements.txt`,
  start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- [ ] **Step 3:** Add environment variables in Render's dashboard:
  `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY` — the real
  values, never committed to the repo.
- [ ] **Step 4:** Once deployed, verify: `curl https://<render-url>/health`
  returns `{"status":"healthy","service":"zorgnotitie"}`.
- [ ] **Step 5:** Update `backend/app/main.py`'s CORS `allow_origins` to the
  real deployed frontend URL (from Task 7.2) instead of
  `http://localhost:3000`, then redeploy.

### Task 7.2: Deploy frontend to Vercel

- [ ] **Step 1:** In Vercel, import the same GitHub repo, set root directory
  to `frontend/`.
- [ ] **Step 2:** Add environment variable `NEXT_PUBLIC_API_URL` pointing at
  the Render backend URL from Task 7.1.
- [ ] **Step 3:** Deploy, verify the live URL loads the Opnemen page.
- [ ] **Step 4:** Run the full record → review → save → dashboard flow once
  against the live deployment (same manual check as Task 6.2's script, now
  through the real UI) before calling this done.

### Task 7.3: Case study write-up and LinkedIn post prep

**Files:**
- Create: `C:\Users\skayh\Desktop\zorgnotitie\CASE_STUDY.md`

- [ ] **Step 1:** Write a short case study following the spec's "Follow-on:
  LinkedIn post" section — real problem with real numbers, what was built,
  the human-in-the-loop/no-clinical-claims constraint that makes it
  trustworthy, and a CTA. Use the corrected problem-statement wording from
  the finalized spec (Phase 0-era correction: don't overclaim adoption of
  the old registration model; don't cite the training-budget figure as if it
  funds this specific workflow).
- [ ] **Step 2:** Hand off to the user for the actual LinkedIn post text and
  graphic — that is a separate content task, not part of this build plan.
- [ ] **Step 3: Commit**

```bash
git add CASE_STUDY.md
git commit -m "docs: add case study write-up"
```

---

## Self-Review Notes

- **Spec coverage:** Problem/positioning → Task 7.3. Non-goals → enforced via
  Global Constraints + explicit test assertions (e.g.
  `test_alert_reason_never_contains_risk_language`). Data model → Task 1.1.
  Data flow steps 1-9 → Tasks 3.2, 3.3, 4.2, 4.3, 4.4, 5.1. Alert logic →
  Task 2.2. Error handling → Tasks 3.1, 3.2, 4.1, 4.2. Testing section →
  covered across Tasks 2.1-2.3, 3.1-3.2, 4.1-4.3, 6.1. UI scope (3 pages) →
  Tasks 3.3, 4.4, 5.2. Compliance posture → layout banner in Task 3.3 Step 8,
  reiterated in Task 7.3.
- **Known deferred item:** Task 3.2 flags that its raw `.insert()` calls for
  updates are a simplification that Task 4.2/4.3 correct to real
  Supabase `.update()` semantics once wired against a real project — call
  this out again explicitly to whoever executes Task 3.2/4.2/4.3: replace
  `client.table("zorgmomenten").insert({"id": zorgmoment_id, ...})` calls
  with `client.table("zorgmomenten").update({...}).eq("id", zorgmoment_id)`
  when running against the real Supabase client (the `FakeTable` test double
  doesn't distinguish insert/update, which is why tests pass either way —
  this must be fixed before Phase 7 deployment, not left as `.insert()` in
  production code).
- **Type consistency:** `ExtractionDraft` field names are identical across
  `schemas.py`, `alerts.py`, `extraction.py`, `zorgmomenten.py` (save
  endpoint), and the frontend `ExtractionDraft` TypeScript interface —
  verified by re-reading each task's interface block above.

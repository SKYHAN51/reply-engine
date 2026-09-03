# ZorgNotitie — Design Spec

**Date:** 2026-09-03
**Status:** Approved for implementation planning
**Owner:** Salih Kayhan

## Problem

Dutch home care (wijkverpleging) staffing is at its worst point since CBS started
tracking it: 68,500 open vacancies at the end of Q2 2026, the highest since 2011,
projected to grow to a 301,000-worker shortfall by 2035 (worst in elderly care).
NZa (Nederlandse Zorgautoriteit) names unnecessary administrative burden as one
driver of staff leaving the sector — specifically citing manual "vijfminutenregistratie"
(five-minute-increment care logging) as an example, even though that model was
formally scrapped nationally in 2019 in favor of "Zorgplan = Planning = Realisatie,
tenzij" (ZPRT): care is pre-planned, and staff only need to document when reality
deviates from the plan. In practice, organizations vary in how much friction this
still causes — older systems, habits, and unclear deviation-reporting workflows
mean documentation still eats time care workers would rather spend with clients.

The 2026 government budget (€53M rising to €185M by 2029) explicitly targets
"meer inzet van ICT" to reduce this administrative burden — so there is real
institutional appetite behind solving a narrow piece of it.

## Non-goals (explicit scope boundary)

This is a portfolio demo, not a clinical or production system. It must never:
- Present itself as a medical device, diagnostic tool, or clinical decision system
- Auto-escalate to a doctor, pharmacist, or family member
- Assign a clinical risk score or severity level (low/medium/high) to any observation
- Store or process real patient data, real names, BSN, addresses, or medication records
- Replace a real ECD (electronic care record), scheduling engine, or billing system
- Add multi-agent architecture or extra AI layers that don't serve the core workflow

## Positioning

ZorgNotitie is a privacy-aware workflow prototype that turns a short spoken care
observation into a checkable ZPRT-style draft report, with explicit human approval
before anything is saved, and simple, rule-based (not AI-scored) attention flags
for deviations or mood/behavior changes. AI proposes; the human decides.

## Target users

- **Primary — Verzorgende IG / zorgmedewerker:** wants to log a care moment
  quickly and correctly without a long administrative flow.
- **Secondary — Teamleider / wijkverpleegkundige:** wants a fast overview of
  which care moments deviated from plan or need human follow-up.

## Demo scenario (grounding example)

- Demo client: "Mevrouw De Vries"
- Planned care: "Ochtendzorg: hulp bij wassen en aankleden, medicatieherinnering
  en ontbijtvoorbereiding."
- Spoken note (caregiver, ~20-40 sec): "Mevrouw De Vries wilde vandaag niet
  douchen omdat ze zich erg moe voelde. Aankleden is wel gelukt met extra hulp.
  Ze oogde stiller dan normaal en wilde nauwelijks ontbijten."
- Structured draft the system proposes:
  - `actual_care`: "Aankleden met extra hulp en medicatieherinnering uitgevoerd;
    douchen niet uitgevoerd; ontbijt nauwelijks gebruikt"
  - `deviation_detected`: true, `deviation_reason`: "Cliënt voelde zich moe en
    weigerde douchen"
  - `mood_observation`: "veranderd: stiller dan normaal"
  - `behaviour_observation`: "verminderde eetlust / weinig initiatief"
- Caregiver reviews/edits the draft, saves it explicitly.
- Because `deviation_detected` and `mood_observation`/`behaviour_observation`
  indicate change, the system creates open attention-flags ("aandachtspunten") —
  never phrased as a risk or diagnosis.

## Architecture

**Stack** (consistent with Salih's existing live projects — Reply Engine, Voice
Receptionist — for portfolio coherence and reuse of familiar patterns):
- Frontend: Next.js + TypeScript + Tailwind
- Backend: FastAPI (separate service, so extraction/alert logic is independently
  testable with pytest, matching the pattern already proven in Reply Engine and
  Voice Receptionist)
- Database: **new, standalone** Supabase project (not connected to SMR or Coach
  Bot infrastructure — no shared blast radius), Postgres + RLS from day one
- Speech-to-text: OpenAI Whisper API, behind a thin provider abstraction so the
  backend isn't hard-wired to one vendor
- Structured extraction: a compact OpenAI chat model, constrained to a strict
  JSON schema, server-side validated before anything touches the database —
  the model proposes, it never writes directly
- Audio handling: uploaded transiently for transcription, then **deleted
  immediately** — only the transcript and structured output persist
- Deployment: Vercel (frontend + edge), Render (FastAPI service) — same
  pattern as Voice Receptionist / Reply Engine
- Hosting name: standalone project, working name **ZorgNotitie**

**Design principle:** AI transcribes and structures. Deterministic business
rules decide alerts. The human is the final authority on saved content.

## Data flow

1. Caregiver picks a demo client, sees the pre-loaded planned care for that visit.
2. Caregiver records a short voice note (start/stop).
3. Audio uploads, Whisper transcribes, audio is deleted.
4. Extraction service turns the transcript into a JSON draft matching the fixed
   schema below (model proposes only — never writes to the final fields).
5. Server validates the JSON against the schema; malformed output is rejected
   and surfaced as a retry-able error, not silently guessed at.
6. Rule engine evaluates the validated draft fields (see Alert logic) and stages
   an alert if triggered — staged, not yet visible to the manager, until the
   caregiver's review is saved.
7. Caregiver sees raw transcript + structured draft, edits any field, and must
   explicitly save — the save button is inactive until the review step is
   reached.
8. On save: final `zorgmomenten` row is written, `audit_log` records the AI's
   original proposal vs. the human-approved final values, and any staged alert
   is committed to `alerts`.
9. Manager dashboard reads only saved, reviewed data — never in-progress drafts.

## Data model

**`demo_clients`** — fictional only
`id, display_name, care_plan_summary, active`

**`zorgmomenten`** — the core record
`id, demo_client_id, planned_care_summary, audio_status, transcript,
extraction_json, actual_care_summary, deviation_detected, deviation_reason,
mood_observation, mood_changed, behaviour_observation, behaviour_changed,
review_status, reviewed_by, reviewed_at, created_at, updated_at`
`review_status`: `processing | draft | needs_review | reviewed | failed`

`mood_observation`/`behaviour_observation` are the free-text descriptions
(editable by the caregiver). `mood_changed`/`behaviour_changed` are explicit
booleans the extraction step sets (and the caregiver can override during
review) — the alert rule reads these booleans directly, never re-interprets
free text at rule-evaluation time. This keeps the deterministic-rule guarantee
consistent for all three alert types, not just `deviation_detected`.

**`alerts`** — attention flags, never a risk score
`id, zorgmoment_id, alert_type, reason, status, created_at, acknowledged_at,
resolved_at`
`alert_type`: `care_deviation | mood_change | behaviour_change`
`status`: `open | acknowledged | resolved`

**`processing_events`** — pipeline traceability for debugging/observability
`id, zorgmoment_id, stage, status, error_code, error_message_safe, created_at`

**`audit_log`** — proves AI never silently decided the final content
`id, zorgmoment_id, actor_type, event_type, before_json, after_json, created_at`

`extraction_json` (the AI's raw proposal) and the individual editable fields
(the human-approved final version) are never merged into one column — this is
what makes the audit trail meaningful.

## Alert logic (deterministic, not AI-scored)

```
if deviation_detected == true:
    create_or_update_alert('care_deviation')
if mood_changed == true:
    create_or_update_alert('mood_change')
if behaviour_changed == true:
    create_or_update_alert('behaviour_change')
```

All three conditions read explicit booleans set during extraction (and
overridable by the caregiver at review time) — never a re-interpretation of
free text at rule-evaluation time.

Never: a sentiment/confidence score used as a clinical signal, a severity label
(low/medium/high), automatic escalation, or copy implying AI made a health
judgment. Alert copy reads "Aandachtspunt voor beoordeling" — never "AI heeft
een gezondheidsrisico vastgesteld."

## Error handling

- STT failure (timeout, empty/unintelligible audio): surfaced to the caregiver
  as a clear, retry-able state — never silently produces an empty or guessed
  draft.
- Extraction returning invalid JSON against the schema: rejected server-side,
  logged to `processing_events`, surfaced as a retry, not passed through.
- Every pipeline stage writes a `processing_events` row so failures are
  traceable without guessing from logs alone.

## Testing

pytest suite (matching the pattern already used in Reply Engine and Voice
Receptionist this session — both currently green):
- Schema validation of extraction output (valid and invalid cases)
- Alert-rule logic (each trigger condition, and the no-alert case)
- No duplicate alerts on re-save of an already-flagged `zorgmoment`
- Mocked STT/LLM failure paths return the correct error state, not a silent
  fallback

## UI scope (3 pages)

1. **Opnemen** — client selector, planned care shown, record/stop control,
   explicit status (recording / transcribing / drafting / done), retry-able
   error state.
2. **Controleren en opslaan** — raw transcript + structured draft, every field
   editable, one line explaining "AI doet een voorstel. Jij controleert en
   beslist.", save button inactive until review is reached.
3. **Teamoverzicht** — list of care moments, filter by client/date/deviation/
   review status, open attention-flags surfaced first, detail view shows the
   original AI draft vs. the human-edited final plus audit metadata.

## Compliance posture (portfolio mode)

- Synthetic demo clients and fictional transcripts only, always
- Visible in-app and in any write-up: "Demo met synthetische gegevens; geen
  medisch hulpmiddel; geen klinische besluitvorming."
- No real names, BSN, addresses, medication records
- Human review is mandatory before anything is saved — this is a product
  requirement, not just a nice-to-have

## Out of scope for this build

Real patient integration, ECD coupling, scheduling/rostering engine, billing,
medication checking, automatic medical interpretation, native mobile app,
multi-agent architecture for its own sake.

## Success criteria

- A non-technical viewer understands the flow within 60 seconds
- A healthcare professional can point to exactly where human review happens
- Core logic (extraction validation, alert rules) has real test coverage
- The demo visibly handles at least the STT-failure and invalid-extraction
  error cases, not just the happy path

## Follow-on: LinkedIn post

Once live: same narrative pattern as the SMR and Supabase-RLS posts (real
problem with real numbers → what was built → the constraint that makes it
trustworthy, here: human-in-the-loop + no clinical claims → CTA). Framing note:
don't claim most organizations still use the old five-minute model — say
organizations vary in maturity and systems, and deviation-reporting still
causes friction. Visual: a single graphic, same style as the RLS post (dark,
technical), showing the flow: spoken note → AI draft → human review → saved +
flagged.

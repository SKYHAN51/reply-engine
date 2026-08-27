# Regie Glass-Box Demo — Design Spec

**Date:** 2026-08-27
**Status:** Approved for implementation planning
**Repos touched:** `regie` (backend + new demo route), `skyhan-app` (portfolio entry)

## 1. Purpose

skyhan.app's portfolio currently shows Regie nowhere, even though it's the
most technically credible project Salih has built (append-only hash-chained
ledger, trust-ladder gated autonomy, human-in-the-loop approval, kill-switch
+ revert). Reply Engine already proves the "live interactive demo" pattern
works for visitors, but it only lets a visitor *watch* a pipeline run — it
doesn't let them experience governance.

This project exposes a safe, public slice of the real Regie system so a
visitor can:

1. Send a message as a "customer" and watch the AI reason and draft a
   response in real time.
2. Switch hats to "business owner" and approve that response themselves,
   triggering a real, hash-chained ledger entry.

Audience: **both** technical evaluators (employers/recruiters — proves real
engineering, not a toy) and prospective SMB clients (proves the system is
safe/controllable, not a black box).

## 2. Non-goals

- No changes to real tenant flows (tenant #0 / skyhan, barber, nagelstudio).
- No real outbound delivery (no Telegram/WhatsApp message actually sent) —
  the demo's "execute" step is a ledger record only, not a real dispatch.
- No admin UI for managing the demo tenant — seeding is a one-time bundle file.
- No automated ledger pruning in v1 — manual truncate if/when needed (same
  approach already used for Regie's test data).

## 3. Architecture overview

Regie's channel support is already a clean registry pattern (one file per
channel in `src/core/contact/normalizers/`, e.g. `telegram.ts`,
`whatsapp.ts`, `missed_call.ts`). This project adds one more channel
(`web`) plus two new public-safe API routes that wrap the existing core
functions — the real `/api/ingest/[channel]` and `/api/gate` endpoints stay
authenticated and untouched.

```
Visitor browser (skyhan.app case-study page, or regie-five.vercel.app/demo)
        │
        │ session_id (cookie, generated client-side on first visit)
        ▼
POST /api/demo/message  ──────────────► ingestAndRespond("web", {session_id, text}, DEMO_TENANT_ID)
        │                                        │
        │                                        ▼
        │                              web normalizer → ContactEvent
        │                              (thread_id = "web:{session_id}")
        │                                        │
        │                                        ▼
        │                              existing brain/gate/ledger core
        │                              (unchanged) → gate_request logged
        ▼
Response: draft answer + reasoning summary + ledger seq (awaiting approval)
        │
        │ visitor clicks "Onayla" (business-owner hat)
        ▼
POST /api/demo/approve ──────────────► resolveGate({tenant_id: DEMO_TENANT_ID, ledger_seq, human_id: session_id, decision: "approve"})
        │                                        │
        │                                        ▼
        │                              existing gate/resolve core (unchanged)
        │                              dispatchFn = noopWebDispatch (new)
        ▼
Response: execute ledger entry (hash-chained, real) + final message shown
```

## 4. New components

### 4.1 `web` contact normalizer — `regie/src/core/contact/normalizers/web.ts`

Same shape as the existing `missed_call.ts`/`telegram.ts` normalizers.
Input: `{ session_id: string; text: string }`. Produces a `ContactEvent`
with `channel: "web"`, `thread_id: "web:{session_id}"`,
`contact.external_id: session_id`. Registered via the existing
`registerNormalizer("web", ...)` call — no changes to the registry
mechanism itself.

### 4.2 Demo tenant bundle — `regie/bundles/demo.yaml`

A new fictional business (not barber/nagelstudio, which stay reserved for
real prospective-client pitches). Small FAQ set covering 3-4 topics so the
preset buttons have real knowledge-base grounding (mirrors Reply Engine's
"GroenTech Services BV" approach). Trust level pinned at 0 so every message
always requires the approval step — this is deliberate: a visitor who
never sees the gate never experiences the point of the demo.

### 4.3 Public demo routes — `regie/src/app/api/demo/message/route.ts`, `regie/src/app/api/demo/approve/route.ts`

Thin wrappers, not copies:

- `message`: validates `session_id` + `text` (length-capped), calls
  `ingestAndRespond("web", raw, DEMO_TENANT_ID)` directly (in-process — no
  API-key auth needed since the tenant is hardcoded to the demo tenant and
  the function is not the real public ingest webhook). Returns the ledger
  entries relevant to that thread since the visitor's last poll.
- `approve`: validates that `body.tenant_id === DEMO_TENANT_ID` and that
  the `ledger_seq` being resolved belongs to a gate whose thread matches
  the caller's `session_id` (prevents one visitor approving another's
  message). Calls `resolveGate` with `dispatchFn: noopWebDispatch`.

### 4.4 No-op dispatch for the `web` channel — `regie/src/server/dispatch.ts`

`dispatchIntent` currently routes to n8n → Telegram send. Add a branch: if
the originating channel is `web`, skip the n8n call and record the
`execute` ledger entry directly with a `note: "demo — not delivered"` field
so the ledger honestly reflects that nothing left the system. This is a
small conditional in an existing function, not a new subsystem.

### 4.5 Demo page — `regie/src/app/(public)/demo/page.tsx`

Purpose-built for a first-time visitor (not a repurposed `/mission`
screen): composer (3 preset buttons + free-text input, same UX pattern as
Reply Engine) on one side, live trace view on the other showing each
ledger entry as it appears (intent → draft → gate_request → [visitor
action] → execute), with a persistent caption: "Elke stap die je hier ziet
is een echte, hash-chained ledger-entry — geen mockup." Session id
generated client-side on first load, stored in `localStorage`, sent with
every request.

Polling (not SSE, unlike Reply Engine): simplest reliable option given
`ingestAndRespond` already returns the outcome synchronously in one
request/response — no need for step-by-step streaming infrastructure. The
UI shows a brief "AI denkt na..." loading state between request and
response instead.

### 4.6 skyhan.app portfolio entry — `skyhan-app/src/data/projects.ts`

New `ProjectData` entry (next `index`, e.g. `"07"`), same shape as the
existing Reply Engine entry: `title: "Regie"`, `url` pointing to the new
`/demo` route, `tags: ["Next.js", "Supabase", "Ledger", "Agentic"]`.
`description`/`challenge`/`solution`/`outcomes` copy written to speak to
both audiences explicitly — one line on the audit-trail/governance
mechanism (technical credibility) and one line on "nooit meer een klant
kwijtraken" (business value), matching the pattern already used in the
Reply Engine and Voice Receptionist entries.

## 5. Safety & cost control

- **Per-IP rate limit** on `/api/demo/message`: cap (e.g. 5 messages/hour)
  to bound OpenAI cost from public traffic — same spirit as Reply Engine's
  existing `slowapi` limiting, implemented as simple in-memory or
  Supabase-backed counter (no new infra dependency).
- **Input length cap** on the free-text field (short, matches a
  customer-message use case — not a general-purpose chat box).
- **Approval scoping**: `approve` route rejects any `ledger_seq` whose
  thread doesn't match the caller's own `session_id`.

## 6. Data lifecycle

Ledger is append-only by design (no delete) — demo traffic accumulates
there like any tenant's data. No automated cleanup in v1; if the demo
tenant's data grows large, a manual `truncate` (already the established
method for clearing Regie test data) is sufficient. Not a v1 concern at
expected traffic levels.

## 7. Error handling

- Unknown/missing `session_id` → 400 (message route), same style as the
  existing ingest route's `422` for normalizer failures.
- Brain/LLM failure during `ingestAndRespond` → surfaced to the visitor as
  a plain "even geen antwoord kunnen genereren, probeer het opnieuw" state,
  not a raw stack trace.
- `approve` on an already-resolved gate → existing `GateResolveError` →
  409, surfaced as "deze actie is al afgehandeld."

## 8. Testing

- Unit test for the new `web` normalizer (same pattern as existing
  normalizer tests — construct raw payload, assert `ContactEvent` shape).
- Unit test for the `web`-channel no-op branch in `dispatchIntent`.
- Route test for `/api/demo/approve` rejecting a `session_id` mismatch.
- Manual QA pass on the `/demo` page: preset button flow and free-text
  flow, on both desktop and mobile widths.

## 9. Open questions for implementation time

- Exact copy/FAQ content for `bundles/demo.yaml` (Salih to provide, or
  draft for approval — small, non-blocking).
- Whether `/demo` lives only on `regie-five.vercel.app` or also gets
  embedded (iframe) directly into the skyhan.app case-study page — default
  to linking out (matches existing Reply Engine/Voice Receptionist
  pattern), embedding is a nice-to-have, not required for v1.

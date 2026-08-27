# Regie Glass-Box Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose a safe, session-scoped public demo of Regie's real ledger/gate/trust pipeline, embedded as a new portfolio entry on skyhan.app, so a visitor can act as both the "customer" sending a message and the "business owner" approving the AI's response.

**Architecture:** Two repos. In `regie` (the real product): one new channel normalizer (`web_form`), two new public API routes that compose existing, unmodified core functions (`ingest`, `respondToInbound`, `resolveGate`) against a dedicated, always-gated demo tenant, a no-op dispatch that still writes a real ledger `execute` entry, and a new client-facing demo page. In `skyhan-app` (the portfolio): one new `PROJECTS` entry linking to that page. No existing production code path (real tenants, real dispatch, real ingest/gate endpoints) is modified.

**Tech Stack:** Next.js 16 (App Router) + TypeScript, Supabase (Postgres), Vitest, existing Regie core (`src/core/*`). skyhan-app: Next.js + Tailwind, static `PROJECTS` data array.

**Spec:** `docs/superpowers/specs/2026-08-27-regie-glassbox-demo-design.md`

## Global Constraints

- Real tenant flows (tenant #0/skyhan, `barber`, `nagelstudio`) are never touched or modified.
- The demo tenant's trust stays at level 0 for every gate action (no `trust_state` rows inserted) — every demo message must require visible approval.
- No real outbound delivery for demo traffic: approving a demo gate never calls n8n or a real messaging provider.
- `/api/demo/message` rate limit: 5 requests / hour / IP.
- Free-text input capped at 500 characters.
- Existing production routes (`/api/ingest/[channel]`, `/api/gate`) are not modified and stay the only way to reach real tenants.
- Demo tenant fixed id: `a1c9f5e2-6b3d-4a2f-9d71-0f6b6a1e6001` (env var `REGIE_DEMO_TENANT_ID`).

---

### Task 1: `web_form` contact normalizer

**Files:**
- Create: `regie/src/core/contact/normalizers/web_form.ts`
- Modify: `regie/src/core/ingest/ingest.ts` (add one side-effect import, same line style as the existing three)
- Test: `regie/tests/core/contact/normalizer.test.ts` (add cases to the existing file)

**Interfaces:**
- Consumes: `registerNormalizer` from `@/core/contact/normalizer`, `ContactEvent` from `@/core/contact/types` (both unchanged).
- Produces: normalizer registered under channel key `"web_form"`, callable via `normalize("web_form", {session_id, text}, tenant_id)`. Later tasks' API routes call `ingest("web_form", ...)`, which requires this import to be present in `ingest.ts` or the normalizer will not be registered at runtime.

- [ ] **Step 1: Write the failing tests**

Add to `regie/tests/core/contact/normalizer.test.ts` (alongside the existing `whatsapp`/`missed_call` tests):

```ts
import "@/core/contact/normalizers/web_form";

test("web_form raw payload normalizes to ContactEvent", () => {
  const raw = { session_id: "sess-123", text: "Wat is Regie?" };
  const ev = normalize("web_form", raw, "t1");
  expect(ev.channel).toBe("web_form");
  expect(ev.direction).toBe("inbound");
  expect(ev.contact.external_id).toBe("sess-123");
  expect(ev.payload.text).toBe("Wat is Regie?");
  expect(ev.thread_id).toBe("web_form:sess-123");
  expect(ev.tenant_id).toBe("t1");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd regie && npx vitest run tests/core/contact/normalizer.test.ts`
Expected: FAIL — `No normalizer registered for channel: web_form`

- [ ] **Step 3: Write the normalizer**

Create `regie/src/core/contact/normalizers/web_form.ts`:

```ts
import { randomUUID } from "node:crypto";
import { registerNormalizer } from "../normalizer";
import type { ContactEvent } from "../types";

interface WebFormRaw {
  session_id: string;
  text: string;
}

// A visitor-typed message from the public glass-box demo page (spec §4.1).
// `session_id` is a browser-generated id, not a real phone/handle — it exists
// only to give each visitor their own isolated thread on the shared demo tenant.
registerNormalizer("web_form", (raw, tenant_id): ContactEvent => {
  const r = raw as WebFormRaw;
  const id = randomUUID();
  const nowIso = new Date().toISOString();
  return {
    id,
    tenant_id,
    occurred_at: nowIso,
    received_at: nowIso,
    channel: "web_form",
    direction: "inbound",
    contact: { external_id: r.session_id },
    thread_id: `web_form:${r.session_id}`,
    payload: { text: r.text },
    raw_ref: `raw:${id}`,
  };
});
```

- [ ] **Step 4: Register it in the ingest module**

Modify `regie/src/core/ingest/ingest.ts` — add one line next to the existing three normalizer imports:

```ts
import "@/core/contact/normalizers/whatsapp";
import "@/core/contact/normalizers/telegram";
import "@/core/contact/normalizers/missed_call";
import "@/core/contact/normalizers/web_form";
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd regie && npx vitest run tests/core/contact/normalizer.test.ts`
Expected: PASS (all tests in the file, including the pre-existing ones)

- [ ] **Step 6: Commit**

```bash
cd regie
git add src/core/contact/normalizers/web_form.ts src/core/ingest/ingest.ts tests/core/contact/normalizer.test.ts
git commit -m "feat: add web_form contact normalizer for the public demo channel"
```

---

### Task 2: Gate lookup helpers

**Files:**
- Create: `regie/src/core/gate/lookup.ts`
- Test: `regie/tests/core/gate/lookup.test.ts`

**Interfaces:**
- Consumes: `LedgerEntry` from `@/core/ledger/types`, `Lead` from `@/core/lead/types`.
- Produces: `findOpenGateRequestSeq(entries: LedgerEntry[], lead_id: string): number | null` and `gateRequestBelongsToContact(entries: LedgerEntry[], leads: Lead[], ledger_seq: number, contact_external_id: string): boolean`. Task 6's message route uses the first; Task 7's approve route uses the second.

- [ ] **Step 1: Write the failing tests**

Create `regie/tests/core/gate/lookup.test.ts`:

```ts
import { findOpenGateRequestSeq, gateRequestBelongsToContact } from "@/core/gate/lookup";
import { ledger, makeLedger } from "@/core/ledger/ledger";
import type { Lead } from "@/core/lead/types";
import { expect, test } from "vitest";

test("finds the seq of an open gate_request for a lead", async () => {
  const { db } = makeLedger();
  await ledger.append(db, {
    tenant_id: "t1", actor: "ai_brain", action_type: "decide",
    subject_ref: { lead_id: "lead-1" }, input_digest: "d", output: {},
  });
  await ledger.append(db, {
    tenant_id: "t1", actor: "ai_brain", action_type: "gate_request",
    subject_ref: { lead_id: "lead-1" }, input_digest: "d", output: {},
  });
  const entries = await ledger.getForTenant(db, "t1");
  expect(findOpenGateRequestSeq(entries, "lead-1")).toBe(2);
});

test("returns null once the gate_request is resolved", async () => {
  const { db } = makeLedger();
  await ledger.append(db, {
    tenant_id: "t1", actor: "ai_brain", action_type: "gate_request",
    subject_ref: { lead_id: "lead-1" }, input_digest: "d", output: {},
  });
  await ledger.append(db, {
    tenant_id: "t1", actor: "human", action_type: "gate_approve",
    subject_ref: { ledger_seq: 1 }, input_digest: "d", output: {},
  });
  const entries = await ledger.getForTenant(db, "t1");
  expect(findOpenGateRequestSeq(entries, "lead-1")).toBeNull();
});

test("returns null when the lead has no gate_request", async () => {
  const { db } = makeLedger();
  const entries = await ledger.getForTenant(db, "t1");
  expect(findOpenGateRequestSeq(entries, "lead-1")).toBeNull();
});

test("gateRequestBelongsToContact is true only for the owning session", async () => {
  const { db } = makeLedger();
  await ledger.append(db, {
    tenant_id: "t1", actor: "ai_brain", action_type: "gate_request",
    subject_ref: { lead_id: "lead-1" }, input_digest: "d", output: {},
  });
  const entries = await ledger.getForTenant(db, "t1");
  const leads: Lead[] = [
    {
      id: "lead-1", tenant_id: "t1", contact_external_id: "session-a", state: "NEW",
      channel_first_seen: "web_form", created_at: "now", updated_at: "now",
    },
  ];
  expect(gateRequestBelongsToContact(entries, leads, 1, "session-a")).toBe(true);
  expect(gateRequestBelongsToContact(entries, leads, 1, "session-b")).toBe(false);
});

test("gateRequestBelongsToContact is false for a non-existent seq", async () => {
  expect(gateRequestBelongsToContact([], [], 1, "session-a")).toBe(false);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd regie && npx vitest run tests/core/gate/lookup.test.ts`
Expected: FAIL — `Cannot find module '@/core/gate/lookup'`

- [ ] **Step 3: Implement the helpers**

Create `regie/src/core/gate/lookup.ts`:

```ts
import type { LedgerEntry } from "@/core/ledger/types";
import type { Lead } from "@/core/lead/types";

// emitDecision() only returns an EmitOutcome string, not the ledger entry it
// wrote — the demo message route needs the actual seq to hand back to the
// approve step, so it re-derives it from the tenant's ledger.
export function findOpenGateRequestSeq(entries: LedgerEntry[], lead_id: string): number | null {
  const resolvedSeqs = new Set(
    entries
      .filter((e) => e.action_type === "gate_approve" || e.action_type === "gate_reject")
      .map((e) => e.subject_ref.ledger_seq),
  );
  const openRequests = entries
    .filter((e) => e.action_type === "gate_request" && e.subject_ref.lead_id === lead_id)
    .filter((e) => !resolvedSeqs.has(e.seq))
    .sort((a, b) => b.seq - a.seq);
  return openRequests[0]?.seq ?? null;
}

// True only if `ledger_seq` is a gate_request belonging to a lead whose
// contact_external_id matches `contact_external_id` — the demo's approve
// route uses this so one visitor's session can never resolve another's gate.
export function gateRequestBelongsToContact(
  entries: LedgerEntry[],
  leads: Lead[],
  ledger_seq: number,
  contact_external_id: string,
): boolean {
  const request = entries.find((e) => e.seq === ledger_seq && e.action_type === "gate_request");
  if (!request?.subject_ref.lead_id) return false;
  const lead = leads.find((l) => l.id === request.subject_ref.lead_id);
  return lead?.contact_external_id === contact_external_id;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd regie && npx vitest run tests/core/gate/lookup.test.ts`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
cd regie
git add src/core/gate/lookup.ts tests/core/gate/lookup.test.ts
git commit -m "feat: add gate lookup helpers for the public demo routes"
```

---

### Task 3: Rate-limit helper

**Files:**
- Create: `regie/src/server/rate-limit.ts`
- Test: `regie/tests/server/rate-limit.test.ts`

**Interfaces:**
- Produces: `checkRateLimit(store: Map<string, RateLimitEntry>, key: string, max: number, windowMs: number, now?: number): boolean`. Task 6's message route calls this with a module-level `Map` and the caller's IP as `key`.

- [ ] **Step 1: Write the failing tests**

Create `regie/tests/server/rate-limit.test.ts`:

```ts
import { checkRateLimit, type RateLimitEntry } from "@/server/rate-limit";
import { expect, test } from "vitest";

test("allows up to max requests within the window", () => {
  const store = new Map<string, RateLimitEntry>();
  expect(checkRateLimit(store, "ip1", 2, 1000, 0)).toBe(true);
  expect(checkRateLimit(store, "ip1", 2, 1000, 100)).toBe(true);
  expect(checkRateLimit(store, "ip1", 2, 1000, 200)).toBe(false);
});

test("resets once the window has passed", () => {
  const store = new Map<string, RateLimitEntry>();
  checkRateLimit(store, "ip1", 1, 1000, 0);
  expect(checkRateLimit(store, "ip1", 1, 1000, 1500)).toBe(true);
});

test("tracks separate keys independently", () => {
  const store = new Map<string, RateLimitEntry>();
  checkRateLimit(store, "ip1", 1, 1000, 0);
  expect(checkRateLimit(store, "ip2", 1, 1000, 0)).toBe(true);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd regie && npx vitest run tests/server/rate-limit.test.ts`
Expected: FAIL — `Cannot find module '@/server/rate-limit'`

- [ ] **Step 3: Implement the helper**

Create `regie/src/server/rate-limit.ts`:

```ts
// Minimal fixed-window rate limiter. In-memory and per-instance — acceptable
// for a low-stakes public demo (spec §5); not a general-purpose limiter.
export interface RateLimitEntry {
  count: number;
  resetAt: number;
}

export function checkRateLimit(
  store: Map<string, RateLimitEntry>,
  key: string,
  max: number,
  windowMs: number,
  now: number = Date.now(),
): boolean {
  const entry = store.get(key);
  if (!entry || now >= entry.resetAt) {
    store.set(key, { count: 1, resetAt: now + windowMs });
    return true;
  }
  if (entry.count >= max) return false;
  entry.count += 1;
  return true;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd regie && npx vitest run tests/server/rate-limit.test.ts`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Commit**

```bash
cd regie
git add src/server/rate-limit.ts tests/server/rate-limit.test.ts
git commit -m "feat: add in-memory rate limiter for the public demo endpoint"
```

---

### Task 4: No-op demo dispatch

**Files:**
- Create: `regie/src/server/demo-dispatch.ts`
- Test: `regie/tests/server/demo-dispatch.test.ts`

**Interfaces:**
- Consumes: `handleN8nCallback` and `ExecuteIntent` from `@/limbs/execute` (unchanged), `LedgerDB` from `@/core/ledger/ledger`, `ledgerDB` from `@/server/db`.
- Produces: `noopWebDispatch(intent: ExecuteIntent, db?: LedgerDB): Promise<void>` — structurally assignable to `ResolveGateDeps["dispatchFn"]` (`(intent: ExecuteIntent) => Promise<void>`), used by Tasks 6 and 7 as the `dispatchFn`.

- [ ] **Step 1: Write the failing test**

Create `regie/tests/server/demo-dispatch.test.ts`:

```ts
import { noopWebDispatch } from "@/server/demo-dispatch";
import { ledger, makeLedger } from "@/core/ledger/ledger";
import { expect, test } from "vitest";

test("writes a real execute ledger entry without calling any external service", async () => {
  const { db } = makeLedger();
  await noopWebDispatch(
    { tenant_id: "t1", ledger_seq: 3, channel: "web_form", target: "session-a", payload: { text: "hoi" } },
    db,
  );
  const entries = await ledger.getForTenant(db, "t1");
  expect(entries).toHaveLength(1);
  expect(entries[0].action_type).toBe("execute");
  expect(entries[0].actor).toBe("n8n");
  expect((entries[0].output as { provider_ref: string }).provider_ref).toBe("demo-noop");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd regie && npx vitest run tests/server/demo-dispatch.test.ts`
Expected: FAIL — `Cannot find module '@/server/demo-dispatch'`

- [ ] **Step 3: Implement the no-op dispatch**

Create `regie/src/server/demo-dispatch.ts`:

```ts
import { handleN8nCallback, type ExecuteIntent } from "@/limbs/execute";
import { ledgerDB } from "@/server/db";
import type { LedgerDB } from "@/core/ledger/ledger";

// Demo-only dispatch: writes the same `execute` ledger entry a real n8n
// callback would (spec §4.4), but never calls n8n or an external channel —
// there is no real recipient for a public visitor's session. The `db` param
// defaults to the real Supabase-backed ledger (matching the `ledgerDB(client
// = supabase())` injection idiom already used in this file) so this same
// function is both the production wiring and directly unit-testable.
export async function noopWebDispatch(intent: ExecuteIntent, db: LedgerDB = ledgerDB()): Promise<void> {
  await handleN8nCallback(
    {
      tenant_id: intent.tenant_id,
      ledger_seq: intent.ledger_seq,
      channel: intent.channel,
      target: intent.target,
      ok: true,
      provider_ref: "demo-noop",
    },
    db,
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd regie && npx vitest run tests/server/demo-dispatch.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd regie
git add src/server/demo-dispatch.ts tests/server/demo-dispatch.test.ts
git commit -m "feat: add no-op dispatch for the public demo tenant"
```

---

### Task 5: Demo vertical bundle

**Files:**
- Create: `regie/bundles/demo.yaml`
- Test: `regie/tests/core/bundle/demo-bundle.test.ts`

**Interfaces:**
- Consumes: `loadBundle` from `@/core/bundle/loader` (unchanged, validates against its existing zod schema).
- Produces: a loadable bundle with `id: "demo"`, referenced by Task 7's demo tenant row via `vertical_bundle_id`.

- [ ] **Step 1: Write the failing test**

Create `regie/tests/core/bundle/demo-bundle.test.ts`:

```ts
import { resolve } from "node:path";
import { loadBundle } from "@/core/bundle/loader";
import { expect, test } from "vitest";

test("the demo bundle parses without throwing", () => {
  const bundle = loadBundle(resolve(process.cwd(), "bundles", "demo.yaml"));
  expect(bundle.id).toBe("demo");
  expect(bundle.knowledge.faqs?.length).toBeGreaterThan(0);
  expect(bundle.playbooks).toContain("new_lead_response");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd regie && npx vitest run tests/core/bundle/demo-bundle.test.ts`
Expected: FAIL — `ENOENT: no such file or directory, open '.../bundles/demo.yaml'`

- [ ] **Step 3: Write the bundle**

Create `regie/bundles/demo.yaml`:

```yaml
id: demo
name: "Regie Demo — Klantvraag"
locale: nl-NL
knowledge:
  services:
    - { name: "Demo consult", price: 0, duration_min: 15 }
  hours: "ma-vr 09:00-17:00"
  faqs:
    - { q: "Wat is Regie?", a: "Regie is het mission control systeem voor de AI-medewerkers van een bedrijf — elke actie wordt vastgelegd, uitgelegd, en moet worden goedgekeurd voor die echt gebeurt." }
    - { q: "Is dit een echte AI?", a: "Ja — dit gesprek loopt door hetzelfde brein, dezelfde ledger en dezelfde goedkeuringsstap als een echte Regie-klant. Er wordt alleen niets echt verstuurd." }
    - { q: "Kan de AI zomaar dingen doen zonder toestemming?", a: "Nee. Elke actie op vertrouwensniveau 0 wacht op een menselijke goedkeuring — dat zie je hieronder in de flow." }
  policies:
    - "Nooit beweren dat dit een echt bedrijf is — dit is een demonstratie van het Regie-platform zelf."
voice:
  tone: "helder, transparant, een beetje trots op de eigen techniek"
  language: nl
  sample_messages:
    - "Dank voor je bericht! Hier is mijn concept-antwoord — een mens moet dit nog goedkeuren voordat het verstuurd wordt."
channels:
  - { type: web_form }
compliance_profile:
  region: EU
  consent_required: false
  retention_days: 30
  default_gates: []
playbooks:
  - new_lead_response
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd regie && npx vitest run tests/core/bundle/demo-bundle.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd regie
git add bundles/demo.yaml tests/core/bundle/demo-bundle.test.ts
git commit -m "feat: add demo vertical bundle for the public glass-box showcase"
```

---

### Task 6: Demo tenant + env var

**Files:**
- Create: `regie/supabase/migrations/0007_demo_tenant.sql`
- Modify: `regie/src/config/env.ts` (add one entry to `ENV_KEYS`)

**Interfaces:**
- Produces: a `tenant` row with `id = 'a1c9f5e2-6b3d-4a2f-9d71-0f6b6a1e6001'`, `vertical_bundle_id = 'demo'`, `status = 'active'`, retrievable via the existing `getTenant()` in `@/server/db`. Tasks 7 and 8 read this id via `requireEnv("REGIE_DEMO_TENANT_ID")`.

No unit test — this is a data migration + deployment config, consistent with how the existing `0001`-`0006` migrations have no test files (they're exercised by the integration/go-live steps, per `docs/GO-LIVE.md`).

- [ ] **Step 1: Write the migration**

Create `regie/supabase/migrations/0007_demo_tenant.sql`:

```sql
-- Demo tenant for the public skyhan.app "glass-box" showcase
-- (docs/superpowers/specs/2026-08-27-regie-glassbox-demo-design.md).
-- Fixed id so the demo API routes can reference it via REGIE_DEMO_TENANT_ID
-- without a lookup. Trust for this tenant is intentionally never seeded —
-- missing trust_state rows default to level 0, so every demo action gates.
insert into tenant (id, name, region, vertical_bundle_id, status)
values ('a1c9f5e2-6b3d-4a2f-9d71-0f6b6a1e6001', 'Regie Public Demo', 'EU', 'demo', 'active');
```

- [ ] **Step 2: Register the new env var**

Modify `regie/src/config/env.ts` — add one line to `ENV_KEYS`:

```ts
export const ENV_KEYS = [
  "SUPABASE_URL",
  "SUPABASE_SERVICE_KEY",
  "REGIE_LLM_PROVIDER",
  "REGIE_MODEL_FRONTIER",
  "REGIE_MODEL_CHEAP",
  "ANTHROPIC_API_KEY",
  "OPENAI_API_KEY",
  "N8N_WEBHOOK_BASE",
  "TELEGRAM_BOT_TOKEN",
  "REGIE_OWNER_TELEGRAM_CHAT",
  "REGIE_PUBLIC_URL",
  "FOLLOWUP_DELAY_MINUTES",
  "EXPIRE_DELAY_MINUTES",
  "REGIE_API_SECRET",
  "TELEGRAM_WEBHOOK_SECRET",
  "REGIE_DEMO_TENANT_ID", // fixed id of the public glass-box demo tenant
] as const;
```

- [ ] **Step 3: Apply the migration and set the env var (manual, not code)**

Run the SQL in `0007_demo_tenant.sql` against the real Supabase project (SQL editor or `supabase db push`, matching however `0001`-`0006` were applied). Then add `REGIE_DEMO_TENANT_ID=a1c9f5e2-6b3d-4a2f-9d71-0f6b6a1e6001` to the Vercel project's environment variables (Production and Preview) and to local `.env`.

Verify with:

```bash
psql "$SUPABASE_DB_URL" -c "select id, name, vertical_bundle_id, status from tenant where id = 'a1c9f5e2-6b3d-4a2f-9d71-0f6b6a1e6001';"
```

Expected: one row, `vertical_bundle_id = demo`, `status = active`.

- [ ] **Step 4: Commit**

```bash
cd regie
git add supabase/migrations/0007_demo_tenant.sql src/config/env.ts
git commit -m "feat: seed the public demo tenant and register REGIE_DEMO_TENANT_ID"
```

---

### Task 7: `/api/demo/message` route

**Files:**
- Create: `regie/src/app/api/demo/message/route.ts`

**Interfaces:**
- Consumes: `ingest` (`@/core/ingest/ingest`), `respondToInbound` (`@/core/inbound/respond`), `loadBundle` (`@/core/bundle/loader`), `defaultModel` (`@/server/model`), `noopWebDispatch` (Task 4), `ledger.getForTenant` (`@/core/ledger/ledger`), `findOpenGateRequestSeq` (Task 2), `checkRateLimit` (Task 3), `ledgerDB`/`leadStore`/`getTenant`/`getTrustState` (`@/server/db`), `requireEnv` (`@/config/env`).
- Produces: `POST` handler returning `{ outcome: "gate"|"dispatch"|"none", draft: {channel,text}|null, rationale: string, confidence: number, gate_seq: number|null }`. Task 9 (the demo page) calls this.

Depends on: Tasks 1, 2, 3, 4, 5, 6 all being in place (this route composes all of them).

No unit test — this repo has no route-level test files for any existing endpoint (`/api/ingest`, `/api/gate` included); routes are verified manually. This task's manual `curl` step is that verification.

- [ ] **Step 1: Write the route**

Create `regie/src/app/api/demo/message/route.ts`:

```ts
import { resolve } from "node:path";
import { NextResponse } from "next/server";
import { ingest } from "@/core/ingest/ingest";
import { respondToInbound } from "@/core/inbound/respond";
import { loadBundle } from "@/core/bundle/loader";
import { defaultModel } from "@/server/model";
import { noopWebDispatch } from "@/server/demo-dispatch";
import { ledger } from "@/core/ledger/ledger";
import { findOpenGateRequestSeq } from "@/core/gate/lookup";
import { checkRateLimit, type RateLimitEntry } from "@/server/rate-limit";
import { requireEnv } from "@/config/env";
import { ledgerDB, leadStore, getTenant, getTrustState } from "@/server/db";
import type { ContactEvent } from "@/core/contact/types";
import type { Lead } from "@/core/lead/types";
import type { EmitOutcome } from "@/core/brain/emit";
import type { DecideResponse } from "@/core/brain/types";

// Public, unauthenticated endpoint for the glass-box demo page (spec §4.3).
// Hardcoded to the demo tenant only — never a stand-in for the real,
// authenticated /api/ingest/[channel] webhook.
const RATE_LIMIT_STORE = new Map<string, RateLimitEntry>();
const RATE_LIMIT_MAX = 5;
const RATE_LIMIT_WINDOW_MS = 60 * 60 * 1000;

export async function POST(req: Request) {
  const body = (await req.json()) as Partial<{ session_id: string; text: string }>;
  if (!body.session_id || typeof body.session_id !== "string") {
    return NextResponse.json({ error: "session_id required" }, { status: 400 });
  }
  if (!body.text || typeof body.text !== "string" || body.text.length === 0 || body.text.length > 500) {
    return NextResponse.json({ error: "text required, max 500 characters" }, { status: 400 });
  }

  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "unknown";
  if (!checkRateLimit(RATE_LIMIT_STORE, ip, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW_MS)) {
    return NextResponse.json({ error: "too many demo messages, try again later" }, { status: 429 });
  }

  const tenant_id = requireEnv("REGIE_DEMO_TENANT_ID");
  const db = ledgerDB();
  const store = leadStore();

  let event: ContactEvent;
  let lead: Lead;
  try {
    ({ event, lead } = await ingest("web_form", { session_id: body.session_id, text: body.text }, tenant_id, { db, store }));
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 422 });
  }

  const tenant = await getTenant(tenant_id);
  if (!tenant) {
    return NextResponse.json({ error: "demo tenant not configured" }, { status: 500 });
  }

  let outcome: EmitOutcome;
  let decision: DecideResponse;
  try {
    const bundle = loadBundle(resolve(process.cwd(), "bundles", `${tenant.vertical_bundle_id}.yaml`));
    const trustState = await getTrustState(tenant_id);
    ({ outcome, decision } = await respondToInbound(
      { event, lead, bundle, trustState },
      { db, model: defaultModel(), dispatchFn: noopWebDispatch },
    ));
  } catch {
    return NextResponse.json(
      { error: "kon geen antwoord genereren, probeer het opnieuw" },
      { status: 502 },
    );
  }

  let gate_seq: number | null = null;
  if (outcome === "gate") {
    const entries = await ledger.getForTenant(db, tenant_id);
    gate_seq = findOpenGateRequestSeq(entries, lead.id);
  }

  return NextResponse.json({
    outcome,
    draft: decision.draft ?? null,
    rationale: decision.rationale,
    confidence: decision.confidence,
    gate_seq,
  });
}
```

- [ ] **Step 2: Manual verification**

Run the dev server (`cd regie && npm run dev`), then in another terminal:

```bash
curl -s -X POST http://localhost:3000/api/demo/message \
  -H "content-type: application/json" \
  -d '{"session_id":"manual-test-1","text":"Wat is Regie?"}'
```

Expected: HTTP 200, JSON body with `"outcome":"gate"`, a non-null `draft.text`, and a numeric `gate_seq` (not null — trust is pinned at 0, so every message must gate).

- [ ] **Step 3: Commit**

```bash
cd regie
git add src/app/api/demo/message/route.ts
git commit -m "feat: add public /api/demo/message endpoint"
```

---

### Task 8: `/api/demo/approve` route

**Files:**
- Create: `regie/src/app/api/demo/approve/route.ts`

**Interfaces:**
- Consumes: `resolveGate`/`GateResolveError` (`@/core/gate/resolve`), `gateRequestBelongsToContact` (Task 2), `noopWebDispatch` (Task 4), `requireEnv` (`@/config/env`), `ledger.getForTenant` (`@/core/ledger/ledger`), `ledgerDB`/`leadStore` (`@/server/db`).
- Produces: `POST` handler returning `{ seq: number, action_type: string, dispatched: boolean }` on success. Task 9 calls this after Task 7 returns a `gate_seq`.

Depends on: Tasks 2, 4, 6, 7 (needs a `gate_seq` from the message route to test against).

- [ ] **Step 1: Write the route**

Create `regie/src/app/api/demo/approve/route.ts`:

```ts
import { NextResponse } from "next/server";
import { resolveGate, GateResolveError } from "@/core/gate/resolve";
import { gateRequestBelongsToContact } from "@/core/gate/lookup";
import { noopWebDispatch } from "@/server/demo-dispatch";
import { requireEnv } from "@/config/env";
import { ledger } from "@/core/ledger/ledger";
import { ledgerDB, leadStore } from "@/server/db";

// Public counterpart to /api/demo/message. Ownership-checked so one visitor's
// session can never resolve a gate belonging to another visitor's thread —
// never a stand-in for the real, authenticated /api/gate endpoint.
export async function POST(req: Request) {
  const body = (await req.json()) as Partial<{
    session_id: string;
    ledger_seq: number;
    decision: "approve" | "reject";
  }>;
  if (
    !body.session_id ||
    typeof body.ledger_seq !== "number" ||
    (body.decision !== "approve" && body.decision !== "reject")
  ) {
    return NextResponse.json(
      { error: "session_id, ledger_seq, decision(approve|reject) required" },
      { status: 400 },
    );
  }

  const tenant_id = requireEnv("REGIE_DEMO_TENANT_ID");
  const db = ledgerDB();

  const entries = await ledger.getForTenant(db, tenant_id);
  const leads = await leadStore().activeLeads(tenant_id);
  if (!gateRequestBelongsToContact(entries, leads, body.ledger_seq, body.session_id)) {
    return NextResponse.json({ error: "not your gate to resolve" }, { status: 403 });
  }

  try {
    const { gate, dispatched } = await resolveGate(
      { tenant_id, ledger_seq: body.ledger_seq, human_id: body.session_id, decision: body.decision },
      { db, dispatchFn: noopWebDispatch },
    );
    return NextResponse.json({ seq: gate.seq, action_type: gate.action_type, dispatched });
  } catch (e) {
    if (e instanceof GateResolveError) {
      return NextResponse.json({ error: e.message }, { status: 409 });
    }
    throw e;
  }
}
```

- [ ] **Step 2: Manual verification**

With the dev server still running, repeat Task 7's curl call to get a fresh `gate_seq`, then:

```bash
curl -s -X POST http://localhost:3000/api/demo/message \
  -H "content-type: application/json" \
  -d '{"session_id":"manual-test-2","text":"Wat is Regie?"}'
# note the returned gate_seq, then:

curl -s -X POST http://localhost:3000/api/demo/approve \
  -H "content-type: application/json" \
  -d '{"session_id":"manual-test-2","ledger_seq":<gate_seq from above>,"decision":"approve"}'
```

Expected: HTTP 200, `{"seq":<n>,"action_type":"gate_approve","dispatched":true}`.

Then verify ownership rejection:

```bash
curl -s -X POST http://localhost:3000/api/demo/approve \
  -H "content-type: application/json" \
  -d '{"session_id":"someone-elses-session","ledger_seq":<same gate_seq>,"decision":"approve"}'
```

Expected: HTTP 403, `{"error":"not your gate to resolve"}`.

- [ ] **Step 3: Commit**

```bash
cd regie
git add src/app/api/demo/approve/route.ts
git commit -m "feat: add public /api/demo/approve endpoint"
```

---

### Task 9: Public demo page

**Files:**
- Create: `regie/src/app/demo/page.tsx`

**Interfaces:**
- Consumes: `POST /api/demo/message` and `POST /api/demo/approve` (Tasks 7, 8) via `fetch`.
- Produces: the page at `/demo` on `regie-five.vercel.app`, the URL Task 10's skyhan.app portfolio entry links to.

- [ ] **Step 1: Write the page**

Create `regie/src/app/demo/page.tsx`:

```tsx
"use client";

import { useState } from "react";

interface MessageResult {
  outcome: "gate" | "dispatch" | "none";
  draft: { channel: string; text: string } | null;
  rationale: string;
  confidence: number;
  gate_seq: number | null;
}

const PRESETS = [
  "Wat is Regie?",
  "Is dit een echte AI?",
  "Kan de AI zomaar dingen doen zonder toestemming?",
];

function getSessionId(): string {
  const key = "regie_demo_session_id";
  let id = window.localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(key, id);
  }
  return id;
}

export default function DemoPage() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MessageResult | null>(null);
  const [resolved, setResolved] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function sendMessage(message: string) {
    setLoading(true);
    setError(null);
    setResult(null);
    setResolved(null);
    try {
      const res = await fetch("/api/demo/message", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ session_id: getSessionId(), text: message }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "onbekende fout");
      setResult(data as MessageResult);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function resolveGate(decision: "approve" | "reject") {
    if (!result?.gate_seq) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/demo/approve", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ session_id: getSessionId(), ledger_seq: result.gate_seq, decision }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "onbekende fout");
      setResolved(decision);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-16 text-[#F3F1EC]">
      <h1 className="text-2xl font-semibold mb-2">Regie — glass-box demo</h1>
      <p className="text-sm text-white/60 mb-8">
        Stuur een bericht als klant. Elke stap hierna is een echte, hash-chained ledger-entry —
        geen mockup. Jij keurt hem zelf goed voor er iets &quot;verstuurd&quot; wordt.
      </p>

      <div className="flex flex-wrap gap-2 mb-4">
        {PRESETS.map((p) => (
          <button
            key={p}
            onClick={() => sendMessage(p)}
            disabled={loading}
            className="rounded-full border border-white/20 px-4 py-2 text-sm hover:bg-white/10 disabled:opacity-40"
          >
            {p}
          </button>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim()) sendMessage(text.trim());
        }}
        className="flex gap-2 mb-8"
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Schrijf je eigen klantvraag..."
          disabled={loading}
          maxLength={500}
          className="flex-1 rounded border border-white/20 bg-transparent px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={loading || !text.trim()}
          className="rounded bg-[#5FA396] px-4 py-2 text-sm font-medium disabled:opacity-40"
        >
          Verwerken →
        </button>
      </form>

      {loading && <p className="text-sm text-white/50">AI denkt na...</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}

      {result && (
        <div className="rounded border border-white/10 p-4 space-y-3">
          <p className="text-xs uppercase tracking-wide text-white/40">Concept-antwoord</p>
          <p className="text-sm">{result.draft?.text}</p>
          <p className="text-xs text-white/40">
            Rationale: {result.rationale} — confidence {(result.confidence * 100).toFixed(0)}%
          </p>

          {result.outcome === "gate" && !resolved && (
            <div className="flex gap-2 pt-2">
              <button
                onClick={() => resolveGate("approve")}
                disabled={loading}
                className="rounded bg-[#5FA396] px-4 py-2 text-sm font-medium"
              >
                Goedkeuren
              </button>
              <button
                onClick={() => resolveGate("reject")}
                disabled={loading}
                className="rounded border border-white/20 px-4 py-2 text-sm"
              >
                Afwijzen
              </button>
            </div>
          )}

          {resolved === "approve" && (
            <p className="text-sm text-[#5FA396]">
              ✓ Goedgekeurd — vastgelegd in de ledger (seq {result.gate_seq}).
            </p>
          )}
          {resolved === "reject" && (
            <p className="text-sm text-white/50">Afgewezen — ook dit staat vastgelegd in de ledger.</p>
          )}
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Manual verification**

Run `cd regie && npm run dev`, open `http://localhost:3000/demo` in a browser:
1. Click a preset button → within a few seconds a concept answer + rationale appears, with "Goedkeuren"/"Afwijzen" buttons.
2. Click "Goedkeuren" → the confirmation line with the ledger seq appears, buttons disappear.
3. Reload the page, type a free-text question, submit → same flow works.
4. Open a private/incognito window (fresh `localStorage`, i.e. a fresh session id), repeat step 1 — confirm it works independently (own thread, not mixed with the first session's).

- [ ] **Step 3: Commit**

```bash
cd regie
git add src/app/demo/page.tsx
git commit -m "feat: add public glass-box demo page at /demo"
```

- [ ] **Step 4: Deploy**

Push to the branch Vercel deploys from (or run `vercel --prod` per `[[reference-skyhan-deploy]]`-style manual deploy) so `https://regie-five.vercel.app/demo` is live before Task 10.

---

### Task 10: skyhan.app portfolio entry

**Files:**
- Modify: `skyhan-app/src/data/projects.ts` (add one `ProjectData` entry)
- Create: `skyhan-app/public/assets/images/project-regie.png`

**Interfaces:**
- Consumes: the existing `ProjectData` interface (unchanged) and the existing `/projects/[slug]/page.tsx` renderer (unchanged — no code changes needed there, it already renders any entry in `PROJECTS`).

Depends on: Task 9 being deployed (the screenshot and the linked URL both need the live page).

- [ ] **Step 1: Capture the screenshot**

Visit the deployed `https://regie-five.vercel.app/demo`, trigger a preset question so the concept-answer + approve buttons are visible, take a screenshot, crop it to the same aspect ratio as `public/assets/images/project-reply-engine.png`, save it as `skyhan-app/public/assets/images/project-regie.png`.

- [ ] **Step 2: Add the portfolio entry**

Modify `skyhan-app/src/data/projects.ts` — add this entry to the `PROJECTS` array (after the existing `k-ran` entry, as the new highest index):

```ts
{
  index:       "07",
  slug:        "regie",
  title:       "Regie",
  result:      "Live Demo · Hash-Chained Ledger · Human-in-the-loop",
  tags:        ["Next.js", "Supabase", "Ledger", "Agentic AI"],
  image:       "/assets/images/project-regie.png",
  year:        "2026",
  url:         "https://regie-five.vercel.app/demo",
  description: "Mission control voor de AI-medewerkers van een bedrijf. Elke actie wordt vastgelegd in een hash-chained, tamper-evident ledger, uitgelegd in gewone taal, en moet worden goedgekeurd voor die echt gebeurt. Probeer het zelf: stuur een bericht als klant, en keur het concept-antwoord daarna zelf goed als bedrijfseigenaar.",
  challenge:   "AI-agents die zelfstandig acties ondernemen klinken krachtig, maar zonder een controleerbaar spoor durft geen ondernemer ze los te laten op klanten. \"Vertrouw de AI maar\" is geen strategie.",
  solution:    "Een append-only, hash-chained Action Ledger legt elke observatie, beslissing en actie vast — onveranderbaar en te verifiëren. Een trust-ladder bepaalt per actietype hoeveel autonomie een AI-medewerker heeft verdiend; bij twijfel wacht het systeem op een menselijke goedkeuring. Een halt-knop stopt een tenant per direct.",
  process: [
    { step: "Observeren", detail: "Elk inkomend bericht wordt genormaliseerd en vastgelegd, ongeacht het kanaal" },
    { step: "Beslissen",  detail: "Het AI-brein stelt een reactie voor met een expliciete reden en zekerheidsscore" },
    { step: "Goedkeuren", detail: "Bij een laag vertrouwensniveau wacht de actie op een mens — zichtbaar, niet verborgen" },
    { step: "Uitvoeren",  detail: "Pas na goedkeuring wordt de actie echt uitgevoerd, en vastgelegd als bewijs" },
  ],
  outcomes: [
    "Elke actie herleidbaar tot een hash-chained ledgerregel — geverifieerd, niet beloofd",
    "Trust-ladder: AI verdient autonomie per actietype, net als een medewerker in proeftijd",
    "Halt + revert: een tenant is per direct te pauzeren en acties terug te draaien",
    "Live te proberen: stuur zelf een bericht en keur het zelf goed",
  ],
},
```

- [ ] **Step 3: Verify locally**

Run `cd skyhan-app && npm run dev`, visit `http://localhost:3000/#projects` and confirm the new "Regie" card appears, then visit `http://localhost:3000/projects/regie` and confirm the case-study page renders with the image, copy, and a working "Live Demo" link to `https://regie-five.vercel.app/demo`.

- [ ] **Step 4: Commit**

```bash
cd skyhan-app
git add src/data/projects.ts public/assets/images/project-regie.png
git commit -m "feat: add Regie glass-box demo to the projects portfolio"
```

- [ ] **Step 5: Deploy**

Deploy skyhan-app per `[[reference-skyhan-deploy]]` (manual `vercel deploy --prod` + alias set).

---

### Task 11: End-to-end QA on production

**Files:** none (verification only)

- [ ] **Step 1:** Visit `https://skyhan.app/#projects`, confirm the Regie card is visible and links to `https://skyhan.app/projects/regie`.
- [ ] **Step 2:** From that case-study page, click through to the live demo at `https://regie-five.vercel.app/demo`.
- [ ] **Step 3:** Run through the full flow (preset button → draft appears → Goedkeuren → confirmation) on the production URL, not just localhost.
- [ ] **Step 4:** Confirm the real tenants are unaffected — visit `https://regie-five.vercel.app/mission?tenant=f74365ab-710b-4e94-8aa4-48ff4851ca4b` (tenant #0) and confirm it still shows only real skyhan leads, no demo traffic mixed in.
- [ ] **Step 5:** Trigger the rate limit deliberately (6 requests within an hour from the same browser) and confirm the 6th returns the "too many demo messages" error instead of a 500.

Before release:
- Run relevant tests, typecheck, lint, and build for the product being shipped
  (Reply Engine: `cd demo/api && pytest`; Voice Receptionist: `cd demo/voice && npm run build`)
- Check for secrets or env vars accidentally exposed
- Review CORS, auth, and rate limits where applicable
- Verify no real external side effect (SMS/email/booking) will fire unintentionally
- Verify any public-facing claims still match reality

Return GO, GO_WITH_FIXES, or NO_GO.

Do not deploy without explicit confirmation.

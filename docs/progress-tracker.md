# Opportunity Radar — Progress Tracker

Last updated: 2026-07-16

## Status: MVP code complete (Phases 0-7 written). Awaiting deploy: DB migration, secrets, first manual Actions run.

## Phase status

- [x] Phase 0 — Foundations (repo scaffold, .env.example, migration 001_init.sql)
- [x] Phase 1 — Source discovery (Brave client, DDG fallback, daily query rotation)
- [x] Phase 2 — Extraction & normalization (Candidate dataclass, URL normalization, board-noise blocklist)
- [x] Phase 3 — Scoring & summarization (Groq primary / Gemini fallback, batched JSON scoring, profile at config/profile.md)
- [x] Phase 4 — Dedup (pre-scoring filter_unseen, post-send record_candidates with sent flag)
- [x] Phase 5 — Email digest (HTML + plaintext, Gmail SMTP SSL 465)
- [x] Phase 6 — Circuit breaker (QuotaGuard on api_usage table, 90% stop line, brave monthly / groq+gemini daily)
- [ ] Phase 7 — Scheduling & E2E test (workflow written; NOT yet run: needs secrets + manual dispatch + one real cron cycle)
- [ ] Phase 8 — Stretch (WhatsApp, tuning)

## Decisions made this session (2026-07-16)

- Separate database `opportunity_radar` on the existing Postgres instance (not a schema in appdb). One-line env change if reversed.
- ALL scored candidates are recorded in seen_opportunities (with a `sent` boolean), not only the sent ones. Deviation from original plan; prevents re-scoring the same low scorers daily and wasting Groq quota.
- Quota counted on attempt, not success.
- Dedup runs BEFORE scoring to save LLM quota.
- Failed email send = candidates not recorded, so they retry tomorrow.

## Deploy checklist (next actions, in order)

1. GCP node or WSL: CREATE DATABASE opportunity_radar OWNER appuser; then run migrations/001_init.sql (commands in README).
2. Browser: create Brave, Groq, Gemini keys + Gmail app password.
3. WSL: .env, `python -m src.main` local run, `pytest`.
4. WSL: git init, push (private repo), add Actions secrets, manual workflow_dispatch run.
5. Verify one real 04:30 WAT cron delivery, then tune config/profile.md and query templates from the first week of digests.

## Gotchas log

- CREATE DATABASE can't run inside the migration transaction; it's a manual step.
- GitHub cron can lag 5-15 min; schedule is 03:30 UTC to land before 5am WAT.
- GitHub disables cron after 60 days without pushes.
- DDG result links are wrapped in a uddg= redirect; client unwraps them.
- Gmail SMTP needs an app password (2FA required), not the account password.

# Progress

Authoritative tracker lives in the Claude skill file
(`references/progress-tracker.md`). This file is a lightweight mirror
for anyone browsing the repo directly.

- [x] Phase 0 — Foundations
- [x] Phase 1 — Source discovery
- [x] Phase 2 — Extraction & normalization
- [x] Phase 3 — Scoring & summarization
- [x] Phase 4 — Dedup
- [x] Phase 5 — Email digest
- [x] Phase 6 — Circuit breaker
- [x] Phase 7 — Scheduling & E2E test
- [ ] Phase 8 — Stretch

## 2026-10-12: reactivation
- Postgres on GCP retired (billing removed). State moved to data/radar.db (SQLite), committed by the workflow.
- Gemini default moved to gemini-2.5-flash (2.0 Flash retired).
- New `devfund` category: foreign-donor / implementing-firm roles on Nigeria programmes, 3 reserved digest slots, optional ReliefWeb jobs feed.
- Brave optional: empty key or 401/402/403 falls through to DuckDuckGo.

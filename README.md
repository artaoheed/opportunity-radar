# opportunity-radar

Zero-cost daily agent that discovers tech opportunities (job openings,
early-stage startup roles, conference CFPs) that don't usually hit
mainstream job boards, scores them against a career profile, and emails
a top-8 digest by 5am WAT.

**Hard constraint:** $0/month. Every external dependency runs on a free
tier, with a circuit breaker preventing silent quota overages.

## Status

See `docs/progress.md` for current phase status (mirrors the tracker in
the Claude skill file).

## Architecture

- **Discovery:** Brave Search API (primary), DuckDuckGo scrape (fallback)
- **Scoring:** Groq / Llama 3.3 70B (primary), Gemini 2.0 Flash (fallback)
- **Dedup:** Postgres (`seen_opportunities` table, reuses existing
  baseline-LLMOps instance on GCP k3s)
- **Delivery:** Gmail SMTP
- **Scheduler:** GitHub Actions cron, ~4:30am WAT

## Local setup

1. `cp .env.example .env` and fill in real values (never commit `.env`)
2. `python -m venv venv && source venv/bin/activate`
3. `pip install -r requirements.txt`
4. Apply the DB migration: see `db/migrations/001_create_seen_opportunities.sql`

## Repo layout

```
src/
├── discovery/        # Phase 1 — Brave Search + DDG fallback
├── extraction/        # Phase 2 — normalize raw results into candidates
├── scoring/            # Phase 3 — Groq/Gemini relevance scoring
├── dedup/                # Phase 4 — seen_opportunities checks
├── email/                 # Phase 5 — digest formatting + SMTP send
└── circuit_breaker/        # Phase 6 — quota tracking and hard-stop
db/
└── migrations/         # SQL schema migrations
.github/workflows/       # Phase 7 — cron workflow
```

# opportunity-radar

Zero-cost daily agent. Finds tech opportunities (jobs, early-stage startup
roles, conference CFPs) from sources that skip mainstream boards, scores them
against `config/profile.md` with an LLM, and emails a top-8 digest by 5am WAT.

Hard constraint: $0/month. Brave Search free tier + DuckDuckGo fallback,
Groq free tier + Gemini free tier fallback, existing Postgres for dedup,
GitHub Actions cron for scheduling, Gmail SMTP for delivery. A circuit
breaker (`src/circuit_breaker.py`) refuses any call that would push a
provider past 90% of its free quota.

## Architecture

```
GitHub Actions cron (03:30 UTC / 04:30 WAT)
  └─ src/main.py
       ├─ queries.todays_queries()      9 queries/day, rotated templates
       ├─ brave.search()                → duckduckgo.search() fallback
       ├─ extract.build_candidates()    normalize URLs, drop board noise
       ├─ db.filter_unseen()            Postgres dedup BEFORE scoring
       ├─ score.score_all()             Groq → Gemini fallback, batched
       ├─ digest + mailer               top 8 ≥ MIN_SCORE via Gmail SMTP
       └─ db.record_candidates()        everything scored, sent flagged
```

Every external call goes through `QuotaGuard` backed by the `api_usage`
table. Brave is counted monthly, Groq and Gemini daily. At the stop line the
run degrades (Brave→DDG, Groq→Gemini) or stops cleanly with a "skipped —
near quota" email. It never falls through to a paid tier.

## One-time setup

### 1. Database (GCP node, or WSL via psql to the NodePort)

```bash
# connected to the existing instance, any db:
psql -h <NODE_EXTERNAL_IP> -p 30432 -U appuser -d appdb \
  -c "CREATE DATABASE opportunity_radar OWNER appuser;"

# then the schema:
psql -h <NODE_EXTERNAL_IP> -p 30432 -U appuser -d opportunity_radar \
  -f migrations/001_init.sql
```

### 2. API keys (browser)

- Brave Search API key: api.search.brave.com (Free plan)
- Groq API key: console.groq.com
- Gemini API key: aistudio.google.com (free tier)
- Gmail app password: Google Account → Security → 2-Step Verification →
  App passwords (regular password won't work over SMTP)

### 3. Local test run (WSL, repo root)

```bash
pip install -r requirements.txt
cp .env.example .env       # fill in real values; .env is gitignored
set -a; source .env; set +a
python -m src.main
pytest                     # offline smoke tests
```

### 4. GitHub (WSL)

```bash
git init && git add -A && git commit -m "opportunity-radar MVP"
gh repo create opportunity-radar --private --source . --push
```

Then add every variable from `.env.example` as an Actions secret
(repo → Settings → Secrets and variables → Actions). Trigger a manual run
from the Actions tab (`workflow_dispatch`) before trusting the cron.

## Failure behaviour

- Postgres unreachable / bad secrets / unparseable LLM output / SMTP failure
  → exit 1 → GitHub emails you a workflow-failure notice.
- Both LLM providers near quota → clean stop + "skipped" email → exit 0.
- Email send failure → candidates are NOT recorded, so they retry tomorrow.
- GitHub disables cron on repos with no pushes for 60 days: any commit
  (even a README touch) resets the clock.

## Known sharp edges

- The Postgres NodePort is internet-exposed (GitHub runners have no stable
  IPs). Mitigation: strong password, separate database, and the `appuser`
  role only. Consider `pg_hba.conf` tightening or Tailscale later.
- DuckDuckGo scraping is best-effort: markup changes or CAPTCHAs return
  empty results silently. Brave is the real source; DDG only cushions
  quota exhaustion.
- Groq free-tier ceilings shift; `GROQ_DAILY_LIMIT` is conservative at
  1000/day. A normal day uses 1-3 calls, so this is far from binding.

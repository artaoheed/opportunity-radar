# opportunity-radar

Zero-cost daily agent. Finds opportunities (tech jobs, early-stage startup
roles, conference CFPs, and foreign-donor-funded Nigeria programme roles) from sources that skip mainstream boards, scores them
against `config/profile.md` with an LLM, and emails a top-8 digest by 5am WAT.

Hard constraint: $0/month. Brave Search free tier + DuckDuckGo fallback,
Groq free tier + Gemini free tier fallback, a SQLite file committed back to the repo for dedup,
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
       ├─ db.filter_unseen()            SQLite dedup BEFORE scoring
       ├─ score.score_all()             Groq → Gemini fallback, batched
       ├─ digest + mailer               top 8 ≥ MIN_SCORE via Gmail SMTP
       └─ db.record_candidates()        everything scored, sent flagged
```

Every external call goes through `QuotaGuard` backed by the `api_usage`
table. Brave is counted monthly, Groq and Gemini daily. At the stop line the
run degrades (Brave→DDG, Groq→Gemini) or stops cleanly with a "skipped —
near quota" email. It never falls through to a paid tier.

## One-time setup

### 1. State

None to set up. `data/radar.db` (SQLite) is created on the first run and the
workflow commits it back after every run. It stores only URL hashes, scores
and quota counters, no titles or links. That commit also keeps the repo
active, so GitHub never auto-disables the schedule.

### 2. API keys (browser)

- Brave Search API key: api.search.brave.com (optional; no free tier since
  Feb 2026, so leave empty to run on DuckDuckGo only)
- ReliefWeb appname (optional): pre-approved appname for the jobs API,
  apidoc.reliefweb.int. Adds a structured Nigeria jobs feed to `devfund`.
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

- Bad secrets / unparseable LLM output / SMTP failure
  → exit 1 → GitHub emails you a workflow-failure notice.
- Both LLM providers near quota → clean stop + "skipped" email → exit 0.
- Email send failure → candidates are NOT recorded, so they retry tomorrow.
- Brave 401/402/403 (bad key or lapsed plan) → DuckDuckGo for the rest of
  the run, no crash.
- State is committed even when the run fails, so quota counters persist.

## Known sharp edges

- DuckDuckGo scraping is best-effort: markup changes or CAPTCHAs return
  empty results silently. Brave and ReliefWeb are the reliable sources.
- Groq free-tier ceilings shift; `GROQ_DAILY_LIMIT` is conservative at
  1000/day. A normal day uses 1-3 calls, so this is far from binding.

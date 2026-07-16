-- Run on the GCP node (or from WSL via psql to <NODE_IP>:30432).
-- Step 1 (once, connected to any database, e.g. appdb):
--   CREATE DATABASE opportunity_radar OWNER appuser;
-- CREATE DATABASE cannot run inside a transaction/migration, hence manual.
--
-- Step 2 (this file, connected to opportunity_radar):
--   psql -h <NODE_IP> -p 30432 -U appuser -d opportunity_radar -f migrations/001_init.sql

BEGIN;

CREATE TABLE IF NOT EXISTS seen_opportunities (
    url_hash    TEXT PRIMARY KEY,          -- sha256 of normalized URL
    url         TEXT NOT NULL,
    title       TEXT NOT NULL,
    category    TEXT NOT NULL,             -- job | startup | cfp
    score       INTEGER,
    sent        BOOLEAN NOT NULL DEFAULT FALSE,
    first_seen  DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE INDEX IF NOT EXISTS idx_seen_first_seen ON seen_opportunities (first_seen);

CREATE TABLE IF NOT EXISTS api_usage (
    provider    TEXT NOT NULL,             -- brave | groq | gemini
    period_key  TEXT NOT NULL,             -- YYYY-MM (brave) or YYYY-MM-DD
    count       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (provider, period_key)
);

COMMIT;

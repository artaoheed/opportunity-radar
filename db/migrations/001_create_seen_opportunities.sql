-- Phase 0: dedup table for opportunity-radar
-- Applied against the existing Postgres instance already running
-- baseline-LLMOps on the GCP k3s cluster. New table only, no new DB service.

CREATE TABLE IF NOT EXISTS seen_opportunities (
    id SERIAL PRIMARY KEY,
    url_hash TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('job', 'startup_role', 'cfp')),
    source_domain TEXT,
    first_seen DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE INDEX IF NOT EXISTS idx_seen_opportunities_url_hash
    ON seen_opportunities (url_hash);

-- Phase 6 will add a quota_usage table for the circuit breaker.
-- Not created here to keep Phase 0 scoped to dedup only.

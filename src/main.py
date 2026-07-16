"""Orchestrator. Run with `python -m src.main` from the repo root.

Flow: quota pre-check -> search (Brave, DDG fallback) -> normalize ->
dedup against Postgres -> LLM score -> top 8 -> email -> record seen.

Exit codes: 0 success (including 'nothing new today'), 1 hard failure
(GitHub Actions marks the run failed and emails a workflow-failure notice)."""

import logging
import sys

import requests

from . import db, digest, mailer, settings
from .circuit_breaker import QuotaExceeded, QuotaGuard
from .extract import build_candidates
from .score import score_all
from .search import brave, duckduckgo, queries

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("main")


def run() -> int:
    missing = settings.validate()
    if missing:
        log.error("Missing required settings: %s", ", ".join(missing))
        return 1

    try:
        conn = db.connect()
    except Exception as exc:
        log.error("Cannot reach Postgres at %s:%s — %s", settings.PG_HOST, settings.PG_PORT, exc)
        return 1

    guard = QuotaGuard(conn)
    log.info("Quota at start: %s", guard.status_line())

    # --- Phase 1: search ---
    raw: list[tuple[str, dict]] = []
    brave_blocked = False
    for category, query in queries.todays_queries():
        results: list[dict] = []
        if not brave_blocked:
            try:
                results = brave.search(guard, query)
            except QuotaExceeded as exc:
                log.warning("Brave near quota (%s); using DuckDuckGo for the rest", exc)
                brave_blocked = True
            except requests.RequestException as exc:
                log.warning("Brave failed on %r (%s); trying DuckDuckGo", query, exc)
        if not results:
            results = duckduckgo.search(query, settings.RESULTS_PER_QUERY)
        log.info("[%s] %r -> %d results", category, query, len(results))
        raw.extend((category, r) for r in results)

    # --- Phase 2: extract/normalize ---
    candidates = build_candidates(raw)
    log.info("%d raw results -> %d unique candidates", len(raw), len(candidates))

    # --- Phase 4 (first half): dedup BEFORE scoring, to save LLM quota ---
    unseen = db.filter_unseen(conn, [c.url_hash for c in candidates])
    candidates = [c for c in candidates if c.url_hash in unseen]
    log.info("%d candidates are new (not in seen_opportunities)", len(candidates))

    if not candidates:
        log.info("Nothing new today.")
        if settings.SEND_EMPTY_DIGEST:
            mailer.send(
                "Opportunity Radar — nothing new today",
                "No new opportunities found today.\n\nQuota: " + guard.status_line(),
                f"<p>No new opportunities found today.</p><p style='color:#999;font-size:11px'>Quota: {guard.status_line()}</p>",
            )
        conn.close()
        return 0

    # --- Phase 3: score ---
    try:
        score_all(guard, candidates)
    except QuotaExceeded as exc:
        # Both LLM providers at the stop line: abort cleanly, tell me why.
        log.error("Run stopped by circuit breaker: %s", exc)
        mailer.send(
            "Opportunity Radar — skipped (near quota)",
            f"Run stopped: {exc}\nQuota: {guard.status_line()}",
            f"<p>Run stopped: {exc}</p><p>Quota: {guard.status_line()}</p>",
        )
        conn.close()
        return 0  # intentional stop, not a failure
    except RuntimeError as exc:
        log.error("Scoring failed: %s", exc)
        conn.close()
        return 1

    # --- Phase 5: digest ---
    ranked = sorted(candidates, key=lambda c: c.score or 0, reverse=True)
    top = [c for c in ranked if (c.score or 0) >= settings.MIN_SCORE][: settings.DIGEST_SIZE]

    if not top:
        log.info("Everything scored below MIN_SCORE=%d.", settings.MIN_SCORE)
        db.record_candidates(conn, candidates, sent_hashes=set())
        conn.close()
        return 0

    quota_line = guard.status_line()
    try:
        mailer.send(
            digest.subject(top),
            digest.plaintext(top, quota_line),
            digest.html_body(top, quota_line),
        )
    except Exception as exc:
        log.error("Email send failed: %s", exc)
        conn.close()
        return 1  # do NOT record candidates: unsent items must retry tomorrow

    # --- Phase 4 (second half): record everything scored, mark sent ones ---
    db.record_candidates(conn, candidates, sent_hashes={c.url_hash for c in top})
    log.info("Recorded %d candidates (%d sent). Quota at end: %s",
             len(candidates), len(top), guard.status_line())
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(run())

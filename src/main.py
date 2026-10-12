"""Orchestrator. Run with `python -m src.main` from the repo root.

Flow: quota pre-check -> search (Brave, DDG fallback) + ReliefWeb ->
normalize -> dedup against SQLite -> LLM score -> top 8 (devfund slots
reserved) -> email -> record seen. The workflow commits data/radar.db after.

Exit codes: 0 success (including 'nothing new today'), 1 hard failure
(GitHub Actions marks the run failed and emails a workflow-failure notice)."""

import logging
import sys

import requests

from . import db, digest, mailer, settings
from .circuit_breaker import QuotaExceeded, QuotaGuard
from .extract import build_candidates
from .score import score_all
from .search import brave, duckduckgo, queries, reliefweb

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
        log.error("Cannot open state DB at %s: %s", settings.DB_PATH, exc)
        return 1
    pruned = db.prune(conn)
    if pruned:
        log.info("Pruned %d stale dedup rows", pruned)

    guard = QuotaGuard(conn)
    log.info("Quota at start: %s", guard.status_line())

    # --- Phase 1: search ---
    raw: list[tuple[str, dict]] = []
    brave_blocked = not settings.BRAVE_API_KEY
    if brave_blocked:
        log.info("No BRAVE_API_KEY: using DuckDuckGo for all queries")
    for category, query in queries.todays_queries():
        results: list[dict] = []
        if not brave_blocked:
            try:
                results = brave.search(guard, query)
            except QuotaExceeded as exc:
                log.warning("Brave near quota (%s); using DuckDuckGo for the rest", exc)
                brave_blocked = True
            except requests.HTTPError as exc:
                code = exc.response.status_code if exc.response is not None else None
                if code in (401, 402, 403):
                    # Bad key or lapsed plan: stop hammering Brave this run.
                    log.warning("Brave returned %s (key invalid or plan lapsed); "
                                "using DuckDuckGo for the rest", code)
                    brave_blocked = True
                else:
                    log.warning("Brave failed on %r (%s); trying DuckDuckGo", query, exc)
            except requests.RequestException as exc:
                log.warning("Brave failed on %r (%s); trying DuckDuckGo", query, exc)
        if not results:
            results = duckduckgo.search(query, settings.RESULTS_PER_QUERY)
        log.info("[%s] %r -> %d results", category, query, len(results))
        raw.extend((category, r) for r in results)

    raw.extend(("devfund", r) for r in reliefweb.search())

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
                "Opportunity Radar: nothing new today",
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
            "Opportunity Radar: skipped (near quota)",
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
    top = digest.select_top(candidates)

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

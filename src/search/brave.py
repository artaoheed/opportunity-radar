"""Brave Search API client. Free tier: ~2,000 queries/month, 1 req/sec.

Raises QuotaExceeded (via the guard) before a call that would breach the
stop line; caller falls back to DuckDuckGo."""

import logging
import time

import requests

from .. import settings
from ..circuit_breaker import QuotaGuard

log = logging.getLogger(__name__)


def search(guard: QuotaGuard, query: str) -> list[dict]:
    """Return [{'title', 'url', 'snippet'}, ...]. Raises QuotaExceeded or
    requests exceptions; caller handles both."""
    guard.check("brave")
    guard.record("brave")  # count the attempt, not the success: a failed
    # call may still burn quota on the provider side.

    resp = requests.get(
        settings.BRAVE_ENDPOINT,
        params={
            "q": query,
            "count": settings.RESULTS_PER_QUERY,
            "freshness": "pw",  # past week: opportunities go stale fast
        },
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": settings.BRAVE_API_KEY,
        },
        timeout=20,
    )
    if resp.status_code == 429:
        # Provider-side rate limit. Respect it: brief pause, one retry.
        log.warning("Brave 429 on %r, retrying once after 2s", query)
        time.sleep(2)
        resp = requests.get(
            settings.BRAVE_ENDPOINT,
            params={"q": query, "count": settings.RESULTS_PER_QUERY, "freshness": "pw"},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": settings.BRAVE_API_KEY,
            },
            timeout=20,
        )
    resp.raise_for_status()

    results = resp.json().get("web", {}).get("results", [])
    out = []
    for r in results:
        url = r.get("url", "")
        title = r.get("title", "")
        if url and title:
            out.append({"title": title, "url": url, "snippet": r.get("description", "")})
    # Free tier is 1 req/sec: pace ourselves between queries.
    time.sleep(1.1)
    return out

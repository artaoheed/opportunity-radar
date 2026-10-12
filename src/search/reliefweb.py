"""ReliefWeb jobs API: structured feed of donor/UN/NGO-funded roles in Nigeria.

Optional. Runs only when RELIEFWEB_APPNAME is set (an appname pre-approved by
ReliefWeb, required since November 2025). Every failure is non-fatal: the
run continues with search results only. No quota guard needed: one call per
run, far under any limit."""

import logging

import requests

from .. import settings

log = logging.getLogger(__name__)


def search() -> list[dict]:
    """Return [{'title', 'url', 'snippet'}, ...] for recent Nigeria jobs."""
    if not settings.RELIEFWEB_APPNAME:
        return []
    body = {
        "limit": settings.RELIEFWEB_LIMIT,
        "filter": {"field": "country.name", "value": "Nigeria"},
        "sort": ["date.created:desc"],
        "fields": {"include": ["title", "url", "source.name", "date.closing"]},
    }
    try:
        resp = requests.post(
            settings.RELIEFWEB_ENDPOINT,
            params={"appname": settings.RELIEFWEB_APPNAME},
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except (requests.RequestException, ValueError) as exc:
        log.warning("ReliefWeb fetch failed: %s", exc)
        return []

    out = []
    for item in data:
        f = item.get("fields", {})
        title, url = f.get("title"), f.get("url")
        if not (title and url):
            continue
        sources = ", ".join(s.get("name", "") for s in f.get("source", []) if s.get("name"))
        closing = (f.get("date") or {}).get("closing", "")[:10]
        snippet = f"Organisation: {sources}." + (f" Closes {closing}." if closing else "")
        out.append({"title": title, "url": url, "snippet": snippet})
    log.info("ReliefWeb returned %d Nigeria jobs", len(out))
    return out

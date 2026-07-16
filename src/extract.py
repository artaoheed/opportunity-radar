"""Turn raw search results into normalized Candidate objects with stable
URL hashes for dedup."""

import hashlib
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "ref", "src",
}

# Domains that are pure aggregation noise: drop them outright.
BLOCKED_DOMAINS = {
    "linkedin.com", "www.linkedin.com",   # mainstream board, defeats the point
    "indeed.com", "www.indeed.com",
    "glassdoor.com", "www.glassdoor.com",
}


@dataclass
class Candidate:
    title: str
    url: str
    snippet: str
    category: str
    url_hash: str = field(default="")
    score: int | None = None
    rationale: str = ""

    def __post_init__(self):
        self.url = normalize_url(self.url)
        self.url_hash = hashlib.sha256(self.url.encode()).hexdigest()


def normalize_url(url: str) -> str:
    """Lowercase host, strip fragments, tracking params, and trailing slash,
    so the same posting found twice hashes identically."""
    p = urlparse(url.strip())
    query = urlencode(
        [(k, v) for k, v in parse_qsl(p.query) if k.lower() not in TRACKING_PARAMS]
    )
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", query, ""))


def build_candidates(raw: list[tuple[str, dict]]) -> list[Candidate]:
    """raw: [(category, {'title','url','snippet'}), ...]. Dedupes within the
    run and drops blocked domains."""
    seen: set[str] = set()
    out: list[Candidate] = []
    for category, r in raw:
        c = Candidate(
            title=r["title"][:300],
            url=r["url"],
            snippet=r.get("snippet", "")[:500],
            category=category,
        )
        host = urlparse(c.url).netloc
        if host in BLOCKED_DOMAINS:
            continue
        if c.url_hash in seen:
            continue
        seen.add(c.url_hash)
        out.append(c)
    return out

"""DuckDuckGo HTML scrape fallback. No API key, no quota, but brittle:
DDG can change markup or throw a CAPTCHA. Treat every failure as
non-fatal and return an empty list; the run continues with whatever the
other queries produced."""

import logging
import time
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

ENDPOINT = "https://html.duckduckgo.com/html/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0"
}


def _clean_href(href: str) -> str:
    """DDG wraps result links in a redirect: //duckduckgo.com/l/?uddg=<real>."""
    if "uddg=" in href:
        qs = parse_qs(urlparse(href).query)
        if qs.get("uddg"):
            return unquote(qs["uddg"][0])
    return href


def search(query: str, max_results: int = 10) -> list[dict]:
    try:
        resp = requests.get(ENDPOINT, params={"q": query}, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.warning("DuckDuckGo fallback failed for %r: %s", query, exc)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    out = []
    for result in soup.select("div.result"):
        a = result.select_one("a.result__a")
        if not a or not a.get("href"):
            continue
        url = _clean_href(a["href"])
        if not url.startswith("http"):
            continue
        snippet_el = result.select_one("a.result__snippet, div.result__snippet")
        out.append({
            "title": a.get_text(strip=True),
            "url": url,
            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
        })
        if len(out) >= max_results:
            break
    time.sleep(2)  # be polite: this is scraping, not an API
    return out

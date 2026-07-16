"""Offline smoke tests: URL normalization, dedup hashing, query rotation,
LLM output parsing. Run with `pytest` from the repo root. No network, no DB."""

from src.extract import Candidate, build_candidates, normalize_url
from src.score import _strip_fences
from src.search.queries import TEMPLATES, todays_queries


def test_normalize_strips_tracking_and_fragment():
    a = normalize_url("https://Boards.Greenhouse.io/acme/jobs/123?utm_source=x&gh_jid=9#apply")
    b = normalize_url("https://boards.greenhouse.io/acme/jobs/123/?gh_jid=9")
    assert a == b


def test_same_url_same_hash():
    c1 = Candidate("A", "https://example.com/job?utm_campaign=z", "", "job")
    c2 = Candidate("B", "https://EXAMPLE.com/job/", "", "job")
    assert c1.url_hash == c2.url_hash


def test_build_candidates_dedupes_and_blocks():
    raw = [
        ("job", {"title": "DevOps Eng", "url": "https://example.com/a", "snippet": ""}),
        ("job", {"title": "DevOps Eng dup", "url": "https://example.com/a/", "snippet": ""}),
        ("job", {"title": "Board noise", "url": "https://www.linkedin.com/jobs/x", "snippet": ""}),
    ]
    out = build_candidates(raw)
    assert len(out) == 1
    assert out[0].url == "https://example.com/a"


def test_todays_queries_shape():
    qs = todays_queries()
    assert len(qs) == 3 * 3  # QUERIES_PER_CATEGORY default 3 x 3 categories
    assert {cat for cat, _ in qs} == set(TEMPLATES.keys())


def test_strip_fences_variants():
    assert _strip_fences('```json\n[{"i":0}]\n```') == '[{"i":0}]'
    assert _strip_fences('Here you go:\n[{"i":0,"score":5}] hope that helps') == '[{"i":0,"score":5}]'
    assert _strip_fences('[{"i":1}]') == '[{"i":1}]'

"""Offline smoke tests: URL normalization, dedup hashing, query rotation,
LLM output parsing, SQLite store, digest slots. Run with `pytest` from the
repo root. No network."""

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
    assert len(qs) == 3 * len(TEMPLATES)  # QUERIES_PER_CATEGORY default 3
    assert {cat for cat, _ in qs} == set(TEMPLATES.keys())


def test_strip_fences_variants():
    assert _strip_fences('```json\n[{"i":0}]\n```') == '[{"i":0}]'
    assert _strip_fences('Here you go:\n[{"i":0,"score":5}] hope that helps') == '[{"i":0,"score":5}]'
    assert _strip_fences('[{"i":1}]') == '[{"i":1}]'


def test_sqlite_dedup_and_usage(tmp_path):
    from src import db

    conn = db.connect(tmp_path / "radar.db")
    a = Candidate("A", "https://example.com/a", "", "job")
    b = Candidate("B", "https://example.com/b", "", "devfund")
    a.score, b.score = 70, 90
    assert db.filter_unseen(conn, [a.url_hash, b.url_hash]) == {a.url_hash, b.url_hash}
    db.record_candidates(conn, [a, b], sent_hashes={b.url_hash})
    assert db.filter_unseen(conn, [a.url_hash, b.url_hash]) == set()
    db.record_candidates(conn, [a], sent_hashes=set())  # idempotent

    db.increment_usage(conn, "groq", "2026-10-12")
    db.increment_usage(conn, "groq", "2026-10-12", by=2)
    assert db.get_usage(conn, "groq", "2026-10-12") == 3
    assert db.get_usage(conn, "gemini", "2026-10-12") == 0
    db.prune(conn)  # must not error on fresh rows
    assert db.filter_unseen(conn, [a.url_hash]) == set()


def test_select_top_reserves_devfund_slots(monkeypatch):
    from src import digest, settings

    monkeypatch.setattr(settings, "DIGEST_SIZE", 4)
    monkeypatch.setattr(settings, "DEVFUND_SLOTS", 2)
    monkeypatch.setattr(settings, "MIN_SCORE", 40)

    def mk(n, cat, score):
        c = Candidate(f"t{n}", f"https://example.com/{n}", "", cat)
        c.score = score
        return c

    jobs = [mk(i, "job", 95 - i) for i in range(5)]           # 95..91
    dev = [mk(10, "devfund", 60), mk(11, "devfund", 50), mk(12, "devfund", 30)]
    top = digest.select_top(jobs + dev)
    assert len(top) == 4
    assert sum(c.category == "devfund" for c in top) == 2     # reserved, 30 excluded
    assert [c.score for c in top] == sorted((c.score for c in top), reverse=True)

    # No devfund above MIN_SCORE: slots fall back to other categories.
    top = digest.select_top(jobs + [dev[2]])
    assert len(top) == 4 and all(c.category == "job" for c in top)

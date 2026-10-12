"""SQLite state store: dedup table and API usage counters.

The file lives at data/radar.db and the GitHub Actions workflow commits it
back to the repo after every run. That keeps state between runs with no
hosted database, and the commit doubles as repo activity so GitHub never
auto-disables the scheduled workflow.

Only url_hash, category, score, sent and first_seen are stored. No titles or
URLs, because the repo is public."""

import logging
import sqlite3
from pathlib import Path

from . import settings

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_opportunities (
    url_hash    TEXT PRIMARY KEY,
    category    TEXT NOT NULL,
    score       INTEGER,
    sent        INTEGER NOT NULL DEFAULT 0,
    first_seen  TEXT NOT NULL DEFAULT (date('now'))
);
CREATE INDEX IF NOT EXISTS idx_seen_first_seen ON seen_opportunities (first_seen);

CREATE TABLE IF NOT EXISTS api_usage (
    provider    TEXT NOT NULL,
    period_key  TEXT NOT NULL,
    count       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (provider, period_key)
);
"""

# Drop dedup rows older than this so the committed file stays small.
# A posting not seen for 120 days is effectively new if it reappears.
RETENTION_DAYS = 120


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or settings.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def filter_unseen(conn: sqlite3.Connection, url_hashes: list[str]) -> set[str]:
    """Return the subset of url_hashes NOT already in seen_opportunities."""
    if not url_hashes:
        return set()
    seen: set[str] = set()
    # SQLite caps bound parameters per statement; chunk to stay well under it.
    for start in range(0, len(url_hashes), 500):
        chunk = url_hashes[start:start + 500]
        marks = ",".join("?" * len(chunk))
        rows = conn.execute(
            f"SELECT url_hash FROM seen_opportunities WHERE url_hash IN ({marks})",
            chunk,
        ).fetchall()
        seen.update(r[0] for r in rows)
    return set(url_hashes) - seen


def record_candidates(conn: sqlite3.Connection, candidates, sent_hashes: set[str]) -> None:
    """Insert every scored candidate so low scorers aren't re-scored.
    `sent` marks the ones that made the digest."""
    conn.executemany(
        """
        INSERT OR IGNORE INTO seen_opportunities (url_hash, category, score, sent)
        VALUES (?, ?, ?, ?)
        """,
        [(c.url_hash, c.category, c.score, int(c.url_hash in sent_hashes))
         for c in candidates],
    )
    conn.commit()


def prune(conn: sqlite3.Connection) -> int:
    """Delete stale dedup rows and old usage counters. Returns rows removed."""
    cur = conn.execute(
        "DELETE FROM seen_opportunities WHERE first_seen < date('now', ?)",
        (f"-{RETENTION_DAYS} days",),
    )
    removed = cur.rowcount
    # Usage keys are YYYY-MM or YYYY-MM-DD; anything before last month is dead.
    conn.execute(
        "DELETE FROM api_usage WHERE substr(period_key, 1, 7) < strftime('%Y-%m', 'now', '-1 month')"
    )
    conn.commit()
    return removed


# --- quota counters ---

def get_usage(conn: sqlite3.Connection, provider: str, period_key: str) -> int:
    row = conn.execute(
        "SELECT count FROM api_usage WHERE provider = ? AND period_key = ?",
        (provider, period_key),
    ).fetchone()
    return row[0] if row else 0


def increment_usage(conn: sqlite3.Connection, provider: str, period_key: str, by: int = 1) -> None:
    conn.execute(
        """
        INSERT INTO api_usage (provider, period_key, count) VALUES (?, ?, ?)
        ON CONFLICT (provider, period_key) DO UPDATE SET count = count + excluded.count
        """,
        (provider, period_key, by),
    )
    conn.commit()

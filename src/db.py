"""Postgres access: dedup store and API usage counters.

Uses the existing baseline-LLMOps Postgres instance (NodePort 30432 on the
GCP node), separate database `opportunity_radar`. psycopg v3, plain SQL,
no ORM."""

import logging

import psycopg

from . import settings

log = logging.getLogger(__name__)


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=settings.PG_HOST,
        port=settings.PG_PORT,
        user=settings.PG_USER,
        password=settings.PG_PASSWORD,
        dbname=settings.PG_DATABASE,
        connect_timeout=15,
        autocommit=False,
    )


def filter_unseen(conn: psycopg.Connection, url_hashes: list[str]) -> set[str]:
    """Return the subset of url_hashes NOT already in seen_opportunities."""
    if not url_hashes:
        return set()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT url_hash FROM seen_opportunities WHERE url_hash = ANY(%s)",
            (url_hashes,),
        )
        seen = {row[0] for row in cur.fetchall()}
    return set(url_hashes) - seen


def record_candidates(conn: psycopg.Connection, candidates, sent_hashes: set[str]) -> None:
    """Insert every scored candidate so low scorers aren't re-scored daily.
    `sent` marks the ones that made the digest."""
    with conn.cursor() as cur:
        for c in candidates:
            cur.execute(
                """
                INSERT INTO seen_opportunities
                    (url_hash, url, title, category, score, sent)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (url_hash) DO NOTHING
                """,
                (c.url_hash, c.url, c.title, c.category, c.score,
                 c.url_hash in sent_hashes),
            )
    conn.commit()


# --- quota counters ---

def get_usage(conn: psycopg.Connection, provider: str, period_key: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count FROM api_usage WHERE provider = %s AND period_key = %s",
            (provider, period_key),
        )
        row = cur.fetchone()
    return row[0] if row else 0


def increment_usage(conn: psycopg.Connection, provider: str, period_key: str, by: int = 1) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO api_usage (provider, period_key, count)
            VALUES (%s, %s, %s)
            ON CONFLICT (provider, period_key)
            DO UPDATE SET count = api_usage.count + EXCLUDED.count
            """,
            (provider, period_key, by),
        )
    conn.commit()

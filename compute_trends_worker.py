#!/usr/bin/env python3
"""Compute term/topic trends into Postgres (Phase 8)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import List

import psycopg
from dotenv import load_dotenv

from watchfuleye.analytics.trends import compute_term_trends
from watchfuleye.storage.postgres_schema import ensure_postgres_schema


def _fetch_texts(pg_dsn: str, *, start: datetime, end: datetime, limit: int = 20000) -> List[str]:
    with psycopg.connect(pg_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(title,'') || ' ' || COALESCE(description,'') || ' ' || COALESCE(excerpt,'')
                FROM articles
                WHERE bucket = 'main'
                  AND trust_score >= 0.55
                  AND created_at >= %s
                  AND created_at < %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (start, end, limit),
            )
            return [r[0] for r in cur.fetchall() if r and r[0]]


def _store_term_trends(pg_dsn: str, *, window_start: datetime, window_end: datetime, trends) -> int:
    if not trends:
        return 0
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            n = 0
            for t in trends:
                cur.execute(
                    """
                    INSERT INTO term_trends (term, window_start, window_end, count, z_score)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (term, window_start, window_end) DO UPDATE SET
                      count = EXCLUDED.count,
                      z_score = EXCLUDED.z_score,
                      created_at = now()
                    """,
                    (t.term, window_start, window_end, int(t.count), float(t.z_score)),
                )
                n += 1
    return n


def _store_topic_trends(pg_dsn: str, *, window_start: datetime, window_end: datetime, baseline_start: datetime, baseline_end: datetime) -> int:
    # Use brief_topic from analyses JSON as "topics"
    with psycopg.connect(pg_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(raw_response_json->>'brief_topic','unknown') AS topic, COUNT(*)
                FROM analyses
                WHERE created_at >= %s AND created_at < %s
                GROUP BY 1
                """,
                (window_start, window_end),
            )
            recent = {r[0]: int(r[1] or 0) for r in cur.fetchall() if r and r[0]}
            cur.execute(
                """
                SELECT COALESCE(raw_response_json->>'brief_topic','unknown') AS topic, COUNT(*)
                FROM analyses
                WHERE created_at >= %s AND created_at < %s
                GROUP BY 1
                """,
                (baseline_start, baseline_end),
            )
            baseline = {r[0]: int(r[1] or 0) for r in cur.fetchall() if r and r[0]}

    baseline_hours = max(1.0, (baseline_end - baseline_start).total_seconds() / 3600.0)
    recent_hours = max(1.0, (window_end - window_start).total_seconds() / 3600.0)

    # Poisson-ish z-score
    def z(obs: int, base_count: int) -> float:
        rate = base_count / baseline_hours
        expected = rate * recent_hours
        return (obs - expected) / ((expected + 1.0) ** 0.5)

    items = []
    for topic, obs in recent.items():
        items.append((topic, obs, float(z(obs, baseline.get(topic, 0)))))

    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            n = 0
            for topic, count, z_score in items:
                cur.execute(
                    """
                    INSERT INTO topic_trends (topic, window_start, window_end, count, z_score)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (topic, window_start, window_end) DO UPDATE SET
                      count = EXCLUDED.count,
                      z_score = EXCLUDED.z_score,
                      created_at = now()
                    """,
                    (topic, window_start, window_end, int(count), float(z_score)),
                )
                n += 1
    return n


def main() -> int:
    load_dotenv()
    pg_dsn = os.environ.get("PG_DSN", "dbname=watchfuleye user=watchful password=watchfulpass host=localhost port=5432")
    ensure_postgres_schema(pg_dsn)

    now = datetime.now(timezone.utc)
    window_end = now
    window_start = now - timedelta(hours=24)
    baseline_end = window_start
    baseline_start = now - timedelta(days=7)

    recent_texts = _fetch_texts(pg_dsn, start=window_start, end=window_end)
    baseline_texts = _fetch_texts(pg_dsn, start=baseline_start, end=baseline_end)

    trends = compute_term_trends(
        recent_texts=recent_texts,
        baseline_texts=baseline_texts,
        recent_hours=24.0,
        baseline_hours=max(1.0, (baseline_end - baseline_start).total_seconds() / 3600.0),
        min_count=6,
        top_k=200,
    )

    n_terms = _store_term_trends(pg_dsn, window_start=window_start, window_end=window_end, trends=trends)
    n_topics = _store_topic_trends(
        pg_dsn,
        window_start=window_start,
        window_end=window_end,
        baseline_start=baseline_start,
        baseline_end=baseline_end,
    )

    print(f"[trends] stored term_trends={n_terms} topic_trends={n_topics}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



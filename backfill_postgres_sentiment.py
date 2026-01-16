#!/usr/bin/env python3
"""Backfill Postgres article market-sentiment fields.

Safe to re-run. Default scope: last 14 days, capped batches.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import psycopg

from watchfuleye.scoring.sentiment import score_market_sentiment
from watchfuleye.storage.postgres_schema import ensure_postgres_schema


def main() -> int:
    pg_dsn = os.environ.get(
        "PG_DSN",
        "dbname=watchfuleye user=watchful password=watchfulpass host=localhost port=5432",
    )
    ensure_postgres_schema(pg_dsn)

    lookback_days = int(os.environ.get("SENTIMENT_LOOKBACK_DAYS", "14"))
    batch_size = int(os.environ.get("SENTIMENT_BATCH_SIZE", "500"))
    max_batches = int(os.environ.get("SENTIMENT_MAX_BATCHES", "20"))

    updated_total = 0
    started = datetime.now(timezone.utc)

    with psycopg.connect(pg_dsn) as conn:
        with conn.cursor() as cur:
            for _ in range(max_batches):
                cur.execute(
                    """
                    SELECT id, title, description
                    FROM articles
                    WHERE created_at >= now() - (%s || ' days')::interval
                      AND (
                        sentiment_analysis_text IS NULL
                        OR sentiment_confidence IS NULL
                        OR sentiment_confidence = 0
                      )
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (lookback_days, batch_size),
                )
                rows = cur.fetchall()
                if not rows:
                    break

                updates = []
                for aid, title, desc in rows:
                    r = score_market_sentiment(title or "", desc or "")
                    updates.append((float(r.score), float(r.confidence), r.reasoning, int(aid)))

                cur.executemany(
                    """
                    UPDATE articles
                    SET sentiment_score = %s,
                        sentiment_confidence = %s,
                        sentiment_analysis_text = %s,
                        updated_at = now()
                    WHERE id = %s
                    """,
                    updates,
                )
                conn.commit()
                updated_total += len(updates)

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    print(f"[backfill_postgres_sentiment] updated={updated_total} elapsed_s={elapsed:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


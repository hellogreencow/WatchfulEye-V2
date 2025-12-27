#!/usr/bin/env python3
"""Fulltext extraction worker (Phase 3).

Fetches publisher URLs, extracts main text, and stores it in Postgres for RAG/embeddings.
We store only an excerpt for UI use elsewhere (not full text rendering).
"""

from __future__ import annotations

import os
import time

import psycopg
from dotenv import load_dotenv

from watchfuleye.extraction.fulltext import fetch_and_extract
from watchfuleye.storage.postgres_schema import ensure_postgres_schema


def main() -> int:
    load_dotenv()
    pg_dsn = os.environ.get("PG_DSN", "dbname=watchfuleye user=watchful password=watchfulpass host=localhost port=5432")
    ensure_postgres_schema(pg_dsn)

    batch_size = int(os.environ.get("FULLTEXT_BATCH", "50"))
    min_trust = float(os.environ.get("FULLTEXT_MIN_TRUST", "0.6"))
    sleep_s = float(os.environ.get("FULLTEXT_SLEEP", "0.5"))

    updated = 0
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, canonical_url
                FROM articles
                WHERE bucket = 'main'
                  AND trust_score >= %s
                  AND extracted_text IS NULL
                  AND (fulltext_fetched_at IS NULL OR fulltext_fetched_at < now() - interval '7 days')
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (min_trust, batch_size),
            )
            rows = cur.fetchall()

        for aid, url in rows:
            res = fetch_and_extract(url)
            excerpt = None
            if res.text:
                excerpt = res.text[:500]
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE articles
                    SET extracted_text=%s,
                        excerpt=COALESCE(%s, excerpt),
                        extraction_confidence=%s,
                        fulltext_fetched_at=now(),
                        fulltext_fetch_status=%s,
                        fulltext_fetch_error=%s,
                        updated_at=now()
                    WHERE id=%s
                    """,
                    (
                        res.text,
                        excerpt,
                        float(res.confidence),
                        res.status,
                        res.error,
                        int(aid),
                    ),
                )
            updated += 1
            if updated % 10 == 0:
                print(f"[fulltext] updated={updated}/{len(rows)}")
            time.sleep(max(0.0, sleep_s))

    print(f"[fulltext] completed updated={updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



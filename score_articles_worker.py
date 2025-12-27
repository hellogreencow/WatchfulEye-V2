#!/usr/bin/env python3
"""Score ingested articles in Postgres (Phase 2 scoring).

This updates:
- sources.trust_score (prior)
- articles.trust_score, articles.quality_score, articles.bucket
and applies near-duplicate penalties based on content_hash collisions.
"""

from __future__ import annotations

import os
from typing import Dict, Set

import psycopg
from dotenv import load_dotenv

from watchfuleye.scoring.article_scoring import score_article, source_trust_prior
from watchfuleye.storage.postgres_schema import ensure_postgres_schema


def main() -> int:
    load_dotenv()
    pg_dsn = os.environ.get("PG_DSN", "dbname=watchfuleye user=watchful password=watchfulpass host=localhost port=5432")
    ensure_postgres_schema(pg_dsn)

    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Find near-duplicate hashes in recent window
            cur.execute(
                """
                SELECT content_hash
                FROM articles
                WHERE content_hash IS NOT NULL
                  AND created_at > now() - interval '7 days'
                GROUP BY content_hash
                HAVING COUNT(*) > 1
                """
            )
            dup_hashes: Set[str] = {r[0] for r in cur.fetchall() if r and r[0]}

        # Score recent articles that haven't been scored yet (or were defaulted)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, description, source_domain, source_name, published_at, content_hash
                FROM articles
                WHERE created_at > now() - interval '7 days'
                  AND (quality_score IS NULL OR quality_score = 0.0)
                ORDER BY created_at DESC
                LIMIT 5000
                """
            )
            rows = cur.fetchall()

        updated = 0
        with conn.cursor() as cur:
            for (aid, title, desc, domain, source_name, published_at, chash) in rows:
                scored = score_article(
                    title=title or "",
                    description=desc,
                    domain=domain,
                    source_name=source_name,
                    published_at=published_at,
                    is_duplicate=bool(chash and chash in dup_hashes),
                )
                cur.execute(
                    """
                    UPDATE articles
                    SET trust_score=%s, quality_score=%s, bucket=%s, updated_at=now()
                    WHERE id=%s
                    """,
                    (float(scored.trust), float(scored.quality), scored.bucket, int(aid)),
                )
                updated += 1

        # Update sources table trust_score for recently seen domains
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT source_domain
                FROM articles
                WHERE source_domain IS NOT NULL
                  AND created_at > now() - interval '30 days'
                """
            )
            domains = [r[0] for r in cur.fetchall() if r and r[0]]

        with conn.cursor() as cur:
            for d in domains:
                trust = source_trust_prior(d)
                cur.execute(
                    """
                    INSERT INTO sources(domain, trust_score)
                    VALUES (%s, %s)
                    ON CONFLICT (domain) DO UPDATE SET trust_score=EXCLUDED.trust_score, updated_at=now()
                    """,
                    (d, float(trust)),
                )

    print(f"[score] updated_articles={updated} recent_dup_hashes={len(dup_hashes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



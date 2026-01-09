"""Minimal Postgres repository for storing ingested articles.

This is intentionally lightweight (psycopg + SQL) to keep control and transparency.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import hashlib
from typing import Iterable, List, Optional, Sequence, Tuple

import psycopg
from psycopg.types.json import Jsonb

from watchfuleye.ingestion.article_types import ArticleCandidate
from watchfuleye.ingestion.url_utils import canonicalize_url, url_hash


class PostgresRepo:
    def __init__(self, pg_dsn: str):
        self.pg_dsn = pg_dsn

    def upsert_sources(self, domains: Iterable[str]) -> None:
        doms = [d.strip().lower() for d in domains if d and str(d).strip()]
        if not doms:
            return
        with psycopg.connect(self.pg_dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                for d in doms:
                    cur.execute(
                        """
                        INSERT INTO sources(domain)
                        VALUES (%s)
                        ON CONFLICT (domain) DO NOTHING
                        """,
                        (d,),
                    )

    def upsert_articles(self, items: Sequence[ArticleCandidate]) -> Tuple[int, int]:
        """Upsert articles by url_hash.

        Returns (processed_count, distinct_count_in_db_after) best-effort.
        """
        if not items:
            return 0, 0
        processed = 0

        with psycopg.connect(self.pg_dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                for it in items:
                    canon = canonicalize_url(it.url)
                    uhash = url_hash(it.url)
                    # Near-dup content signature (lightweight; fulltext dedup comes later)
                    sig = (it.title or "").strip().lower() + "\n" + (it.description or "").strip().lower()
                    content_hash = hashlib.sha256(sig.encode("utf-8")).hexdigest() if sig.strip() else None

                    # Very rough bucket routing (scoring system will refine)
                    bucket = "main"
                    txt = f"{it.title} {it.description or ''}".lower()
                    if any(k in txt for k in ("deal", "discount", "coupon", "promo code", "save $", "off today")):
                        bucket = "deals"
                    excerpt = None
                    if it.description:
                        excerpt = it.description.strip()[:500]
                    raw = it.raw or {}
                    # Keep the original url in raw for provenance
                    raw.setdefault("original_url", it.url)
                    cur.execute(
                        """
                        INSERT INTO articles (
                          canonical_url, url_hash, content_hash, title, description, excerpt, published_at,
                          source_domain, source_name, language, ingestion_source, raw,
                          bucket, extraction_confidence, trust_score, quality_score
                        )
                        VALUES (
                          %(canonical_url)s, %(url_hash)s, %(content_hash)s, %(title)s, %(description)s, %(excerpt)s, %(published_at)s,
                          %(source_domain)s, %(source_name)s, %(language)s, %(ingestion_source)s, %(raw)s,
                          %(bucket)s, %(extraction_confidence)s, %(trust_score)s, %(quality_score)s
                        )
                        ON CONFLICT (url_hash) DO UPDATE SET
                          canonical_url = EXCLUDED.canonical_url,
                          content_hash = COALESCE(EXCLUDED.content_hash, articles.content_hash),
                          title = EXCLUDED.title,
                          description = COALESCE(EXCLUDED.description, articles.description),
                          excerpt = COALESCE(EXCLUDED.excerpt, articles.excerpt),
                          published_at = COALESCE(EXCLUDED.published_at, articles.published_at),
                          source_domain = COALESCE(EXCLUDED.source_domain, articles.source_domain),
                          source_name = COALESCE(EXCLUDED.source_name, articles.source_name),
                          language = COALESCE(EXCLUDED.language, articles.language),
                          ingestion_source = COALESCE(EXCLUDED.ingestion_source, articles.ingestion_source),
                          bucket = COALESCE(EXCLUDED.bucket, articles.bucket),
                          raw = COALESCE(EXCLUDED.raw, articles.raw),
                          updated_at = now()
                        ;
                        """,
                        {
                            "canonical_url": canon or it.url,
                            "url_hash": uhash,
                            "content_hash": content_hash,
                            "title": it.title,
                            "description": it.description,
                            "excerpt": excerpt,
                            "published_at": it.published_at,
                            "source_domain": it.source_domain,
                            "source_name": it.source_name,
                            "language": "en",
                            "ingestion_source": it.ingestion_source,
                            "raw": Jsonb(raw),
                            "bucket": bucket,
                            "extraction_confidence": 0.0,
                            "trust_score": 0.5,
                            "quality_score": 0.0,
                        },
                    )
                    processed += 1

        # best-effort distinct count
        try:
            with psycopg.connect(self.pg_dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM articles")
                    total = int(cur.fetchone()[0] or 0)
        except Exception:
            total = 0
        return processed, total



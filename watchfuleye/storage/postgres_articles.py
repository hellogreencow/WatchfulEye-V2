"""Postgres-backed article queries for the frontend/search API.

This is a transitional layer: the rest of the app historically used SQLite.
We keep the response shape compatible with the existing React dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import psycopg


def _parse_timeframe_to_hours(timeframe: Optional[str]) -> Optional[int]:
    if not timeframe:
        return None
    tf = str(timeframe).strip().lower()
    if not tf:
        return None
    # formats: 24h, 7d, 30d, 2w
    import re

    m = re.fullmatch(r"(\d+)\s*([hdw])", tf)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    if unit == "h":
        return n
    if unit == "d":
        return n * 24
    if unit == "w":
        return n * 24 * 7
    return None


@dataclass
class PostgresArticleStore:
    pg_dsn: str

    def _connect(self):
        return psycopg.connect(self.pg_dsn)

    def get_recent_articles(
        self,
        *,
        limit: int = 20,
        bucket: Optional[str] = None,
        since_hours: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        where = ["1=1"]
        params: List[Any] = []
        if bucket and bucket.strip().lower() not in ("all", "any", ""):
            where.append("bucket = %s")
            params.append(bucket.strip().lower())
        if since_hours and since_hours > 0:
            where.append("created_at >= now() - (%s || ' hours')::interval")
            params.append(int(since_hours))

        sql = f"""
        SELECT id, title, description, canonical_url, source_name, source_domain, published_at, created_at,
               excerpt, trust_score, quality_score, bucket
        FROM articles
        WHERE {' AND '.join(where)}
        ORDER BY created_at DESC
        LIMIT {limit}
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return [self._row_to_article(row) for row in rows]

    def search(
        self,
        *,
        query: str,
        limit: int = 50,
        bucket: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        q = (query or "").strip()
        if len(q) < 2:
            return []
        limit = max(1, min(int(limit), 200))
        since_hours = _parse_timeframe_to_hours(timeframe)

        where = ["search_tsv @@ websearch_to_tsquery('english', %s)"]
        params: List[Any] = [q]
        if bucket and bucket.strip().lower() not in ("all", "any", ""):
            where.append("bucket = %s")
            params.append(bucket.strip().lower())
        if since_hours and since_hours > 0:
            where.append("created_at >= now() - (%s || ' hours')::interval")
            params.append(int(since_hours))

        sql = f"""
        SELECT id, title, description, canonical_url, source_name, source_domain, published_at, created_at,
               excerpt, trust_score, quality_score, bucket,
               ts_rank_cd(search_tsv, websearch_to_tsquery('english', %s)) AS rank
        FROM articles
        WHERE {' AND '.join(where)}
        ORDER BY rank DESC, created_at DESC
        LIMIT {limit}
        """
        # Note: query appears twice (tsquery in WHERE and in rank), so append again
        params_with_rank = params + [q]
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params_with_rank)
                rows = cur.fetchall()
        return [self._row_to_article(row) for row in rows]

    def get_buckets(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT bucket, COUNT(*) AS count, AVG(quality_score) AS avg_quality
                    FROM articles
                    GROUP BY bucket
                    ORDER BY count DESC
                    """
                )
                rows = cur.fetchall()
        out = []
        for bucket, count, avg_quality in rows:
            out.append(
                {
                    "name": bucket,
                    "display_name": str(bucket).title(),
                    "count": int(count or 0),
                    # Frontend expects avg_sentiment/avg_confidence sometimes; map quality
                    "avg_sentiment": float(avg_quality or 0.0),
                    "avg_confidence": float(avg_quality or 0.0),
                }
            )
        return out

    def _row_to_article(self, row) -> Dict[str, Any]:
        # Row ordering matches selects above.
        (
            aid,
            title,
            description,
            canonical_url,
            source_name,
            source_domain,
            published_at,
            created_at,
            excerpt,
            trust_score,
            quality_score,
            bucket,
            *rest,
        ) = row
        src = source_name or source_domain or "Unknown"
        return {
            "id": int(aid),
            "title": title,
            "description": description,
            "content": None,  # do not expose fulltext
            "url": canonical_url,
            "url_hash": None,
            "published_at": published_at.isoformat() if published_at else None,
            "source": src,
            "category": bucket,  # reuse existing UI filter path; legacy category system is deprecated
            "category_confidence": float(trust_score or 0.0),
            "sentiment_score": 0.0,
            "sentiment_confidence": float(quality_score or 0.0),
            "sentiment_analysis_text": excerpt,
            "word_count": 0,
            "language": "en",
            "created_at": created_at.isoformat() if created_at else None,
            "updated_at": None,
            "is_saved": False,
        }



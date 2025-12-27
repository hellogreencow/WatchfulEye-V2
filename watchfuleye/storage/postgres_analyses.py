"""Postgres-backed analysis storage (Global Briefs)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.types.json import Jsonb


class PostgresAnalysesStore:
    def __init__(self, pg_dsn: str):
        self.pg_dsn = pg_dsn

    def store_analysis(
        self,
        *,
        content: Optional[str],
        model_used: Optional[str],
        article_count: Optional[int],
        processing_time: Optional[float],
        topic: Optional[str],
        raw_response: Dict[str, Any],
        quality_score: Optional[float] = None,
    ) -> int:
        content_preview = None
        if content:
            content_preview = content[:500] + ("..." if len(content) > 500 else "")
        with psycopg.connect(self.pg_dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO analyses (
                      created_at, content, content_preview, model_used, article_count, processing_time, quality_score, topic, raw_response_json
                    )
                    VALUES (now(), %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        content,
                        content_preview,
                        model_used,
                        article_count,
                        processing_time,
                        quality_score,
                        topic,
                        Jsonb(raw_response),
                    ),
                )
                return int(cur.fetchone()[0])

    def get_recent(self, *, limit: int = 10) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 50))
        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, created_at, model_used, article_count, processing_time, topic, quality_score,
                           content_preview, sentiment_summary, category_breakdown, raw_response_json
                    FROM analyses
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
        out: List[Dict[str, Any]] = []
        for (aid, created_at, model_used, article_count, processing_time, topic, quality_score, content_preview, sentiment_summary, category_breakdown, raw_json) in rows:
            dt = created_at.astimezone(timezone.utc) if isinstance(created_at, datetime) else None
            out.append(
                {
                    "id": int(aid),
                    "created_at": dt.isoformat().replace("+00:00", "Z") if dt else None,
                    "model_used": model_used,
                    "article_count": int(article_count) if article_count is not None else None,
                    "processing_time": float(processing_time) if processing_time is not None else None,
                    "topic": topic,
                    "quality_score": float(quality_score) if quality_score is not None else None,
                    "content_preview": content_preview,
                    "sentiment_summary": sentiment_summary,
                    "category_breakdown": category_breakdown,
                    # UI expects raw_response_json as string (SQLite stored JSON string).
                    "raw_response_json": json.dumps(raw_json) if raw_json is not None else None,
                }
            )
        return out



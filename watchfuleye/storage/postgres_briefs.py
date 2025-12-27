"""Store Global Briefs and extracted recommendations in Postgres."""

from __future__ import annotations

from typing import Any, Dict, Optional

import psycopg

from watchfuleye.contracts.global_brief import extract_recommendations
from watchfuleye.storage.postgres_analyses import PostgresAnalysesStore


def store_brief_and_recommendations(
    pg_dsn: str,
    *,
    prompt: Optional[str],
    model_used: Optional[str],
    article_count: Optional[int],
    processing_time: Optional[float],
    topic: Optional[str],
    brief_json: Dict[str, Any],
    quality_score: Optional[float] = None,
) -> int:
    """Store an analysis row and its `idea_desk` recommendations; return analysis_id."""
    analyses = PostgresAnalysesStore(pg_dsn)
    analysis_id = analyses.store_analysis(
        content=prompt,
        model_used=model_used,
        article_count=article_count,
        processing_time=processing_time,
        topic=topic,
        raw_response=brief_json,
        quality_score=quality_score,
    )

    recs = extract_recommendations(brief_json, source_analysis_id=analysis_id)
    if recs:
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                for r in recs:
                    cur.execute(
                        """
                        INSERT INTO recommendations (analysis_id, action, ticker, rationale)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (analysis_id, r.action, r.ticker, r.rationale),
                    )
    return analysis_id



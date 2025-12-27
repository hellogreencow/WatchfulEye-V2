"""Postgres schema management for WatchfulEye.

This module creates the Postgres tables required by the v2 plan.
We intentionally keep schema creation idempotent (CREATE IF NOT EXISTS).
"""

from __future__ import annotations

from typing import Iterable, Optional

import psycopg


SCHEMA_STATEMENTS: list[str] = [
    # Extensions
    "CREATE EXTENSION IF NOT EXISTS vector;",
    "CREATE EXTENSION IF NOT EXISTS pg_trgm;",
    # Sources
    """
    CREATE TABLE IF NOT EXISTS sources (
      id BIGSERIAL PRIMARY KEY,
      domain TEXT UNIQUE NOT NULL,
      display_name TEXT,
      trust_score REAL NOT NULL DEFAULT 0.5,
      allow_ingest BOOLEAN NOT NULL DEFAULT TRUE,
      allow_briefs BOOLEAN NOT NULL DEFAULT TRUE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    # Articles (fulltext internal; excerpt for UI)
    """
    CREATE TABLE IF NOT EXISTS articles (
      id BIGSERIAL PRIMARY KEY,
      canonical_url TEXT NOT NULL UNIQUE,
      url_hash TEXT NOT NULL UNIQUE,
      content_hash TEXT,
      title TEXT NOT NULL,
      description TEXT,
      extracted_text TEXT,
      excerpt TEXT,
      fulltext_fetched_at TIMESTAMPTZ,
      fulltext_fetch_status TEXT,
      fulltext_fetch_error TEXT,
      published_at TIMESTAMPTZ,
      source_domain TEXT,
      source_name TEXT,
      language TEXT NOT NULL DEFAULT 'en',
      ingestion_source TEXT,
      bucket TEXT NOT NULL DEFAULT 'main',
      raw JSONB,
      extraction_confidence REAL NOT NULL DEFAULT 0.0,
      trust_score REAL NOT NULL DEFAULT 0.5,
      quality_score REAL NOT NULL DEFAULT 0.0,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      search_tsv tsvector GENERATED ALWAYS AS (
        to_tsvector(
          'english',
          coalesce(title,'') || ' ' || coalesce(description,'') || ' ' || coalesce(extracted_text,'')
        )
      ) STORED
    );
    """,
    # Backward-compatible column adds (safe if table already exists)
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS content_hash TEXT;",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS bucket TEXT NOT NULL DEFAULT 'main';",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS fulltext_fetched_at TIMESTAMPTZ;",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS fulltext_fetch_status TEXT;",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS fulltext_fetch_error TEXT;",
    "CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles (created_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles (published_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_articles_source_domain ON articles (source_domain);",
    "CREATE INDEX IF NOT EXISTS idx_articles_quality_score ON articles (quality_score DESC);",
    "CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles (content_hash) WHERE content_hash IS NOT NULL;",
    "CREATE INDEX IF NOT EXISTS idx_articles_search_tsv ON articles USING GIN (search_tsv);",
    "CREATE INDEX IF NOT EXISTS idx_articles_title_trgm ON articles USING GIN (title gin_trgm_ops);",
    # Analyses (Global Brief JSON stored in raw_response_json)
    """
    CREATE TABLE IF NOT EXISTS analyses (
      id BIGSERIAL PRIMARY KEY,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      content TEXT,
      content_hash TEXT,
      content_preview TEXT,
      model_used TEXT,
      article_count INTEGER,
      processing_time REAL,
      quality_score REAL,
      topic TEXT,
      raw_response_json JSONB,
      sentiment_summary JSONB,
      category_breakdown JSONB,
      sent_to_telegram BOOLEAN NOT NULL DEFAULT FALSE,
      sent_successfully BOOLEAN NOT NULL DEFAULT FALSE
    );
    """,
    # Backward-compatible column adds (safe if table already exists)
    "ALTER TABLE analyses ADD COLUMN IF NOT EXISTS content_hash TEXT;",
    "ALTER TABLE analyses ADD COLUMN IF NOT EXISTS sentiment_summary JSONB;",
    "ALTER TABLE analyses ADD COLUMN IF NOT EXISTS category_breakdown JSONB;",
    "CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses (created_at DESC);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_analyses_content_hash ON analyses (content_hash) WHERE content_hash IS NOT NULL;",
    # Recommendations (parsed from Global Brief idea_desk)
    """
    CREATE TABLE IF NOT EXISTS recommendations (
      id BIGSERIAL PRIMARY KEY,
      analysis_id BIGINT REFERENCES analyses(id) ON DELETE CASCADE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      action TEXT NOT NULL,
      ticker TEXT NOT NULL,
      rationale TEXT NOT NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_recommendations_ticker_created ON recommendations (ticker, created_at DESC);",
    # Prices (daily close)
    """
    CREATE TABLE IF NOT EXISTS prices_daily (
      symbol TEXT NOT NULL,
      date DATE NOT NULL,
      close NUMERIC NOT NULL,
      source TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      PRIMARY KEY (symbol, date)
    );
    """,
    # Recommendation performance snapshots
    """
    CREATE TABLE IF NOT EXISTS recommendation_performance (
      recommendation_id BIGINT REFERENCES recommendations(id) ON DELETE CASCADE,
      horizon_days INTEGER NOT NULL,
      benchmark_symbol TEXT NOT NULL,
      rec_return NUMERIC,
      benchmark_return NUMERIC,
      alpha NUMERIC,
      computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      PRIMARY KEY (recommendation_id, horizon_days, benchmark_symbol)
    );
    """,
    # Trends tables (owner analytics)
    """
    CREATE TABLE IF NOT EXISTS term_trends (
      term TEXT NOT NULL,
      window_start TIMESTAMPTZ NOT NULL,
      window_end TIMESTAMPTZ NOT NULL,
      count INTEGER NOT NULL,
      z_score REAL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      PRIMARY KEY (term, window_start, window_end)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS topic_trends (
      topic TEXT NOT NULL,
      window_start TIMESTAMPTZ NOT NULL,
      window_end TIMESTAMPTZ NOT NULL,
      count INTEGER NOT NULL,
      z_score REAL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      PRIMARY KEY (topic, window_start, window_end)
    );
    """,
    # Publishing workflow (owner insights)
    """
    CREATE TABLE IF NOT EXISTS insight_posts (
      id BIGSERIAL PRIMARY KEY,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      status TEXT NOT NULL DEFAULT 'draft', -- draft|published|archived
      title TEXT NOT NULL,
      body_md TEXT NOT NULL DEFAULT '',
      tags TEXT[],
      evidence JSONB,
      published_at TIMESTAMPTZ,
      external_url TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_insight_posts_status_created ON insight_posts (status, created_at DESC);",
    # Embeddings tables (keep aligned with existing web_app.py expectations)
    """
    CREATE TABLE IF NOT EXISTS article_embeddings (
      article_id BIGINT PRIMARY KEY,
      embedding vector(1536),
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    # Use cosine distance operator class; our queries use `<=>` (cosine distance).
    "CREATE INDEX IF NOT EXISTS idx_article_embeddings_hnsw ON article_embeddings USING hnsw (embedding vector_cosine_ops);",
    """
    CREATE TABLE IF NOT EXISTS article_embeddings_voyage (
      article_id BIGINT PRIMARY KEY,
      embedding vector(2048),
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    # NOTE: pgvector indexing methods currently error above 2000 dimensions.
    # Voyage-3-large embeddings are 2048 dims, so we store them but do not create a vector index.
]


def ensure_postgres_schema(pg_dsn: str, *, statements: Optional[Iterable[str]] = None) -> None:
    """Ensure Postgres schema exists."""
    stmts = list(statements) if statements is not None else SCHEMA_STATEMENTS
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            for s in stmts:
                cur.execute(s)



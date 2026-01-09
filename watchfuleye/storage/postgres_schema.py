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
      embedding vector(1024),
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,

    # =====================
    # WS0 (V3): Entity Resolution + Identifiers (minimal schema)
    # =====================
    """
    CREATE TABLE IF NOT EXISTS entities (
      id TEXT PRIMARY KEY,
      entity_type TEXT NOT NULL, -- ticker|country|sanctions_target (v1 scope)
      label TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_entities_type_label ON entities (entity_type, label);",

    """
    CREATE TABLE IF NOT EXISTS entity_identifiers (
      id BIGSERIAL PRIMARY KEY,
      entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
      identifier_type TEXT NOT NULL, -- ticker|iso3166|ofac_id|name
      identifier_value TEXT NOT NULL,
      confidence REAL NOT NULL DEFAULT 1.0,
      provenance JSONB,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (identifier_type, identifier_value)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_entity_identifiers_entity_id ON entity_identifiers (entity_id);",

    """
    CREATE TABLE IF NOT EXISTS entity_aliases (
      id BIGSERIAL PRIMARY KEY,
      entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
      alias TEXT NOT NULL,
      confidence REAL NOT NULL DEFAULT 0.8,
      provenance JSONB,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (entity_id, alias)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_entity_aliases_alias ON entity_aliases (alias);",

    """
    CREATE TABLE IF NOT EXISTS entity_same_as_edges (
      id BIGSERIAL PRIMARY KEY,
      src_entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
      dst_entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
      confidence REAL NOT NULL DEFAULT 0.0,
      conflicted BOOLEAN NOT NULL DEFAULT FALSE,
      provenance JSONB,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (src_entity_id, dst_entity_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_entity_same_as_src ON entity_same_as_edges (src_entity_id);",

    # =====================
    # WS0 (V3): Investigations + Reports (contract scaffolding)
    # =====================
    """
    CREATE TABLE IF NOT EXISTS v3_investigations (
      id TEXT PRIMARY KEY,
      query TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'queued', -- queued|running|succeeded|failed
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      trace_id TEXT NOT NULL,
      meta JSONB
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_v3_investigations_created_at ON v3_investigations (created_at DESC);",

    """
    CREATE TABLE IF NOT EXISTS v3_reports (
      id TEXT PRIMARY KEY,
      investigation_id TEXT NOT NULL REFERENCES v3_investigations(id) ON DELETE CASCADE,
      title TEXT NOT NULL,
      summary TEXT NOT NULL,
      content JSONB,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_v3_reports_investigation_id ON v3_reports (investigation_id);",

    # =====================
    # WS6.1 (V3): Forecast Accountability (accuracy engine)
    # =====================
    """
    CREATE TABLE IF NOT EXISTS forecasts (
      id TEXT PRIMARY KEY,
      report_id TEXT NOT NULL REFERENCES v3_reports(id) ON DELETE CASCADE,
      investigation_id TEXT REFERENCES v3_investigations(id) ON DELETE CASCADE,

      -- Forecast content
      claim TEXT NOT NULL,
      probability REAL NOT NULL CHECK (probability >= 0.0 AND probability <= 1.0),
      horizon_days INTEGER NOT NULL,
      horizon_date TIMESTAMPTZ NOT NULL,

      -- Entity linking (references WS0 entities)
      entity_ids TEXT[],
      entity_types TEXT[],

      -- Evidence
      evidence_ids TEXT[],
      assumptions TEXT[],

      -- Outcome tracking
      outcome_status TEXT NOT NULL DEFAULT 'pending', -- pending|resolved|unresolved
      outcome_result BOOLEAN,
      outcome_confidence REAL,
      outcome_measured_at TIMESTAMPTZ,
      outcome_method TEXT,
      outcome_evidence JSONB,

      -- Scoring (calculated from scorer.py)
      brier_score REAL,
      log_score REAL,
      calibration_bin INTEGER,

      -- Metadata
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      created_by TEXT,
      tags TEXT[]
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecasts_report_id ON forecasts(report_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecasts_horizon_date ON forecasts(horizon_date);",
    "CREATE INDEX IF NOT EXISTS idx_forecasts_outcome_status ON forecasts(outcome_status);",
    "CREATE INDEX IF NOT EXISTS idx_forecasts_entity_ids ON forecasts USING GIN(entity_ids);",
    "CREATE INDEX IF NOT EXISTS idx_forecasts_tags ON forecasts USING GIN(tags);",
    "CREATE INDEX IF NOT EXISTS idx_forecasts_created_at ON forecasts(created_at DESC);",

    """
    CREATE TABLE IF NOT EXISTS forecast_updates (
      id BIGSERIAL PRIMARY KEY,
      forecast_id TEXT NOT NULL REFERENCES forecasts(id) ON DELETE CASCADE,
      update_type TEXT NOT NULL, -- probability_revision|outcome_measurement|manual_correction
      previous_state JSONB,
      new_state JSONB,
      reason TEXT,
      updated_by TEXT,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_updates_forecast_id ON forecast_updates(forecast_id);",
    "CREATE INDEX IF NOT EXISTS idx_forecast_updates_updated_at ON forecast_updates(updated_at DESC);",
]


def ensure_postgres_schema(pg_dsn: str, *, statements: Optional[Iterable[str]] = None) -> None:
    """Ensure Postgres schema exists."""
    stmts = list(statements) if statements is not None else SCHEMA_STATEMENTS
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            for s in stmts:
                cur.execute(s)

            # Safety: ensure embedding column dimensions match our configured models.
            # pgvector stores dimension in atttypmod for vector columns.
            def _ensure_dim(table: str, dim: int) -> None:
                cur.execute(
                    """
                    SELECT a.atttypmod
                    FROM pg_attribute a
                    JOIN pg_class c ON c.oid=a.attrelid
                    JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE c.relname=%s AND a.attname='embedding' AND a.attnum>0
                    """,
                    (table,),
                )
                row = cur.fetchone()
                if not row:
                    return
                current = int(row[0] or 0)
                if current == dim:
                    return
                # Attempt in-place migration; will fail if existing rows cannot be cast.
                cur.execute(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({dim}) USING embedding::vector({dim})")

            _ensure_dim("article_embeddings", 1536)
            _ensure_dim("article_embeddings_voyage", 1024)

            # Create voyage vector index after migration (older installs may have had 2048 dims).
            try:
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_article_embeddings_voyage_hnsw "
                    "ON article_embeddings_voyage USING hnsw (embedding vector_cosine_ops);"
                )
            except Exception:
                # If pgvector/index method can't support it, skip (FTS-only fallback remains).
                pass



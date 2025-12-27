#!/usr/bin/env python3
"""Backfill legacy SQLite (news_bot.db) into Postgres.

This supports the v2 plan migration where Postgres becomes the primary store.

Design goals:
- Idempotent: re-runs should not duplicate rows
- Preserve IDs: keep SQLite `articles.id` and `analyses.id` as Postgres IDs so existing
  embedding rows keyed by article_id remain compatible during transition.
- Robust JSON handling: invalid JSON is wrapped so inserts never fail.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime
import hashlib
from typing import Any, Dict, Iterable, Optional, Tuple
from urllib.parse import urlparse

import psycopg
from psycopg.types.json import Jsonb

from watchfuleye.ingestion.url_utils import canonicalize_url, url_hash
from watchfuleye.storage.postgres_schema import ensure_postgres_schema


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Normalize common formats
    s = s.replace("Z", "+00:00")
    s = s.replace(" ", "T") if " " in s and "T" not in s else s
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _safe_json(value: Any) -> Optional[dict]:
    """Parse JSON if possible; else wrap as raw text."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, (list, int, float, bool)):
        return {"value": value}
    s = str(value).strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return {"raw_text": s}


def _source_domain_from_url(url: str) -> Optional[str]:
    try:
        p = urlparse(url or "")
        host = (p.netloc or "").lower().strip()
        return host or None
    except Exception:
        return None


def _sqlite_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cur.fetchall()}
    return cols


def _migrate_articles(sqlite_conn: sqlite3.Connection, pg_conn: psycopg.Connection, *, limit: Optional[int] = None) -> Tuple[int, int]:
    cols = _sqlite_columns(sqlite_conn, "articles")
    select_cols = ["id", "title", "description", "content", "url", "published_at", "source", "language", "created_at", "updated_at"]
    # best-effort: only select columns that exist
    select_cols = [c for c in select_cols if c in cols]
    cur = sqlite_conn.cursor()
    sql = f"SELECT {', '.join(select_cols)} FROM articles ORDER BY id ASC"
    if isinstance(limit, int) and limit > 0:
        sql += f" LIMIT {int(limit)}"
    cur.execute(sql)
    inserted = 0
    updated = 0  # kept for backward compatibility; inserts use UPSERT so we don't track updates precisely

    with pg_conn.cursor() as pgcur:
        while True:
            rows = cur.fetchmany(500)
            if not rows:
                break
            for r in rows:
                raw_url = (r["url"] if "url" in r.keys() else "") or ""
                canon = canonicalize_url(raw_url)
                uhash = url_hash(raw_url)
                source_name = (r["source"] if "source" in r.keys() else None) or None
                sdomain = _source_domain_from_url(canon) or _source_domain_from_url(raw_url)
                title = (r["title"] if "title" in r.keys() else "") or ""
                desc = (r["description"] if "description" in r.keys() else None) or None
                extracted_text = (r["content"] if "content" in r.keys() else None) or None
                excerpt = None
                if extracted_text and isinstance(extracted_text, str):
                    excerpt = extracted_text.strip()[:500]
                elif desc and isinstance(desc, str):
                    excerpt = desc.strip()[:300]
                published_at = _parse_dt(r["published_at"]) if "published_at" in r.keys() else None
                created_at = _parse_dt(r["created_at"]) if "created_at" in r.keys() else None
                updated_at = _parse_dt(r["updated_at"]) if "updated_at" in r.keys() else None
                language = (r["language"] if "language" in r.keys() else None) or "en"

                raw_row = dict(r)
                sig = (title or "").strip().lower() + "\n" + (desc or "").strip().lower()
                content_hash = hashlib.sha256(sig.encode("utf-8")).hexdigest() if sig.strip() else None
                txt = f"{title} {desc or ''}".lower()
                bucket = "deals" if any(k in txt for k in ("deal", "discount", "coupon", "promo code")) else "main"
                pgcur.execute(
                    """
                    INSERT INTO articles (
                      id, canonical_url, url_hash, content_hash, title, description, extracted_text, excerpt,
                      published_at, source_domain, source_name, language, ingestion_source, raw,
                      bucket,
                      extraction_confidence, trust_score, quality_score, created_at, updated_at
                    )
                    VALUES (
                      %(id)s, %(canonical_url)s, %(url_hash)s, %(content_hash)s, %(title)s, %(description)s, %(extracted_text)s, %(excerpt)s,
                      %(published_at)s, %(source_domain)s, %(source_name)s, %(language)s, %(ingestion_source)s, %(raw)s,
                      %(bucket)s,
                      %(extraction_confidence)s, %(trust_score)s, %(quality_score)s, %(created_at)s, %(updated_at)s
                    )
                    ON CONFLICT (url_hash) DO UPDATE SET
                      canonical_url = EXCLUDED.canonical_url,
                      content_hash = COALESCE(EXCLUDED.content_hash, articles.content_hash),
                      title = EXCLUDED.title,
                      description = EXCLUDED.description,
                      extracted_text = COALESCE(EXCLUDED.extracted_text, articles.extracted_text),
                      excerpt = COALESCE(EXCLUDED.excerpt, articles.excerpt),
                      published_at = COALESCE(EXCLUDED.published_at, articles.published_at),
                      source_domain = COALESCE(EXCLUDED.source_domain, articles.source_domain),
                      source_name = COALESCE(EXCLUDED.source_name, articles.source_name),
                      language = COALESCE(EXCLUDED.language, articles.language),
                      bucket = COALESCE(EXCLUDED.bucket, articles.bucket),
                      raw = COALESCE(EXCLUDED.raw, articles.raw),
                      updated_at = now()
                    ;
                    """,
                    {
                        "id": int(r["id"]),
                        "canonical_url": canon or raw_url,
                        "url_hash": uhash,
                        "content_hash": content_hash,
                        "title": title or "(untitled)",
                        "description": desc,
                        "extracted_text": extracted_text,
                        "excerpt": excerpt,
                        "published_at": published_at,
                        "source_domain": sdomain,
                        "source_name": source_name,
                        "language": language,
                        "ingestion_source": "legacy_sqlite",
                        "raw": Jsonb(raw_row),
                        "bucket": bucket,
                        "extraction_confidence": 0.0,
                        "trust_score": 0.5,
                        "quality_score": 0.0,
                        "created_at": created_at,
                        "updated_at": updated_at,
                    },
                )
                inserted += 1
                if inserted % 5000 == 0:
                    print(f"[backfill] articles migrated: {inserted}")

    return inserted, updated


def _migrate_analyses(sqlite_conn: sqlite3.Connection, pg_conn: psycopg.Connection, *, limit: Optional[int] = None) -> Tuple[int, int]:
    cols = _sqlite_columns(sqlite_conn, "analyses")
    select_cols = [
        "id",
        "created_at",
        "timestamp",
        "content",
        "content_hash",
        "content_preview",
        "model_used",
        "article_count",
        "processing_time",
        "quality_score",
        "raw_response_json",
        "sentiment_summary",
        "category_breakdown",
        "sent_to_telegram",
        "sent_successfully",
    ]
    select_cols = [c for c in select_cols if c in cols]
    cur = sqlite_conn.cursor()
    sql = f"SELECT {', '.join(select_cols)} FROM analyses ORDER BY id ASC"
    if isinstance(limit, int) and limit > 0:
        sql += f" LIMIT {int(limit)}"
    cur.execute(sql)
    inserted = 0
    updated = 0
    with pg_conn.cursor() as pgcur:
        while True:
            rows = cur.fetchmany(500)
            if not rows:
                break
            for r in rows:
                # Prefer created_at, else timestamp
                dt = _parse_dt(r["created_at"]) if "created_at" in r.keys() else None
                if not dt and "timestamp" in r.keys():
                    dt = _parse_dt(r["timestamp"])

                content = (r["content"] if "content" in r.keys() else None) or None
                content_preview = (r["content_preview"] if "content_preview" in r.keys() else None) or None
                content_hash = (r["content_hash"] if "content_hash" in r.keys() else None) or None
                model_used = (r["model_used"] if "model_used" in r.keys() else None) or None
                article_count = (r["article_count"] if "article_count" in r.keys() else None) or None
                processing_time = (r["processing_time"] if "processing_time" in r.keys() else None) or None
                quality_score = (r["quality_score"] if "quality_score" in r.keys() else None) or None

                raw_response_json = _safe_json(r["raw_response_json"]) if "raw_response_json" in r.keys() else None
                sentiment_summary = _safe_json(r["sentiment_summary"]) if "sentiment_summary" in r.keys() else None
                category_breakdown = _safe_json(r["category_breakdown"]) if "category_breakdown" in r.keys() else None

                sent_to_telegram = bool(r["sent_to_telegram"]) if "sent_to_telegram" in r.keys() and r["sent_to_telegram"] is not None else False
                sent_successfully = bool(r["sent_successfully"]) if "sent_successfully" in r.keys() and r["sent_successfully"] is not None else False

                pgcur.execute(
                    """
                    INSERT INTO analyses (
                      id, created_at, content, content_hash, content_preview, model_used, article_count, processing_time,
                      quality_score, raw_response_json, sentiment_summary, category_breakdown, sent_to_telegram, sent_successfully
                    )
                    VALUES (
                      %(id)s, %(created_at)s, %(content)s, %(content_hash)s, %(content_preview)s, %(model_used)s, %(article_count)s, %(processing_time)s,
                      %(quality_score)s, %(raw_response_json)s, %(sentiment_summary)s, %(category_breakdown)s, %(sent_to_telegram)s, %(sent_successfully)s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                      created_at = COALESCE(EXCLUDED.created_at, analyses.created_at),
                      content = COALESCE(EXCLUDED.content, analyses.content),
                      content_hash = COALESCE(EXCLUDED.content_hash, analyses.content_hash),
                      content_preview = COALESCE(EXCLUDED.content_preview, analyses.content_preview),
                      model_used = COALESCE(EXCLUDED.model_used, analyses.model_used),
                      article_count = COALESCE(EXCLUDED.article_count, analyses.article_count),
                      processing_time = COALESCE(EXCLUDED.processing_time, analyses.processing_time),
                      quality_score = COALESCE(EXCLUDED.quality_score, analyses.quality_score),
                      raw_response_json = COALESCE(EXCLUDED.raw_response_json, analyses.raw_response_json),
                      sentiment_summary = COALESCE(EXCLUDED.sentiment_summary, analyses.sentiment_summary),
                      category_breakdown = COALESCE(EXCLUDED.category_breakdown, analyses.category_breakdown),
                      sent_to_telegram = EXCLUDED.sent_to_telegram,
                      sent_successfully = EXCLUDED.sent_successfully
                    ;
                    """,
                    {
                        "id": int(r["id"]),
                        "created_at": dt,
                    "content": content,
                    "content_hash": content_hash,
                    "content_preview": content_preview,
                    "model_used": model_used,
                    "article_count": int(article_count) if article_count is not None else None,
                    "processing_time": float(processing_time) if processing_time is not None else None,
                    "quality_score": float(quality_score) if quality_score is not None else None,
                    "raw_response_json": Jsonb(raw_response_json) if raw_response_json is not None else None,
                    "sentiment_summary": Jsonb(sentiment_summary) if sentiment_summary is not None else None,
                    "category_breakdown": Jsonb(category_breakdown) if category_breakdown is not None else None,
                    "sent_to_telegram": sent_to_telegram,
                    "sent_successfully": sent_successfully,
                    },
                )
                inserted += 1
                if inserted % 500 == 0:
                    print(f"[backfill] analyses migrated: {inserted}")
    return inserted, updated


def _bump_sequences(pg_conn: psycopg.Connection) -> None:
    """Ensure BIGSERIAL sequences are >= max(id)+1 after explicit inserts."""
    with pg_conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(id), 0) FROM articles;")
        max_articles = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT setval(pg_get_serial_sequence('articles','id'), %s, true);", (max_articles,))

        cur.execute("SELECT COALESCE(MAX(id), 0) FROM analyses;")
        max_analyses = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT setval(pg_get_serial_sequence('analyses','id'), %s, true);", (max_analyses,))


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill legacy SQLite into Postgres")
    parser.add_argument("--sqlite", default=os.environ.get("DB_PATH", "news_bot.db"), help="Path to SQLite DB")
    parser.add_argument("--pg-dsn", default=os.environ.get("PG_DSN", "dbname=watchfuleye user=watchful password=watchfulpass host=localhost port=5432"), help="Postgres DSN")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for quick runs (0 = no limit)")
    args = parser.parse_args()

    limit = args.limit if args.limit and args.limit > 0 else None

    # Ensure schema exists
    ensure_postgres_schema(args.pg_dsn)

    # Read SQLite
    sqlite_conn = sqlite3.connect(args.sqlite)
    sqlite_conn.row_factory = sqlite3.Row

    with psycopg.connect(args.pg_dsn, autocommit=True) as pg_conn:
        a_ins, a_upd = _migrate_articles(sqlite_conn, pg_conn, limit=limit)
        n_ins, n_upd = _migrate_analyses(sqlite_conn, pg_conn, limit=limit)
        _bump_sequences(pg_conn)

        # Validation counts
        with sqlite_conn as sconn:
            scur = sconn.cursor()
            scur.execute("SELECT COUNT(*) FROM articles")
            sqlite_articles = int(scur.fetchone()[0] or 0)
            scur.execute("SELECT COUNT(*) FROM analyses")
            sqlite_analyses = int(scur.fetchone()[0] or 0)

        with pg_conn.cursor() as pcur:
            pcur.execute("SELECT COUNT(*) FROM articles")
            pg_articles = int(pcur.fetchone()[0] or 0)
            pcur.execute("SELECT COUNT(*) FROM analyses")
            pg_analyses = int(pcur.fetchone()[0] or 0)

    print("Backfill complete.")
    print(f"Articles: inserted={a_ins} updated={a_upd} | sqlite={sqlite_articles} postgres={pg_articles}")
    print(f"Analyses: inserted={n_ins} updated={n_upd} | sqlite={sqlite_analyses} postgres={pg_analyses}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())



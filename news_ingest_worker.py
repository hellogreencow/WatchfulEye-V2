#!/usr/bin/env python3
"""Multi-source ingestion worker (Phase 2).

Runs one ingestion cycle (or scheduled) to ingest:
- NewsAPI (breadth)
- RSS feeds (reputable + official)
- GDELT doc API (discovery)

Stores normalized article metadata into Postgres (fulltext extraction comes later).
"""

from __future__ import annotations

import os
import time
from dataclasses import asdict
from typing import Dict, List

import schedule
from dotenv import load_dotenv

from watchfuleye.ingestion.ingestors import GDELTIngestor, RSSIngestor, default_rss_feeds, NewsAPIIngestor
from watchfuleye.ingestion.url_utils import url_hash
from watchfuleye.storage.postgres_repo import PostgresRepo
from watchfuleye.storage.postgres_schema import ensure_postgres_schema


def _dedupe(items):
    seen = set()
    out = []
    for it in items:
        h = url_hash(it.url)
        if h in seen:
            continue
        seen.add(h)
        out.append(it)
    return out


def run_once() -> None:
    load_dotenv()
    pg_dsn = os.environ.get("PG_DSN", "dbname=watchfuleye user=watchful password=watchfulpass host=localhost port=5432")
    ensure_postgres_schema(pg_dsn)
    repo = PostgresRepo(pg_dsn)

    items = []

    # RSS first (reputable baseline)
    rss = RSSIngestor(default_rss_feeds())
    items.extend(rss.fetch(limit=200))

    # GDELT discovery (broad)
    gdelt = GDELTIngestor()
    items.extend(gdelt.fetch(limit=200, query="geopolitics OR markets OR sanctions OR central bank"))

    # NewsAPI (if key present)
    newsapi_key = os.environ.get("NEWSAPI_KEY", "").strip()
    if newsapi_key:
        news = NewsAPIIngestor(api_key=newsapi_key)
        items.extend(news.fetch(limit=100, query="geopolitics OR markets OR sanctions OR central bank"))

    items = _dedupe(items)

    # Upsert source domains (optional)
    domains = [it.source_domain for it in items if it.source_domain]
    repo.upsert_sources(domains)

    processed, total = repo.upsert_articles(items)
    print(f"[ingest] processed={processed} distinct_in_db={total}")


def run_scheduled() -> None:
    # Every 30 minutes: lightweight ingestion
    schedule.every(30).minutes.do(run_once)
    while True:
        schedule.run_pending()
        time.sleep(5)


if __name__ == "__main__":
    mode = (os.environ.get("INGEST_MODE") or "once").lower().strip()
    if mode in ("scheduled", "daemon"):
        run_scheduled()
    else:
        run_once()



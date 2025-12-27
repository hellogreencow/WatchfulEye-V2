#!/usr/bin/env python3
"""
Backfill Voyage embeddings into Supabase pgvector for WatchfulEye.

Why this exists:
- The SQLite corpus can be 100k+ rows, while pgvector may only contain a small subset.
- Semantic search quality is capped by pgvector coverage.

What it does:
- Reads articles from SQLite in batches (newest-first by id).
- For each batch, asks Supabase which article_ids already have embeddings.
- Embeds only missing articles using voyage-3-large (2048 dims).
- Upserts embeddings into Supabase `article_embeddings_voyage`.
- Persists progress to a local JSON file so it can resume safely.

Safety notes:
- This script can incur Voyage API cost proportional to the number of embedded articles.
- Start with a small `--max` for a cheap sanity check.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


def _load_env(env_path: str) -> None:
    try:
        from dotenv import load_dotenv
    except Exception as e:
        raise RuntimeError("python-dotenv is required (pip install python-dotenv)") from e
    load_dotenv(env_path)


def _read_sqlite_articles(db_path: str, max_id: int, batch_size: int) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        # Detect whether the `content` column exists (older DBs won't have it yet).
        try:
            cur.execute("PRAGMA table_info(articles)")
            cols = {r[1] for r in cur.fetchall()}
        except Exception:
            cols = set()
        has_content = "content" in cols

        select_cols = "id, title, description" + (", content" if has_content else "")
        cur.execute(
            """
            SELECT {cols}
            FROM articles
            WHERE id <= ?
            ORDER BY id DESC
            LIMIT ?
            """.format(cols=select_cols),
            (max_id, batch_size),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _get_sqlite_max_id(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT MAX(id) FROM articles")
        row = cur.fetchone()
        return int(row[0] or 0)
    finally:
        conn.close()


def _compose_text(a: Dict[str, Any], max_chars: int = 8000) -> str:
    parts: List[str] = []
    for key in ("title", "description", "content"):
        v = a.get(key)
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())
    text = "\n".join(parts).strip()
    return text[:max_chars]


def _chunk(seq: Sequence[Any], n: int) -> Iterable[Sequence[Any]]:
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


@dataclass
class Progress:
    cursor_id: int
    processed: int = 0
    embedded: int = 0
    skipped_existing: int = 0


def _load_progress(path: str, start_id: int) -> Progress:
    if not os.path.exists(path):
        return Progress(cursor_id=start_id)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        return Progress(
            cursor_id=int(data.get("cursor_id", start_id)),
            processed=int(data.get("processed", 0)),
            embedded=int(data.get("embedded", 0)),
            skipped_existing=int(data.get("skipped_existing", 0)),
        )
    except Exception:
        return Progress(cursor_id=start_id)


def _save_progress(path: str, p: Progress) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(
            {
                "cursor_id": p.cursor_id,
                "processed": p.processed,
                "embedded": p.embedded,
                "skipped_existing": p.skipped_existing,
                "updated_at": time.time(),
            },
            f,
        )
    os.replace(tmp, path)


def main() -> int:
    root = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="Backfill voyage-3-large embeddings into Supabase pgvector")
    parser.add_argument("--env", default=os.path.join(root, ".env"), help="Path to .env file")
    parser.add_argument("--db", default=None, help="Path to SQLite DB (defaults to DB_PATH in env)")
    parser.add_argument("--batch-size", type=int, default=500, help="SQLite batch size (article rows per step)")
    parser.add_argument("--embed-batch", type=int, default=64, help="Voyage embed batch size (texts per request)")
    parser.add_argument("--sleep", type=float, default=0.25, help="Sleep seconds between embed/upsert steps")
    parser.add_argument(
        "--max-backoff",
        type=float,
        default=60.0,
        help="Max seconds to back off when Supabase errors (adaptive throttling)",
    )
    parser.add_argument("--max", type=int, default=0, help="Max articles to embed this run (0 = unlimited)")
    parser.add_argument("--start-id", type=int, default=0, help="Start cursor id (0 = auto from MAX(id))")
    parser.add_argument(
        "--progress-file",
        default=os.path.join(root, "state", "embeddings_backfill.json"),
        help="Progress JSON file path",
    )
    args = parser.parse_args()

    _load_env(args.env)

    db_path = args.db or os.getenv("DB_PATH") or "news_bot.db"
    if not os.path.isabs(db_path):
        db_path = os.path.join(root, db_path)
    if not os.path.exists(db_path):
        raise RuntimeError(f"SQLite DB not found at {db_path}")

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    voyage_key = os.getenv("VOYAGE_API_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set for Supabase-only backfill")
    if not voyage_key:
        raise RuntimeError("VOYAGE_API_KEY must be set to embed with voyage-3-large")

    from supabase import create_client  # type: ignore

    supabase = create_client(supabase_url, supabase_key)
    vo = __import__("voyageai").Client(api_key=voyage_key)  # avoid import issues in some envs

    table = "article_embeddings_voyage"

    start_id = args.start_id if args.start_id > 0 else _get_sqlite_max_id(db_path)
    if start_id <= 0:
        print("No articles found in SQLite (MAX(id)=0).")
        return 0

    progress = _load_progress(args.progress_file, start_id=start_id)
    cursor_id = progress.cursor_id
    if cursor_id <= 0:
        cursor_id = start_id

    print(f"DB: {db_path}")
    print(f"Supabase table: {table}")
    print(f"Starting cursor_id: {cursor_id}")
    print(f"Batch size: sqlite={args.batch_size}, voyage={args.embed_batch}")
    print(f"Max embeds this run: {args.max if args.max > 0 else 'unlimited'}")
    print(f"Adaptive backoff: base={args.sleep}s max={args.max_backoff}s")

    embedded_this_run = 0
    supabase_backoff = max(0.0, float(args.sleep))
    while cursor_id > 0:
        rows = _read_sqlite_articles(db_path, max_id=cursor_id, batch_size=args.batch_size)
        if not rows:
            break

        ids = [int(r["id"]) for r in rows if r.get("id") is not None]
        if not ids:
            break

        # Compute next cursor but do NOT advance it until this batch is safely processed.
        next_cursor_id = min(ids) - 1

        # Find which already exist in Supabase (batch query)
        existing: Set[int] = set()
        while True:
            try:
                resp = supabase.table(table).select("article_id").in_("article_id", ids).execute()
                for r in (resp.data or []):
                    try:
                        existing.add(int(r["article_id"]))
                    except Exception:
                        continue
                # Successful Supabase call: slowly relax backoff toward baseline
                supabase_backoff = max(float(args.sleep), supabase_backoff * 0.8)
                break
            except Exception as e:
                print(f"[warn] Supabase existence query failed (will retry after backoff): {e}")
                # Back off aggressively on Supabase instability to avoid making it worse.
                supabase_backoff = min(max(1.0, supabase_backoff * 2.0), float(args.max_backoff))
                time.sleep(supabase_backoff)

        missing = [r for r in rows if int(r["id"]) not in existing]
        # If everything already exists, we can safely advance the cursor for this batch.
        if not missing:
            progress.processed += len(rows)
            progress.skipped_existing += len(rows)
            cursor_id = next_cursor_id
            progress.cursor_id = cursor_id
            _save_progress(args.progress_file, progress)
            continue

        # Build text payload for Voyage
        texts: List[str] = []
        missing_ids: List[int] = []
        for r in missing:
            txt = _compose_text(r)
            if not txt:
                continue
            missing_ids.append(int(r["id"]))
            texts.append(txt)

        # Embed + upsert in chunks
        for chunk_ids, chunk_texts in zip(_chunk(missing_ids, args.embed_batch), _chunk(texts, args.embed_batch)):
            if args.max > 0 and embedded_this_run >= args.max:
                print("Reached --max limit for this run. Stopping.")
                progress.cursor_id = cursor_id
                _save_progress(args.progress_file, progress)
                return 0

            # Respect --max precisely by trimming the chunk
            if args.max > 0:
                remaining = max(0, args.max - embedded_this_run)
                if remaining <= 0:
                    continue
                if len(chunk_ids) > remaining:
                    chunk_ids = chunk_ids[:remaining]
                    chunk_texts = chunk_texts[:remaining]

            # Embed (retry on transient failures)
            while True:
                try:
                    emb_res = vo.embed(texts=list(chunk_texts), model="voyage-3-large")
                    embeddings = emb_res.embeddings
                    break
                except Exception as e:
                    print(f"[warn] Voyage embed failed (will retry after backoff): {e}")
                    time.sleep(max(1.0, float(args.sleep)))

            payload = []
            for aid, vec in zip(chunk_ids, embeddings):
                payload.append({"article_id": int(aid), "embedding": vec})

            # Upsert (retry; DO NOT drop the chunk, otherwise we'll create permanent holes)
            while True:
                try:
                    supabase.table(table).upsert(payload).execute()
                    progress.embedded += len(payload)
                    embedded_this_run += len(payload)
                    # Successful Supabase write: slowly relax backoff toward baseline
                    supabase_backoff = max(float(args.sleep), supabase_backoff * 0.8)
                    break
                except Exception as e:
                    print(f"[warn] Supabase upsert failed (will retry after backoff): {e}")
                    supabase_backoff = min(max(1.0, supabase_backoff * 2.0), float(args.max_backoff))
                    time.sleep(supabase_backoff)

            _save_progress(args.progress_file, progress)
            if supabase_backoff > 0:
                time.sleep(supabase_backoff)

        # Batch is safely processed; now advance cursor.
        progress.processed += len(rows)
        progress.skipped_existing += (len(rows) - len(missing))
        cursor_id = next_cursor_id
        progress.cursor_id = cursor_id
        _save_progress(args.progress_file, progress)

        # Progress output every batch
        if progress.processed % (args.batch_size * 10) == 0:
            print(
                f"cursor_id={progress.cursor_id} processed={progress.processed} "
                f"embedded_total={progress.embedded} skipped_existing={progress.skipped_existing}"
            )

    _save_progress(args.progress_file, progress)
    print(
        f"Done. processed={progress.processed} embedded_total={progress.embedded} "
        f"skipped_existing={progress.skipped_existing} cursor_id={progress.cursor_id}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130)



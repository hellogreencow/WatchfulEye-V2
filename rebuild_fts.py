#!/usr/bin/env python3
"""
Rebuild SQLite FTS5 index for WatchfulEye.

Why:
- If the FTS5 virtual table exists but its shadow index tables are empty,
  `MATCH` will return 0 results even though rows appear selectable.
- This rebuild forces FTS to index all documents again.

What it does:
- Runs: INSERT INTO articles_fts(articles_fts) VALUES('rebuild');
- Prints before/after index row counts for quick verification.

This can take minutes on 100k+ documents.
"""

from __future__ import annotations

import os
import sqlite3
import time


def _count(cur: sqlite3.Cursor, table: str) -> int:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return int(cur.fetchone()[0] or 0)
    except Exception:
        return -1


def main() -> int:
    root = os.path.dirname(os.path.abspath(__file__))
    db_path = os.environ.get("DB_PATH", "news_bot.db")
    if not os.path.isabs(db_path):
        db_path = os.path.join(root, db_path)

    print(f"DB: {db_path}")
    t0 = time.time()

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        # Sanity: ensure FTS exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='articles_fts'")
        if not cur.fetchone():
            raise RuntimeError("articles_fts does not exist. Start backend once to initialize FTS, then retry.")

        before_idx = _count(cur, "articles_fts_idx")
        before_doc = _count(cur, "articles_fts_docsize")
        before_rows = _count(cur, "articles_fts")
        print(f"Before: articles_fts rows={before_rows}, idx={before_idx}, docsize={before_doc}")

        print("Rebuilding FTS index…")
        cur.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")
        conn.commit()

        after_idx = _count(cur, "articles_fts_idx")
        after_doc = _count(cur, "articles_fts_docsize")
        after_rows = _count(cur, "articles_fts")
        print(f"After:  articles_fts rows={after_rows}, idx={after_idx}, docsize={after_doc}")

        dt = time.time() - t0
        print(f"Done in {dt:.1f}s")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())



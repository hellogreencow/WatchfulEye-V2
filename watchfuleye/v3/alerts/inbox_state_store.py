"""WS6: in-app delivery state for alerts (reliable inbox semantics).

We keep "what has this user already seen?" in SQLite (DB_PATH) because:
- user/session auth is already in SQLite
- it's cheap, local, and doesn't require Postgres schema changes

The alert_events themselves remain the durable system log in Postgres.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path() -> str:
    return os.environ.get("DB_PATH", "news_bot.db")


def ensure_inbox_state_schema(db_path: str | None = None) -> None:
    path = db_path or _db_path()
    with sqlite3.connect(path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS v3_alert_inbox_state (
              user_id INTEGER PRIMARY KEY,
              last_seen_event_id INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def get_last_seen_event_id(*, user_id: int, db_path: str | None = None) -> int:
    ensure_inbox_state_schema(db_path)
    path = db_path or _db_path()
    with sqlite3.connect(path) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT last_seen_event_id FROM v3_alert_inbox_state WHERE user_id = ?",
            (int(user_id),),
        )
        row = cur.fetchone()
        if not row:
            return 0
        return int(row[0] or 0)


def set_last_seen_event_id(*, user_id: int, last_seen_event_id: int, db_path: str | None = None) -> int:
    """Set last seen id, but never allow it to go backwards.

    Returns the stored value.
    """
    ensure_inbox_state_schema(db_path)
    path = db_path or _db_path()
    uid = int(user_id)
    new_val = max(0, int(last_seen_event_id))

    with sqlite3.connect(path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT last_seen_event_id FROM v3_alert_inbox_state WHERE user_id = ?", (uid,))
        row = cur.fetchone()
        current = int(row[0] or 0) if row else 0
        final = max(current, new_val)

        cur.execute(
            """
            INSERT INTO v3_alert_inbox_state (user_id, last_seen_event_id, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
              last_seen_event_id = excluded.last_seen_event_id,
              updated_at = excluded.updated_at
            """,
            (uid, final, _utcnow_iso()),
        )
        conn.commit()

    return final



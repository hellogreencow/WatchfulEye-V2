"""Encrypted API key storage for V3 (SQLite-backed).

We intentionally store API keys in the existing SQLite DB (`DB_PATH`) to avoid:
- New Postgres schema surface area for secrets
- Extra migrations for what is fundamentally ops/config

Keys are stored in table `v3_api_keys` as Fernet-encrypted ciphertext.
The encryption key must be provided via `V3_API_KEYS_ENCRYPTION_KEY`.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Any

from cryptography.fernet import Fernet
 
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS v3_api_keys (
  name TEXT PRIMARY KEY,
  ciphertext TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_by TEXT
);
"""


def upsert_api_key(db_path: str, *, name: str, plaintext: str, updated_by: str | None) -> None:
    """Insert/update an encrypted API key value."""
    ciphertext = encrypt_value(plaintext)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        _ensure_schema(cur)
        cur.execute(
            """
            INSERT INTO v3_api_keys (name, ciphertext, updated_by, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(name) DO UPDATE SET
              ciphertext=excluded.ciphertext,
              updated_by=excluded.updated_by,
              updated_at=CURRENT_TIMESTAMP
            """,
            (name, ciphertext, updated_by),
        )
        conn.commit()


def get_api_key_record(db_path: str, *, name: str) -> dict[str, Any] | None:
    """Return key record metadata (no decryption)."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        _ensure_schema(cur)
        cur.execute(
            "SELECT name, ciphertext, created_at, updated_at, updated_by FROM v3_api_keys WHERE name=?",
            (name,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_api_key_plaintext(db_path: str, *, name: str) -> str | None:
    """Return decrypted key value, or None if missing."""
    rec = get_api_key_record(db_path, name=name)
    if not rec:
        return None
    ct = rec.get("ciphertext")
    if not isinstance(ct, str) or not ct:
        return None
    try:
        return decrypt_value(ct)
    except Exception:
        return None


def list_api_keys(db_path: str) -> list[dict[str, Any]]:
    """List stored API key names + timestamps (no plaintext)."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        _ensure_schema(cur)
        cur.execute("SELECT name, created_at, updated_at, updated_by FROM v3_api_keys ORDER BY updated_at DESC")
        return [dict(r) for r in (cur.fetchall() or [])]


def encrypt_value(plaintext: str) -> str:
    f = _get_fernet()
    token = f.encrypt((plaintext or "").encode("utf-8"))
    return token.decode("utf-8")


def decrypt_value(ciphertext: str) -> str:
    f = _get_fernet()
    out = f.decrypt((ciphertext or "").encode("utf-8"))
    return out.decode("utf-8")


def is_encryption_configured() -> bool:
    return bool(os.environ.get("V3_API_KEYS_ENCRYPTION_KEY"))


def _get_fernet() -> Fernet:
    key = os.environ.get("V3_API_KEYS_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("V3_API_KEYS_ENCRYPTION_KEY not configured")
    return Fernet(key.encode("utf-8"))


def _iso(dt: Any) -> str | None:
    if isinstance(dt, datetime):
        try:
            return dt.isoformat()
        except Exception:
            return str(dt)
    return None


def _ensure_schema(cur: sqlite3.Cursor) -> None:
    cur.execute(_SCHEMA_SQL)



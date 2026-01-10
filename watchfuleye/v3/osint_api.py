"""WS5: OSINT ingestion API (no scraping).

This is a governed ingestion surface:
- We do NOT scrape X/Twitter directly.
- We accept upstream-collected payloads (manual paste, compliant API provider, or internal collector).
- We store raw payloads in Postgres `osint_posts` for auditability.
- We can optionally "promote" a post into `articles` to enter the Evidence pipeline.

Flag gates:
- `V3_CONNECTORS` and `V3_OSINT` must be enabled.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg
from flask import Blueprint, jsonify, request
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from watchfuleye.storage.postgres_schema import ensure_postgres_schema
from watchfuleye.v3.flags import is_v3_connectors_enabled, is_v3_osint_enabled


bp_v3_osint = Blueprint("v3_osint", __name__, url_prefix="/api/v3/osint")


@bp_v3_osint.route("/posts/ingest", methods=["POST"])
def ingest_osint_posts():
    if not (is_v3_connectors_enabled() and is_v3_osint_enabled()):
        return ("Not Found", 404)

    payload: Any = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    platform = str(payload.get("platform") or "x").strip().lower()
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return jsonify({"error": "items must be a non-empty list"}), 400

    pg_dsn = os.environ.get("PG_DSN")
    if not pg_dsn:
        return jsonify({"error": "PG_DSN not configured"}), 500

    ensure_postgres_schema(pg_dsn)

    upserted = 0
    errors: list[str] = []

    with psycopg.connect(pg_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            for it in items:
                try:
                    if not isinstance(it, dict):
                        continue
                    handle = str(it.get("handle") or "").strip().lstrip("@")
                    post_id = str(it.get("post_id") or it.get("id") or "").strip()
                    if not handle or not post_id:
                        continue
                    url = it.get("url")
                    content_text = it.get("text") or it.get("content_text") or it.get("content")
                    posted_at = _parse_dt(it.get("posted_at") or it.get("created_at"))
                    raw = it.get("raw") if isinstance(it.get("raw"), dict) else it

                    row_id = it.get("row_id")
                    if not isinstance(row_id, str) or not row_id:
                        row_id = f"osint_{uuid.uuid4().hex}"

                    cur.execute(
                        """
                        INSERT INTO osint_posts (
                          id, platform, handle, post_id, url, content_text, posted_at, raw
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (platform, handle, post_id) DO UPDATE
                          SET url = EXCLUDED.url,
                              content_text = EXCLUDED.content_text,
                              posted_at = EXCLUDED.posted_at,
                              raw = EXCLUDED.raw,
                              fetched_at = now()
                        """,
                        (
                            row_id,
                            platform,
                            handle,
                            post_id,
                            str(url) if url else None,
                            str(content_text) if content_text else None,
                            posted_at,
                            Jsonb(raw if isinstance(raw, dict) else {"raw": raw}),
                        ),
                    )
                    upserted += 1
                except Exception as e:
                    errors.append(str(e))
        conn.commit()

    return jsonify({"upserted": upserted, "errors": errors[:20]}), 200


@bp_v3_osint.route("/posts/recent", methods=["GET"])
def list_recent_posts():
    if not (is_v3_connectors_enabled() and is_v3_osint_enabled()):
        return ("Not Found", 404)

    pg_dsn = os.environ.get("PG_DSN")
    if not pg_dsn:
        return jsonify({"error": "PG_DSN not configured"}), 500
    ensure_postgres_schema(pg_dsn)

    handle = request.args.get("handle")
    limit = min(max(int(request.args.get("limit", "50")), 1), 200)

    with psycopg.connect(pg_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            if handle:
                cur.execute(
                    """
                    SELECT id, platform, handle, post_id, url, content_text, posted_at, fetched_at, promoted_article_id, promoted_at
                    FROM osint_posts
                    WHERE handle = %s
                    ORDER BY posted_at DESC NULLS LAST, fetched_at DESC
                    LIMIT %s
                    """,
                    (handle.lstrip("@"), limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id, platform, handle, post_id, url, content_text, posted_at, fetched_at, promoted_article_id, promoted_at
                    FROM osint_posts
                    ORDER BY posted_at DESC NULLS LAST, fetched_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            rows = cur.fetchall()
    return jsonify({"items": rows}), 200


@bp_v3_osint.route("/posts/<post_row_id>/promote", methods=["POST"])
def promote_post_to_article(post_row_id: str):
    if not (is_v3_connectors_enabled() and is_v3_osint_enabled()):
        return ("Not Found", 404)

    pg_dsn = os.environ.get("PG_DSN")
    if not pg_dsn:
        return jsonify({"error": "PG_DSN not configured"}), 500
    ensure_postgres_schema(pg_dsn)

    with psycopg.connect(pg_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, platform, handle, post_id, url, content_text, posted_at
                FROM osint_posts
                WHERE id = %s
                """,
                (post_row_id,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "not found"}), 404

            canonical_url = row.get("url") or _fallback_x_url(row.get("handle"), row.get("post_id"))
            title = f"OSINT @{row.get('handle')}: {str(row.get('content_text') or '')[:80]}".strip()
            excerpt = (row.get("content_text") or "")[:280] if row.get("content_text") else None
            url_hash = _sha256_hex(str(canonical_url))
            raw = {
                "osint": True,
                "platform": row.get("platform"),
                "handle": row.get("handle"),
                "post_id": row.get("post_id"),
                "source": "osint_x",
                "promoted_at": datetime.now(timezone.utc).isoformat(),
            }

            cur.execute(
                """
                INSERT INTO articles (
                  canonical_url, url_hash, title, description, excerpt,
                  published_at, source_domain, source_name, ingestion_source, raw
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT (canonical_url) DO UPDATE
                  SET updated_at = now()
                RETURNING id
                """,
                (
                    str(canonical_url),
                    url_hash,
                    title or "OSINT post",
                    None,
                    excerpt,
                    row.get("posted_at"),
                    "x.com",
                    f"@{row.get('handle')}",
                    "osint_x",
                    Jsonb(raw),
                ),
            )
            article_id = int(cur.fetchone()["id"])

            cur.execute(
                """
                UPDATE osint_posts
                SET promoted_article_id = %s, promoted_at = now()
                WHERE id = %s
                """,
                (article_id, post_row_id),
            )
        conn.commit()

    return jsonify({"article_id": article_id}), 200


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _parse_dt(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc) if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, (int, float)):
        # epoch seconds
        try:
            return datetime.fromtimestamp(float(v), tz=timezone.utc)
        except Exception:
            return None
    if isinstance(v, str) and v.strip():
        s = v.strip()
        # best-effort ISO parse (common case from upstream collectors)
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _fallback_x_url(handle: Any, post_id: Any) -> str:
    h = str(handle or "").lstrip("@") or "unknown"
    pid = str(post_id or "")
    return f"https://x.com/{h}/status/{pid}"



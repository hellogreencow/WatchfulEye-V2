"""WS4: Evidence retrieval for V3 Examine.

Evidence-first constraint:
- Prefer returning *small, citeable* items (title/source/url/date/snippet).
- Never hard-fail if Postgres is missing/unreachable/misconfigured.
"""

from __future__ import annotations

from typing import Any, Optional, Tuple


def _clamp_int(val: Any, *, default: int, lo: int, hi: int) -> int:
    try:
        n = int(val)
    except Exception:
        n = int(default)
    return max(int(lo), min(int(n), int(hi)))


def fetch_evidence(pg_dsn: str, q: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch evidence items for query `q`.

    Returns [] on any error (including no matching rows).
    """
    items, _err = fetch_evidence_detailed(pg_dsn, q, limit=limit)
    return items


def fetch_evidence_detailed(
    pg_dsn: str,
    q: str,
    limit: int = 10,
) -> Tuple[list[dict[str, Any]], Optional[str]]:
    """Fetch evidence and an error code (if any).

    Error codes are intentionally coarse (safe to persist/return without leaking DSNs):
    - None: success (rows may be empty)
    - "psycopg_unavailable"
    - "postgres_unavailable"
    """
    q_s = (q or "").strip()
    if len(q_s) < 2:
        return [], None

    limit_i = _clamp_int(limit, default=10, lo=1, hi=50)

    try:
        import psycopg  # type: ignore
    except Exception:
        return [], "psycopg_unavailable"

    # NOTE: This mirrors the app's existing FTS query path (see watchfuleye/storage/postgres_articles.py)
    sql = """
    SELECT id, title, canonical_url, source_name, source_domain, published_at, created_at,
           COALESCE(excerpt, description, '') AS snippet,
           ts_rank_cd(search_tsv, websearch_to_tsquery('english', %s)) AS rank
    FROM articles
    WHERE search_tsv @@ websearch_to_tsquery('english', %s)
    ORDER BY rank DESC, created_at DESC
    LIMIT %s
    """

    try:
        with psycopg.connect(pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (q_s, q_s, int(limit_i)))
                rows = cur.fetchall()
    except Exception:
        return [], "postgres_unavailable"

    out: list[dict[str, Any]] = []
    for row in rows:
        (
            aid,
            title,
            canonical_url,
            source_name,
            source_domain,
            published_at,
            _created_at,
            snippet,
            _rank,
        ) = row
        src = source_name or source_domain or "Unknown"
        published_at_s: Optional[str]
        if published_at is None:
            published_at_s = None
        else:
            try:
                published_at_s = published_at.isoformat()
            except Exception:
                published_at_s = None

        sn = (snippet or "").strip()
        if len(sn) > 320:
            sn = sn[:317].rstrip() + "..."

        out.append(
            {
                "id": int(aid) if aid is not None else None,
                "title": (title or "").strip(),
                "url": (canonical_url or "").strip(),
                "source_name": str(src).strip(),
                "published_at": published_at_s,
                "snippet": sn,
            }
        )

    return out, None



"""CI smoke: alerts schema + minimal trigger path.

This intentionally avoids running the Flask server. It validates:
- Postgres is reachable via PG_DSN
- ensure_postgres_schema() runs cleanly (extensions + tables + indexes)
- alert_rules + term_trends can drive writing alert_events (minimal inline evaluator)

This is a hard gate intended to prevent "green unit tests" while the actual
retention engine path is broken.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from watchfuleye.storage.postgres_schema import ensure_postgres_schema


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _eval_term_trend_inline(conn: psycopg.Connection[dict[str, object]], *, rule_id: str) -> int:
    """Minimal inline evaluator for term_trend rules.

    We intentionally keep this tiny and deterministic to avoid flake in CI.
    WS6's real evaluator is tested in PR #36; this job is a schema + I/O tripwire.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT config FROM alert_rules WHERE id=%s AND enabled=TRUE", (rule_id,))
        row = cur.fetchone()
        if not row:
            return 0
        config = row.get("config") or {}
        threshold = float(config.get("threshold", 3.0))
        min_count = int(config.get("min_count", 1))

        cur.execute(
            """
            SELECT term, window_start, window_end, count, z_score
            FROM term_trends
            WHERE z_score IS NOT NULL
              AND z_score >= %s
              AND count >= %s
            ORDER BY z_score DESC
            LIMIT 5
            """,
            (threshold, min_count),
        )
        trends = cur.fetchall()

    if not trends:
        return 0

    now = _utcnow()
    written = 0
    for t in trends:
        payload = {
            "rule_type": "term_trend",
            "term": t.get("term"),
            "window_start": t.get("window_start").isoformat() if t.get("window_start") else None,
            "window_end": t.get("window_end").isoformat() if t.get("window_end") else None,
            "count": t.get("count"),
            "z_score": t.get("z_score"),
            "source": "ci_smoke_inline_eval",
        }
        with conn.cursor() as cur2:
            cur2.execute(
                """
                INSERT INTO alert_events (rule_id, event_type, payload, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (rule_id, "fired", Jsonb(payload), now),
            )
        written += 1
    return written


def main() -> int:
    pg_dsn = os.environ.get("PG_DSN")
    if not pg_dsn:
        raise RuntimeError("PG_DSN not configured")

    # Schema must be runnable in CI (extensions included).
    ensure_postgres_schema(pg_dsn)

    rule_id = "ci_smoke_rule_term_trend"
    term = "ci_smoke_term"
    now = _utcnow()
    window_start = now - timedelta(hours=1)
    window_end = now

    with psycopg.connect(pg_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            # Seed one high-z-score term trend in the lookback window.
            cur.execute(
                """
                INSERT INTO term_trends (term, window_start, window_end, count, z_score, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (term, window_start, window_end) DO UPDATE SET
                  count=excluded.count,
                  z_score=excluded.z_score,
                  created_at=excluded.created_at
                """,
                (term, window_start, window_end, 10, 5.0, now),
            )

            # Seed an enabled rule that should fire on that trend row.
            cur.execute(
                """
                INSERT INTO alert_rules (id, name, enabled, rule_type, config, channels, created_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                  enabled=excluded.enabled,
                  rule_type=excluded.rule_type,
                  config=excluded.config,
                  channels=excluded.channels,
                  updated_at=excluded.updated_at
                """,
                (
                    rule_id,
                    "CI Smoke: term_trend fires",
                    True,
                    "term_trend",
                    Jsonb({"threshold": 3.0, "min_count": 1, "lookback_hours": 24}),
                    ["in_app"],
                    "ci",
                    now,
                    now,
                ),
            )

            # Ensure a clean assertion surface.
            cur.execute("DELETE FROM alert_events WHERE rule_id=%s", (rule_id,))
        conn.commit()

    with psycopg.connect(pg_dsn, row_factory=dict_row) as conn3:
        wrote = _eval_term_trend_inline(conn3, rule_id=rule_id)
        conn3.commit()

    with psycopg.connect(pg_dsn, row_factory=dict_row) as conn2:
        with conn2.cursor() as cur2:
            cur2.execute("SELECT COUNT(*) AS n FROM alert_events WHERE rule_id=%s", (rule_id,))
            row = cur2.fetchone()
            n = int((row or {}).get("n") or 0)

    if n < 1:
        raise RuntimeError("expected >= 1 alert_event from term_trend rule, got 0")

    print(
        "OK: alerts schema smoke passed",
        {"events_written": n, "events_written_by_inline_eval": wrote},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



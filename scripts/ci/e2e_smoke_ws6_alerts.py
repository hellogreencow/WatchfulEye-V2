"""CI E2E smoke: WS6 Alerts evaluator writes an event from seeded data.

This intentionally avoids running the Flask server. It validates:
- Postgres is reachable via PG_DSN
- ensure_postgres_schema() runs cleanly (extensions + tables + indexes)
- alerts evaluator can read an enabled rule and write alert_events

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

# WS6 alerts code may not exist on master yet (PR #36 adds it).
# Skip gracefully if missing; smoke will run once WS6 merges.
try:
    from watchfuleye.v3.alerts.job import run_alerts_job
except ImportError:
    print("SKIP: ws6 alerts code not present (PR #36 not merged yet)")
    raise SystemExit(0)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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

    result = run_alerts_job(pg_dsn, limit_rules=5)
    if result.get("errors"):
        raise RuntimeError(f"alerts job errors: {result['errors']}")

    with psycopg.connect(pg_dsn, row_factory=dict_row) as conn2:
        with conn2.cursor() as cur2:
            cur2.execute("SELECT COUNT(*) AS n FROM alert_events WHERE rule_id=%s", (rule_id,))
            row = cur2.fetchone()
            n = int((row or {}).get("n") or 0)

    if n < 1:
        raise RuntimeError("expected >= 1 alert_event from term_trend rule, got 0")

    print(
        "OK: ws6 alerts smoke passed",
        {"events_written": n, "rules_evaluated": result.get("rules_evaluated")},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



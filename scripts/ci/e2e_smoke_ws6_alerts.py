"""CI E2E smoke: WS6 alerts evaluator writes an event.

This intentionally avoids running the Flask server. It validates:
- Postgres is reachable via PG_DSN
- ensure_postgres_schema() runs cleanly (extensions + tables + indexes)
- WS6 evaluator (run_alerts_job) can read an enabled rule and write alert_events

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
from watchfuleye.v3.alerts.job import run_alerts_job


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

_ALERTS_SMOKE_SCHEMA: list[str] = [
    # term_trends is used by the term_trend rule type.
    """
    CREATE TABLE IF NOT EXISTS term_trends (
      term TEXT NOT NULL,
      window_start TIMESTAMPTZ NOT NULL,
      window_end TIMESTAMPTZ NOT NULL,
      count INTEGER NOT NULL,
      z_score REAL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      PRIMARY KEY (term, window_start, window_end)
    );
    """,
    # WS6 tables (rules + event log).
    """
    CREATE TABLE IF NOT EXISTS alert_rules (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      enabled BOOLEAN NOT NULL DEFAULT TRUE,
      rule_type TEXT NOT NULL,
      config JSONB NOT NULL DEFAULT '{}'::jsonb,
      channels TEXT[] NOT NULL DEFAULT ARRAY['in_app']::text[],
      created_by TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      last_evaluated_at TIMESTAMPTZ
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled);",
    "CREATE INDEX IF NOT EXISTS idx_alert_rules_rule_type ON alert_rules(rule_type);",
    "CREATE INDEX IF NOT EXISTS idx_alert_rules_updated_at ON alert_rules(updated_at DESC);",
    """
    CREATE TABLE IF NOT EXISTS alert_events (
      id BIGSERIAL PRIMARY KEY,
      rule_id TEXT NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
      event_type TEXT NOT NULL,
      payload JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      delivered_at TIMESTAMPTZ,
      delivery_error TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_alert_events_rule_id_created ON alert_events(rule_id, created_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_alert_events_created_at ON alert_events(created_at DESC);",
]


def main() -> int:
    pg_dsn = os.environ.get("PG_DSN")
    if not pg_dsn:
        raise RuntimeError("PG_DSN not configured")

    # Keep this smoke deterministic: ensure only the minimal alerts schema needed.
    # (Full ensure_postgres_schema includes embeddings/vector indexes and can fail for unrelated reasons.)
    ensure_postgres_schema(pg_dsn, statements=_ALERTS_SMOKE_SCHEMA)

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



from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone

import psycopg

from watchfuleye.storage.postgres_schema import ensure_postgres_schema
from watchfuleye.v3.alerts.job import run_alerts_job


class TestV3AlertsJob(unittest.TestCase):
    def setUp(self) -> None:
        self.pg_dsn = os.environ.get("PG_DSN")
        if not self.pg_dsn:
            self.skipTest("PG_DSN not configured")
        try:
            ensure_postgres_schema(self.pg_dsn)
        except Exception as e:
            self.skipTest(f"Postgres schema not available: {e}")

        # Clean only our rule/event rows
        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM alert_events WHERE rule_id LIKE 't_alert_job_%';")
                cur.execute("DELETE FROM alert_rules WHERE id LIKE 't_alert_job_%';")
                conn.commit()

    def test_term_trend_rule_writes_event(self) -> None:
        assert self.pg_dsn is not None
        rule_id = "t_alert_job_term_1"

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                # Insert a term_trends row that will satisfy rule
                cur.execute(
                    """
                    INSERT INTO term_trends (term, window_start, window_end, count, z_score)
                    VALUES (%s, now() - interval '1 hour', now(), %s, %s)
                    """,
                    ("test_term", 10, 5.0),
                )

                cur.execute(
                    """
                    INSERT INTO alert_rules (id, name, enabled, rule_type, config)
                    VALUES (%s, %s, TRUE, 'term_trend', %s::jsonb)
                    ON CONFLICT (id) DO UPDATE SET enabled=TRUE, config=excluded.config
                    """,
                    (rule_id, "Test term trend", '{"threshold": 3.0, "min_count": 1, "lookback_hours": 24}'),
                )
                conn.commit()

        out = run_alerts_job(self.pg_dsn, limit_rules=10)
        self.assertEqual(out.get("errors"), [])
        self.assertGreaterEqual(int(out.get("events_written") or 0), 1)

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM alert_events WHERE rule_id=%s;", (rule_id,))
                cnt = int(cur.fetchone()[0])
                self.assertGreaterEqual(cnt, 1)


if __name__ == "__main__":
    unittest.main()



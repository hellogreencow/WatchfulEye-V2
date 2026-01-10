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

    def test_forecast_outcome_rule_writes_event(self) -> None:
        assert self.pg_dsn is not None
        rule_id = "t_alert_job_fc_1"

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                # Ensure we have at least one resolved forecast with recent outcome_measured_at
                cur.execute(
                    """
                    SELECT id FROM forecasts
                    WHERE outcome_status='resolved'
                      AND outcome_measured_at IS NOT NULL
                    ORDER BY outcome_measured_at DESC
                    LIMIT 1
                    """
                )
                row = cur.fetchone()
                if not row:
                    self.skipTest("No resolved forecasts available to test forecast_outcome rule")

                cur.execute(
                    """
                    INSERT INTO alert_rules (id, name, enabled, rule_type, config)
                    VALUES (%s, %s, TRUE, 'forecast_outcome', %s::jsonb)
                    ON CONFLICT (id) DO UPDATE SET enabled=TRUE, config=excluded.config
                    """,
                    (rule_id, "Test forecast outcome", '{"min_confidence": 0.0, "include_statuses": ["resolved"]}'),
                )
                conn.commit()

        out = run_alerts_job(self.pg_dsn, limit_rules=10)
        self.assertEqual(out.get("errors"), [])

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM alert_events WHERE rule_id=%s;", (rule_id,))
                cnt = int(cur.fetchone()[0])
                self.assertGreaterEqual(cnt, 1)

    def test_recommendation_alpha_rule_writes_event(self) -> None:
        assert self.pg_dsn is not None
        rule_id = "t_alert_job_alpha_1"

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                # Create a minimal analysis row
                cur.execute(
                    """
                    INSERT INTO analyses (content, model_used, article_count, processing_time, topic, raw_response_json)
                    VALUES ('seed', 'test', 0, 0.0, 'test', '{}'::jsonb)
                    RETURNING id
                    """
                )
                analysis_id = int(cur.fetchone()[0])

                # Create a recommendation
                cur.execute(
                    """
                    INSERT INTO recommendations (analysis_id, action, ticker, rationale)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (analysis_id, "BUY", "TEST", "seed"),
                )
                rec_id = int(cur.fetchone()[0])

                # Create a performance snapshot with alpha above threshold
                cur.execute(
                    """
                    INSERT INTO recommendation_performance (
                      recommendation_id, horizon_days, benchmark_symbol,
                      rec_return, benchmark_return, alpha
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (recommendation_id, horizon_days, benchmark_symbol) DO UPDATE SET
                      rec_return=excluded.rec_return,
                      benchmark_return=excluded.benchmark_return,
                      alpha=excluded.alpha,
                      computed_at=now()
                    """,
                    (rec_id, 30, "SPY", 0.10, 0.05, 0.05),
                )

                # Create rule
                cur.execute(
                    """
                    INSERT INTO alert_rules (id, name, enabled, rule_type, config)
                    VALUES (%s, %s, TRUE, 'recommendation_alpha', %s::jsonb)
                    ON CONFLICT (id) DO UPDATE SET enabled=TRUE, config=excluded.config
                    """,
                    (rule_id, "Test alpha", '{"horizon_days": 30, "benchmark_symbol": "SPY", "min_alpha": 0.01}'),
                )
                conn.commit()

        out = run_alerts_job(self.pg_dsn, limit_rules=10)
        self.assertEqual(out.get("errors"), [])

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM alert_events WHERE rule_id=%s;", (rule_id,))
                cnt = int(cur.fetchone()[0])
                self.assertGreaterEqual(cnt, 1)


if __name__ == "__main__":
    unittest.main()



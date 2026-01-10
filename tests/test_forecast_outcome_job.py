from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import psycopg


class TestForecastOutcomeJob(unittest.TestCase):
    def setUp(self) -> None:
        self.pg_dsn = os.environ.get("PG_DSN")
        if self.pg_dsn:
            try:
                with psycopg.connect(self.pg_dsn):
                    pass
            except Exception:
                self.pg_dsn = None
        # Always enable WS6.1 for these tests (they are explicitly about the job behavior).
        os.environ["V3_FORECAST_TRACKING"] = "true"

    def tearDown(self) -> None:
        os.environ.pop("V3_FORECAST_TRACKING", None)
        if not self.pg_dsn:
            return
        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM forecast_updates WHERE updated_by='system:forecast_outcome_job'")
                cur.execute("DELETE FROM forecasts WHERE created_by='test:outcome_job'")
                cur.execute("DELETE FROM v3_reports WHERE id LIKE 'rep_test_outcome_job_%'")
                cur.execute("DELETE FROM v3_investigations WHERE id LIKE 'inv_test_outcome_job_%'")
            conn.commit()

    def test_job_updates_forecast_and_writes_audit(self) -> None:
        if not self.pg_dsn:
            self.skipTest("PG_DSN not configured")

        from watchfuleye.storage.postgres_schema import ensure_postgres_schema
        from watchfuleye.v3.forecast.outcome_job import run_forecast_outcome_job

        ensure_postgres_schema(self.pg_dsn)

        now = datetime.now(timezone.utc)
        past = now - timedelta(days=2)

        inv_id = "inv_test_outcome_job_001"
        rep_id = "rep_test_outcome_job_001"
        fc_id = "fc_test_outcome_job_001"

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO v3_investigations (id, query, status, trace_id)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (inv_id, "outcome job test", "succeeded", "trace_outcome_job_001"),
                )
                cur.execute(
                    """
                    INSERT INTO v3_reports (id, investigation_id, title, summary, content)
                    VALUES (%s,%s,%s,%s,%s::jsonb)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (rep_id, inv_id, "Outcome Job", "Summary", '{"predictions": []}'),
                )
                cur.execute(
                    """
                    INSERT INTO forecasts (
                      id, report_id, investigation_id, claim, probability,
                      horizon_days, horizon_date, outcome_status,
                      created_by
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        fc_id,
                        rep_id,
                        inv_id,
                        "Test claim",
                        0.7,
                        1,
                        past,
                        "pending",
                        "test:outcome_job",
                    ),
                )
            conn.commit()

        async def fake_measure(_forecast_id: str, _forecast: dict):
            return {
                "outcome_status": "resolved",
                "outcome_result": True,
                "outcome_confidence": 1.0,
                "outcome_method": "test",
                "outcome_measured_at": now,
                "outcome_evidence": {"note": "unit test"},
            }

        with patch("watchfuleye.v3.forecast.outcome_job.measure_forecast_outcome", new=fake_measure):
            result = run_forecast_outcome_job(self.pg_dsn, limit=10)

        self.assertEqual(result.get("processed"), 1)
        self.assertEqual(result.get("resolved"), 1)

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT outcome_status, outcome_result, brier_score, calibration_bin
                    FROM forecasts
                    WHERE id=%s
                    """,
                    (fc_id,),
                )
                row = cur.fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[0], "resolved")
                self.assertEqual(row[1], True)
                # Brier score: (0.7 - 1)^2 = 0.09
                self.assertAlmostEqual(float(row[2]), 0.09, places=3)
                self.assertEqual(int(row[3]), 7)

                cur.execute(
                    """
                    SELECT update_type, updated_by
                    FROM forecast_updates
                    WHERE forecast_id=%s
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (fc_id,),
                )
                upd = cur.fetchone()
                self.assertIsNotNone(upd)
                self.assertEqual(upd[0], "outcome_measurement")
                self.assertEqual(upd[1], "system:forecast_outcome_job")


if __name__ == "__main__":
    unittest.main()



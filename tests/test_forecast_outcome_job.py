from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import psycopg


class TestForecastOutcomeJob(unittest.TestCase):
    def setUp(self) -> None:
        self._pg_dsn_raw = os.environ.get("PG_DSN")
        self.pg_dsn = self._pg_dsn_raw
        self._pg_schema = None
        if self.pg_dsn:
            try:
                with psycopg.connect(self.pg_dsn):
                    pass
            except Exception:
                self.pg_dsn = None
                self._pg_dsn_raw = None

        # Use a unique schema per test run so dev data never pollutes assertions.
        if self.pg_dsn and self._pg_dsn_raw:
            self._pg_schema = f"test_ws61_outcome_{uuid4().hex[:10]}"
            with psycopg.connect(self._pg_dsn_raw) as conn:
                with conn.cursor() as cur:
                    cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{self._pg_schema}"')
                conn.commit()
            # Include `public` so extension operator classes (e.g., gin_trgm_ops) resolve.
            self.pg_dsn = f"{self._pg_dsn_raw} options='-c search_path={self._pg_schema},public'"
            os.environ["PG_DSN"] = self.pg_dsn
        # Always enable WS6.1 for these tests (they are explicitly about the job behavior).
        os.environ["V3_FORECAST_TRACKING"] = "true"

    def tearDown(self) -> None:
        os.environ.pop("V3_FORECAST_TRACKING", None)
        if self._pg_schema and self._pg_dsn_raw:
            try:
                with psycopg.connect(self._pg_dsn_raw) as conn:
                    with conn.cursor() as cur:
                        cur.execute(f'DROP SCHEMA IF EXISTS "{self._pg_schema}" CASCADE')
                    conn.commit()
            finally:
                os.environ["PG_DSN"] = self._pg_dsn_raw

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
        self.assertEqual(result.get("invalid"), 0)

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

    def test_job_marks_meta_claim_invalid_and_skips_measurement(self) -> None:
        if not self.pg_dsn:
            self.skipTest("PG_DSN not configured")

        from watchfuleye.storage.postgres_schema import ensure_postgres_schema
        from watchfuleye.v3.forecast.outcome_job import run_forecast_outcome_job

        ensure_postgres_schema(self.pg_dsn)

        now = datetime.now(timezone.utc)
        past = now - timedelta(days=2)

        inv_id = "inv_test_outcome_job_002"
        rep_id = "rep_test_outcome_job_002"
        fc_id = "fc_test_outcome_job_002"

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO v3_investigations (id, query, status, trace_id)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (inv_id, "outcome job test 2", "succeeded", "trace_outcome_job_002"),
                )
                cur.execute(
                    """
                    INSERT INTO v3_reports (id, investigation_id, title, summary, content)
                    VALUES (%s,%s,%s,%s,%s::jsonb)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (rep_id, inv_id, "Outcome Job 2", "Summary", '{"predictions": []}'),
                )
                cur.execute(
                    """
                    INSERT INTO forecasts (
                      id, report_id, investigation_id, claim, probability,
                      horizon_days, horizon_date, outcome_status,
                      created_by, evidence_ids
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        fc_id,
                        rep_id,
                        inv_id,
                        "No matching articles found for query 'AAPL' (dataset coverage issue).",
                        0.75,
                        7,
                        past,
                        "pending",
                        "test:outcome_job",
                        [],  # no evidence => treated as non-verifiable
                    ),
                )
            conn.commit()

        async def should_not_call(_forecast_id: str, _forecast: dict):
            raise AssertionError("measure_forecast_outcome should not be called for invalid/meta claims")

        with patch("watchfuleye.v3.forecast.outcome_job.measure_forecast_outcome", new=should_not_call):
            result = run_forecast_outcome_job(self.pg_dsn, limit=10)

        self.assertEqual(result.get("processed"), 1)
        self.assertEqual(result.get("invalid"), 1)

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT outcome_status, outcome_method, brier_score
                    FROM forecasts
                    WHERE id=%s
                    """,
                    (fc_id,),
                )
                row = cur.fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[0], "invalid")
                self.assertEqual(row[1], "invalid")
                self.assertIsNone(row[2])

                cur.execute(
                    """
                    SELECT COUNT(*) FROM forecast_updates WHERE forecast_id=%s
                    """,
                    (fc_id,),
                )
                self.assertEqual(int(cur.fetchone()[0] or 0), 1)


if __name__ == "__main__":
    unittest.main()



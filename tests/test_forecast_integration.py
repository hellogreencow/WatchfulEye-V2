"""WS6.1 TASK 8: Integration tests for forecast accountability system.

Tests end-to-end flow:
1. POST /api/v3/examine → generates report with forecasts
2. Forecasts extracted and stored in database
3. GET /api/v3/forecast/metrics → returns aggregate metrics
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone

import psycopg


class TestForecastIntegration(unittest.TestCase):
    """Integration tests for forecast system."""

    def setUp(self):
        """Set up test database connection."""
        self.pg_dsn = os.environ.get("PG_DSN")
        if not self.pg_dsn:
            self.skipTest("PG_DSN not configured")

        # Enable forecast tracking for tests
        os.environ["V3_FORECAST_TRACKING"] = "1"
        os.environ["V3_EXAMINE_MVP"] = "1"

    def tearDown(self):
        """Clean up test data."""
        if self.pg_dsn:
            with psycopg.connect(self.pg_dsn) as conn:
                with conn.cursor() as cur:
                    # Clean up test forecasts
                    cur.execute("DELETE FROM forecasts WHERE created_by LIKE 'test:%'")
                    # Clean up test reports
                    cur.execute("DELETE FROM v3_reports WHERE id LIKE 'rep_test%'")
                    cur.execute("DELETE FROM v3_investigations WHERE id LIKE 'inv_test%'")
                    conn.commit()

    def test_examine_to_forecast_extraction(self):
        """Test that examine API extracts forecasts from report."""
        from watchfuleye.v3.forecast.extractor import extract_forecasts_from_report

        # Simulate report content with predictions
        report_content = {
            "predictions": [
                "70% chance Iran increases oil exports within 30 days",
                "Highly likely TSLA stock rises by end of quarter",
            ],
            "evidence_ids": ["art_123"],
        }

        forecasts = extract_forecasts_from_report(
            report_id="rep_test_001",
            report_content=report_content,
            investigation_id="inv_test_001",
        )

        # Verify extraction
        self.assertEqual(len(forecasts), 2)

        # Check first forecast
        fc1 = forecasts[0]
        self.assertAlmostEqual(fc1["probability"], 0.7)
        self.assertEqual(fc1["horizon_days"], 30)
        self.assertIn("Iran", fc1["claim"])
        self.assertIn("oil exports", fc1["claim"])

        # Check second forecast
        fc2 = forecasts[1]
        self.assertAlmostEqual(fc2["probability"], 0.75)
        self.assertEqual(fc2["horizon_days"], 90)

    def test_forecast_storage_and_retrieval(self):
        """Test storing forecasts and retrieving via metrics API."""
        from watchfuleye.storage.postgres_schema import ensure_postgres_schema

        ensure_postgres_schema(self.pg_dsn)

        # Insert test investigation and report
        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                # Create investigation
                cur.execute(
                    """
                    INSERT INTO v3_investigations (id, query, status, trace_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    ("inv_test_002", "Test query", "succeeded", "trace_test_002"),
                )

                # Create report
                cur.execute(
                    """
                    INSERT INTO v3_reports (id, investigation_id, title, summary, content)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        "rep_test_002",
                        "inv_test_002",
                        "Test Report",
                        "Test summary",
                        '{"predictions": []}',
                    ),
                )

                # Insert test forecasts
                cur.execute(
                    """
                    INSERT INTO forecasts (
                        id, report_id, investigation_id, claim, probability,
                        horizon_days, horizon_date, outcome_status, created_by,
                        brier_score, outcome_result
                    )
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s),
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s),
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        # Forecast 1: resolved, correct
                        "fc_test_001",
                        "rep_test_002",
                        "inv_test_002",
                        "Test claim 1",
                        0.7,
                        30,
                        datetime.now(timezone.utc),
                        "resolved",
                        "test:integration",
                        0.09,  # (0.7 - 1)^2
                        True,
                        # Forecast 2: resolved, incorrect
                        "fc_test_002",
                        "rep_test_002",
                        "inv_test_002",
                        "Test claim 2",
                        0.8,
                        30,
                        datetime.now(timezone.utc),
                        "resolved",
                        "test:integration",
                        0.64,  # (0.8 - 0)^2
                        False,
                        # Forecast 3: pending
                        "fc_test_003",
                        "rep_test_002",
                        "inv_test_002",
                        "Test claim 3",
                        0.6,
                        60,
                        datetime.now(timezone.utc),
                        "pending",
                        "test:integration",
                        None,
                        None,
                    ),
                )
                conn.commit()

        # Retrieve forecasts and calculate metrics
        from watchfuleye.v3.forecast.scorer import calculate_overall_metrics

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        probability, outcome_status, outcome_result, brier_score
                    FROM forecasts
                    WHERE created_by = 'test:integration'
                    """
                )
                rows = cur.fetchall()

        forecasts = [
            {
                "probability": row[0],
                "outcome_status": row[1],
                "outcome_result": row[2],
                "brier_score": row[3],
            }
            for row in rows
        ]

        metrics = calculate_overall_metrics(forecasts)

        # Verify metrics calculation
        self.assertEqual(metrics["total_forecasts"], 2)  # Only resolved
        self.assertIsNotNone(metrics["mean_brier_score"])
        # Average of 0.09 and 0.64 = 0.365
        self.assertAlmostEqual(metrics["mean_brier_score"], 0.365, places=2)

    def test_forecast_scoring_updates(self):
        """Test updating forecasts with outcome measurements and scores."""
        from watchfuleye.storage.postgres_schema import ensure_postgres_schema
        from watchfuleye.v3.forecast.scorer import (
            assign_calibration_bin,
            calculate_brier_score,
        )

        ensure_postgres_schema(self.pg_dsn)

        # Insert test forecast
        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO v3_investigations (id, query, status, trace_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    ("inv_test_003", "Test query", "succeeded", "trace_test_003"),
                )

                cur.execute(
                    """
                    INSERT INTO v3_reports (id, investigation_id, title, summary, content)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        "rep_test_003",
                        "inv_test_003",
                        "Test Report",
                        "Test summary",
                        '{"predictions": []}',
                    ),
                )

                cur.execute(
                    """
                    INSERT INTO forecasts (
                        id, report_id, investigation_id, claim, probability,
                        horizon_days, horizon_date, outcome_status, created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        "fc_test_004",
                        "rep_test_003",
                        "inv_test_003",
                        "Test forecast for scoring",
                        0.75,
                        30,
                        datetime.now(timezone.utc),
                        "pending",
                        "test:integration",
                    ),
                )
                conn.commit()

        # Simulate outcome measurement
        outcome_happened = True
        probability = 0.75

        # Calculate scores
        brier = calculate_brier_score(probability, outcome_happened)
        calib_bin = assign_calibration_bin(probability)

        # Update forecast with outcome
        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE forecasts
                    SET
                        outcome_status = 'resolved',
                        outcome_result = %s,
                        outcome_measured_at = now(),
                        outcome_method = 'test',
                        brier_score = %s,
                        calibration_bin = %s,
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (outcome_happened, brier, calib_bin, "fc_test_004"),
                )
                conn.commit()

                # Verify update
                cur.execute(
                    """
                    SELECT outcome_status, outcome_result, brier_score, calibration_bin
                    FROM forecasts
                    WHERE id = %s
                    """,
                    ("fc_test_004",),
                )
                row = cur.fetchone()

        self.assertEqual(row[0], "resolved")
        self.assertEqual(row[1], True)
        self.assertAlmostEqual(row[2], 0.0625, places=4)  # (0.75 - 1)^2
        self.assertEqual(row[3], 7)  # Bin for 0.75


if __name__ == "__main__":
    unittest.main()

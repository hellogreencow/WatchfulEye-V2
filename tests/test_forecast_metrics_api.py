from __future__ import annotations

import importlib
import os
import unittest
from datetime import datetime, timezone

import psycopg


class TestForecastMetricsApi(unittest.TestCase):
    def setUp(self) -> None:
        # Keep tests isolated from one another via explicit cleanup.
        self.pg_dsn = os.environ.get("PG_DSN")
        if self.pg_dsn:
            try:
                with psycopg.connect(self.pg_dsn):
                    pass
            except Exception:
                # Local dev often runs without Postgres; treat as "not configured".
                self.pg_dsn = None

        # Ensure flags are not leaking across tests.
        os.environ.pop("V3_FORECAST_TRACKING", None)

    def tearDown(self) -> None:
        if not self.pg_dsn:
            return
        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM forecast_updates WHERE updated_by = 'test:metrics_api'")
                cur.execute("DELETE FROM forecasts WHERE created_by = 'test:metrics_api'")
                cur.execute("DELETE FROM v3_reports WHERE id LIKE 'rep_test_metrics_%'")
                cur.execute("DELETE FROM v3_investigations WHERE id LIKE 'inv_test_metrics_%'")
            conn.commit()

    def test_metrics_flag_off_404(self) -> None:
        import web_app as web_app_mod

        web_app_mod = importlib.reload(web_app_mod)
        client = web_app_mod.app.test_client()
        r = client.get("/api/v3/forecast/metrics")
        self.assertEqual(r.status_code, 404)

    def test_metrics_flag_on_empty_shape(self) -> None:
        if not self.pg_dsn:
            self.skipTest("PG_DSN not configured")

        # Enable WS6.1
        os.environ["V3_FORECAST_TRACKING"] = "true"

        # Ensure schema exists and is empty for this test
        from watchfuleye.storage.postgres_schema import ensure_postgres_schema

        ensure_postgres_schema(self.pg_dsn)
        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                # Only clean test-owned rows; never nuke developer data.
                cur.execute("DELETE FROM forecast_updates WHERE updated_by = 'test:metrics_api'")
                cur.execute("DELETE FROM forecasts WHERE created_by = 'test:metrics_api'")
                conn.commit()

                cur.execute("SELECT COUNT(*) FROM forecasts")
                remaining = int(cur.fetchone()[0] or 0)
                if remaining != 0:
                    self.skipTest("Refusing to DELETE non-test forecasts; database is not empty")

        import web_app as web_app_mod

        web_app_mod = importlib.reload(web_app_mod)
        client = web_app_mod.app.test_client()
        r = client.get("/api/v3/forecast/metrics")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIsInstance(data, dict)
        self.assertIn("overall", data)
        self.assertIn("by_domain", data)
        self.assertIn("recent_performance", data)
        self.assertIn("calibration_curve", data)

        overall = data["overall"]
        self.assertEqual(overall["total_forecasts"], 0)
        self.assertEqual(overall["resolved_forecasts"], 0)
        self.assertEqual(overall["pending_forecasts"], 0)
        self.assertIsNone(overall["mean_brier_score"])
        self.assertIsNone(overall["mean_log_score"])
        self.assertIsNone(overall["calibration_error"])
        self.assertIsNone(overall["accuracy_percentage"])

        hit = overall.get("hit_rate_by_horizon")
        self.assertIsInstance(hit, dict)
        for k in ("7_days", "30_days", "90_days"):
            self.assertIn(k, hit)
            self.assertIsNone(hit[k])

    def test_metrics_flag_on_with_data_counts_and_scores(self) -> None:
        if not self.pg_dsn:
            self.skipTest("PG_DSN not configured")

        os.environ["V3_FORECAST_TRACKING"] = "true"

        from watchfuleye.storage.postgres_schema import ensure_postgres_schema

        ensure_postgres_schema(self.pg_dsn)

        now = datetime.now(timezone.utc)

        inv_id = "inv_test_metrics_001"
        rep_id = "rep_test_metrics_001"

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                # Investigation + report (required by FK)
                cur.execute(
                    """
                    INSERT INTO v3_investigations (id, query, status, trace_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (inv_id, "metrics test", "succeeded", "trace_metrics_001"),
                )
                cur.execute(
                    """
                    INSERT INTO v3_reports (id, investigation_id, title, summary, content)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (rep_id, inv_id, "Metrics Test", "Summary", '{"predictions": []}'),
                )

                # Two resolved forecasts + one pending
                cur.execute(
                    """
                    INSERT INTO forecasts (
                      id, report_id, investigation_id, claim, probability,
                      horizon_days, horizon_date,
                      outcome_status, outcome_result, outcome_measured_at, outcome_method,
                      created_by, tags
                    )
                    VALUES
                      (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s),
                      (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s),
                      (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        # resolved A (correct)
                        "fc_test_metrics_001",
                        rep_id,
                        inv_id,
                        "A rises",
                        0.7,
                        7,
                        now,
                        "resolved",
                        True,
                        now,
                        "test",
                        "test:metrics_api",
                        ["markets"],
                        # resolved B (incorrect)
                        "fc_test_metrics_002",
                        rep_id,
                        inv_id,
                        "B falls",
                        0.8,
                        30,
                        now,
                        "resolved",
                        False,
                        now,
                        "test",
                        "test:metrics_api",
                        ["markets"],
                        # pending
                        "fc_test_metrics_003",
                        rep_id,
                        inv_id,
                        "C pending",
                        0.6,
                        30,
                        now,
                        "pending",
                        None,
                        None,
                        None,
                        "test:metrics_api",
                        ["geopolitics"],
                    ),
                )
            conn.commit()

        import web_app as web_app_mod

        web_app_mod = importlib.reload(web_app_mod)
        client = web_app_mod.app.test_client()
        r = client.get("/api/v3/forecast/metrics")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        overall = data["overall"]

        # Counts
        self.assertEqual(overall["total_forecasts"], 3)
        self.assertEqual(overall["resolved_forecasts"], 2)
        self.assertEqual(overall["pending_forecasts"], 1)

        # Scores: mean of (0.09, 0.64) = 0.365
        self.assertIsInstance(overall["mean_brier_score"], (int, float))
        self.assertAlmostEqual(float(overall["mean_brier_score"]), 0.365, places=2)

        # Accuracy: 1/2 correct
        self.assertIsInstance(overall["accuracy_percentage"], (int, float))
        self.assertAlmostEqual(float(overall["accuracy_percentage"]), 50.0, places=1)

        # Horizon hit rates (7-day has only A)
        hit = overall["hit_rate_by_horizon"]
        self.assertAlmostEqual(float(hit["7_days"]), 1.0, places=3)
        self.assertAlmostEqual(float(hit["30_days"]), 0.5, places=3)
        self.assertAlmostEqual(float(hit["90_days"]), 0.5, places=3)


if __name__ == "__main__":
    unittest.main()



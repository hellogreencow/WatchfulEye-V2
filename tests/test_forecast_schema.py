"""Tests for WS6.1 forecast database schema (TASK 1).

Validates that forecast tables can be created and have correct constraints.
"""

from __future__ import annotations

import os
import unittest

import psycopg


class TestForecastSchema(unittest.TestCase):
    """Tests for forecast database schema."""

    def setUp(self):
        """Set up test database connection if available."""
        self.pg_dsn = os.environ.get("PG_DSN")
        if not self.pg_dsn:
            self.skipTest("PG_DSN not configured")

    def test_schema_creation(self):
        """Test that forecast tables can be created."""
        from watchfuleye.storage.postgres_schema import ensure_postgres_schema

        # Should not raise
        ensure_postgres_schema(self.pg_dsn)

        # Verify tables exist
        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                # Check forecasts table exists
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'forecasts'
                    )
                    """
                )
                self.assertTrue(cur.fetchone()[0])

                # Check forecast_updates table exists
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'forecast_updates'
                    )
                    """
                )
                self.assertTrue(cur.fetchone()[0])

    def test_forecasts_table_columns(self):
        """Test that forecasts table has required columns."""
        from watchfuleye.storage.postgres_schema import ensure_postgres_schema

        ensure_postgres_schema(self.pg_dsn)

        required_columns = [
            "id",
            "report_id",
            "investigation_id",
            "claim",
            "probability",
            "horizon_days",
            "horizon_date",
            "entity_ids",
            "entity_types",
            "evidence_ids",
            "assumptions",
            "outcome_status",
            "outcome_result",
            "outcome_confidence",
            "outcome_measured_at",
            "outcome_method",
            "outcome_evidence",
            "brier_score",
            "log_score",
            "calibration_bin",
            "created_at",
            "updated_at",
            "created_by",
            "tags",
        ]

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'forecasts'
                    """
                )
                columns = {row[0] for row in cur.fetchall()}

                for col in required_columns:
                    self.assertIn(col, columns, f"Missing column: {col}")

    def test_probability_constraint(self):
        """Test that probability constraint [0, 1] is enforced."""
        from watchfuleye.storage.postgres_schema import ensure_postgres_schema

        ensure_postgres_schema(self.pg_dsn)

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                # Satisfy FK: forecasts.report_id -> v3_reports.id
                cur.execute(
                    """
                    INSERT INTO v3_investigations (id, query, status, trace_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    ("inv_test_schema", "schema test", "succeeded", "trace_schema"),
                )
                cur.execute(
                    """
                    INSERT INTO v3_reports (id, investigation_id, title, summary, content)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    ("rpt_test", "inv_test_schema", "Schema Test", "Summary", "{}"),
                )
                conn.commit()

                # Try to insert invalid probability (should fail)
                with self.assertRaises(psycopg.errors.CheckViolation):
                    cur.execute(
                        """
                        INSERT INTO forecasts (
                            id, report_id, claim, probability,
                            horizon_days, horizon_date
                        )
                        VALUES (%s, %s, %s, %s, %s, now())
                        """,
                        ("fc_test", "rpt_test", "Test claim", 1.5, 30),
                    )
                    conn.commit()

                conn.rollback()

                # Try to insert valid probability (should succeed)
                cur.execute(
                    """
                    INSERT INTO forecasts (
                        id, report_id, claim, probability,
                        horizon_days, horizon_date
                    )
                    VALUES (%s, %s, %s, %s, %s, now())
                    ON CONFLICT (id) DO NOTHING
                    """,
                    ("fc_test_valid", "rpt_test", "Test claim", 0.7, 30),
                )
                conn.commit()

                # Verify it was inserted
                cur.execute("SELECT probability FROM forecasts WHERE id = %s", ("fc_test_valid",))
                row = cur.fetchone()
                self.assertIsNotNone(row)
                self.assertAlmostEqual(row[0], 0.7)

                # Clean up
                cur.execute("DELETE FROM forecasts WHERE id LIKE 'fc_test%'")
                cur.execute("DELETE FROM v3_reports WHERE id = %s", ("rpt_test",))
                cur.execute("DELETE FROM v3_investigations WHERE id = %s", ("inv_test_schema",))
                conn.commit()

    def test_foreign_key_constraints(self):
        """Test that foreign key constraints work."""
        from watchfuleye.storage.postgres_schema import ensure_postgres_schema

        ensure_postgres_schema(self.pg_dsn)

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                # Try to insert forecast with non-existent report_id (should fail)
                with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                    cur.execute(
                        """
                        INSERT INTO forecasts (
                            id, report_id, claim, probability,
                            horizon_days, horizon_date
                        )
                        VALUES (%s, %s, %s, %s, %s, now())
                        """,
                        ("fc_fk_test", "rpt_nonexistent", "Test claim", 0.7, 30),
                    )
                    conn.commit()

                conn.rollback()

    def test_indexes_exist(self):
        """Test that required indexes exist."""
        from watchfuleye.storage.postgres_schema import ensure_postgres_schema

        ensure_postgres_schema(self.pg_dsn)

        required_indexes = [
            "idx_forecasts_report_id",
            "idx_forecasts_horizon_date",
            "idx_forecasts_outcome_status",
            "idx_forecasts_entity_ids",
            "idx_forecasts_tags",
            "idx_forecasts_created_at",
            "idx_forecast_updates_forecast_id",
            "idx_forecast_updates_updated_at",
        ]

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE tablename IN ('forecasts', 'forecast_updates')
                    """
                )
                indexes = {row[0] for row in cur.fetchall()}

                for idx in required_indexes:
                    self.assertIn(idx, indexes, f"Missing index: {idx}")


if __name__ == "__main__":
    unittest.main()

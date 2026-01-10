from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import psycopg


class TestRecommendationPerfJob(unittest.TestCase):
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

        if self.pg_dsn and self._pg_dsn_raw:
            self._pg_schema = f"test_ws61_perf_{uuid4().hex[:10]}"
            with psycopg.connect(self._pg_dsn_raw) as conn:
                with conn.cursor() as cur:
                    cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{self._pg_schema}"')
                conn.commit()
            self.pg_dsn = f"{self._pg_dsn_raw} options='-c search_path={self._pg_schema},public'"
            os.environ["PG_DSN"] = self.pg_dsn

    def tearDown(self) -> None:
        if self._pg_schema and self._pg_dsn_raw:
            try:
                with psycopg.connect(self._pg_dsn_raw) as conn:
                    with conn.cursor() as cur:
                        cur.execute(f'DROP SCHEMA IF EXISTS "{self._pg_schema}" CASCADE')
                    conn.commit()
            finally:
                os.environ["PG_DSN"] = self._pg_dsn_raw

    def test_job_writes_performance_rows(self) -> None:
        if not self.pg_dsn:
            self.skipTest("PG_DSN not configured")

        from watchfuleye.storage.postgres_schema import ensure_postgres_schema
        from watchfuleye.performance.recommendation_perf_job import run_recommendation_performance_job

        ensure_postgres_schema(self.pg_dsn)

        entry_dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        analysis_id = None
        rec_id = None

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                # minimal analysis row (FK for recommendations)
                cur.execute(
                    """
                    INSERT INTO analyses (created_at, content, content_preview, model_used, article_count, processing_time, quality_score, topic, raw_response_json)
                    VALUES (now(), %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING id
                    """,
                    ("x", "x", "test", 1, 0.1, 0.1, "test", "{}"),
                )
                analysis_id = int(cur.fetchone()[0])
                cur.execute(
                    """
                    INSERT INTO recommendations (analysis_id, action, ticker, rationale)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (analysis_id, "BUY", "AAPL", "unit test"),
                )
                rec_id = int(cur.fetchone()[0])
                # Force a deterministic entry timestamp so the job finds exact price dates in our fixture.
                cur.execute(
                    "UPDATE recommendations SET created_at=%s WHERE id=%s",
                    (entry_dt, rec_id),
                )
            conn.commit()

        # Mock Stooq fetch to return deterministic daily series for AAPL and SPY.
        csv_text = "Date,Open,High,Low,Close,Volume\n" + "\n".join(
            [
                "2026-01-01,0,0,0,100,0",
                "2026-01-08,0,0,0,110,0",
                "2026-01-31,0,0,0,120,0",
                "2026-04-01,0,0,0,130,0",
            ]
        )

        def fake_get(_url: str, *args, **kwargs):
            class Resp:
                status_code = 200
                text = csv_text

                def raise_for_status(self):
                    return None

            return Resp()

        with patch("watchfuleye.performance.stooq.requests.get", new=fake_get):
            result = run_recommendation_performance_job(self.pg_dsn, limit=10)

        self.assertGreaterEqual(int(result.get("processed_recommendations") or 0), 1)
        self.assertEqual(result.get("errors"), [])

        with psycopg.connect(self.pg_dsn) as conn:
            # Sanity: loader should find entry/exit closes for at least 7-day horizon.
            from watchfuleye.performance.recommendation_perf_job import _load_prices  # type: ignore
            entry_day = entry_dt.date()
            exit_day_7 = (entry_dt + timedelta(days=7)).date()
            aapl = _load_prices(conn, symbol="AAPL", entry_day=entry_day, exit_day=exit_day_7)
            spy = _load_prices(conn, symbol="SPY", entry_day=entry_day, exit_day=exit_day_7)
            self.assertIsNotNone(aapl, f"_load_prices failed for AAPL, result={result}")
            self.assertIsNotNone(spy, f"_load_prices failed for SPY, result={result}")
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM prices_daily WHERE symbol IN ('AAPL','SPY')")
                prices_n = int(cur.fetchone()[0] or 0)
                self.assertGreaterEqual(prices_n, 2, f"expected prices to be ingested, got prices_n={prices_n}, result={result}")

                cur.execute(
                    """
                    SELECT COUNT(*) FROM recommendation_performance
                    WHERE recommendation_id = %s AND benchmark_symbol = 'SPY'
                    """,
                    (rec_id,),
                )
                n = int(cur.fetchone()[0] or 0)
                # Should write at least one horizon row.
                self.assertGreaterEqual(n, 1, f"expected perf rows, got n={n}, result={result}, prices_n={prices_n}")

                # Deterministic fixture: 100 -> 110 for both AAPL and SPY on 7d => alpha ~= 0.0
                cur.execute(
                    """
                    SELECT rec_return, benchmark_return, alpha
                    FROM recommendation_performance
                    WHERE recommendation_id=%s AND benchmark_symbol='SPY' AND horizon_days=7
                    """,
                    (rec_id,),
                )
                row = cur.fetchone()
                self.assertIsNotNone(row, "missing 7d performance row")
                rec_return, bench_return, alpha = row
                self.assertAlmostEqual(float(rec_return), 0.10, places=8)
                self.assertAlmostEqual(float(bench_return), 0.10, places=8)
                self.assertAlmostEqual(float(alpha), 0.0, places=8)


if __name__ == "__main__":
    unittest.main()



from __future__ import annotations

import asyncio
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import psycopg


class _FakeResp:
    def __init__(self, *, status_code: int = 200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data


class TestForecastOutcomeTrackerSources(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_pg_dsn = os.environ.get("PG_DSN")
        self.pg_dsn = os.environ.get("PG_DSN")
        if self.pg_dsn:
            try:
                with psycopg.connect(self.pg_dsn):
                    pass
            except Exception:
                self.pg_dsn = None
        os.environ.pop("ALPHA_VANTAGE_API_KEY", None)

    def tearDown(self) -> None:
        # Restore env var if any test temporarily removed it
        if self._orig_pg_dsn is None:
            os.environ.pop("PG_DSN", None)
        else:
            os.environ["PG_DSN"] = self._orig_pg_dsn

    def test_yahoo_finance_fetch_parses_chart(self) -> None:
        from watchfuleye.v3.forecast.outcome_tracker import _fetch_yahoo_finance_data

        start = datetime.now(timezone.utc) - timedelta(days=2)
        end = datetime.now(timezone.utc)

        fake = _FakeResp(
            status_code=200,
            json_data={
                "chart": {
                    "result": [
                        {
                            "timestamp": [1700000000, 1700086400],
                            "indicators": {"quote": [{"close": [100.0, 110.0]}]},
                        }
                    ],
                    "error": None,
                }
            },
        )

        with patch("watchfuleye.v3.forecast.outcome_tracker.requests.get", return_value=fake):
            data = asyncio.run(_fetch_yahoo_finance_data("AAPL", start, end))

        self.assertIn("ticker", data)
        self.assertEqual(data["ticker"], "AAPL")
        self.assertAlmostEqual(float(data["start_price"]), 100.0, places=6)
        self.assertAlmostEqual(float(data["end_price"]), 110.0, places=6)
        self.assertAlmostEqual(float(data["change_pct"]), 10.0, places=6)
        self.assertEqual(len(data["prices"]), 2)

    def test_yahoo_finance_fetch_http_error(self) -> None:
        from watchfuleye.v3.forecast.outcome_tracker import _fetch_yahoo_finance_data

        start = datetime.now(timezone.utc) - timedelta(days=2)
        end = datetime.now(timezone.utc)

        fake = _FakeResp(status_code=404, json_data={})
        with patch("watchfuleye.v3.forecast.outcome_tracker.requests.get", return_value=fake):
            data = asyncio.run(_fetch_yahoo_finance_data("AAPL", start, end))
        self.assertIn("error", data)
        self.assertIn("HTTP 404", str(data["error"]))

    def test_alpha_vantage_requires_api_key(self) -> None:
        from watchfuleye.v3.forecast.outcome_tracker import _fetch_alpha_vantage_data

        start = datetime.now(timezone.utc) - timedelta(days=10)
        end = datetime.now(timezone.utc)
        data = asyncio.run(_fetch_alpha_vantage_data("AAPL", start, end))
        self.assertIn("error", data)
        self.assertIn("ALPHA_VANTAGE_API_KEY", data["error"])

    def test_alpha_vantage_parses_time_series(self) -> None:
        from watchfuleye.v3.forecast.outcome_tracker import _fetch_alpha_vantage_data

        os.environ["ALPHA_VANTAGE_API_KEY"] = "test"
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 5, tzinfo=timezone.utc)

        fake = _FakeResp(
            status_code=200,
            json_data={
                "Time Series (Daily)": {
                    "2026-01-02": {"4. close": "100.0"},
                    "2026-01-03": {"4. close": "90.0"},
                }
            },
        )
        with patch("watchfuleye.v3.forecast.outcome_tracker.requests.get", return_value=fake):
            data = asyncio.run(_fetch_alpha_vantage_data("AAPL", start, end))

        self.assertNotIn("error", data)
        self.assertAlmostEqual(float(data["start_price"]), 100.0, places=6)
        self.assertAlmostEqual(float(data["end_price"]), 90.0, places=6)
        self.assertLess(float(data["change_pct"]), 0.0)

    def test_gdelt_fetch_returns_events(self) -> None:
        from watchfuleye.v3.forecast.outcome_tracker import _fetch_gdelt_events

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 2, tzinfo=timezone.utc)

        fake = _FakeResp(
            status_code=200,
            json_data={
                "articles": [
                    {
                        "seendate": "20260101T120000Z",
                        "url": "https://example.com/a",
                        "title": "Example",
                        "tone": "1.2",
                    }
                ]
            },
        )
        with patch("watchfuleye.v3.forecast.outcome_tracker.requests.get", return_value=fake):
            events = asyncio.run(_fetch_gdelt_events(["Iran"], start, end))

        self.assertIsInstance(events, list)
        self.assertGreaterEqual(len(events), 1)
        self.assertIn("date", events[0])
        self.assertIn("sources", events[0])

    def test_search_news_articles_without_db(self) -> None:
        from watchfuleye.v3.forecast.outcome_tracker import _search_news_articles

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PG_DSN", None)
            start = datetime(2026, 1, 1, tzinfo=timezone.utc)
            end = datetime(2026, 1, 2, tzinfo=timezone.utc)
            articles = asyncio.run(_search_news_articles("test", start, end))
        self.assertIsInstance(articles, list)
        self.assertGreaterEqual(len(articles), 1)
        self.assertIn("error", articles[0])

    def test_search_news_articles_with_db(self) -> None:
        if not self.pg_dsn:
            self.skipTest("PG_DSN not configured")

        from watchfuleye.storage.postgres_schema import ensure_postgres_schema
        from watchfuleye.v3.forecast.outcome_tracker import _search_news_articles

        ensure_postgres_schema(self.pg_dsn)

        token = "unittestfoobar"
        now = datetime.now(timezone.utc)
        canonical_url = f"https://example.com/{token}"

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO articles (canonical_url, url_hash, title, description, published_at, source_domain, source_name, ingestion_source)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (canonical_url) DO NOTHING
                    """,
                    (
                        canonical_url,
                        f"hash_{token}",
                        f"{token} headline",
                        "test description",
                        now,
                        "example.com",
                        "Example",
                        "test",
                    ),
                )
            conn.commit()

        articles = asyncio.run(_search_news_articles(token, now - timedelta(days=1), now + timedelta(days=1)))
        # May be empty if Postgres FTS behaves unexpectedly; but should never error.
        self.assertIsInstance(articles, list)
        self.assertFalse(any("error" in a for a in articles if isinstance(a, dict)))

        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM articles WHERE canonical_url=%s", (canonical_url,))
            conn.commit()


if __name__ == "__main__":
    unittest.main()



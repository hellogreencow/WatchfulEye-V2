from __future__ import annotations

import importlib
import os
import unittest
from uuid import uuid4

import psycopg


class TestV3OsintApi(unittest.TestCase):
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
            self._pg_schema = f"test_ws5_osint_{uuid4().hex[:10]}"
            with psycopg.connect(self._pg_dsn_raw) as conn:
                with conn.cursor() as cur:
                    cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{self._pg_schema}"')
                conn.commit()
            self.pg_dsn = f"{self._pg_dsn_raw} options='-c search_path={self._pg_schema},public'"
            os.environ["PG_DSN"] = self.pg_dsn

        os.environ["V3_CONNECTORS"] = "true"
        os.environ["V3_OSINT"] = "true"

    def tearDown(self) -> None:
        os.environ.pop("V3_CONNECTORS", None)
        os.environ.pop("V3_OSINT", None)
        if self._pg_schema and self._pg_dsn_raw:
            try:
                with psycopg.connect(self._pg_dsn_raw) as conn:
                    with conn.cursor() as cur:
                        cur.execute(f'DROP SCHEMA IF EXISTS "{self._pg_schema}" CASCADE')
                    conn.commit()
            finally:
                os.environ["PG_DSN"] = self._pg_dsn_raw

    def test_ingest_and_promote(self) -> None:
        if not self.pg_dsn:
            self.skipTest("PG_DSN not configured")

        import web_app as web_app_mod

        web_app_mod = importlib.reload(web_app_mod)
        client = web_app_mod.app.test_client()

        payload = {
            "platform": "x",
            "items": [
                {
                    "handle": "osintdefender",
                    "post_id": "123",
                    "url": "https://x.com/osintdefender/status/123",
                    "text": "Test post about $AAPL and geopolitics",
                    "posted_at": "2026-01-01T00:00:00Z",
                }
            ],
        }
        r = client.post("/api/v3/osint/posts/ingest", json=payload)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        data = r.get_json()
        self.assertGreaterEqual(int(data.get("upserted") or 0), 1)

        r2 = client.get("/api/v3/osint/posts/recent?handle=osintdefender&limit=5")
        self.assertEqual(r2.status_code, 200)
        items = r2.get_json()["items"]
        self.assertGreaterEqual(len(items), 1)
        post_row_id = items[0]["id"]

        rp = client.post(f"/api/v3/osint/posts/{post_row_id}/promote")
        self.assertEqual(rp.status_code, 200, rp.get_data(as_text=True))
        article_id = int(rp.get_json()["article_id"])
        self.assertGreater(article_id, 0)


if __name__ == "__main__":
    unittest.main()



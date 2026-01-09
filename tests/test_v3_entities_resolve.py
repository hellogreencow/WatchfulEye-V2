import os
import unittest

import psycopg

from watchfuleye.storage.postgres_schema import ensure_postgres_schema
from watchfuleye.v3.entity_seeds import seed_minimal_countries, seed_minimal_sanctions_targets


class TestV3EntitiesResolve(unittest.TestCase):
    PG_DSN = os.environ.get("PG_DSN", "dbname=watchfuleye user=watchful password=watchfulpass host=localhost port=5432")

    @classmethod
    def setUpClass(cls) -> None:
        os.environ["PG_DSN"] = cls.PG_DSN
        ensure_postgres_schema(cls.PG_DSN)
        seed_minimal_countries(cls.PG_DSN)
        seed_minimal_sanctions_targets(cls.PG_DSN)

        # Seed one entity + identifier for exact match testing.
        with psycopg.connect(cls.PG_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO entities (id, entity_type, label)
                    VALUES ('ent_ticker_aapl', 'ticker', 'Apple Inc')
                    ON CONFLICT (id) DO UPDATE SET label = EXCLUDED.label
                    """
                )
                cur.execute(
                    """
                    INSERT INTO entity_identifiers (entity_id, identifier_type, identifier_value, confidence, provenance)
                    VALUES ('ent_ticker_aapl', 'ticker', 'AAPL', 1.0, '{"source_system":"test"}'::jsonb)
                    ON CONFLICT (identifier_type, identifier_value) DO UPDATE
                    SET entity_id = EXCLUDED.entity_id
                    """
                )

    def setUp(self) -> None:
        # Ensure default OFF unless test explicitly enables.
        os.environ.pop("V3_ENTITY_IDS", None)

    def test_resolve_404_when_flag_off(self):
        import importlib
        import web_app as web_app_mod

        web_app_mod = importlib.reload(web_app_mod)
        client = web_app_mod.app.test_client()
        r = client.post("/api/v3/entities/resolve", json={"q": "AAPL"})
        self.assertEqual(r.status_code, 404)

    def test_resolve_returns_stub_shape_when_flag_on(self):
        os.environ["V3_ENTITY_IDS"] = "true"
        import importlib
        import web_app as web_app_mod

        web_app_mod = importlib.reload(web_app_mod)
        client = web_app_mod.app.test_client()
        r = client.post("/api/v3/entities/resolve", json={"q": "AAPL", "k": 5, "types": ["ticker"]})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIsInstance(data, dict)
        self.assertIn("matches", data)
        self.assertIn("trace_id", data)
        self.assertEqual(data.get("q"), "AAPL")
        self.assertEqual(data.get("k"), 5)
        self.assertEqual(data.get("types"), ["ticker"])
        # Should return our seeded exact match via Postgres.
        matches = data.get("matches")
        self.assertIsInstance(matches, list)
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0].get("entity_id"), "ent_ticker_aapl")
        self.assertEqual(matches[0].get("entity_type"), "ticker")
        self.assertIn("confidence", matches[0])

    def test_resolve_country_by_iso2(self):
        os.environ["V3_ENTITY_IDS"] = "true"
        import importlib
        import web_app as web_app_mod

        web_app_mod = importlib.reload(web_app_mod)
        client = web_app_mod.app.test_client()
        r = client.post("/api/v3/entities/resolve", json={"q": "US", "k": 5, "types": ["country"]})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        matches = data.get("matches") or []
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0].get("entity_type"), "country")

    def test_resolve_sanctions_target_by_ofac_id(self):
        os.environ["V3_ENTITY_IDS"] = "true"
        import importlib
        import web_app as web_app_mod

        web_app_mod = importlib.reload(web_app_mod)
        client = web_app_mod.app.test_client()
        r = client.post("/api/v3/entities/resolve", json={"q": "OFAC_TEST_0001", "k": 5, "types": ["sanctions_target"]})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        matches = data.get("matches") or []
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0].get("entity_type"), "sanctions_target")


if __name__ == "__main__":
    unittest.main()



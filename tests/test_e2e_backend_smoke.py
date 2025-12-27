import os
import unittest
from datetime import datetime, timezone

import psycopg

from watchfuleye.storage.postgres_schema import ensure_postgres_schema


PG_DSN = os.environ.get("PG_DSN", "dbname=watchfuleye user=watchful password=watchfulpass host=localhost port=5432")

# Force local-only behavior for deterministic tests (no Supabase, no external embeddings).
os.environ["PG_DSN"] = PG_DSN
os.environ["DISABLE_SEMANTIC"] = "true"
# Prevent python-dotenv from re-populating these from .env during web_app import.
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""


class TestE2EBackendSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure schema exists
        ensure_postgres_schema(PG_DSN)
        # Seed one article that should be searchable via Postgres FTS
        now = datetime.now(timezone.utc)
        cls.seed_title = "E2E Smoke: Sanctions disrupt oil markets"
        cls.seed_desc = "E2E test article describing sanctions and their effect on oil markets."
        cls.seed_url = "https://example.com/e2e/sanctions-oil"
        with psycopg.connect(PG_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sources (domain, display_name, trust_score)
                    VALUES ('example.com', 'Example', 0.90)
                    ON CONFLICT (domain) DO UPDATE SET trust_score = EXCLUDED.trust_score
                    """
                )
                cur.execute(
                    """
                    INSERT INTO articles (
                      canonical_url, url_hash, title, description, source_domain, source_name,
                      bucket, trust_score, quality_score, extraction_confidence, created_at, published_at,
                      excerpt, extracted_text, content_hash
                    )
                    VALUES (
                      %s, md5(%s), %s, %s, 'example.com', 'Example',
                      'main', 0.90, 0.90, 0.90, %s, %s,
                      %s, %s, md5(%s)
                    )
                    ON CONFLICT (canonical_url) DO UPDATE SET
                      title = EXCLUDED.title,
                      description = EXCLUDED.description,
                      trust_score = EXCLUDED.trust_score,
                      quality_score = EXCLUDED.quality_score,
                      extraction_confidence = EXCLUDED.extraction_confidence,
                      excerpt = EXCLUDED.excerpt,
                      extracted_text = EXCLUDED.extracted_text,
                      created_at = EXCLUDED.created_at,
                      published_at = EXCLUDED.published_at
                    """,
                    (
                        cls.seed_url,
                        cls.seed_url,
                        cls.seed_title,
                        cls.seed_desc,
                        now,
                        now,
                        "Sanctions hit supply; markets react.",
                        "Sanctions hit supply; oil markets react strongly in this excerpted fulltext.",
                        cls.seed_url,
                    ),
                )

    def test_postgres_fts_search_hits_seed(self):
        from watchfuleye.storage.postgres_articles import PostgresArticleStore

        store = PostgresArticleStore(PG_DSN)
        results = store.search(query="sanctions oil", limit=20)
        self.assertTrue(any(r.get("url") == self.seed_url for r in results))

    def test_execute_search_rag_returns_sources(self):
        from web_app import execute_search_rag

        sources, ctx = execute_search_rag("sanctions oil", None, limit=5)
        self.assertGreaterEqual(len(sources), 1)
        self.assertTrue(any(s.get("url") == self.seed_url for s in sources))
        self.assertIn("sanctions", (ctx or "").lower())

    def test_api_endpoints_smoke(self):
        import importlib
        import web_app as web_app_mod

        # Reload to pick up env overrides if previously imported.
        web_app_mod = importlib.reload(web_app_mod)
        client = web_app_mod.app.test_client()

        r = client.get("/api/categories")
        self.assertEqual(r.status_code, 200)

        r = client.get("/api/articles?limit=5")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data.get("success"))

        r = client.get("/api/search?q=sanctions&limit=5")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data.get("success"))


if __name__ == "__main__":
    unittest.main()



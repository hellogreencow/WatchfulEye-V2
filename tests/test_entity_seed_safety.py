import os
import unittest

import psycopg

from watchfuleye.storage.postgres_schema import ensure_postgres_schema
from watchfuleye.v3.entity_seeds import seed_minimal_countries


class TestEntitySeedSafety(unittest.TestCase):
    PG_DSN = os.environ.get("PG_DSN", "dbname=watchfuleye user=watchful password=watchfulpass host=localhost port=5432")

    @classmethod
    def setUpClass(cls) -> None:
        ensure_postgres_schema(cls.PG_DSN)

    def tearDown(self) -> None:
        # Clean up any rows created by this test so re-runs are isolated.
        with psycopg.connect(self.PG_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM entity_identifiers WHERE entity_id = 'country_manual_us'")
                cur.execute("DELETE FROM entities WHERE id = 'country_manual_us'")

    def test_seeding_does_not_hijack_existing_identifier(self) -> None:
        # Create a pre-existing identifier owned by a non-seed source.
        with psycopg.connect(self.PG_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO entities (id, entity_type, label)
                    VALUES ('country_manual_us', 'country', 'United States (Manual)')
                    ON CONFLICT (id) DO NOTHING
                    """
                )
                cur.execute(
                    """
                    INSERT INTO entity_identifiers (entity_id, identifier_type, identifier_value, confidence, provenance)
                    VALUES ('country_manual_us', 'iso3166', 'US', 1.0, '{"source_system":"manual"}'::jsonb)
                    ON CONFLICT (identifier_type, identifier_value) DO UPDATE
                      SET entity_id = EXCLUDED.entity_id,
                          confidence = EXCLUDED.confidence,
                          provenance = EXCLUDED.provenance
                    """
                )

        # Run seed; it should not steal iso3166=US away from manual.
        seed_minimal_countries(self.PG_DSN)

        with psycopg.connect(self.PG_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT entity_id, provenance->>'source_system'
                    FROM entity_identifiers
                    WHERE identifier_type = 'iso3166' AND identifier_value = 'US'
                    """
                )
                row = cur.fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[0], "country_manual_us")
                self.assertEqual(row[1], "manual")


if __name__ == "__main__":
    unittest.main()



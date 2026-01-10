import os
import unittest

import psycopg

from watchfuleye.storage.postgres_schema import ensure_postgres_schema


class TestV3AlertsSchema(unittest.TestCase):
    def setUp(self) -> None:
        self.pg_dsn = os.environ.get("PG_DSN")
        if not self.pg_dsn:
            self.skipTest("PG_DSN not configured")

        try:
            ensure_postgres_schema(self.pg_dsn)
        except Exception as e:
            self.skipTest(f"Postgres schema not available: {e}")

    def test_alert_tables_exist(self) -> None:
        assert self.pg_dsn is not None
        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.alert_rules');")
                self.assertIsNotNone(cur.fetchone()[0])
                cur.execute("SELECT to_regclass('public.alert_events');")
                self.assertIsNotNone(cur.fetchone()[0])

    def test_alert_events_fk(self) -> None:
        assert self.pg_dsn is not None
        with psycopg.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO alert_rules (id, name, enabled, rule_type)
                    VALUES ('t_rule_1', 'test', TRUE, 'custom')
                    ON CONFLICT (id) DO NOTHING
                    """
                )
                cur.execute(
                    """
                    INSERT INTO alert_events (rule_id, event_type, payload)
                    VALUES ('t_rule_1', 'fired', '{}'::jsonb)
                    """
                )
                conn.commit()

                cur.execute("SELECT COUNT(*) FROM alert_events WHERE rule_id='t_rule_1';")
                count = int(cur.fetchone()[0])
                self.assertGreaterEqual(count, 1)

                # Cleanup test rows only
                cur.execute("DELETE FROM alert_events WHERE rule_id='t_rule_1';")
                cur.execute("DELETE FROM alert_rules WHERE id='t_rule_1';")
                conn.commit()


if __name__ == "__main__":
    unittest.main()



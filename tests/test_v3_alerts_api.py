from __future__ import annotations

import importlib
import os
import unittest


def _create_session_token(username: str) -> str:
    from database import NewsDatabase

    db_path = os.environ.get("DB_PATH", "news_bot.db")
    db = NewsDatabase(db_path=db_path)
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ? AND is_active = TRUE", (username,))
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"User not found: {username}")
        uid = row["id"] if isinstance(row, dict) or hasattr(row, "keys") else row[0]
    return db.create_session(int(uid))


class TestV3AlertsApi(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_env = dict(os.environ)
        os.environ["V3_ALERTS"] = "true"

        # CI provides PG_DSN; locally this test will skip if not configured.
        if not os.environ.get("PG_DSN"):
            self.skipTest("PG_DSN not configured")

        import web_app as web_app_mod

        self.web_app_mod = importlib.reload(web_app_mod)
        self.client = self.web_app_mod.app.test_client()

        self.admin_token = _create_session_token("oli")
        self.user_token = _create_session_token("todd")

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_rules_requires_auth(self) -> None:
        r = self.client.get("/api/v3/alerts/rules")
        self.assertEqual(r.status_code, 401)

    def test_rules_requires_admin(self) -> None:
        r = self.client.get(
            "/api/v3/alerts/rules",
            headers={"Authorization": f"Bearer {self.user_token}"},
        )
        self.assertEqual(r.status_code, 403)

    def test_create_and_list_rule(self) -> None:
        rid = "t_alert_rule_api_1"
        # Create
        r = self.client.post(
            "/api/v3/alerts/rules",
            json={
                "id": rid,
                "name": "Test Rule",
                "rule_type": "term_trend",
                "enabled": True,
                "config": {"threshold": 3.0, "min_count": 1, "lookback_hours": 1},
                "channels": ["in_app"],
            },
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(r.status_code, 200)

        # List
        r2 = self.client.get(
            "/api/v3/alerts/rules",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(r2.status_code, 200)
        data = r2.get_json()
        self.assertTrue(data.get("success"))
        rules = data.get("data") or []
        self.assertTrue(any(rr.get("id") == rid for rr in rules))


if __name__ == "__main__":
    unittest.main()



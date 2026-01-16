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


class TestV3AlertsInboxApi(unittest.TestCase):
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

    def test_inbox_requires_auth(self) -> None:
        r = self.client.get("/api/v3/alerts/inbox")
        self.assertEqual(r.status_code, 401)

    def test_inbox_allows_non_admin_user(self) -> None:
        r = self.client.get(
            "/api/v3/alerts/inbox?limit=10",
            headers={"Authorization": f"Bearer {self.user_token}"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.get_json() or {}
        self.assertTrue(body.get("success"))
        self.assertIn("unread_count", body)
        self.assertIn("last_seen_event_id", body)
        self.assertIn("newest_event_id", body)

    def test_mark_seen_advances(self) -> None:
        # First read
        r = self.client.get(
            "/api/v3/alerts/inbox?limit=10",
            headers={"Authorization": f"Bearer {self.user_token}"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.get_json() or {}
        newest = int(body.get("newest_event_id") or 0)

        # Mark seen to newest (or 1 if there are no events yet)
        target = newest if newest > 0 else 1
        r2 = self.client.post(
            "/api/v3/alerts/inbox/mark-seen",
            json={"last_seen_event_id": target},
            headers={"Authorization": f"Bearer {self.user_token}"},
        )
        self.assertEqual(r2.status_code, 200)
        body2 = r2.get_json() or {}
        self.assertTrue(body2.get("success"))
        self.assertGreaterEqual(int(body2.get("last_seen_event_id") or 0), target)


if __name__ == "__main__":
    unittest.main()



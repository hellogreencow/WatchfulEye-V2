from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from unittest.mock import patch

TEST_FERNET_KEY = "PiDLPejOZEz6HMwx7tT53M0FvAcbE2p3DoubsmdMAO0="


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


class TestV3ApiKeysApi(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_env = dict(os.environ)

        # Isolated SQLite DB for this test module
        self._tmp_db = tempfile.NamedTemporaryFile(prefix="we_test_api_keys_", suffix=".db", delete=False)
        self._tmp_db.close()
        os.environ["DB_PATH"] = self._tmp_db.name

        # Keep WS6.1 surfaces explicit for tests
        os.environ["V3_FORECAST_TRACKING"] = "true"
        os.environ["V3_API_KEYS_ENCRYPTION_KEY"] = TEST_FERNET_KEY

        # Ensure app is loaded with the v3 blueprint registry
        import web_app as web_app_mod

        self.web_app_mod = importlib.reload(web_app_mod)
        self.client = self.web_app_mod.app.test_client()

        # Auth tokens (SQLite-backed)
        self.admin_token = _create_session_token("oli")
        self.user_token = _create_session_token("todd")

    def tearDown(self) -> None:
        # Restore env
        os.environ.clear()
        os.environ.update(self._orig_env)
        try:
            os.unlink(self._tmp_db.name)
        except Exception:
            pass

    def test_list_requires_auth(self) -> None:
        r = self.client.get("/api/v3/admin/api-keys")
        self.assertEqual(r.status_code, 401)

    def test_list_requires_admin(self) -> None:
        r = self.client.get(
            "/api/v3/admin/api-keys",
            headers={"Authorization": f"Bearer {self.user_token}"},
        )
        self.assertEqual(r.status_code, 403)

    def test_list_admin_shape(self) -> None:
        r = self.client.get(
            "/api/v3/admin/api-keys",
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIsInstance(data, dict)
        self.assertIn("encryption_configured", data)
        self.assertIn("keys", data)
        self.assertIn("endpoint_tests", data)
        keys = data["keys"]
        self.assertIsInstance(keys, list)
        self.assertTrue(any(k.get("name") == "alpha_vantage" for k in keys))

    def test_set_key_and_test_alpha_vantage(self) -> None:
        # Save key
        r = self.client.put(
            "/api/v3/admin/api-keys/alpha_vantage",
            json={"value": "av_test_key"},
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(r.status_code, 200)

        # Mock Alpha Vantage HTTP
        class _Resp:
            status_code = 200

            def json(self):
                return {"Time Series (Daily)": {"2026-01-01": {"4. close": "100.0"}}}

        with patch("watchfuleye.v3.api_keys_api.requests.get", return_value=_Resp()):
            r2 = self.client.post(
                "/api/v3/admin/api-keys/alpha_vantage/test",
                json={},
                headers={"Authorization": f"Bearer {self.admin_token}"},
            )
        self.assertEqual(r2.status_code, 200)
        out = r2.get_json()
        self.assertIsInstance(out, dict)
        self.assertTrue(out.get("ok"))

    def test_endpoint_test_yahoo_finance(self) -> None:
        class _Resp:
            status_code = 200

            def json(self):
                return {"chart": {"result": [{"timestamp": [1], "indicators": {"quote": [{"close": [1.0]}]}}], "error": None}}

        with patch("watchfuleye.v3.api_keys_api.requests.get", return_value=_Resp()):
            r = self.client.post(
                "/api/v3/admin/endpoints/test",
                json={"endpoint": "yahoo_finance"},
                headers={"Authorization": f"Bearer {self.admin_token}"},
            )
        self.assertEqual(r.status_code, 200)
        out = r.get_json()
        self.assertTrue(out.get("ok"))


if __name__ == "__main__":
    unittest.main()



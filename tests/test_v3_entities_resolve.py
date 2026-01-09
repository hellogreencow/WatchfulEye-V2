import os
import unittest


class TestV3EntitiesResolve(unittest.TestCase):
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
        self.assertEqual(data.get("matches"), [])


if __name__ == "__main__":
    unittest.main()



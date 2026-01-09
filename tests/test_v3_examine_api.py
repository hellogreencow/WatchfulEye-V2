import os
import unittest


class TestV3ExamineApi(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("V3_EXAMINE_MVP", None)

    def test_examine_flag_off_404(self) -> None:
        import importlib
        import web_app as web_app_mod

        web_app_mod = importlib.reload(web_app_mod)
        client = web_app_mod.app.test_client()
        r = client.post("/api/v3/examine", json={"q": "US"})
        self.assertEqual(r.status_code, 404)

    def test_examine_flag_on_200_shape(self) -> None:
        os.environ["V3_EXAMINE_MVP"] = "true"
        import importlib
        import web_app as web_app_mod

        web_app_mod = importlib.reload(web_app_mod)
        client = web_app_mod.app.test_client()
        r = client.post("/api/v3/examine", json={"q": "US"})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIsInstance(data, dict)
        self.assertIn("investigation_id", data)
        self.assertIn("report_id", data)
        self.assertIn("trace_id", data)
        self.assertEqual(data.get("status"), "succeeded")
        report = data.get("report")
        self.assertIsInstance(report, dict)
        self.assertIn("title", report)
        self.assertIn("summary", report)
        self.assertIn("content", report)

        content = report.get("content")
        self.assertIsInstance(content, dict)
        for k in ("bullets", "evidence", "predictions", "dissent"):
            self.assertIn(k, content)

        bullets = content.get("bullets")
        self.assertIsInstance(bullets, list)
        self.assertLessEqual(len(bullets), 5)

        evidence = content.get("evidence")
        self.assertIsInstance(evidence, list)

        predictions = content.get("predictions")
        self.assertIsInstance(predictions, list)
        self.assertGreaterEqual(len(predictions), 3)
        for p in predictions:
            self.assertIsInstance(p, dict)
            self.assertIn("probability", p)
            self.assertIn("horizon", p)
            prob = p.get("probability")
            self.assertIsInstance(prob, (int, float))
            self.assertGreaterEqual(float(prob), 0.0)
            self.assertLessEqual(float(prob), 1.0)

        dissent = content.get("dissent")
        self.assertIsInstance(dissent, dict)
        self.assertIn("counter_case", dissent)
        self.assertIsInstance(dissent.get("counter_case"), str)
        self.assertIn("evidence", dissent)
        self.assertIsInstance(dissent.get("evidence"), list)


if __name__ == "__main__":
    unittest.main()



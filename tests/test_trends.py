import unittest

from watchfuleye.analytics.trends import tokenize, compute_term_trends


class TestTrends(unittest.TestCase):
    def test_tokenize_filters_stopwords(self):
        toks = tokenize("The market is on fire and the Fed is watching.")
        self.assertIn("market", toks)
        self.assertIn("fed", toks)
        self.assertNotIn("the", toks)

    def test_compute_term_trends_returns_items(self):
        recent = ["oil sanctions sanctions oil", "oil market"]
        baseline = ["oil", "market", "market"] * 10
        trends = compute_term_trends(recent_texts=recent, baseline_texts=baseline, recent_hours=24, baseline_hours=240, min_count=1, top_k=10)
        self.assertTrue(any(t.term == "sanctions" for t in trends))


if __name__ == "__main__":
    unittest.main()



import unittest

from watchfuleye.scoring.article_scoring import (
    is_deals_or_spam,
    relevance_score,
    source_trust_prior,
)


class TestArticleScoring(unittest.TestCase):
    def test_source_trust_prior_high(self):
        self.assertGreaterEqual(source_trust_prior("reuters.com"), 0.9)

    def test_deals_detection(self):
        self.assertTrue(is_deals_or_spam("Great deal: 50% off headphones today", "limited time discount"))

    def test_relevance_score_nonzero(self):
        score = relevance_score("Sanctions expand amid escalation", "Oil markets react")
        self.assertGreater(score, 0.2)


if __name__ == "__main__":
    unittest.main()



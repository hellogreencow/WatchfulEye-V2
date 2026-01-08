import unittest

from database import NewsDatabase


class TestCategorizationGuardrails(unittest.TestCase):
    def test_sports_does_not_become_sanctions(self):
        db = NewsDatabase(":memory:")
        cat, conf = db._enhanced_categorization(
            "Indiana Pacers face sanctions after league review",
            "NBA disciplinary action could include penalties and fines.",
        )
        self.assertNotEqual(cat, "sanctions")
        self.assertIn(cat, ("general", "sports", "technology", "economics", "trade", "diplomacy", "energy", "conflict"))
        self.assertLessEqual(conf, 0.5)



import json
import os
import unittest

from watchfuleye.contracts.global_brief import (
    extract_recommendations,
    validate_global_brief,
)


class TestGlobalBriefContract(unittest.TestCase):
    def test_sample_fixture_is_valid(self):
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "global_brief_sample.json")
        with open(fixture_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        errors = validate_global_brief(payload)
        self.assertEqual(errors, [], msg="Schema validation failed:\n" + "\n".join(errors))

    def test_extract_recommendations_is_deterministic(self):
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "global_brief_sample.json")
        with open(fixture_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        recs = extract_recommendations(payload, source_analysis_id=123)
        self.assertGreaterEqual(len(recs), 1)
        # Ensure normalization (uppercase action/ticker)
        for r in recs:
            self.assertTrue(r.action.isupper())
            self.assertTrue(r.ticker.isupper())
            self.assertEqual(r.source_analysis_id, 123)
            self.assertTrue(r.rationale)


if __name__ == "__main__":
    unittest.main()



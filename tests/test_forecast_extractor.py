"""Tests for WS6.1 forecast extractor (TASK 2).

Tests extraction of structured forecasts from natural language predictions.
"""

from __future__ import annotations

import unittest

from watchfuleye.v3.forecast.extractor import (
    _extract_horizon,
    _extract_probability,
    _normalize_claim,
    extract_forecasts_from_report,
)


class TestProbabilityExtraction(unittest.TestCase):
    """Tests for probability extraction from text."""

    def test_extract_explicit_percentage(self):
        """Test extraction of explicit percentage values."""
        self.assertAlmostEqual(_extract_probability("70% chance of rain"), 0.7)
        self.assertAlmostEqual(_extract_probability("30 percent chance"), 0.3)
        self.assertAlmostEqual(_extract_probability("probability of 85"), 0.85)
        self.assertAlmostEqual(_extract_probability("95% likelihood"), 0.95)

    def test_extract_decimal_probability(self):
        """Test extraction of decimal probability values."""
        self.assertAlmostEqual(_extract_probability("probability of 0.73"), 0.73)
        self.assertAlmostEqual(_extract_probability("0.65 chance"), 0.65)

    def test_extract_qualitative_high_confidence(self):
        """Test extraction of high-confidence qualitative phrases."""
        self.assertAlmostEqual(_extract_probability("highly likely outcome"), 0.75)
        self.assertAlmostEqual(_extract_probability("almost certain to happen"), 0.95)
        self.assertAlmostEqual(_extract_probability("likely scenario"), 0.65)

    def test_extract_qualitative_medium_confidence(self):
        """Test extraction of medium-confidence qualitative phrases."""
        self.assertAlmostEqual(_extract_probability("possible outcome"), 0.50)
        self.assertAlmostEqual(_extract_probability("could happen"), 0.50)
        self.assertAlmostEqual(_extract_probability("maybe it will occur"), 0.50)

    def test_extract_qualitative_low_confidence(self):
        """Test extraction of low-confidence qualitative phrases."""
        self.assertAlmostEqual(_extract_probability("unlikely event"), 0.35)
        self.assertAlmostEqual(_extract_probability("highly unlikely scenario"), 0.15)
        self.assertAlmostEqual(_extract_probability("improbable outcome"), 0.25)

    def test_extract_no_probability(self):
        """Test that None is returned when no probability is found."""
        self.assertIsNone(_extract_probability("Iran will increase exports"))
        self.assertIsNone(_extract_probability("The market closes today"))


class TestHorizonExtraction(unittest.TestCase):
    """Tests for time horizon extraction from text."""

    def test_extract_days(self):
        """Test extraction of day-based horizons."""
        self.assertEqual(_extract_horizon("within 30 days"), 30)
        self.assertEqual(_extract_horizon("in 7 days"), 7)
        self.assertEqual(_extract_horizon("within 14 days"), 14)

    def test_extract_weeks(self):
        """Test extraction of week-based horizons."""
        self.assertEqual(_extract_horizon("within 2 weeks"), 14)  # 2 * 7
        self.assertEqual(_extract_horizon("in 3 weeks"), 21)  # 3 * 7
        self.assertEqual(_extract_horizon("by end of week"), 7)

    def test_extract_months(self):
        """Test extraction of month-based horizons."""
        self.assertEqual(_extract_horizon("within 3 months"), 90)  # 3 * 30
        self.assertEqual(_extract_horizon("in 2 months"), 60)  # 2 * 30
        self.assertEqual(_extract_horizon("by end of month"), 30)

    def test_extract_quarters(self):
        """Test extraction of quarter-based horizons."""
        self.assertEqual(_extract_horizon("by end of quarter"), 90)
        self.assertEqual(_extract_horizon("by end of the quarter"), 90)

    def test_extract_year(self):
        """Test extraction of year-based horizons."""
        self.assertEqual(_extract_horizon("by end of year"), 365)
        self.assertEqual(_extract_horizon("by end of the year"), 365)

    def test_extract_default_horizon(self):
        """Test default horizon when none specified."""
        self.assertEqual(_extract_horizon("Iran increases exports"), 30)
        self.assertEqual(_extract_horizon("Market will crash"), 30)


class TestClaimNormalization(unittest.TestCase):
    """Tests for claim text normalization."""

    def test_normalize_removes_probability(self):
        """Test that probability phrases are removed."""
        claim = "70% chance that Iran increases oil exports"
        normalized = _normalize_claim(claim)
        self.assertNotIn("70%", normalized)
        self.assertNotIn("chance", normalized.lower())
        self.assertIn("Iran", normalized)

    def test_normalize_removes_horizon(self):
        """Test that horizon phrases are removed."""
        claim = "Iran increases exports within 30 days"
        normalized = _normalize_claim(claim)
        self.assertNotIn("within 30 days", normalized)
        self.assertIn("Iran", normalized)

    def test_normalize_removes_qualitative(self):
        """Test that qualitative probability words are removed."""
        claim = "Highly likely that TSLA stock rises"
        normalized = _normalize_claim(claim)
        self.assertNotIn("highly likely", normalized.lower())
        self.assertIn("TSLA", normalized)

    def test_normalize_cleans_whitespace(self):
        """Test that extra whitespace is cleaned up."""
        claim = "70%    chance    within   30  days   Iran  exports"
        normalized = _normalize_claim(claim)
        # Should have single spaces only
        self.assertNotIn("    ", normalized)
        self.assertNotIn("  ", normalized)


class TestForecastExtraction(unittest.TestCase):
    """Tests for full forecast extraction from reports."""

    def test_extract_single_forecast(self):
        """Test extraction of a single forecast."""
        report_content = {
            "predictions": [
                "70% chance Iran increases oil exports within 30 days"
            ],
            "evidence_ids": ["art_123", "art_456"],
        }

        forecasts = extract_forecasts_from_report("rpt_1", report_content, "inv_1")

        self.assertEqual(len(forecasts), 1)
        fc = forecasts[0]

        # Check core fields
        self.assertIsNotNone(fc["id"])
        self.assertTrue(fc["id"].startswith("fc_"))
        self.assertEqual(fc["report_id"], "rpt_1")
        self.assertEqual(fc["investigation_id"], "inv_1")

        # Check extracted values
        self.assertAlmostEqual(fc["probability"], 0.7)
        self.assertEqual(fc["horizon_days"], 30)
        self.assertIn("Iran", fc["claim"])
        self.assertIn("oil exports", fc["claim"])

        # Check metadata
        self.assertEqual(fc["outcome_status"], "pending")
        self.assertIsNone(fc["outcome_result"])
        self.assertEqual(fc["evidence_ids"], ["art_123", "art_456"])

    def test_extract_multiple_forecasts(self):
        """Test extraction of multiple forecasts from one report."""
        report_content = {
            "predictions": [
                "70% chance Iran increases oil exports within 30 days",
                "Highly likely TSLA stock rises by end of quarter",
                "Unlikely that Gaza conflict resolves in 2 weeks",
            ],
            "evidence_ids": ["art_123"],
        }

        forecasts = extract_forecasts_from_report("rpt_1", report_content)

        self.assertEqual(len(forecasts), 3)

        # Check first forecast
        self.assertAlmostEqual(forecasts[0]["probability"], 0.7)
        self.assertEqual(forecasts[0]["horizon_days"], 30)

        # Check second forecast (qualitative only, no explicit %)
        self.assertAlmostEqual(forecasts[1]["probability"], 0.75)  # "highly likely"
        self.assertEqual(forecasts[1]["horizon_days"], 90)  # quarter

        # Check third forecast
        self.assertAlmostEqual(forecasts[2]["probability"], 0.35)  # "unlikely"
        self.assertEqual(forecasts[2]["horizon_days"], 14)  # 2 weeks

    def test_extract_skips_no_probability(self):
        """Test that predictions without clear probability are skipped."""
        report_content = {
            "predictions": [
                "Iran will increase exports",  # No probability
                "70% chance TSLA rises within 30 days",  # Has probability
            ],
        }

        forecasts = extract_forecasts_from_report("rpt_1", report_content)

        # Should only extract the one with probability
        self.assertEqual(len(forecasts), 1)
        self.assertAlmostEqual(forecasts[0]["probability"], 0.7)

    def test_extract_empty_predictions(self):
        """Test with no predictions."""
        report_content = {"predictions": []}

        forecasts = extract_forecasts_from_report("rpt_1", report_content)

        self.assertEqual(len(forecasts), 0)

    def test_extract_missing_predictions(self):
        """Test with missing predictions key."""
        report_content = {}

        forecasts = extract_forecasts_from_report("rpt_1", report_content)

        self.assertEqual(len(forecasts), 0)

    def test_extract_entity_references(self):
        """Test extraction of entity references."""
        report_content = {
            "predictions": [
                "70% chance TSLA stock rises 10% within 30 days",
                "Highly likely Iran increases exports within 2 months",
            ],
        }

        forecasts = extract_forecasts_from_report("rpt_1", report_content)

        # First forecast should extract TSLA ticker
        fc1 = forecasts[0]
        self.assertIsNotNone(fc1["entity_ids"])
        self.assertIn("ticker", fc1["entity_types"])
        # Check if TSLA was extracted (case insensitive)
        tsla_found = any("tsla" in eid.lower() for eid in fc1["entity_ids"])
        self.assertTrue(tsla_found)

        # Second forecast should extract Iran country
        fc2 = forecasts[1]
        self.assertIsNotNone(fc2["entity_ids"])
        self.assertIn("country", fc2["entity_types"])
        # Check if Iran was extracted
        iran_found = any("iran" in eid.lower() for eid in fc2["entity_ids"])
        self.assertTrue(iran_found)


if __name__ == "__main__":
    unittest.main()

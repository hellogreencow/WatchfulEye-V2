"""Tests for WS6.1 forecast scorer (TASK 5).

Tests proper scoring rules: Brier score, log score, calibration analysis.
"""

from __future__ import annotations

import unittest

from watchfuleye.v3.forecast.scorer import (
    assign_calibration_bin,
    calculate_brier_score,
    calculate_calibration_curve,
    calculate_log_score,
    calculate_overall_metrics,
)


class TestBrierScore(unittest.TestCase):
    """Tests for Brier score calculation."""

    def test_brier_score_perfect_predictions(self):
        """Perfect predictions should have Brier score = 0."""
        self.assertAlmostEqual(calculate_brier_score(1.0, True), 0.0)
        self.assertAlmostEqual(calculate_brier_score(0.0, False), 0.0)

    def test_brier_score_worst_predictions(self):
        """Worst predictions should have Brier score = 1."""
        self.assertAlmostEqual(calculate_brier_score(0.0, True), 1.0)
        self.assertAlmostEqual(calculate_brier_score(1.0, False), 1.0)

    def test_brier_score_partial_confidence(self):
        """Test intermediate confidence levels."""
        # 70% confidence, happened
        self.assertAlmostEqual(calculate_brier_score(0.7, True), 0.09)
        # 70% confidence, didn't happen
        self.assertAlmostEqual(calculate_brier_score(0.7, False), 0.49)
        # 50% confidence (uncertainty)
        self.assertAlmostEqual(calculate_brier_score(0.5, True), 0.25)
        self.assertAlmostEqual(calculate_brier_score(0.5, False), 0.25)

    def test_brier_score_validation(self):
        """Test that invalid probabilities raise ValueError."""
        with self.assertRaises(ValueError):
            calculate_brier_score(1.5, True)
        with self.assertRaises(ValueError):
            calculate_brier_score(-0.1, False)


class TestLogScore(unittest.TestCase):
    """Tests for logarithmic score calculation."""

    def test_log_score_perfect_predictions(self):
        """Perfect predictions should have log score = 0."""
        self.assertAlmostEqual(calculate_log_score(1.0, True), 0.0)
        self.assertAlmostEqual(calculate_log_score(0.0, False), 0.0)

    def test_log_score_good_predictions(self):
        """Good confident predictions should have low log score."""
        # 90% confidence, happened
        score = calculate_log_score(0.9, True)
        self.assertLess(score, 0.2)  # Should be ~0.105
        # 10% confidence, didn't happen
        score = calculate_log_score(0.1, False)
        self.assertLess(score, 0.2)

    def test_log_score_bad_predictions(self):
        """Bad confident predictions should have high log score."""
        # 90% confidence, didn't happen
        score = calculate_log_score(0.9, False)
        self.assertGreater(score, 2.0)  # Should be ~2.303
        # 10% confidence, happened
        score = calculate_log_score(0.1, True)
        self.assertGreater(score, 2.0)

    def test_log_score_uncertain_predictions(self):
        """Uncertain predictions (50%) should have log score ~0.693."""
        score = calculate_log_score(0.5, True)
        self.assertAlmostEqual(score, 0.693, places=2)
        score = calculate_log_score(0.5, False)
        self.assertAlmostEqual(score, 0.693, places=2)

    def test_log_score_edge_cases(self):
        """Test edge cases (0.0 and 1.0 probabilities)."""
        # 0% confidence, happened → infinite penalty
        self.assertEqual(calculate_log_score(0.0, True), float('inf'))
        # 100% confidence, didn't happen → infinite penalty
        self.assertEqual(calculate_log_score(1.0, False), float('inf'))


class TestCalibrationBin(unittest.TestCase):
    """Tests for calibration bin assignment."""

    def test_calibration_bin_assignment(self):
        """Test probability → bin mapping."""
        self.assertEqual(assign_calibration_bin(0.05), 0)
        self.assertEqual(assign_calibration_bin(0.15), 1)
        self.assertEqual(assign_calibration_bin(0.25), 2)
        self.assertEqual(assign_calibration_bin(0.50), 5)
        self.assertEqual(assign_calibration_bin(0.75), 7)
        self.assertEqual(assign_calibration_bin(0.95), 9)
        self.assertEqual(assign_calibration_bin(1.0), 9)  # Edge case

    def test_calibration_bin_boundaries(self):
        """Test bin boundaries."""
        self.assertEqual(assign_calibration_bin(0.0), 0)
        self.assertEqual(assign_calibration_bin(0.09), 0)
        self.assertEqual(assign_calibration_bin(0.1), 1)
        self.assertEqual(assign_calibration_bin(0.19), 1)
        self.assertEqual(assign_calibration_bin(0.2), 2)


class TestCalibrationCurve(unittest.TestCase):
    """Tests for calibration curve calculation."""

    def test_calibration_curve_perfect(self):
        """Test perfectly calibrated forecasts."""
        forecasts = [
            # 7 out of 10 at 70% should happen (perfect calibration)
            {"probability": 0.7, "outcome_status": "resolved", "outcome_result": True},
            {"probability": 0.7, "outcome_status": "resolved", "outcome_result": True},
            {"probability": 0.7, "outcome_status": "resolved", "outcome_result": True},
            {"probability": 0.7, "outcome_status": "resolved", "outcome_result": True},
            {"probability": 0.7, "outcome_status": "resolved", "outcome_result": True},
            {"probability": 0.7, "outcome_status": "resolved", "outcome_result": True},
            {"probability": 0.7, "outcome_status": "resolved", "outcome_result": True},
            {"probability": 0.7, "outcome_status": "resolved", "outcome_result": False},
            {"probability": 0.7, "outcome_status": "resolved", "outcome_result": False},
            {"probability": 0.7, "outcome_status": "resolved", "outcome_result": False},
        ]

        curve = calculate_calibration_curve(forecasts)

        # Should be in bin 7 (70%)
        self.assertIn(7, curve)
        self.assertEqual(curve[7]["count"], 10)
        self.assertAlmostEqual(curve[7]["observed"], 0.7, places=1)
        self.assertAlmostEqual(curve[7]["expected"], 0.75, places=2)  # Midpoint of bin
        self.assertLess(curve[7]["error"], 0.1)  # Low calibration error

    def test_calibration_curve_overconfident(self):
        """Test overconfident forecasts (claim 90% but only hit 60%)."""
        forecasts = [
            {"probability": 0.9, "outcome_status": "resolved", "outcome_result": True},
            {"probability": 0.9, "outcome_status": "resolved", "outcome_result": True},
            {"probability": 0.9, "outcome_status": "resolved", "outcome_result": True},
            {"probability": 0.9, "outcome_status": "resolved", "outcome_result": False},
            {"probability": 0.9, "outcome_status": "resolved", "outcome_result": False},
        ]

        curve = calculate_calibration_curve(forecasts)

        # Should be in bin 9 (90%)
        self.assertIn(9, curve)
        self.assertEqual(curve[9]["count"], 5)
        self.assertAlmostEqual(curve[9]["observed"], 0.6, places=1)  # Only 60% happened
        self.assertAlmostEqual(curve[9]["expected"], 0.95, places=2)  # Expected 95%
        self.assertGreater(curve[9]["error"], 0.2)  # High calibration error

    def test_calibration_curve_ignores_pending(self):
        """Test that pending forecasts are ignored."""
        forecasts = [
            {"probability": 0.7, "outcome_status": "resolved", "outcome_result": True},
            {"probability": 0.7, "outcome_status": "pending", "outcome_result": None},
            {"probability": 0.7, "outcome_status": "unresolved", "outcome_result": None},
        ]

        curve = calculate_calibration_curve(forecasts)

        # Should only count resolved forecast
        if 7 in curve:
            self.assertEqual(curve[7]["count"], 1)


class TestOverallMetrics(unittest.TestCase):
    """Tests for aggregate metrics calculation."""

    def test_overall_metrics_comprehensive(self):
        """Test comprehensive metrics calculation."""
        forecasts = [
            {"probability": 0.7, "outcome_status": "resolved", "outcome_result": True},
            {"probability": 0.8, "outcome_status": "resolved", "outcome_result": True},
            {"probability": 0.6, "outcome_status": "resolved", "outcome_result": False},
            {"probability": 0.9, "outcome_status": "resolved", "outcome_result": True},
            {"probability": 0.5, "outcome_status": "pending", "outcome_result": None},
        ]

        metrics = calculate_overall_metrics(forecasts)

        # Check total counts
        self.assertEqual(metrics["total_forecasts"], 4)  # Only resolved

        # Check Brier score is calculated
        self.assertIsNotNone(metrics["mean_brier_score"])
        self.assertLess(metrics["mean_brier_score"], 0.5)  # Should be decent

        # Check accuracy percentage
        self.assertIsNotNone(metrics["accuracy_percentage"])
        self.assertEqual(metrics["accuracy_percentage"], 75.0)  # 3 out of 4 correct

    def test_overall_metrics_empty(self):
        """Test with no resolved forecasts."""
        forecasts = [
            {"probability": 0.7, "outcome_status": "pending", "outcome_result": None},
        ]

        metrics = calculate_overall_metrics(forecasts)

        self.assertEqual(metrics["total_forecasts"], 0)
        self.assertIsNone(metrics["mean_brier_score"])
        self.assertIsNone(metrics["accuracy_percentage"])


if __name__ == "__main__":
    unittest.main()

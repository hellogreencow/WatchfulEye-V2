"""WS6.1 TASK 5: Proper scoring rules for forecast accuracy.

Pure math functions with no dependencies - can be implemented and tested independently.
Implements Brier score, logarithmic score, and calibration analysis.

References:
- Brier (1950): Verification of forecasts expressed in terms of probability
- Proper scoring rules ensure honesty: best strategy is to report true beliefs
- Target: Brier < 0.20 (73% accuracy), calibration error < 0.10
"""

from __future__ import annotations

import math
from typing import Any


def calculate_brier_score(probability: float, outcome: bool) -> float:
    """Calculate Brier score for a single forecast.

    Brier score = (probability - actual)^2
    Range: [0, 1] where 0 is perfect, 1 is worst

    Args:
        probability: Forecast probability [0, 1]
        outcome: Actual outcome (True/False)

    Returns:
        Brier score in range [0, 1]

    Examples:
        >>> calculate_brier_score(0.7, True)   # Good forecast
        0.09
        >>> calculate_brier_score(0.7, False)  # Bad forecast
        0.49
        >>> calculate_brier_score(1.0, True)   # Perfect
        0.0
    """
    if not (0.0 <= probability <= 1.0):
        raise ValueError(f"Probability must be in [0, 1], got {probability}")

    actual = 1.0 if outcome else 0.0
    return (probability - actual) ** 2


def calculate_log_score(probability: float, outcome: bool) -> float:
    """Calculate logarithmic score for a single forecast.

    Log score = -log(p) if outcome occurred, -log(1-p) otherwise
    Range: [0, ∞] where 0 is perfect, higher is worse

    This is more sensitive to extreme probabilities than Brier score.

    Args:
        probability: Forecast probability [0, 1]
        outcome: Actual outcome (True/False)

    Returns:
        Logarithmic score (lower is better)

    Examples:
        >>> calculate_log_score(0.9, True)   # Good confident forecast
        0.105
        >>> calculate_log_score(0.9, False)  # Bad confident forecast
        2.303
    """
    if not (0.0 < probability < 1.0):
        # Handle edge cases to avoid log(0)
        if probability == 0.0:
            return float('inf') if outcome else 0.0
        if probability == 1.0:
            return 0.0 if outcome else float('inf')
        raise ValueError(f"Probability must be in (0, 1), got {probability}")

    p = probability if outcome else (1.0 - probability)
    return -math.log(p)


def assign_calibration_bin(probability: float) -> int:
    """Assign probability to calibration bin [0-9].

    Bin 0: [0.0, 0.1), Bin 1: [0.1, 0.2), ..., Bin 9: [0.9, 1.0]

    Args:
        probability: Forecast probability [0, 1]

    Returns:
        Bin index 0-9
    """
    if not (0.0 <= probability <= 1.0):
        raise ValueError(f"Probability must be in [0, 1], got {probability}")

    # Handle edge case: probability = 1.0 goes in bin 9
    if probability == 1.0:
        return 9

    return int(probability * 10)


def calculate_calibration_curve(
    forecasts: list[dict[str, Any]]
) -> dict[int, dict[str, float]]:
    """Calculate calibration curve across all resolved forecasts.

    Perfect calibration means: forecasts at 70% should happen 70% of the time.
    This function bins forecasts by probability and measures observed frequency.

    Args:
        forecasts: List of forecast dicts with:
            - probability: float
            - outcome_status: str (must be "resolved")
            - outcome_result: bool

    Returns:
        Dict mapping bin_idx -> {
            "expected": expected frequency for this bin,
            "observed": actual frequency in this bin,
            "count": number of forecasts in this bin,
            "error": |expected - observed|
        }

    Example:
        >>> forecasts = [
        ...     {"probability": 0.7, "outcome_status": "resolved", "outcome_result": True},
        ...     {"probability": 0.7, "outcome_status": "resolved", "outcome_result": True},
        ...     {"probability": 0.7, "outcome_status": "resolved", "outcome_result": False},
        ... ]
        >>> curve = calculate_calibration_curve(forecasts)
        >>> curve[7]["count"]
        3
        >>> abs(curve[7]["observed"] - 0.67) < 0.01
        True
    """
    # Initialize bins
    bins: dict[int, dict[str, int]] = {
        i: {"count": 0, "successes": 0} for i in range(10)
    }

    # Count forecasts per bin
    for f in forecasts:
        if f.get("outcome_status") != "resolved":
            continue

        prob = f.get("probability")
        if prob is None or not (0.0 <= prob <= 1.0):
            continue

        bin_idx = assign_calibration_bin(prob)
        bins[bin_idx]["count"] += 1

        if f.get("outcome_result"):
            bins[bin_idx]["successes"] += 1

    # Calculate observed frequency and error per bin
    calibration: dict[int, dict[str, float]] = {}

    for bin_idx, data in bins.items():
        if data["count"] > 0:
            observed_freq = data["successes"] / data["count"]
            expected_freq = (bin_idx + 0.5) / 10  # Midpoint of bin

            calibration[bin_idx] = {
                "expected": expected_freq,
                "observed": observed_freq,
                "count": data["count"],
                "error": abs(observed_freq - expected_freq),
            }

    return calibration


def calculate_overall_metrics(forecasts: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate aggregate accuracy metrics across all resolved forecasts.

    Args:
        forecasts: List of forecast dicts with probability, outcome_result

    Returns:
        Dict with:
            - total_forecasts: number of resolved forecasts
            - mean_brier_score: average Brier score
            - mean_log_score: average log score
            - calibration_error: mean absolute calibration error
            - accuracy_percentage: % correct (for binary outcomes)
    """
    resolved = [
        f for f in forecasts
        if f.get("outcome_status") == "resolved" and f.get("outcome_result") is not None
    ]

    if not resolved:
        return {
            "total_forecasts": 0,
            "mean_brier_score": None,
            "mean_log_score": None,
            "calibration_error": None,
            "accuracy_percentage": None,
        }

    # Calculate scores
    brier_scores = []
    log_scores = []

    for f in resolved:
        prob = f["probability"]
        outcome = f["outcome_result"]

        brier_scores.append(calculate_brier_score(prob, outcome))
        try:
            log_scores.append(calculate_log_score(prob, outcome))
        except (ValueError, OverflowError):
            # Skip extreme probabilities for log score
            pass

    # Calculate calibration error
    calibration = calculate_calibration_curve(resolved)
    calibration_errors = [
        bin_data["error"] for bin_data in calibration.values()
    ]

    # Calculate binary accuracy (for comparison with traditional metrics)
    correct = sum(
        1 for f in resolved
        if (f["probability"] >= 0.5) == f["outcome_result"]
    )

    return {
        "total_forecasts": len(resolved),
        "mean_brier_score": sum(brier_scores) / len(brier_scores) if brier_scores else None,
        "mean_log_score": sum(log_scores) / len(log_scores) if log_scores else None,
        "calibration_error": sum(calibration_errors) / len(calibration_errors) if calibration_errors else None,
        "accuracy_percentage": (correct / len(resolved)) * 100 if resolved else None,
    }

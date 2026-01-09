"""WS6.1: Forecast Accountability - Accuracy Engine.

This module implements forecast tracking, outcome measurement, and accuracy scoring
to transform WatchfulEye from "AI analysis" to "proven track record".

Target metrics:
- Overall accuracy: 73% (Brier score < 0.20)
- Calibration error: < 0.10
- Track record across 200+ resolved forecasts
"""

from __future__ import annotations

__all__ = [
    "extract_forecasts_from_report",
    "calculate_brier_score",
    "calculate_log_score",
    "calculate_calibration_curve",
    "measure_forecast_outcome",
]

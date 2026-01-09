"""Metrics API for WS6.1 forecast accountability dashboard.

Provides aggregate accuracy metrics for the Track Record panel.

Contract notes:
- This endpoint is **flag-gated** by `V3_FORECAST_TRACKING` (default OFF).
- Response keys must be stable even when there are 0 forecasts, so the UI doesn't
  mis-grade "no data" as "bad performance".
"""

from __future__ import annotations

import os
from typing import Any

from flask import Blueprint, jsonify

from watchfuleye.v3.flags import is_v3_forecast_tracking_enabled
from watchfuleye.v3.forecast.scorer import calculate_calibration_curve, calculate_overall_metrics


bp_v3_forecast = Blueprint("v3_forecast", __name__, url_prefix="/api/v3/forecast")


@bp_v3_forecast.route("/metrics", methods=["GET"])
def get_forecast_metrics():
    """GET /api/v3/forecast/metrics

    Returns aggregate forecast accuracy metrics for the Track Record panel.

    Returns:
        200: {
            "overall": {
                "total_forecasts": int,          # total tracked (pending + resolved + unresolved)
                "resolved_forecasts": int,
                "pending_forecasts": int,        # includes "unresolved"
                "mean_brier_score": float|null,  # across resolved forecasts only
                "mean_log_score": float|null,
                "calibration_error": float|null,
                "accuracy_percentage": float|null,
                "hit_rate_by_horizon": {"7_days": float|null, "30_days": float|null, "90_days": float|null}
            },
            "by_domain": {...},
            "recent_performance": [...],
            "calibration_curve": {...}
        }
        404: Feature disabled
        500: Internal error
    """
    if not is_v3_forecast_tracking_enabled():
        return ("Not Found", 404)

    pg_dsn = os.environ.get("PG_DSN")
    if not pg_dsn:
        return jsonify({"error": "Database not configured"}), 500

    try:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(pg_dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                # Fetch all forecasts
                cur.execute(
                    """
                    SELECT
                        id,
                        claim,
                        probability,
                        horizon_days,
                        horizon_date,
                        outcome_status,
                        outcome_result,
                        outcome_confidence,
                        outcome_measured_at,
                        outcome_method,
                        brier_score,
                        log_score,
                        calibration_bin,
                        tags,
                        created_at
                    FROM forecasts
                    ORDER BY created_at DESC
                    """
                )
                forecasts = cur.fetchall()

        total_forecasts = len(forecasts)
        resolved = [f for f in forecasts if f.get("outcome_status") == "resolved"]
        pending = [f for f in forecasts if f.get("outcome_status") != "resolved"]

        if total_forecasts == 0:
            return jsonify(
                {
                    "overall": {
                        "total_forecasts": 0,
                        "resolved_forecasts": 0,
                        "pending_forecasts": 0,
                        "mean_brier_score": None,
                        "mean_log_score": None,
                        "calibration_error": None,
                        "accuracy_percentage": None,
                        "hit_rate_by_horizon": {"7_days": None, "30_days": None, "90_days": None},
                    },
                    "by_domain": {},
                    "recent_performance": [],
                    "calibration_curve": {},
                }
            )

        # Calculate overall metrics
        overall_stats = calculate_overall_metrics(forecasts)

        # Calculate by-domain metrics
        by_domain = _calculate_domain_metrics(forecasts)

        # Calculate recent performance (last 30 days, grouped by day)
        recent_performance = _calculate_recent_performance(forecasts)

        # Calculate calibration curve (resolved only)
        calibration_curve = calculate_calibration_curve(resolved)

        # Calculate hit rates by horizon (resolved only)
        hit_rate_by_horizon = _calculate_hit_rate_by_horizon(resolved)

        return jsonify({
            "overall": {
                **overall_stats,
                "total_forecasts": total_forecasts,
                "resolved_forecasts": len(resolved),
                "pending_forecasts": len(pending),
                "hit_rate_by_horizon": hit_rate_by_horizon,
            },
            "by_domain": by_domain,
            "recent_performance": recent_performance,
            "calibration_curve": calibration_curve,
        })

    except Exception as e:
        return jsonify({"error": f"Internal error: {str(e)}"}), 500


def _calculate_domain_metrics(forecasts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Calculate metrics by domain (based on tags).

    Args:
        forecasts: List of forecast dicts

    Returns:
        Dict mapping domain to metrics
    """
    domains: dict[str, dict[str, Any]] = {}
    resolved = [f for f in forecasts if f["outcome_status"] == "resolved"]

    for f in resolved:
        tags = f.get("tags", []) or []
        # Infer domain from tags or entity types
        domain = "unknown"
        if any(tag in ["geopolitics", "conflict", "policy"] for tag in tags):
            domain = "geopolitics"
        elif any(tag in ["markets", "stocks", "trading"] for tag in tags):
            domain = "markets"
        elif any(tag in ["cyber", "security", "hacking"] for tag in tags):
            domain = "cyber"

        if domain not in domains:
            domains[domain] = {"forecasts": [], "count": 0}

        domains[domain]["forecasts"].append(f)
        domains[domain]["count"] += 1

    # Calculate average Brier score per domain
    result: dict[str, dict[str, Any]] = {}
    for domain, data in domains.items():
        forecasts_list = data["forecasts"]
        if forecasts_list:
            brier_scores = [fc.get("brier_score") or 0.0 for fc in forecasts_list]
            avg_brier = sum(brier_scores) / len(brier_scores)
            result[domain] = {"avg_brier": avg_brier, "count": data["count"]}

    return result


def _calculate_recent_performance(
    forecasts: list[dict[str, Any]], days: int = 30
) -> list[dict[str, Any]]:
    """Calculate performance over recent period, grouped by day.

    Args:
        forecasts: List of forecast dicts
        days: Number of recent days to include

    Returns:
        List of dicts: [{"date": "YYYY-MM-DD", "brier": float, "count": int}]
    """
    from collections import defaultdict
    from datetime import datetime, timedelta

    resolved = [f for f in forecasts if f["outcome_status"] == "resolved"]

    # Group by date
    by_date = defaultdict(list)
    cutoff = datetime.utcnow() - timedelta(days=days)

    for f in resolved:
        measured_at = f.get("outcome_measured_at")
        if measured_at and measured_at >= cutoff:
            date_str = measured_at.strftime("%Y-%m-%d")
            if f.get("brier_score") is not None:
                by_date[date_str].append(f["brier_score"])

    # Calculate average Brier per day
    result = []
    for date_str in sorted(by_date.keys()):
        brier_scores = by_date[date_str]
        avg_brier = sum(brier_scores) / len(brier_scores)
        result.append({"date": date_str, "brier": avg_brier, "count": len(brier_scores)})

    return result


def _calculate_hit_rate_by_horizon(forecasts: list[dict[str, Any]]) -> dict[str, float | None]:
    """Calculate hit rate by time horizon.

    Args:
        forecasts: List of resolved forecast dicts

    Returns:
        Dict mapping horizon to hit rate (None if no data):
            {"7_days": 0.73, "30_days": 0.68, "90_days": 0.61}
    """
    horizons = {"7_days": 7, "30_days": 30, "90_days": 90}
    result: dict[str, float | None] = {}

    for label, days in horizons.items():
        # Filter forecasts by horizon
        in_horizon = [
            f for f in forecasts
            if f.get("horizon_days") is not None and f["horizon_days"] <= days
        ]

        if in_horizon:
            # Calculate hit rate (for forecasts >50%)
            high_confidence = [f for f in in_horizon if f.get("probability", 0) > 0.5]
            if high_confidence:
                hits = sum(1 for f in high_confidence if f.get("outcome_result"))
                result[label] = hits / len(high_confidence)
            else:
                result[label] = None
        else:
            result[label] = None

    return result

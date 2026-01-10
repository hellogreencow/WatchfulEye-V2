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


bp_v3_forecast = Blueprint("v3_forecast", __name__, url_prefix="/api/v3/forecast")


@bp_v3_forecast.route("/metrics", methods=["GET"])
def get_forecast_metrics():
    """GET /api/v3/forecast/metrics

    Returns aggregate forecast accuracy metrics for the Track Record panel.

    Returns:
        200: {
            "overall": {
                "total_forecasts": int,          # total tracked (pending + resolved + unresolved + invalid)
                "resolved_forecasts": int,
                "pending_forecasts": int,
                "unresolved_forecasts": int,
                "invalid_forecasts": int,
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

    # UX guardrails: never imply statistical confidence at tiny sample sizes.
    guardrails = {
        "min_resolved_for_grade": 20,
        "min_resolved_for_calibration": 50,
        "min_resolved_for_domain": 10,
    }

    try:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(pg_dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                # Counts (constant-time)
                cur.execute(
                    """
                    SELECT
                      COUNT(*)::int AS total_forecasts,
                      COUNT(*) FILTER (WHERE outcome_status = 'resolved')::int AS resolved_forecasts,
                      COUNT(*) FILTER (WHERE outcome_status = 'pending')::int AS pending_forecasts,
                      COUNT(*) FILTER (WHERE outcome_status = 'unresolved')::int AS unresolved_forecasts,
                      COUNT(*) FILTER (WHERE outcome_status = 'invalid')::int AS invalid_forecasts
                    FROM forecasts
                    """
                )
                counts = cur.fetchone() or {}

                total_forecasts = int(counts.get("total_forecasts") or 0)
                resolved_count = int(counts.get("resolved_forecasts") or 0)
                pending_count = int(counts.get("pending_forecasts") or 0)
                unresolved_count = int(counts.get("unresolved_forecasts") or 0)
                invalid_count = int(counts.get("invalid_forecasts") or 0)

                if total_forecasts == 0:
                    return jsonify(
                        {
                            "overall": {
                                "total_forecasts": 0,
                                "resolved_forecasts": 0,
                                "pending_forecasts": 0,
                                "unresolved_forecasts": 0,
                                "invalid_forecasts": 0,
                                "mean_brier_score": None,
                                "mean_log_score": None,
                                "calibration_error": None,
                                "accuracy_percentage": None,
                                "hit_rate_by_horizon": {"7_days": None, "30_days": None, "90_days": None},
                            },
                            "by_domain": {},
                            "recent_performance": [],
                            "calibration_curve": {},
                            "recent_forecasts": [],
                            "guardrails": guardrails,
                        }
                    )

                # Overall metrics (resolved only). Compute scores from probability/outcome so the API
                # works even if the background job hasn't populated brier/log fields yet.
                cur.execute(
                    """
                    SELECT
                      AVG(POWER(probability - (CASE WHEN outcome_result THEN 1.0 ELSE 0.0 END), 2))::float
                        AS mean_brier_score,
                      AVG(
                        CASE
                          WHEN outcome_result IS TRUE
                            THEN LN(GREATEST(probability, 1e-10))
                          ELSE LN(GREATEST(1.0 - probability, 1e-10))
                        END
                      )::float AS mean_log_score,
                      (AVG(
                        CASE
                          WHEN outcome_result IS NULL THEN NULL
                          WHEN (probability >= 0.5) = outcome_result THEN 1.0
                          ELSE 0.0
                        END
                      ) * 100.0)::float AS accuracy_percentage
                    FROM forecasts
                    WHERE outcome_status = 'resolved'
                      AND outcome_result IS NOT NULL
                    """
                )
                overall_stats = cur.fetchone() or {}

                # Calibration curve (resolved only). Compute bin from probability so we don't depend on
                # stored calibration_bin.
                cur.execute(
                    """
                    SELECT
                      LEAST(FLOOR(probability * 10), 9)::int AS bin,
                      COUNT(*)::int AS count,
                      AVG(CASE WHEN outcome_result THEN 1.0 ELSE 0.0 END)::float AS observed
                    FROM forecasts
                    WHERE outcome_status = 'resolved'
                      AND outcome_result IS NOT NULL
                    GROUP BY bin
                    ORDER BY bin
                    """
                )
                calibration_rows = cur.fetchall() or []

                calibration_curve: dict[str, dict[str, Any]] = {}
                calibration_error = None
                if calibration_rows:
                    total_in_bins = sum(int(r.get("count") or 0) for r in calibration_rows) or 0
                    weighted_error = 0.0
                    for r in calibration_rows:
                        b = int(r["bin"])
                        expected = (b + 0.5) / 10.0
                        observed = float(r.get("observed") or 0.0)
                        count = int(r.get("count") or 0)
                        err = abs(observed - expected)
                        calibration_curve[str(b)] = {
                            "expected": expected,
                            "observed": observed,
                            "count": count,
                            "error": err,
                        }
                        weighted_error += err * count
                    calibration_error = (weighted_error / total_in_bins) if total_in_bins else None

                # Hit rate by horizon (resolved only; for p>0.5)
                def _hit(days: int) -> float | None:
                    cur.execute(
                        """
                        SELECT
                          COUNT(*) FILTER (WHERE outcome_result IS TRUE)::int AS hits,
                          COUNT(*)::int AS total
                        FROM forecasts
                        WHERE outcome_status = 'resolved'
                          AND outcome_result IS NOT NULL
                          AND probability > 0.5
                          AND horizon_days IS NOT NULL
                          AND horizon_days <= %s
                        """,
                        (days,),
                    )
                    row = cur.fetchone() or {}
                    total = int(row.get("total") or 0)
                    hits = int(row.get("hits") or 0)
                    return (hits / total) if total else None

                hit_rate_by_horizon = {
                    "7_days": _hit(7),
                    "30_days": _hit(30),
                    "90_days": _hit(90),
                }

                # By-domain metrics (resolved only) — inferred from tags
                def _domain_avg(tags: list[str]) -> dict[str, Any] | None:
                    cur.execute(
                        """
                        SELECT
                          AVG(POWER(probability - (CASE WHEN outcome_result THEN 1.0 ELSE 0.0 END), 2))::float
                            AS avg_brier,
                          COUNT(*)::int AS count
                        FROM forecasts
                        WHERE outcome_status = 'resolved'
                          AND outcome_result IS NOT NULL
                          AND tags && %s::text[]
                        """,
                        (tags,),
                    )
                    row = cur.fetchone() or {}
                    count = int(row.get("count") or 0)
                    if count <= 0:
                        return None
                    return {"avg_brier": float(row.get("avg_brier") or 0.0), "count": count}

                by_domain: dict[str, dict[str, Any]] = {}
                for name, tags in (
                    ("geopolitics", ["geopolitics", "conflict", "policy"]),
                    ("markets", ["markets", "stocks", "trading"]),
                    ("cyber", ["cyber", "security", "hacking"]),
                ):
                    row = _domain_avg(tags)
                    if row:
                        by_domain[name] = row

                # Recent performance (last 30 days)
                cur.execute(
                    """
                    SELECT
                      date_trunc('day', outcome_measured_at AT TIME ZONE 'UTC') AS day,
                      AVG(POWER(probability - (CASE WHEN outcome_result THEN 1.0 ELSE 0.0 END), 2))::float
                        AS brier,
                      COUNT(*)::int AS count
                    FROM forecasts
                    WHERE outcome_status = 'resolved'
                      AND outcome_result IS NOT NULL
                      AND outcome_measured_at IS NOT NULL
                      AND outcome_measured_at >= (now() - interval '30 days')
                    GROUP BY day
                    ORDER BY day
                    """
                )
                recent_performance = [
                    {
                        "date": (r.get("day").date().isoformat() if r.get("day") else ""),
                        "brier": float(r.get("brier") or 0.0),
                        "count": int(r.get("count") or 0),
                    }
                    for r in (cur.fetchall() or [])
                    if r.get("day") is not None
                ]

                # Recent items (UI ledger)
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
                      brier_score,
                      log_score,
                      outcome_method,
                      outcome_measured_at,
                      created_at,
                      tags
                    FROM forecasts
                    ORDER BY created_at DESC
                    LIMIT 25
                    """
                )
                recent_forecasts = [_serialize_recent_forecast(f) for f in (cur.fetchall() or [])]

        return jsonify({
            "overall": {
                "mean_brier_score": overall_stats.get("mean_brier_score"),
                "mean_log_score": overall_stats.get("mean_log_score"),
                "calibration_error": calibration_error,
                "accuracy_percentage": overall_stats.get("accuracy_percentage"),
                "total_forecasts": total_forecasts,
                "resolved_forecasts": resolved_count,
                "pending_forecasts": pending_count,
                "unresolved_forecasts": unresolved_count,
                "invalid_forecasts": invalid_count,
                "hit_rate_by_horizon": hit_rate_by_horizon,
            },
            "by_domain": by_domain,
            "recent_performance": recent_performance,
            "calibration_curve": calibration_curve,
            "recent_forecasts": recent_forecasts,
            "guardrails": guardrails,
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
    from datetime import datetime, timedelta, timezone

    resolved = [f for f in forecasts if f["outcome_status"] == "resolved"]

    # Group by date
    by_date = defaultdict(list)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

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


def _serialize_recent_forecast(f: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-serializable subset for the UI ledger."""
    def _iso_any(v: Any) -> str | None:
        try:
            return v.isoformat() if v is not None else None
        except Exception:
            return None

    brier = f.get("brier_score")
    log_score = f.get("log_score")
    try:
        if brier is None and f.get("outcome_status") == "resolved" and f.get("outcome_result") is not None:
            prob_raw = f.get("probability")
            if prob_raw is None:
                raise ValueError("probability missing")
            prob = float(prob_raw)
            actual = 1.0 if bool(f.get("outcome_result")) else 0.0
            brier = (prob - actual) ** 2
            if bool(f.get("outcome_result")):
                log_score = float(__import__("math").log(max(prob, 1e-10)))
            else:
                log_score = float(__import__("math").log(max(1.0 - prob, 1e-10)))
    except Exception:
        # Best-effort only; leave fields as-is on any parsing error.
        pass

    return {
        "id": f.get("id"),
        "claim": f.get("claim"),
        "probability": f.get("probability"),
        "horizon_days": f.get("horizon_days"),
        "horizon_date": _iso_any(f.get("horizon_date")),
        "outcome_status": f.get("outcome_status"),
        "outcome_result": f.get("outcome_result"),
        "brier_score": brier,
        "log_score": log_score,
        "outcome_method": f.get("outcome_method"),
        "outcome_measured_at": _iso_any(f.get("outcome_measured_at")),
        "created_at": _iso_any(f.get("created_at")),
        "tags": f.get("tags") or [],
    }

"""WS6.1: Automated forecast outcome measurement job.

This job closes the WS6.1 loop:
1) Find forecasts whose horizon has elapsed and are still pending/unresolved
2) Measure outcome (best-effort) via `outcome_tracker.py`
3) Persist outcome + scoring fields on the forecast row
4) Append an audit trail entry in `forecast_updates`

Safety rules:
- Flag-gated by `V3_FORECAST_TRACKING` (default OFF).
- Never raises on missing Postgres / transient errors; returns a summary instead.
- External calls must be mockable in unit tests (use `requests.get` patching).
"""

from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from watchfuleye.storage.postgres_schema import ensure_postgres_schema
from watchfuleye.v3.flags import is_v3_forecast_tracking_enabled
from watchfuleye.v3.forecast.outcome_tracker import measure_forecast_outcome
from watchfuleye.v3.forecast.scorer import (
    assign_calibration_bin,
    calculate_brier_score,
    calculate_log_score,
)


def run_forecast_outcome_job(
    pg_dsn: str,
    *,
    limit: int = 50,
    log: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Run one pass of forecast outcome resolution.

    Args:
        pg_dsn: Postgres DSN
        limit: Max forecasts to process in this run
        log: Optional logger callback

    Returns:
        Summary dict: counts + error strings
    """
    _log = log or (lambda _msg: None)

    if not is_v3_forecast_tracking_enabled():
        return {"skipped": True, "reason": "V3_FORECAST_TRACKING disabled"}
    now = datetime.now(timezone.utc)
    retry_cutoff = now - timedelta(hours=6)
    processed = 0
    updated_resolved = 0
    updated_unresolved = 0
    updated_invalid = 0
    errors: list[str] = []

    try:
        # Ensure schema inside the try so Postgres outages return a summary (never raise).
        ensure_postgres_schema(pg_dsn)

        with psycopg.connect(pg_dsn, row_factory=dict_row) as conn:
            # Process one row at a time so commits don't release locks for unprocessed rows.
            while processed < int(limit):
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                          id,
                          report_id,
                          investigation_id,
                          claim,
                          probability,
                          horizon_days,
                          horizon_date,
                          entity_ids,
                          entity_types,
                          evidence_ids,
                          assumptions,
                          tags,
                          created_at,
                          updated_at,
                          outcome_status,
                          outcome_result,
                          outcome_confidence,
                          outcome_measured_at,
                          outcome_method,
                          outcome_evidence,
                          brier_score,
                          log_score,
                          calibration_bin
                        FROM forecasts
                        WHERE horizon_date <= %s
                          AND (
                            outcome_status = 'pending'
                            OR (
                              outcome_status = 'unresolved'
                              AND (outcome_measured_at IS NULL OR outcome_measured_at <= %s)
                            )
                          )
                        ORDER BY horizon_date ASC, created_at ASC
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                        """,
                        (now, retry_cutoff),
                    )
                    fc = cur.fetchone()

                if not fc:
                    break

                forecast_id = fc["id"]
                previous_state = _audit_state(fc)

                try:
                    if _is_unverifiable_forecast(fc):
                        # Keep the row for auditability, but do not "resolve" non-verifiable meta-claims.
                        outcome = {
                            "outcome_status": "invalid",
                            "outcome_result": None,
                            "outcome_confidence": 0.0,
                            "outcome_method": "invalid",
                            "outcome_measured_at": datetime.now(timezone.utc),
                            "outcome_evidence": {
                                "reason": "Non-verifiable/meta claim (excluded from scoring)",
                            },
                        }
                    else:
                        outcome = asyncio.run(measure_forecast_outcome(forecast_id, fc))
                except Exception as e:
                    # Cron/CLI job: treat any asyncio issues as a measurement failure but do not crash.
                    errors.append(f"{forecast_id}: measurement error: {e}")
                    outcome = {
                        "outcome_status": "unresolved",
                        "outcome_result": None,
                        "outcome_confidence": 0.0,
                        "outcome_method": "error",
                        "outcome_measured_at": datetime.now(timezone.utc),
                        "outcome_evidence": {"error": str(e)},
                    }

                # Compute scoring fields if resolved.
                brier_score = None
                log_score = None
                calibration_bin = None

                if outcome.get("outcome_status") == "resolved" and outcome.get("outcome_result") is not None:
                    try:
                        prob = float(fc["probability"])
                        happened = bool(outcome["outcome_result"])
                        brier_score = float(calculate_brier_score(prob, happened))
                        ls = float(calculate_log_score(prob, happened))
                        log_score = ls if math.isfinite(ls) else None
                        calibration_bin = int(assign_calibration_bin(prob))
                    except Exception as e:
                        errors.append(f"{forecast_id}: scoring error: {e}")

                # Persist update + audit trail
                new_state = {
                    **_audit_state(fc),
                    "outcome_status": outcome.get("outcome_status"),
                    "outcome_result": outcome.get("outcome_result"),
                    "outcome_confidence": outcome.get("outcome_confidence"),
                    "outcome_measured_at": _iso(outcome.get("outcome_measured_at")),
                    "outcome_method": outcome.get("outcome_method"),
                    "outcome_evidence": _json_sanitize(outcome.get("outcome_evidence")),
                    "brier_score": brier_score,
                    "log_score": log_score,
                    "calibration_bin": calibration_bin,
                }

                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE forecasts
                            SET
                              outcome_status=%s,
                              outcome_result=%s,
                              outcome_confidence=%s,
                              outcome_measured_at=%s,
                              outcome_method=%s,
                              outcome_evidence=%s,
                              brier_score=%s,
                              log_score=%s,
                              calibration_bin=%s,
                              updated_at=now()
                            WHERE id=%s
                            """,
                            (
                                outcome.get("outcome_status"),
                                outcome.get("outcome_result"),
                                outcome.get("outcome_confidence"),
                                outcome.get("outcome_measured_at"),
                                outcome.get("outcome_method"),
                                Jsonb(_json_sanitize(outcome.get("outcome_evidence"))) if outcome.get("outcome_evidence") else None,
                                brier_score,
                                log_score,
                                calibration_bin,
                                forecast_id,
                            ),
                        )

                        cur.execute(
                            """
                            INSERT INTO forecast_updates (
                              forecast_id, update_type, previous_state, new_state, reason, updated_by
                            )
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                forecast_id,
                                "outcome_measurement",
                                Jsonb(previous_state),
                                Jsonb(new_state),
                                f"automated:{outcome.get('outcome_method')}",
                                "system:forecast_outcome_job",
                            ),
                        )

                    conn.commit()
                    processed += 1
                    if outcome.get("outcome_status") == "resolved":
                        updated_resolved += 1
                    elif outcome.get("outcome_status") == "invalid":
                        updated_invalid += 1
                    else:
                        updated_unresolved += 1
                except Exception as e:
                    conn.rollback()
                    errors.append(f"{forecast_id}: db update error: {e}")
                    continue

        _log(
            f"[forecast_outcome_job] processed={processed} resolved={updated_resolved} "
            f"unresolved={updated_unresolved} invalid={updated_invalid} errors={len(errors)}"
        )
        return {
            "processed": processed,
            "resolved": updated_resolved,
            "unresolved": updated_unresolved,
            "invalid": updated_invalid,
            "errors": errors,
        }
    except Exception as e:
        return {
            "processed": processed,
            "resolved": updated_resolved,
            "unresolved": updated_unresolved,
            "invalid": updated_invalid,
            "errors": errors + [str(e)],
        }


def _audit_state(forecast_row: dict[str, Any]) -> dict[str, Any]:
    """Extract a compact JSON-serializable state for audit trail rows."""
    # NOTE: Keep this small; avoid storing huge payloads in audit trail.
    return {
        "outcome_status": forecast_row.get("outcome_status"),
        "outcome_result": forecast_row.get("outcome_result"),
        "outcome_confidence": forecast_row.get("outcome_confidence"),
        "outcome_measured_at": _iso(forecast_row.get("outcome_measured_at")),
        "outcome_method": forecast_row.get("outcome_method"),
        "brier_score": forecast_row.get("brier_score"),
        "log_score": forecast_row.get("log_score"),
        "calibration_bin": forecast_row.get("calibration_bin"),
    }


def _iso(dt: Any) -> str | None:
    if isinstance(dt, datetime):
        try:
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            return dt.isoformat()
    return None


def _is_unverifiable_forecast(forecast_row: dict[str, Any]) -> bool:
    """Heuristic guardrail: forecasts that cannot be resolved against external reality.

    We keep them for auditability, but mark them `invalid` so they don't corrupt track record metrics.
    """
    claim = (forecast_row.get("claim") or "").strip()
    if not claim:
        return True

    # If there is no evidence attached, treat as non-verifiable for now (often a placeholder prediction).
    eids = forecast_row.get("evidence_ids")
    if isinstance(eids, list) and len(eids) == 0:
        return True

    claim_lower = claim.lower()
    meta_keywords = (
        "dataset",
        "index",
        "retrieval",
        "query",
        "coverage",
        "search",
        "no matching articles",
        "evidence-first mode",
    )
    return any(k in claim_lower for k in meta_keywords)


def _json_sanitize(obj: Any) -> Any:
    """Make a best-effort JSON-serializable copy (convert datetimes, recurse)."""
    if obj is None:
        return None
    if isinstance(obj, datetime):
        return _iso(obj)
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [_json_sanitize(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _json_sanitize(v) for k, v in obj.items()}
    # Fallback: string representation
    return str(obj)



"""WS6: Alerts evaluator job (MVP).

This job evaluates enabled rules and writes alert_events. It does NOT deliver
notifications yet; delivery can be built as a separate step that consumes
alert_events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from watchfuleye.storage.postgres_schema import ensure_postgres_schema


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class AlertsJobResult:
    rules_evaluated: int
    events_written: int
    errors: list[str]


def run_alerts_job(
    pg_dsn: str,
    *,
    limit_rules: int = 50,
    log: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Evaluate enabled alert rules once and write alert_events.

    Rule types supported (MVP):
    - term_trend: fires when term_trends.z_score >= threshold since last_evaluated_at
      config: { "threshold": 3.0, "min_count": 5, "lookback_hours": 24 }
    - forecast_outcome: fires on newly resolved forecasts since last_evaluated_at
      config: { "min_confidence": 0.7, "include_statuses": ["resolved"] }
    - recommendation_alpha: fires when newly computed alpha crosses threshold since last_evaluated_at
      config: { "horizon_days": 30, "benchmark_symbol": "SPY", "min_alpha": 0.02 }
    """

    def _log(msg: str) -> None:
        if log is not None:
            try:
                log(msg)
            except Exception:
                pass

    errors: list[str] = []
    rules_evaluated = 0
    events_written = 0

    try:
        ensure_postgres_schema(pg_dsn)
        with psycopg.connect(pg_dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, rule_type, config, last_evaluated_at
                    FROM alert_rules
                    WHERE enabled = TRUE
                    ORDER BY updated_at DESC
                    LIMIT %s
                    """,
                    (int(limit_rules),),
                )
                rules = cur.fetchall()

            for r in rules:
                rules_evaluated += 1
                try:
                    rule_id = str(r["id"])
                    rule_type = str(r["rule_type"])
                    config = r.get("config") or {}
                    last_eval = r.get("last_evaluated_at")

                    if rule_type == "term_trend":
                        wrote = _eval_term_trend(conn, rule_id=rule_id, config=config, since=last_eval)
                        events_written += wrote
                    elif rule_type == "forecast_outcome":
                        wrote = _eval_forecast_outcome(conn, rule_id=rule_id, config=config, since=last_eval)
                        events_written += wrote
                    elif rule_type == "recommendation_alpha":
                        wrote = _eval_recommendation_alpha(conn, rule_id=rule_id, config=config, since=last_eval)
                        events_written += wrote
                    else:
                        # Unknown rule types are no-ops for now; keep system stable.
                        continue

                    with conn.cursor() as cur2:
                        cur2.execute(
                            "UPDATE alert_rules SET last_evaluated_at=%s, updated_at=%s WHERE id=%s",
                            (_utcnow(), _utcnow(), rule_id),
                        )
                    conn.commit()
                except Exception as e:
                    errors.append(f"rule:{r.get('id')}: {e}")
                    _log(f"alerts_job error: rule:{r.get('id')}: {e}")
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    continue

        return {
            "rules_evaluated": rules_evaluated,
            "events_written": events_written,
            "errors": errors,
        }
    except Exception as e:
        return {
            "rules_evaluated": rules_evaluated,
            "events_written": events_written,
            "errors": errors + [str(e)],
        }


def _eval_term_trend(
    conn: psycopg.Connection[dict[str, Any]],
    *,
    rule_id: str,
    config: dict[str, Any],
    since: datetime | None,
) -> int:
    threshold = float(config.get("threshold", 3.0))
    min_count = int(config.get("min_count", 5))
    lookback_hours = int(config.get("lookback_hours", 24))

    cutoff = since
    if cutoff is None:
        cutoff = _utcnow() - timedelta(hours=int(lookback_hours))

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT term, window_start, window_end, count, z_score
            FROM term_trends
            WHERE created_at > %s
              AND z_score IS NOT NULL
              AND z_score >= %s
              AND count >= %s
            ORDER BY z_score DESC
            LIMIT 25
            """,
            (cutoff, threshold, min_count),
        )
        rows = cur.fetchall()

    written = 0
    now = _utcnow()
    for row in rows:
        payload = {
            "rule_type": "term_trend",
            "term": row.get("term"),
            "window_start": _iso(row.get("window_start")),
            "window_end": _iso(row.get("window_end")),
            "count": row.get("count"),
            "z_score": row.get("z_score"),
        }
        with conn.cursor() as cur2:
            cur2.execute(
                """
                INSERT INTO alert_events (rule_id, event_type, payload, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (rule_id, "fired", Jsonb(payload), now),
            )
            written += 1
    return written


def _eval_forecast_outcome(
    conn: psycopg.Connection[dict[str, Any]],
    *,
    rule_id: str,
    config: dict[str, Any],
    since: datetime | None,
) -> int:
    min_conf = float(config.get("min_confidence", 0.7))
    include_statuses = config.get("include_statuses") or ["resolved"]
    if not isinstance(include_statuses, list) or not include_statuses:
        include_statuses = ["resolved"]

    cutoff = since or (_utcnow() - timedelta(hours=24))
    now = _utcnow()
    written = 0

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, claim, probability, horizon_days, horizon_date,
                   outcome_status, outcome_result, outcome_confidence, outcome_method,
                   outcome_measured_at, created_at, tags
            FROM forecasts
            WHERE outcome_measured_at IS NOT NULL
              AND outcome_measured_at > %s
              AND outcome_status = ANY(%s)
              AND COALESCE(outcome_confidence, 0.0) >= %s
            ORDER BY outcome_measured_at DESC
            LIMIT 50
            """,
            (cutoff, include_statuses, min_conf),
        )
        rows = cur.fetchall()

    for row in rows:
        payload = {
            "rule_type": "forecast_outcome",
            "forecast_id": row.get("id"),
            "claim": row.get("claim"),
            "probability": row.get("probability"),
            "horizon_days": row.get("horizon_days"),
            "horizon_date": _iso(row.get("horizon_date")),
            "outcome_status": row.get("outcome_status"),
            "outcome_result": row.get("outcome_result"),
            "outcome_confidence": row.get("outcome_confidence"),
            "outcome_method": row.get("outcome_method"),
            "outcome_measured_at": _iso(row.get("outcome_measured_at")),
            "tags": row.get("tags") or [],
        }
        with conn.cursor() as cur2:
            cur2.execute(
                """
                INSERT INTO alert_events (rule_id, event_type, payload, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (rule_id, "fired", Jsonb(payload), now),
            )
            written += 1
    return written


def _eval_recommendation_alpha(
    conn: psycopg.Connection[dict[str, Any]],
    *,
    rule_id: str,
    config: dict[str, Any],
    since: datetime | None,
) -> int:
    horizon_days = int(config.get("horizon_days", 30))
    benchmark_symbol = str(config.get("benchmark_symbol", "SPY") or "SPY").strip().upper()
    min_alpha = float(config.get("min_alpha", 0.02))

    cutoff = since or (_utcnow() - timedelta(hours=24))
    now = _utcnow()
    written = 0

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.recommendation_id, p.horizon_days, p.benchmark_symbol,
                   p.rec_return, p.benchmark_return, p.alpha, p.computed_at,
                   r.ticker, r.action
            FROM recommendation_performance p
            JOIN recommendations r ON r.id = p.recommendation_id
            WHERE p.computed_at > %s
              AND p.horizon_days = %s
              AND p.benchmark_symbol = %s
              AND p.alpha IS NOT NULL
              AND p.alpha >= %s
            ORDER BY p.computed_at DESC
            LIMIT 50
            """,
            (cutoff, horizon_days, benchmark_symbol, min_alpha),
        )
        rows = cur.fetchall()

    for row in rows:
        def _num(v: Any) -> float | None:
            try:
                return float(v) if v is not None else None
            except Exception:
                return None

        payload = {
            "rule_type": "recommendation_alpha",
            "recommendation_id": row.get("recommendation_id"),
            "ticker": row.get("ticker"),
            "action": row.get("action"),
            "horizon_days": row.get("horizon_days"),
            "benchmark_symbol": row.get("benchmark_symbol"),
            "rec_return": _num(row.get("rec_return")),
            "benchmark_return": _num(row.get("benchmark_return")),
            "alpha": _num(row.get("alpha")),
            "computed_at": _iso(row.get("computed_at")),
        }
        with conn.cursor() as cur2:
            cur2.execute(
                """
                INSERT INTO alert_events (rule_id, event_type, payload, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (rule_id, "fired", Jsonb(payload), now),
            )
            written += 1
    return written


def _iso(v: Any) -> str | None:
    try:
        return v.isoformat() if v is not None else None
    except Exception:
        return None



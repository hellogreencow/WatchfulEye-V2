"""
WS6.1 seed runner: populate Forecast Accountability with *real* historical WatchfulEye outputs.

Why this exists:
- The Track Record / Ledger UI is only meaningful with a non-trivial number of forecasts/recommendations.
- We should seed from *actual past AI outputs* (Global Briefs + V3 reports) rather than synthetic lorem.

What it does (idempotent):
1) Backfill forecasts for existing V3 reports that have predictions but no `forecasts` rows.
2) Convert existing Global Brief `idea_desk` recommendations into forecast rows by creating "seed"
   V3 investigations/reports (to satisfy FK constraints).

Safety:
- Uses deterministic IDs and INSERT ... ON CONFLICT DO NOTHING.
- Never deletes.
- Tags all seeded artifacts with `seed:*` tags and `created_by`.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import psycopg
from psycopg.types.json import Jsonb

from watchfuleye.storage.postgres_schema import ensure_postgres_schema
from watchfuleye.v3.forecast.extractor import extract_forecasts_from_report


@dataclass(frozen=True)
class SeedResult:
    created_investigations: int
    created_reports: int
    inserted_forecasts: int
    backfilled_reports: int


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _deterministic_seed_inv_id(analysis_id: int) -> str:
    return f"seed_inv_global_brief_{analysis_id}"


def _deterministic_seed_report_id(analysis_id: int) -> str:
    return f"seed_rpt_global_brief_{analysis_id}"


def _deterministic_seed_forecast_id(*, recommendation_id: int, horizon_days: int) -> str:
    return f"seed_fc_rec_{recommendation_id}_{horizon_days}"


def _action_to_probability(action: str) -> float:
    a = (action or "").strip().lower()
    # Keep this conservative: seed is for UI/data plumbing, not "prove we were right".
    if a in {"strong buy", "strong_long", "strong long"}:
        return 0.65
    if a in {"buy", "long"}:
        return 0.6
    if a in {"sell", "short"}:
        return 0.6
    if a in {"strong sell", "strong_short", "strong short"}:
        return 0.65
    # Unknown action: don't pretend certainty.
    return 0.55


def _action_to_direction(action: str) -> str:
    a = (action or "").strip().lower()
    if a in {"sell", "short", "strong sell", "strong_short", "strong short"}:
        return "underperforms"
    return "outperforms"


def _parse_horizons_days(raw: str) -> list[int]:
    """Parse comma-separated horizons into positive integers, preserving order and de-duping."""
    out: list[int] = []
    seen: set[int] = set()
    for tok in (raw or "").split(","):
        tok = tok.strip()
        if not tok:
            continue
        n = int(tok)
        if n <= 0:
            continue
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def _yield_backfill_candidates(cur: psycopg.Cursor, *, max_reports: int) -> Iterable[tuple[str, str, dict[str, Any]]]:
    cur.execute(
        """
        SELECT r.id, r.investigation_id, COALESCE(r.content, '{}'::jsonb) AS content
        FROM v3_reports r
        LEFT JOIN forecasts f ON f.report_id = r.id
        WHERE f.id IS NULL
        ORDER BY r.created_at DESC
        LIMIT %s
        """,
        (max_reports,),
    )
    for (report_id, investigation_id, content) in cur.fetchall():
        yield str(report_id), str(investigation_id), (content or {})


def _backfill_forecasts_from_v3_reports(conn: psycopg.Connection, *, max_reports: int, dry_run: bool) -> tuple[int, int]:
    inserted = 0
    backfilled_reports = 0
    with conn.cursor() as cur:
        for report_id, investigation_id, report_content in _yield_backfill_candidates(cur, max_reports=max_reports):
            forecasts = extract_forecasts_from_report(report_id, report_content, investigation_id)
            if not forecasts:
                continue

            backfilled_reports += 1
            for f in forecasts:
                # extractor returns dict with required fields
                forecast_id = f["id"]
                if dry_run:
                    inserted += 1
                    continue
                cur.execute(
                    """
                    INSERT INTO forecasts (
                      id, report_id, investigation_id,
                      claim, probability, horizon_days, horizon_date,
                      entity_ids, entity_types,
                      evidence_ids, assumptions,
                      created_by, tags
                    )
                    VALUES (
                      %s, %s, %s,
                      %s, %s, %s, %s,
                      %s, %s,
                      %s, %s,
                      %s, %s
                    )
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        forecast_id,
                        report_id,
                        investigation_id,
                        f["claim"],
                        f["probability"],
                        f["horizon_days"],
                        f["horizon_date"],
                        f.get("entity_ids"),
                        f.get("entity_types"),
                        f.get("evidence_ids"),
                        f.get("assumptions"),
                        "seed:backfill_v3_reports",
                        f.get("tags") or ["seed", "seed:backfill_v3_reports"],
                    ),
                )
                if cur.rowcount == 1:
                    inserted += 1
    return inserted, backfilled_reports


def _seed_from_global_brief_recommendations(
    conn: psycopg.Connection,
    *,
    max_analyses: int,
    horizons_days: list[int],
    dry_run: bool,
) -> SeedResult:
    created_invs = 0
    created_reports = 0
    inserted_forecasts = 0

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT r.id, r.analysis_id, r.created_at, r.action, r.ticker, r.rationale,
                   a.raw_response_json, a.topic
            FROM recommendations r
            JOIN analyses a ON a.id = r.analysis_id
            ORDER BY r.created_at DESC
            LIMIT %s
            """,
            (max_analyses,),
        )
        rec_rows = cur.fetchall()

        for (rec_id, analysis_id, rec_created_at, action, ticker, rationale, raw_json, topic) in rec_rows:
            analysis_id_int = int(analysis_id)
            inv_id = _deterministic_seed_inv_id(analysis_id_int)
            report_id = _deterministic_seed_report_id(analysis_id_int)

            # Create seed investigation + seed report once per analysis_id.
            if not dry_run:
                cur.execute(
                    """
                    INSERT INTO v3_investigations (id, query, status, trace_id, meta)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        inv_id,
                        f"Seed(Global Brief): {topic or 'global'}",
                        "succeeded",
                        f"seed_trace_global_brief_{analysis_id_int}",
                        Jsonb({"seed": True, "source": "global_brief", "analysis_id": analysis_id_int}),
                    ),
                )
                if cur.rowcount == 1:
                    created_invs += 1

                cur.execute(
                    """
                    INSERT INTO v3_reports (id, investigation_id, title, summary, content)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        report_id,
                        inv_id,
                        f"Seeded Global Brief ({topic or 'global'})",
                        "Seed report created from historical Global Brief output (for WS6.1 track record seeding).",
                        Jsonb({"source": "global_brief", "analysis_id": analysis_id_int, "raw": raw_json}),
                    ),
                )
                if cur.rowcount == 1:
                    created_reports += 1

            # Convert recommendation → forecast claim (market accountability hooks).
            direction = _action_to_direction(str(action))
            p = _action_to_probability(str(action))
            created_at = rec_created_at.astimezone(timezone.utc) if isinstance(rec_created_at, datetime) else _utcnow()

            base_tags = [
                "seed",
                "seed:global_brief_recommendations",
                "domain:markets",
                "benchmark:SPY",
                f"action:{str(action).strip().lower()}",
            ]

            for horizon_days in horizons_days:
                if horizon_days <= 0:
                    continue

                claim = f"{ticker} {direction} SPY over {horizon_days} days"
                fc_id = _deterministic_seed_forecast_id(
                    recommendation_id=int(rec_id), horizon_days=int(horizon_days)
                )
                horizon_date = created_at + timedelta(days=int(horizon_days))
                tags = base_tags + [f"horizon:{int(horizon_days)}d"]

                if dry_run:
                    inserted_forecasts += 1
                    continue

                cur.execute(
                    """
                    INSERT INTO forecasts (
                      id, report_id, investigation_id,
                      claim, probability, horizon_days, horizon_date,
                      evidence_ids, assumptions,
                      created_at, updated_at,
                      created_by, tags,
                      outcome_status
                    )
                    VALUES (
                      %s, %s, %s,
                      %s, %s, %s, %s,
                      %s, %s,
                      %s, %s,
                      %s, %s,
                      %s
                    )
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        fc_id,
                        report_id,
                        inv_id,
                        claim,
                        p,
                        int(horizon_days),
                        horizon_date,
                        None,
                        [f"Seeded from Global Brief recommendation {ticker} {action}: {rationale}"],
                        created_at,
                        created_at,
                        "seed:global_brief_recommendations",
                        tags,
                        "pending",
                    ),
                )
                if cur.rowcount == 1:
                    inserted_forecasts += 1

    return SeedResult(
        created_investigations=created_invs,
        created_reports=created_reports,
        inserted_forecasts=inserted_forecasts,
        backfilled_reports=0,
    )


def run_seed(
    *,
    pg_dsn: str,
    max_v3_reports: int,
    max_analyses: int,
    horizons_days: list[int],
    dry_run: bool,
) -> SeedResult:
    try:
        ensure_postgres_schema(pg_dsn)
    except Exception as e:
        msg = str(e)
        # Common first-run failure on a fresh Postgres without pg_trgm installed.
        if "gin_trgm_ops" in msg or "pg_trgm" in msg:
            raise RuntimeError(
                "Postgres extension pg_trgm appears to be missing. "
                "Fix by running: CREATE EXTENSION IF NOT EXISTS pg_trgm; "
                "Then re-run this seed script."
            ) from e
        raise

    inserted_backfill = 0
    backfilled_reports = 0
    created_invs = 0
    created_reports = 0
    inserted_forecasts = 0

    with psycopg.connect(pg_dsn) as conn:
        # One transaction for the whole run (idempotent inserts). If it fails, nothing half-applies.
        with conn.transaction():
            b_ins, b_reports = _backfill_forecasts_from_v3_reports(
                conn, max_reports=max_v3_reports, dry_run=dry_run
            )
            inserted_backfill += b_ins
            backfilled_reports += b_reports

            seed_res = _seed_from_global_brief_recommendations(
                conn,
                max_analyses=max_analyses,
                horizons_days=horizons_days,
                dry_run=dry_run,
            )
            created_invs += seed_res.created_investigations
            created_reports += seed_res.created_reports
            inserted_forecasts += seed_res.inserted_forecasts

    return SeedResult(
        created_investigations=created_invs,
        created_reports=created_reports,
        inserted_forecasts=inserted_forecasts + inserted_backfill,
        backfilled_reports=backfilled_reports,
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pg-dsn", default=os.environ.get("PG_DSN"))
    p.add_argument("--max-v3-reports", type=int, default=50)
    p.add_argument("--max-analyses", type=int, default=50)
    p.add_argument(
        "--horizons-days",
        type=str,
        default="7,30,90",
        help="Comma-separated horizon days to seed for Global Brief recommendations (default: 7,30,90).",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if not args.pg_dsn:
        raise SystemExit("PG_DSN is required (arg --pg-dsn or env PG_DSN).")

    horizons_days = _parse_horizons_days(str(args.horizons_days))

    res = run_seed(
        pg_dsn=str(args.pg_dsn),
        max_v3_reports=int(args.max_v3_reports),
        max_analyses=int(args.max_analyses),
        horizons_days=horizons_days,
        dry_run=bool(args.dry_run),
    )
    print(
        {
            "created_investigations": res.created_investigations,
            "created_reports": res.created_reports,
            "backfilled_reports": res.backfilled_reports,
            "inserted_forecasts": res.inserted_forecasts,
            "dry_run": bool(args.dry_run),
            "horizons_days": horizons_days,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



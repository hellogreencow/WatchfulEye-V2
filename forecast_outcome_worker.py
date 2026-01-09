#!/usr/bin/env python3
"""WS6.1: Run forecast outcome measurement once (cron/systemd friendly).

This is intentionally a one-shot worker:
- Safe to run on a schedule (e.g., hourly/daily)
- Does not start long-running servers
- Exits 0 even when work is skipped (flag off) to avoid noisy cron failures
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from watchfuleye.v3.forecast.outcome_job import run_forecast_outcome_job


def main() -> int:
    load_dotenv()
    pg_dsn = os.environ.get(
        "PG_DSN",
        "dbname=watchfuleye user=watchful password=watchfulpass host=localhost port=5432",
    )
    limit_raw = os.environ.get("FORECAST_OUTCOME_LIMIT", "50")
    try:
        limit = int(limit_raw)
    except Exception:
        limit = 50

    result = run_forecast_outcome_job(pg_dsn, limit=limit, log=print)
    print(result)
    # Never fail the process for "skipped" runs; hard failures should be visible in logs.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



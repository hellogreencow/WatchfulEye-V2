"""CLI/worker entrypoint for WS6.1 market performance accountability.

Usage (cron/systemd):
  export PG_DSN='dbname=watchfuleye user=watchful ...'
  python3 recommendation_perf_worker.py
"""

from __future__ import annotations

import os
import sys

from watchfuleye.performance.recommendation_perf_job import run_recommendation_performance_job


def main() -> int:
    pg_dsn = os.environ.get("PG_DSN")
    if not pg_dsn:
        print("[recommendation_perf_worker] missing PG_DSN", file=sys.stderr)
        return 1

    limit_raw = os.environ.get("PERF_LIMIT", "100")
    try:
        limit = int(limit_raw)
    except ValueError:
        print(f"[recommendation_perf_worker] invalid PERF_LIMIT={limit_raw!r}", file=sys.stderr)
        return 1
    if limit <= 0:
        print(f"[recommendation_perf_worker] PERF_LIMIT must be > 0 (got {limit})", file=sys.stderr)
        return 1

    result = run_recommendation_performance_job(pg_dsn, limit=limit)
    errors = result.get("errors") or []

    print(
        "[recommendation_perf_worker] "
        f"processed={result.get('processed_recommendations')} "
        f"prices_upserted={result.get('prices_upserted')} "
        f"perf_rows_written={result.get('performance_rows_written')} "
        f"errors={len(errors)}"
    )
    for e in errors[:20]:
        print(f"  - {e}", file=sys.stderr)

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())



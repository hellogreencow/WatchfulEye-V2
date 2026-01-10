"""WS6: Alerts evaluator worker (cron/systemd friendly).

Runs the WS6 alerts job once. Safe to run periodically (e.g., every 1-5 minutes).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from watchfuleye.v3.alerts.job import run_alerts_job
from watchfuleye.v3.flags import is_v3_alerts_enabled


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    print(f"[alerts_worker {ts}] {msg}", flush=True)


def main() -> int:
    if not is_v3_alerts_enabled():
        _log("skipped: V3_ALERTS is disabled")
        return 0

    pg_dsn = os.environ.get("PG_DSN")
    if not pg_dsn:
        _log("error: PG_DSN not configured")
        return 1

    limit = int(os.environ.get("ALERTS_LIMIT", "50") or "50")
    result = run_alerts_job(pg_dsn, limit_rules=limit, log=_log)

    errors = result.get("errors") or []
    _log(f"result: rules_evaluated={result.get('rules_evaluated')} events_written={result.get('events_written')} errors={len(errors)}")
    if errors:
        _log(f"errors: {errors[:3]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



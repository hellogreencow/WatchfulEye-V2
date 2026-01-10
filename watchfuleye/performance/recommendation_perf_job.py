"""WS6.1 (market accountability): compute recommendation performance vs benchmark.

Goal:
- For each stored recommendation (action + ticker), compute return and alpha vs benchmark (e.g. SPY)
  over standard horizons (7/30/90 days).
- Persist results in Postgres (`prices_daily`, `recommendation_performance`).

Design:
- Uses Stooq daily prices (free CSV) via `watchfuleye.performance.stooq`.
- Idempotent: safe to rerun; upserts prices and performance.
- Best-effort: failures are recorded in result summary; never raises for cron/worker use.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row

from watchfuleye.performance.perf_calc import compute_returns
from watchfuleye.performance.stooq import fetch_stooq_daily, normalize_symbol
from watchfuleye.storage.postgres_schema import ensure_postgres_schema


@dataclass(frozen=True)
class PerfJobConfig:
    horizons_days: tuple[int, ...] = (7, 30, 90)
    benchmark_ticker: str = "SPY"


def run_recommendation_performance_job(
    pg_dsn: str,
    *,
    limit: int = 100,
    cfg: PerfJobConfig | None = None,
) -> dict[str, Any]:
    """Run one pass of recommendation performance computation."""
    cfg = cfg or PerfJobConfig()
    errors: list[str] = []
    processed_recs = 0
    perf_rows_written = 0
    prices_upserted = 0

    try:
        ensure_postgres_schema(pg_dsn)
        bars_cache: dict[str, Any] = {}
        with psycopg.connect(pg_dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                # Pick recent recommendations that are missing at least one horizon for this benchmark.
                cur.execute(
                    """
                    SELECT r.id, r.created_at, r.action, r.ticker
                    FROM recommendations r
                    LEFT JOIN recommendation_performance p
                      ON p.recommendation_id = r.id
                     AND p.benchmark_symbol = %s
                     AND p.horizon_days = ANY(%s)
                    GROUP BY r.id, r.created_at, r.action, r.ticker
                    HAVING COUNT(DISTINCT p.horizon_days) < %s
                    ORDER BY r.created_at DESC
                    LIMIT %s
                    """,
                    (cfg.benchmark_ticker, list(cfg.horizons_days), len(cfg.horizons_days), int(limit)),
                )
                recs = cur.fetchall()

            for r in recs:
                try:
                    rec_id = int(r["id"])
                    created_at = r["created_at"]
                    action = str(r["action"] or "").strip().upper()
                    ticker = str(r["ticker"] or "").strip().upper()
                    if not ticker:
                        continue
                    processed_recs += 1

                    entry_dt = _as_utc_datetime(created_at) or datetime.now(timezone.utc)
                    entry_day = entry_dt.date()

                    # Ensure prices exist for rec ticker and benchmark.
                    prices_upserted += _ensure_prices_daily(
                        conn,
                        ticker=ticker,
                        benchmark=cfg.benchmark_ticker,
                        entry_day=entry_day,
                        horizons=cfg.horizons_days,
                        bars_cache=bars_cache,
                    )

                    for h in cfg.horizons_days:
                        exit_day = entry_day + timedelta(days=int(h))
                        perf = _compute_one(
                            conn,
                            recommendation_id=rec_id,
                            action=action,
                            ticker=ticker,
                            benchmark=cfg.benchmark_ticker,
                            entry_day=entry_day,
                            exit_day=exit_day,
                            horizon_days=int(h),
                        )
                        if perf:
                            perf_rows_written += 1

                except Exception as e:
                    errors.append(f"rec:{r.get('id')}: {e}")
                    continue

            conn.commit()

        return {
            "processed_recommendations": processed_recs,
            "prices_upserted": prices_upserted,
            "performance_rows_written": perf_rows_written,
            "errors": errors,
        }
    except Exception as e:
        return {
            "processed_recommendations": processed_recs,
            "prices_upserted": prices_upserted,
            "performance_rows_written": perf_rows_written,
            "errors": errors + [str(e)],
        }


def _ensure_prices_daily(
    conn: psycopg.Connection,
    *,
    ticker: str,
    benchmark: str,
    entry_day: date,
    horizons: Iterable[int],
    bars_cache: dict[str, Any] | None = None,
) -> int:
    """Fetch and upsert daily closes for ticker and benchmark for needed window."""
    max_h = max(int(h) for h in horizons) if horizons else 0
    # Pad window so we can find the next trading day.
    start = entry_day - timedelta(days=3)
    end = entry_day + timedelta(days=max_h + 7)

    upserted = 0
    for t in (ticker, benchmark):
        sym = normalize_symbol(t)
        if not sym:
            continue
        if bars_cache is not None and sym in bars_cache:
            bars = bars_cache[sym]
        else:
            bars = fetch_stooq_daily(sym)
            if bars_cache is not None:
                bars_cache[sym] = bars
        if not bars:
            continue
        with conn.cursor() as cur:
            for b in bars:
                if b.date < start or b.date > end:
                    continue
                cur.execute(
                    """
                    INSERT INTO prices_daily (symbol, date, close, source)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (symbol, date) DO UPDATE
                      SET close = EXCLUDED.close,
                          source = EXCLUDED.source
                    """,
                    (t.upper(), b.date, b.close, b.source),
                )
                upserted += 1
    return upserted


def _compute_one(
    conn: psycopg.Connection,
    *,
    recommendation_id: int,
    action: str,
    ticker: str,
    benchmark: str,
    entry_day: date,
    exit_day: date,
    horizon_days: int,
) -> bool:
    prices = _load_prices(conn, symbol=ticker, entry_day=entry_day, exit_day=exit_day)
    bench = _load_prices(conn, symbol=benchmark, entry_day=entry_day, exit_day=exit_day)
    if not prices or not bench:
        return False

    entry_price, exit_price = prices
    bench_entry, bench_exit = bench

    perf = compute_returns(
        action=action,
        entry_price=entry_price,
        exit_price=exit_price,
        benchmark_entry=bench_entry,
        benchmark_exit=bench_exit,
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO recommendation_performance (
              recommendation_id, horizon_days, benchmark_symbol,
              rec_return, benchmark_return, alpha
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (recommendation_id, horizon_days, benchmark_symbol) DO UPDATE
              SET rec_return = EXCLUDED.rec_return,
                  benchmark_return = EXCLUDED.benchmark_return,
                  alpha = EXCLUDED.alpha,
                  computed_at = now()
            """,
            (
                int(recommendation_id),
                int(horizon_days),
                str(benchmark).upper(),
                perf.rec_return,
                perf.benchmark_return,
                perf.alpha,
            ),
        )
    return True


def _load_prices(
    conn: psycopg.Connection,
    *,
    symbol: str,
    entry_day: date,
    exit_day: date,
) -> tuple[float, float] | None:
    """Load (entry_close, exit_close), using next available trading day on/after target dates."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT close
            FROM prices_daily
            WHERE symbol = %s AND date >= %s
            ORDER BY date ASC
            LIMIT 1
            """,
            (symbol.upper(), entry_day),
        )
        r1 = cur.fetchone()
        cur.execute(
            """
            SELECT close
            FROM prices_daily
            WHERE symbol = %s AND date >= %s
            ORDER BY date ASC
            LIMIT 1
            """,
            (symbol.upper(), exit_day),
        )
        r2 = cur.fetchone()
    if not r1 or not r2:
        return None
    try:
        return (float(_row_close_value(r1)), float(_row_close_value(r2)))
    except Exception:
        return None


def _row_close_value(row: Any) -> Any:
    """psycopg can return tuple rows or dict_row rows depending on connection row_factory."""
    if isinstance(row, dict):
        return row.get("close")
    try:
        return row[0]
    except Exception:
        return None


def _as_utc_datetime(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)
    return None



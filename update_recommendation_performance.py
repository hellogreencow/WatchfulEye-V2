#!/usr/bin/env python3
"""Ingest daily closes and compute recommendation performance vs benchmarks (Phase 7).

Data sources:
- Stooq daily CSV (free) for US equities/ETFs.

Scope:
- Track ONLY Global Brief `idea_desk` recommendations (stored in Postgres `recommendations`).
- Benchmarks: SPY/QQQ/IWM
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import psycopg
from dotenv import load_dotenv

from watchfuleye.performance.perf_calc import compute_returns
from watchfuleye.performance.stooq import fetch_stooq_daily, normalize_symbol
from watchfuleye.storage.postgres_schema import ensure_postgres_schema


BENCHMARKS = {
    "SPY": "spy.us",
    "QQQ": "qqq.us",
    "IWM": "iwm.us",
}
HORIZONS_DAYS = [1, 7, 30]


def _upsert_prices(pg_dsn: str, bars) -> None:
    if not bars:
        return
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            for b in bars:
                cur.execute(
                    """
                    INSERT INTO prices_daily(symbol, date, close, source)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (symbol, date) DO UPDATE
                      SET close = EXCLUDED.close,
                          source = EXCLUDED.source,
                          created_at = now()
                    """,
                    (b.symbol, b.date, float(b.close), b.source),
                )


def ingest_symbol_prices(pg_dsn: str, symbol: str) -> int:
    bars = fetch_stooq_daily(symbol)
    if not bars:
        return 0
    # Only keep last ~3 years for storage control
    cutoff = date.today() - timedelta(days=365 * 3)
    bars = [b for b in bars if b.date >= cutoff]
    _upsert_prices(pg_dsn, bars)
    return len(bars)


def _lookup_next_close(cur, symbol: str, target_date: date) -> Optional[Tuple[date, float]]:
    cur.execute(
        """
        SELECT date, close
        FROM prices_daily
        WHERE symbol = %s AND date >= %s
        ORDER BY date ASC
        LIMIT 1
        """,
        (symbol, target_date),
    )
    row = cur.fetchone()
    if not row:
        return None
    return (row[0], float(row[1]))


def compute_performance(pg_dsn: str) -> int:
    computed = 0
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, created_at, action, ticker FROM recommendations ORDER BY created_at DESC")
            recs = cur.fetchall()

        with conn.cursor() as cur:
            for rid, created_at, action, ticker in recs:
                sym = normalize_symbol(ticker)
                if not sym:
                    continue
                entry_target = created_at.date()
                entry = _lookup_next_close(cur, sym, entry_target)
                if not entry:
                    continue
                entry_date, entry_close = entry

                for horizon in HORIZONS_DAYS:
                    exit_target = entry_date + timedelta(days=horizon)
                    exit_row = _lookup_next_close(cur, sym, exit_target)
                    if not exit_row:
                        continue
                    exit_date, exit_close = exit_row

                    for bench, bench_sym in BENCHMARKS.items():
                        b_entry = _lookup_next_close(cur, bench_sym, entry_date)
                        b_exit = _lookup_next_close(cur, bench_sym, exit_date)
                        if not b_entry or not b_exit:
                            continue
                        _, b_entry_close = b_entry
                        _, b_exit_close = b_exit

                        perf = compute_returns(
                            action=str(action),
                            entry_price=float(entry_close),
                            exit_price=float(exit_close),
                            benchmark_entry=float(b_entry_close),
                            benchmark_exit=float(b_exit_close),
                        )
                        if perf.alpha is None:
                            continue

                        cur.execute(
                            """
                            INSERT INTO recommendation_performance (
                              recommendation_id, horizon_days, benchmark_symbol, rec_return, benchmark_return, alpha, computed_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, now())
                            ON CONFLICT (recommendation_id, horizon_days, benchmark_symbol) DO UPDATE SET
                              rec_return = EXCLUDED.rec_return,
                              benchmark_return = EXCLUDED.benchmark_return,
                              alpha = EXCLUDED.alpha,
                              computed_at = now()
                            """,
                            (
                                int(rid),
                                int(horizon),
                                bench,
                                float(perf.rec_return),
                                float(perf.benchmark_return),
                                float(perf.alpha),
                            ),
                        )
                        computed += 1
    return computed


def main() -> int:
    load_dotenv()
    pg_dsn = os.environ.get("PG_DSN", "dbname=watchfuleye user=watchful password=watchfulpass host=localhost port=5432")
    ensure_postgres_schema(pg_dsn)

    # Ingest benchmarks always
    for sym in BENCHMARKS.values():
        n = ingest_symbol_prices(pg_dsn, sym)
        print(f"[prices] ingested {n} bars for {sym}")

    # Ingest all recommendation symbols
    with psycopg.connect(pg_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT ticker FROM recommendations")
            tickers = [r[0] for r in cur.fetchall() if r and r[0]]

    symbols = sorted({normalize_symbol(t) for t in tickers if normalize_symbol(t)})
    for sym in symbols:
        n = ingest_symbol_prices(pg_dsn, sym)
        print(f"[prices] ingested {n} bars for {sym}")

    computed = compute_performance(pg_dsn)
    print(f"[perf] upserted {computed} performance rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



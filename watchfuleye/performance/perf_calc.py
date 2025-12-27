"""Core performance calculations (pure functions)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PerfResult:
    rec_return: Optional[float]
    benchmark_return: Optional[float]
    alpha: Optional[float]


def position_multiplier(action: str) -> int:
    """Map recommendation action into +1 (long) or -1 (short)."""
    a = (action or "").strip().upper()
    if a in {"SELL", "SHORT"}:
        return -1
    # BUY/LONG/HEDGE treated as long exposure for now
    return 1


def compute_returns(
    *,
    action: str,
    entry_price: float,
    exit_price: float,
    benchmark_entry: float,
    benchmark_exit: float,
) -> PerfResult:
    if entry_price <= 0 or benchmark_entry <= 0:
        return PerfResult(rec_return=None, benchmark_return=None, alpha=None)
    mult = position_multiplier(action)
    raw = (exit_price - entry_price) / entry_price
    rec = float(mult) * raw
    bench = (benchmark_exit - benchmark_entry) / benchmark_entry
    return PerfResult(rec_return=rec, benchmark_return=bench, alpha=rec - bench)



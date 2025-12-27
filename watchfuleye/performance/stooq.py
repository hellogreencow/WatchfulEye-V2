"""Price ingestion via Stooq (free daily OHLCV CSV)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, List, Optional, Tuple

import requests


@dataclass(frozen=True)
class DailyBar:
    symbol: str
    date: date
    close: float
    source: str = "stooq"


def normalize_symbol(ticker: str) -> Optional[str]:
    """Best-effort mapping from model tickers to Stooq symbols.

    Notes:
    - Most US equities/ETFs: {ticker}.us
    - Some assets (e.g. VIX) are not available on Stooq; return None.
    """
    if not ticker:
        return None
    t = str(ticker).strip().upper()
    if not t:
        return None
    # Reject obviously non-symbol strings
    if any(ch in t for ch in (" ", "/", "\\", ":", ";", ",")):
        return None
    # Known unsupported / ambiguous symbols
    if t in {"VIX"}:
        return None
    if t.startswith("^"):
        return None
    # US equities/ETFs baseline
    if t.isalpha() and 1 <= len(t) <= 5:
        return t.lower() + ".us"
    return None


def fetch_stooq_daily(symbol: str, *, timeout: int = 15) -> List[DailyBar]:
    """Fetch full daily history for a Stooq symbol."""
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "WatchfulEye/2.0"})
    resp.raise_for_status()
    text = resp.text
    if not text or text.strip().lower().startswith("no data"):
        return []
    reader = csv.DictReader(io.StringIO(text))
    out: List[DailyBar] = []
    for row in reader:
        try:
            d = datetime.strptime(row["Date"], "%Y-%m-%d").date()
            close = float(row["Close"])
        except Exception:
            continue
        out.append(DailyBar(symbol=symbol, date=d, close=close))
    return out



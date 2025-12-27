"""Article scoring utilities.

We explicitly DO NOT depend on the legacy sentiment/classification pipeline.
This module provides deterministic scoring for:
- source trust priors
- relevance to WatchfulEye domains (markets/geopolitics)
- spam/deals routing
- near-duplicate penalties
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


# -----------------------------
# Source trust priors (v0)
# -----------------------------
HIGH_TRUST_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "bbc.co.uk",
    "bbc.com",
    "ft.com",
    "wsj.com",
    "bloomberg.com",
    "economist.com",
    "aljazeera.com",
    "npr.org",
    "theguardian.com",
    "washingtonpost.com",
    "nytimes.com",
    "federalreserve.gov",
    "treasury.gov",
}

MED_TRUST_DOMAINS = {
    "cnn.com",
    "abcnews.go.com",
    "cbsnews.com",
    "nbcnews.com",
    "politico.com",
    "axios.com",
    "time.com",
    "marketscreener.com",
    "investing.com",
}


def source_trust_prior(domain: Optional[str], source_name: Optional[str] = None) -> float:
    d = (domain or "").lower().strip()
    if d.startswith("www."):
        d = d[4:]
    if d in HIGH_TRUST_DOMAINS:
        return 0.95
    if d in MED_TRUST_DOMAINS:
        return 0.70
    # Heuristic by name
    name = (source_name or "").lower()
    if any(k in name for k in ("reuters", "associated press", "ap", "financial times", "bloomberg", "economist", "bbc")):
        return 0.90
    if any(k in name for k in ("cnn", "politico", "axios", "time")):
        return 0.70
    if not d:
        return 0.50
    # Penalize obvious spammy domains
    if any(k in d for k in ("coupon", "deals", "discount", "affiliate", "shop")):
        return 0.20
    return 0.45


# -----------------------------
# Spam/deals detection
# -----------------------------
DEALS_PATTERNS = [
    r"\bdeal\b",
    r"\bdeals\b",
    r"\bdiscount\b",
    r"\bcoupon\b",
    r"\bpromo\s*code\b",
    r"\bblack\s*friday\b",
    r"\bcyber\s*monday\b",
    r"\bprime\s*day\b",
    r"\bbest\s+\d+\b",
    r"\btop\s+\d+\b",
    r"\breview:\b",
    r"\bhow\s+to\b",
]


def is_deals_or_spam(title: str, description: Optional[str] = None) -> bool:
    blob = (title or "") + " " + (description or "")
    blob = blob.lower()
    return any(re.search(p, blob) for p in DEALS_PATTERNS)


# -----------------------------
# Relevance scoring (v0)
# -----------------------------
RELEVANCE_KEYWORDS = [
    # markets/macro
    "market",
    "stocks",
    "equities",
    "bond",
    "yield",
    "rates",
    "inflation",
    "gdp",
    "central bank",
    "fed",
    "ecb",
    "boj",
    "boe",
    "sanctions",
    "tariff",
    "trade",
    "oil",
    "gas",
    "shipping",
    "supply chain",
    # geopolitics
    "war",
    "missile",
    "nuclear",
    "diplomacy",
    "election",
    "alliance",
    "nato",
    "china",
    "russia",
    "iran",
    "ukraine",
]


def relevance_score(title: str, description: Optional[str] = None) -> float:
    blob = (title or "") + " " + (description or "")
    blob_l = blob.lower()
    hits = 0
    for kw in RELEVANCE_KEYWORDS:
        if kw in blob_l:
            hits += 1
    # saturating curve
    return 1.0 - math.exp(-hits / 4.0)


def completeness_score(description: Optional[str]) -> float:
    if not description:
        return 0.1
    n = len(description.strip())
    if n >= 240:
        return 1.0
    if n <= 40:
        return 0.2
    return min(1.0, n / 240.0)


def recency_score(published_at: Optional[datetime], *, half_life_hours: float = 24.0) -> float:
    if not published_at:
        return 0.3
    now = datetime.now(timezone.utc)
    dt = published_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (now - dt).total_seconds() / 3600.0)
    # exponential decay with half-life
    return 0.5 ** (age_hours / max(half_life_hours, 1e-6))


@dataclass(frozen=True)
class ScoredArticle:
    trust: float
    relevance: float
    completeness: float
    recency: float
    dup_penalty: float
    bucket: str
    quality: float


def score_article(
    *,
    title: str,
    description: Optional[str],
    domain: Optional[str],
    source_name: Optional[str],
    published_at: Optional[datetime],
    is_duplicate: bool,
) -> ScoredArticle:
    trust = source_trust_prior(domain, source_name)
    rel = relevance_score(title, description)
    comp = completeness_score(description)
    rec = recency_score(published_at)
    deals = is_deals_or_spam(title, description)
    bucket = "deals" if deals else "main"
    dup_penalty = 0.35 if is_duplicate else 0.0

    # Weighted sum, then clamp to [0,1]
    quality = (
        0.40 * trust
        + 0.30 * rel
        + 0.20 * rec
        + 0.10 * comp
        - dup_penalty
        - (0.35 if deals else 0.0)
    )
    quality = max(0.0, min(1.0, quality))
    return ScoredArticle(
        trust=trust,
        relevance=rel,
        completeness=comp,
        recency=rec,
        dup_penalty=dup_penalty,
        bucket=bucket,
        quality=quality,
    )



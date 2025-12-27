"""Term/topic trend computations (Phase 8).

We compute simple, explainable trend scores:
- Term trend z-score approximated via Poisson baseline:
    expected = baseline_rate_per_hour * window_hours
    z ≈ (observed - expected) / sqrt(expected + 1)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple


STOPWORDS = {
    "the","a","an","and","or","but","of","to","in","on","for","with","by","at","as","is","are","was","were","be","been","being",
    "this","that","these","those","it","its","from","about","into","over","after","before","between","through","during","without","within",
    "what","who","whom","which","when","where","why","how","can","could","should","would","may","might","will","shall","do","does","did",
    "their","they","them","we","you","your","i","he","she","his","her","our","ours","us",
}


def tokenize(text: str) -> List[str]:
    if not text:
        return []
    toks = re.findall(r"[a-zA-Z][a-zA-Z0-9\-']{2,}", text.lower())
    out = []
    for t in toks:
        if t in STOPWORDS:
            continue
        # drop pure numbers
        if t.isdigit():
            continue
        out.append(t)
    return out


def count_terms(texts: Sequence[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for txt in texts:
        for t in tokenize(txt):
            counts[t] = counts.get(t, 0) + 1
    return counts


@dataclass(frozen=True)
class TermTrend:
    term: str
    count: int
    z_score: float


def compute_term_trends(
    *,
    recent_texts: Sequence[str],
    baseline_texts: Sequence[str],
    recent_hours: float,
    baseline_hours: float,
    min_count: int = 5,
    top_k: int = 200,
) -> List[TermTrend]:
    recent = count_terms(recent_texts)
    base = count_terms(baseline_texts)

    trends: List[TermTrend] = []
    for term, observed in recent.items():
        if observed < min_count:
            continue
        base_count = base.get(term, 0)
        rate = base_count / max(1e-6, baseline_hours)
        expected = rate * recent_hours
        z = (observed - expected) / math.sqrt(expected + 1.0)
        trends.append(TermTrend(term=term, count=observed, z_score=float(z)))

    trends.sort(key=lambda t: t.z_score, reverse=True)
    return trends[:top_k]



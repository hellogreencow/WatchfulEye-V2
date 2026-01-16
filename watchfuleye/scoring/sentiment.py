"""Deterministic market-sentiment scoring for articles.

This is intentionally lightweight: no external model calls, no heavy deps.
It aims to approximate *market impact* (risk-on/risk-off), not article tone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple


@dataclass(frozen=True)
class SentimentResult:
    """Market sentiment score result.

    - score: -1 (bearish/risk-off) .. +1 (bullish/risk-on)
    - confidence: 0..1
    - reasoning: short, human-readable rationale
    """

    score: float
    confidence: float
    reasoning: str


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z]+(?:'[a-zA-Z]+)?|\d+(?:\.\d+)?", (text or "").lower())


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def score_market_sentiment(title: str, description: str | None = None) -> SentimentResult:
    """Score market sentiment from title/description (no network calls).

    Heuristics:
    - Macro tightening / inflation spikes / defaults / war escalation => bearish
    - De-escalation / ceasefire / stimulus / rate cuts / disinflation => bullish
    - Confidence grows with number/strength of matched signals
    """

    title = (title or "").strip()
    desc = (description or "").strip() if description else ""
    blob = (title + " " + desc).strip()
    if not blob:
        return SentimentResult(score=0.0, confidence=0.1, reasoning="No text to score.")

    tokens = _tokenize(blob)
    if not tokens:
        return SentimentResult(score=0.0, confidence=0.1, reasoning="No tokens to score.")

    # Negation window flips local polarity.
    negators = {"not", "no", "without", "isn't", "wasn't", "aren't", "don't", "didn't", "won't", "can't"}
    intensifiers_pos = {"surge", "soar", "jump", "beat", "record", "strong", "robust"}
    intensifiers_neg = {"plunge", "slump", "crash", "collapse", "panic", "sharp", "severe"}

    # Phrase-level signals (highest weight)
    phrase_signals: List[Tuple[str, float]] = [
        # Dovish / easing
        ("rate cut", +0.65),
        ("cuts rates", +0.65),
        ("lower rates", +0.50),
        ("pause rate hikes", +0.45),
        ("inflation cools", +0.55),
        ("disinflation", +0.55),
        ("ceasefire", +0.60),
        ("peace talks", +0.45),
        ("deal reached", +0.35),
        ("stimulus", +0.40),
        ("bailout", +0.25),
        # Hawkish / tightening / risk
        ("rate hike", -0.65),
        ("hikes rates", -0.65),
        ("higher rates", -0.45),
        ("inflation rises", -0.55),
        ("inflation surge", -0.65),
        ("default", -0.70),
        ("debt crisis", -0.60),
        ("bank run", -0.75),
        ("credit crunch", -0.70),
        ("war", -0.55),
        ("missile strike", -0.70),
        ("airstrike", -0.55),
        ("invasion", -0.75),
        ("sanctions imposed", -0.45),
        ("export ban", -0.40),
        ("shipping disruption", -0.45),
        ("supply chain disruption", -0.45),
        ("terror attack", -0.70),
    ]

    blob_l = blob.lower()
    score = 0.0
    hits: List[str] = []

    for phrase, w in phrase_signals:
        if phrase in blob_l:
            score += w
            hits.append(phrase)

    # Token-level signals (lower weight; helps when no key phrase matches)
    pos_words = {
        "growth",
        "recovery",
        "deal",
        "agreement",
        "stability",
        "calm",
        "easing",
        "cooling",
        "cut",
        "cuts",
        "lower",
        "boost",
        "stimulus",
        "surplus",
        "beat",
    }
    neg_words = {
        "recession",
        "crisis",
        "default",
        "bankrupt",
        "downgrade",
        "collapse",
        "war",
        "conflict",
        "attack",
        "strike",
        "missile",
        "sanction",
        "sanctions",
        "inflation",
        "hike",
        "hikes",
        "tightening",
        "slump",
        "plunge",
        "crash",
    }

    token_score = 0.0
    for i, tok in enumerate(tokens):
        window = tokens[max(0, i - 2) : i]
        flip = any(n in window for n in negators)
        if tok in pos_words:
            token_score += (-0.12 if flip else +0.12)
        elif tok in neg_words:
            token_score += (+0.12 if flip else -0.12)
        # intensifiers slightly amplify the nearest direction
        if tok in intensifiers_pos:
            token_score += 0.06
        elif tok in intensifiers_neg:
            token_score -= 0.06

    # Title gets a bit more weight.
    title_tokens = _tokenize(title)
    if title_tokens:
        title_bonus = 0.0
        for tok in title_tokens:
            if tok in pos_words:
                title_bonus += 0.05
            elif tok in neg_words:
                title_bonus -= 0.05
        token_score += title_bonus

    score += token_score

    # Normalize and clamp: multiple phrase hits can exceed bounds.
    score = _clamp(score, -1.0, 1.0)

    # Confidence: driven by magnitude + number of distinct phrase hits or token evidence.
    evidence = len(hits) + min(10, int(abs(token_score) / 0.12))
    confidence = 0.25 + 0.15 * min(evidence, 5) + 0.35 * abs(score)
    confidence = _clamp(confidence, 0.1, 0.95)

    if hits:
        reasoning = "Signals: " + ", ".join(hits[:4])
    else:
        reasoning = "Signals: lexical market-impact cues"

    return SentimentResult(score=round(score, 3), confidence=round(confidence, 3), reasoning=reasoning)


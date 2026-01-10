"""WS6.1 TASK 2: Extract structured forecasts from natural language predictions.

Parses report content for:
- Explicit probabilities ("70% chance", "30 percent")
- Qualitative confidence ("highly likely", "unlikely")
- Time horizons ("within 30 days", "by Q2 2026")
- Entity references (tickers, countries, sanctions targets)

Integration: Called from examine_api.py after report generation.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


# Probability extraction patterns
EXPLICIT_PROBABILITY_PATTERNS = [
    r'(\d+(?:\.\d+)?)\s*%',  # "70%", "73.5%"
    r'(\d+(?:\.\d+)?)\s*percent',  # "70 percent"
    r'probability\s+of\s+(\d+(?:\.\d+)?)',  # "probability of 0.7"
    r'(\d+(?:\.\d+)?)\s*chance',  # "70 chance"
]

# Qualitative → probability mapping (based on Mellers et al. 2014 research)
# IMPORTANT: Order matters! Check longer/more specific phrases first
QUALITATIVE_PROBABILITIES = [
    ("almost impossible", 0.05),
    ("highly unlikely", 0.15),
    ("almost certain", 0.95),
    ("highly likely", 0.75),
    ("good chance", 0.65),
    ("could happen", 0.50),
    ("improbable", 0.25),  # Must come before "probable"
    ("certain", 0.95),
    ("unlikely", 0.35),
    ("likely", 0.65),
    ("probable", 0.65),
    ("possible", 0.50),
    ("maybe", 0.50),
    ("doubtful", 0.30),
    ("remote", 0.10),
]

# Time horizon patterns
HORIZON_PATTERNS = [
    (r'within\s+(\d+)\s+days?', 1),  # "within 30 days"
    (r'within\s+(\d+)\s+weeks?', 7),  # "within 2 weeks" → multiply by 7
    (r'within\s+(\d+)\s+months?', 30),  # "within 3 months" → multiply by 30
    (r'in\s+(\d+)\s+days?', 1),
    (r'in\s+(\d+)\s+weeks?', 7),
    (r'in\s+(\d+)\s+months?', 30),
    (r'by\s+end\s+of\s+(?:the\s+)?week', 7),  # "by end of week"
    (r'by\s+end\s+of\s+(?:the\s+)?month', 30),  # "by end of month"
    (r'by\s+end\s+of\s+(?:the\s+)?quarter', 90),  # "by end of quarter"
    (r'by\s+end\s+of\s+(?:the\s+)?year', 365),  # "by end of year"
]


def _extract_probability(text: str) -> float | None:
    """Extract probability from text (explicit or qualitative).

    Args:
        text: Prediction text

    Returns:
        Probability in [0, 1] or None if not found
    """
    text_lower = text.lower()

    # Try explicit probability patterns first
    for pattern in EXPLICIT_PROBABILITY_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            value = float(match.group(1))
            # Handle both "70" and "0.70" formats
            if value > 1.0:
                value = value / 100.0
            if 0.0 <= value <= 1.0:
                return value

    # Try qualitative mappings (order matters!)
    for phrase, prob in QUALITATIVE_PROBABILITIES:
        if phrase in text_lower:
            return prob

    return None


def _extract_horizon(text: str) -> int | None:
    """Extract time horizon in days from text.

    Args:
        text: Prediction text

    Returns:
        Number of days or None if not found
    """
    text_lower = text.lower()

    for pattern, multiplier in HORIZON_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            if match.groups():
                # Pattern has capture group (e.g., "within 30 days")
                value = int(match.group(1))
                return value * multiplier
            else:
                # Pattern has no capture group (e.g., "by end of week")
                return multiplier

    # Default horizon if not specified: 30 days
    return 30


def _normalize_claim(text: str) -> str:
    """Normalize claim text for storage.

    Removes probability and horizon phrases to get clean claim.
    """
    claim = text

    # Remove explicit probability phrases
    claim = re.sub(r'\d+(?:\.\d+)?\s*%', '', claim, flags=re.IGNORECASE)
    claim = re.sub(r'\d+(?:\.\d+)?\s*percent', '', claim, flags=re.IGNORECASE)
    claim = re.sub(r'\d+(?:\.\d+)?\s*chance', '', claim, flags=re.IGNORECASE)
    claim = re.sub(r'probability\s+of\s+\d+(?:\.\d+)?', '', claim, flags=re.IGNORECASE)

    # Remove "chance that" and similar connectors
    claim = re.sub(r'\b(chance\s+that|likelihood\s+that)\b', '', claim, flags=re.IGNORECASE)

    # Remove horizon phrases
    for pattern, _ in HORIZON_PATTERNS:
        claim = re.sub(pattern, '', claim, flags=re.IGNORECASE)

    # Remove qualitative probability words (order matters!)
    claim_lower = claim.lower()
    for phrase, _ in QUALITATIVE_PROBABILITIES:
        if phrase in claim_lower:
            # Case-insensitive replacement
            claim = re.sub(re.escape(phrase), '', claim, flags=re.IGNORECASE)
            break  # Only remove first match

    # Clean up whitespace
    claim = ' '.join(claim.split())

    return claim.strip()


def _extract_entity_references(text: str, report_content: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Extract entity IDs and types mentioned in the claim.

    Args:
        text: Claim text
        report_content: Full report content with entity links

    Returns:
        Tuple of (entity_ids, entity_types)
    """
    # TODO: In future, use entity resolution from WS0 schema
    # For now, extract basic patterns

    entity_ids: list[str] = []
    entity_types: list[str] = []

    text_upper = text.upper()

    # Extract ticker symbols (basic pattern: $TICKER or 4-letter uppercase)
    ticker_pattern = r'\$([A-Z]{1,5})\b|\b([A-Z]{2,5})\b'
    tickers = re.findall(ticker_pattern, text_upper)
    for match in tickers:
        ticker = match[0] or match[1]
        if ticker and len(ticker) <= 5:
            entity_ids.append(f"ticker:{ticker}")
            if "ticker" not in entity_types:
                entity_types.append("ticker")

    # Extract country names (basic list - expand later)
    countries = ["CHINA", "RUSSIA", "IRAN", "USA", "ISRAEL", "UKRAINE", "SAUDI ARABIA"]
    for country in countries:
        if country in text_upper:
            entity_ids.append(f"country:{country}")
            if "country" not in entity_types:
                entity_types.append("country")

    return entity_ids, entity_types


def extract_forecasts_from_report(
    report_id: str,
    report_content: dict[str, Any],
    investigation_id: str | None = None,
) -> list[dict[str, Any]]:
    """Extract structured forecasts from report content.

    Looks for "predictions" section in report and parses each prediction
    for probability, horizon, and entities.

    Args:
        report_id: ID of parent report
        report_content: Report content dict (from report_builder.py)
        investigation_id: Optional investigation ID

    Returns:
        List of forecast dicts ready for database insertion

    Example:
        >>> report_content = {
        ...     "predictions": [
        ...         "70% chance Iran increases oil exports within 30 days",
        ...         "Highly likely TSLA stock rises 10% by end of quarter"
        ...     ],
        ...     "evidence_ids": ["art_123", "art_456"]
        ... }
        >>> forecasts = extract_forecasts_from_report("rep_1", report_content)
        >>> len(forecasts)
        2
        >>> forecasts[0]["probability"]
        0.7
        >>> forecasts[0]["horizon_days"]
        30
    """
    predictions = report_content.get("predictions", [])
    if not predictions:
        return []

    now = datetime.now(timezone.utc)
    forecasts: list[dict[str, Any]] = []

    # Optional report-level evidence IDs (legacy shape).
    report_evidence_ids = report_content.get("evidence_ids", [])

    for pred in predictions:
        claim_text: str | None = None
        probability: float | None = None
        horizon_days: int | None = None
        pred_evidence_ids: list[str] | None = None

        # Support both legacy string predictions and WS4 report_builder dict predictions:
        #   {"claim": str, "probability": float, "horizon": "7d", "evidence_ids": [...]}
        if isinstance(pred, dict):
            raw_claim = pred.get("claim")
            if isinstance(raw_claim, str) and raw_claim.strip():
                claim_text = raw_claim.strip()

            # Probability: prefer structured value.
            raw_p = pred.get("probability")
            if isinstance(raw_p, (int, float)):
                p = float(raw_p)
                if p > 1.0:
                    p = p / 100.0
                if 0.0 <= p <= 1.0:
                    probability = p
            elif isinstance(raw_p, str) and raw_p.strip():
                try:
                    p = float(raw_p.strip())
                    if p > 1.0:
                        p = p / 100.0
                    if 0.0 <= p <= 1.0:
                        probability = p
                except Exception:
                    probability = None

            # Horizon: prefer structured value.
            raw_h = pred.get("horizon_days")
            if isinstance(raw_h, int):
                horizon_days = raw_h
            else:
                raw_h2 = pred.get("horizon")
                horizon_days = _parse_horizon_to_days(raw_h2)

            raw_eids = pred.get("evidence_ids")
            if isinstance(raw_eids, list) and raw_eids:
                pred_evidence_ids = [str(x) for x in raw_eids if x is not None]

        elif isinstance(pred, str) and pred.strip():
            claim_text = pred.strip()
            probability = _extract_probability(claim_text)
            horizon_days = _extract_horizon(claim_text)

        if not claim_text:
            continue

        # If probability wasn't provided in structured fields, try extracting from text.
        if probability is None:
            probability = _extract_probability(claim_text)
        if probability is None:
            continue

        if horizon_days is None:
            horizon_days = _extract_horizon(claim_text)
        if horizon_days is None:
            continue

        # Keep claim text as-is for structured inputs; normalize legacy string inputs.
        claim = claim_text if isinstance(pred, dict) else _normalize_claim(claim_text) or claim_text

        entity_ids, entity_types = _extract_entity_references(claim_text, report_content)

        evidence_ids = pred_evidence_ids if pred_evidence_ids is not None else report_evidence_ids

        forecast_id = f"fc_{uuid.uuid4().hex[:12]}"
        horizon_date = now + timedelta(days=horizon_days)

        forecasts.append(
            {
                "id": forecast_id,
                "report_id": report_id,
                "investigation_id": investigation_id,
                "claim": claim,
                "probability": probability,
                "horizon_days": horizon_days,
                "horizon_date": horizon_date,
                "entity_ids": entity_ids if entity_ids else None,
                "entity_types": entity_types if entity_types else None,
                "evidence_ids": [str(x) for x in evidence_ids] if evidence_ids else None,
                "assumptions": None,  # TODO: Extract assumptions in future
                "tags": None,  # TODO: Auto-tag by domain
                "created_by": "extractor:v2",
                "outcome_status": "pending",
                "outcome_result": None,
                "outcome_confidence": None,
                "outcome_measured_at": None,
                "outcome_method": None,
                "outcome_evidence": None,
                "brier_score": None,
                "log_score": None,
                "calibration_bin": None,
            }
        )

    return forecasts


def _parse_horizon_to_days(raw: Any) -> int | None:
    """Parse horizon strings like '7d', '2w', '3m' into days.

    Falls back to None when the input isn't parseable.
    """
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    if not isinstance(raw, str):
        return None
    s = raw.strip().lower()
    if not s:
        return None
    # Common V3 report_builder format: "7d", "14d", "30d", "90d"
    m = re.fullmatch(r"(\d+)\s*([dwm])", s)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    if unit == "d":
        return n
    if unit == "w":
        return n * 7
    if unit == "m":
        return n * 30
    return None

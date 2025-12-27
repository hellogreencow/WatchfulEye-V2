"""Global Brief contract utilities.

The "Global Brief" is the structured JSON payload stored in `analyses.raw_response_json`
and rendered in the UI/Telegram. This module defines:
- A JSON Schema (for validation)
- Helpers to extract recommendations in a deterministic way

Important:
- We preserve backward compatibility with the existing keys used in `web_app.py`
  (breaking_news, key_numbers, market_pulse, crypto_barometer, idea_desk, final_intel).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from jsonschema import Draft202012Validator


GLOBAL_BRIEF_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": [
        "brief_topic",
        "breaking_news",
        "key_numbers",
        "market_pulse",
        "crypto_barometer",
        "tech_emergence",
        "idea_desk",
        "final_intel",
    ],
    "properties": {
        "brief_topic": {"type": "string", "minLength": 1},
        "breaking_news": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["tier", "headline", "time", "summary", "key_insight", "actionable_advice"],
                "properties": {
                    "tier": {"type": "integer", "minimum": 1, "maximum": 3},
                    "headline": {"type": "string", "minLength": 1},
                    "time": {"type": "string", "minLength": 1},
                    "summary": {"type": "string", "minLength": 1},
                    "key_insight": {"type": "string", "minLength": 1},
                    "actionable_advice": {"type": "string", "minLength": 1},
                },
                "additionalProperties": True,
            },
        },
        "key_numbers": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["title", "value", "context"],
                "properties": {
                    "title": {"type": "string", "minLength": 1},
                    "value": {"type": "string", "minLength": 1},
                    "context": {"type": "string", "minLength": 1},
                },
                "additionalProperties": True,
            },
        },
        "market_pulse": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["asset", "direction", "catalyst", "why_it_matters"],
                "properties": {
                    "asset": {"type": "string", "minLength": 1},
                    "direction": {"type": "string", "minLength": 1},
                    "catalyst": {"type": "string", "minLength": 1},
                    "why_it_matters": {"type": "string", "minLength": 1},
                },
                "additionalProperties": True,
            },
        },
        "crypto_barometer": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["token", "movement", "catalyst", "quick_take"],
                "properties": {
                    "token": {"type": "string", "minLength": 1},
                    "movement": {"type": "string", "minLength": 1},
                    "catalyst": {"type": "string", "minLength": 1},
                    "quick_take": {"type": "string", "minLength": 1},
                },
                "additionalProperties": True,
            },
        },
        "tech_emergence": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["innovation", "potential_impact", "adoption_outlook"],
                "properties": {
                    "innovation": {"type": "string", "minLength": 1},
                    "potential_impact": {"type": "string", "minLength": 1},
                    "adoption_outlook": {"type": "string", "minLength": 1},
                },
                "additionalProperties": True,
            },
        },
        "idea_desk": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["action", "ticker", "rationale"],
                "properties": {
                    "action": {"type": "string", "minLength": 1},
                    "ticker": {"type": "string", "minLength": 1},
                    "rationale": {"type": "string", "minLength": 1},
                },
                "additionalProperties": True,
            },
        },
        "final_intel": {
            "type": "object",
            "required": ["summary", "investment_horizon", "key_risks"],
            "properties": {
                "summary": {"type": "string", "minLength": 1},
                "investment_horizon": {"type": "string", "minLength": 1},
                "key_risks": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
            },
            "additionalProperties": True,
        },
    },
    "additionalProperties": True,
}


_VALIDATOR = Draft202012Validator(GLOBAL_BRIEF_SCHEMA)


def validate_global_brief(payload: Dict[str, Any]) -> List[str]:
    """Return a list of human-readable validation errors (empty means valid)."""
    errors = []
    for e in sorted(_VALIDATOR.iter_errors(payload), key=lambda x: list(x.path)):
        path = ".".join(str(p) for p in e.path) if e.path else "<root>"
        errors.append(f"{path}: {e.message}")
    return errors


@dataclass(frozen=True)
class Recommendation:
    """Normalized representation of a Global Brief idea-desk item."""

    action: str
    ticker: str
    rationale: str
    source_analysis_id: Optional[int] = None
    created_at: Optional[datetime] = None


def extract_recommendations(payload: Dict[str, Any], *, source_analysis_id: Optional[int] = None) -> List[Recommendation]:
    """Extract normalized recommendations from Global Brief payload.

    We only track `idea_desk` (per product decision).
    """
    ideas = payload.get("idea_desk") or []
    out: List[Recommendation] = []
    if not isinstance(ideas, list):
        return out
    for idea in ideas:
        if not isinstance(idea, dict):
            continue
        action = str(idea.get("action", "")).strip()
        ticker = str(idea.get("ticker", "")).strip()
        rationale = str(idea.get("rationale", "")).strip()
        if not action or not ticker or not rationale:
            continue
        out.append(
            Recommendation(
                action=action.upper(),
                ticker=ticker.upper(),
                rationale=rationale,
                source_analysis_id=source_analysis_id,
            )
        )
    return out



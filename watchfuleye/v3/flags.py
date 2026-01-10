"""Minimal feature flag helpers for V3.

V3 work is shipped behind flags by default to avoid breaking existing production surfaces.
"""

from __future__ import annotations

import os


def _env_truthy(val: str | None) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on"}


def is_v3_entity_ids_enabled() -> bool:
    """Gate V3 entity resolution surfaces."""
    return _env_truthy(os.environ.get("V3_ENTITY_IDS"))


def is_v3_examine_mvp_enabled() -> bool:
    """Gate the minimal 'Examine X' MVP surface (WS4.0 contract stub lives in WS0)."""
    return _env_truthy(os.environ.get("V3_EXAMINE_MVP"))


def is_v3_forecast_tracking_enabled() -> bool:
    """Gate WS6.1 forecast accountability features (accuracy engine)."""
    return _env_truthy(os.environ.get("V3_FORECAST_TRACKING"))


def is_v3_connectors_enabled() -> bool:
    """Gate WS5 connector surfaces."""
    return _env_truthy(os.environ.get("V3_CONNECTORS"))


def is_v3_osint_enabled() -> bool:
    """Gate WS5 OSINT ingestion surfaces (no scraping; accepts upstream-collected payloads)."""
    return _env_truthy(os.environ.get("V3_OSINT"))


def is_v3_alerts_enabled() -> bool:
    """Gate WS6 alerts/monitoring surfaces."""
    return _env_truthy(os.environ.get("V3_ALERTS"))



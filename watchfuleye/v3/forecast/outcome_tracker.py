"""WS6.1 TASK 3 & 4: Outcome measurement via market data and event feeds.

TASK 3: Market outcome tracker - Yahoo Finance, Alpha Vantage
TASK 4: Event outcome tracker - GDELT, ACLED, news articles

IMPLEMENTATION STATUS: Stub with TODO markers
- Full implementation requires WS5 connectors (market data, event feeds)
- This stub provides contract and type signatures for frontend integration
- TODOs marked for WS5 integration points

Priority order for outcome measurement:
1. Market data (if forecast is about price movements, financial metrics)
2. Event feeds (GDELT, ACLED for geopolitical events)
3. Manual assessment (if automated methods fail or low confidence)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


async def measure_forecast_outcome(
    forecast_id: str, forecast: dict[str, Any]
) -> dict[str, Any]:
    """Measure forecast outcome using multiple methods.

    Priority order:
    1. Market data (if forecast is about price movements)
    2. Event feeds (GDELT, ACLED, news articles)
    3. Manual assessment (if automated methods fail)

    Args:
        forecast_id: Forecast ID
        forecast: Forecast dict with claim, entity_ids, horizon_date, etc.

    Returns:
        Dict with:
            - outcome_status: "resolved" | "pending" | "unresolved"
            - outcome_result: bool | None (True if happened, False if didn't)
            - outcome_confidence: float [0, 1] (confidence in measurement)
            - outcome_method: str (how outcome was measured)
            - outcome_measured_at: datetime
            - outcome_evidence: dict (supporting data)
    """
    # Check if horizon has passed
    if forecast["horizon_date"] > datetime.utcnow():
        return {
            "outcome_status": "pending",
            "outcome_result": None,
            "outcome_confidence": None,
            "outcome_method": None,
            "outcome_measured_at": None,
            "outcome_evidence": None,
        }

    # Route to appropriate measurement method
    if _is_market_forecast(forecast):
        return await _measure_via_market_data(forecast)
    elif _is_event_forecast(forecast):
        return await _measure_via_event_feeds(forecast)
    else:
        return {
            "outcome_status": "pending",
            "outcome_result": None,
            "outcome_confidence": None,
            "outcome_method": "manual",
            "outcome_measured_at": None,
            "outcome_evidence": {"reason": "No automated method available"},
        }


def _is_market_forecast(forecast: dict[str, Any]) -> bool:
    """Check if forecast is about market/financial outcomes.

    Indicators:
    - Entity type includes "ticker"
    - Claim mentions: price, stock, rises, falls, gains, losses, market
    """
    entity_types = forecast.get("entity_types") or []
    if "ticker" in entity_types:
        return True

    claim_lower = forecast["claim"].lower()
    market_keywords = [
        "price", "stock", "rises", "falls", "gains", "losses",
        "market", "trading", "shares", "equity", "up", "down"
    ]

    return any(kw in claim_lower for kw in market_keywords)


def _is_event_forecast(forecast: dict[str, Any]) -> bool:
    """Check if forecast is about geopolitical/news events.

    Indicators:
    - Entity type includes "country" or "sanctions_target"
    - Claim mentions: conflict, war, sanctions, agreement, crisis, attack
    """
    entity_types = forecast.get("entity_types") or []
    if "country" in entity_types or "sanctions_target" in entity_types:
        return True

    claim_lower = forecast["claim"].lower()
    event_keywords = [
        "conflict", "war", "sanctions", "agreement", "treaty",
        "crisis", "attack", "invasion", "escalation", "peace"
    ]

    return any(kw in claim_lower for kw in event_keywords)


# ==========================================
# MARKET DATA METHODS (TASK 3)
# ==========================================

async def _measure_via_market_data(forecast: dict[str, Any]) -> dict[str, Any]:
    """Measure outcome via market data (Yahoo Finance, Alpha Vantage).

    TODO: Implement after WS5 connectors are available.

    Implementation plan:
    1. Extract ticker symbols from entity_ids
    2. Determine claim type: price increase/decrease, threshold crossing
    3. Fetch historical price data for horizon period
    4. Compare actual vs predicted outcome
    5. Calculate confidence based on data quality

    Example claims:
    - "TSLA stock rises 10% within 30 days"
    - "Oil prices exceed $100/barrel by end of quarter"
    - "S&P 500 declines below 4000 within 2 weeks"
    """
    # TODO: Extract ticker symbols
    entity_ids = forecast.get("entity_ids") or []
    tickers = [eid.split(":")[1] for eid in entity_ids if eid.startswith("ticker:")]

    if not tickers:
        return {
            "outcome_status": "unresolved",
            "outcome_result": None,
            "outcome_confidence": 0.0,
            "outcome_method": "market_data",
            "outcome_measured_at": datetime.utcnow(),
            "outcome_evidence": {"error": "No ticker symbols found"},
        }

    # TODO: Implement market data fetch
    # market_data = await _fetch_yahoo_finance_data(tickers, forecast["horizon_date"])

    # Stub: Return unresolved for now
    return {
        "outcome_status": "pending",
        "outcome_result": None,
        "outcome_confidence": None,
        "outcome_method": "market_data",
        "outcome_measured_at": None,
        "outcome_evidence": {"todo": "WS5 market data connector not yet implemented"},
    }


async def _fetch_yahoo_finance_data(
    ticker: str, start_date: datetime, end_date: datetime
) -> dict[str, Any]:
    """Fetch historical price data from Yahoo Finance.

    TODO: Implement using yfinance or direct API.

    Returns:
        Dict with:
            - ticker: str
            - prices: list of {"date": datetime, "close": float}
            - change_pct: float (% change over period)
    """
    # TODO: Implement Yahoo Finance API integration
    return {}


async def _fetch_alpha_vantage_data(
    symbol: str, start_date: datetime, end_date: datetime
) -> dict[str, Any]:
    """Fetch data from Alpha Vantage (alternative to Yahoo Finance).

    TODO: Implement using Alpha Vantage API key from env.

    Returns:
        Dict with price/volume data
    """
    # TODO: Implement Alpha Vantage API integration
    return {}


# ==========================================
# EVENT FEED METHODS (TASK 4)
# ==========================================

async def _measure_via_event_feeds(forecast: dict[str, Any]) -> dict[str, Any]:
    """Measure outcome via event feeds (GDELT, ACLED, news).

    TODO: Implement after WS5 connectors are available.

    Implementation plan:
    1. Extract country/entity from entity_ids
    2. Determine claim type: conflict, agreement, policy change
    3. Fetch GDELT/ACLED events for horizon period
    4. Search news articles for confirming/disconfirming evidence
    5. Score confidence based on event salience and source quality

    Example claims:
    - "Iran increases oil exports within 30 days"
    - "Gaza conflict escalates by end of week"
    - "Russia/Ukraine ceasefire agreement by Q2"
    """
    # TODO: Extract entities
    entity_ids = forecast.get("entity_ids") or []
    countries = [eid.split(":")[1] for eid in entity_ids if eid.startswith("country:")]

    if not countries:
        return {
            "outcome_status": "unresolved",
            "outcome_result": None,
            "outcome_confidence": 0.0,
            "outcome_method": "event_feeds",
            "outcome_measured_at": datetime.utcnow(),
            "outcome_evidence": {"error": "No country entities found"},
        }

    # TODO: Implement event feed fetch
    # events = await _fetch_event_data(countries, forecast["horizon_date"])

    # Stub: Return unresolved for now
    return {
        "outcome_status": "pending",
        "outcome_result": None,
        "outcome_confidence": None,
        "outcome_method": "event_feeds",
        "outcome_measured_at": None,
        "outcome_evidence": {"todo": "WS5 event feed connector not yet implemented"},
    }


async def _fetch_gdelt_events(
    countries: list[str], start_date: datetime, end_date: datetime
) -> list[dict[str, Any]]:
    """Fetch events from GDELT Global Knowledge Graph.

    TODO: Implement GDELT GKG API integration.

    Returns:
        List of events with:
            - date: datetime
            - actors: list[str] (countries/entities)
            - event_type: str (conflict, agreement, etc.)
            - tone: float (sentiment)
            - sources: list[str] (URLs)
    """
    # TODO: Implement GDELT API integration
    return []


async def _fetch_acled_events(
    countries: list[str], start_date: datetime, end_date: datetime
) -> list[dict[str, Any]]:
    """Fetch conflict events from ACLED (Armed Conflict Location & Event Data).

    TODO: Implement ACLED API integration (requires API key).

    Returns:
        List of conflict events with location, type, fatalities
    """
    # TODO: Implement ACLED API integration
    return []


async def _search_news_articles(
    query: str, start_date: datetime, end_date: datetime
) -> list[dict[str, Any]]:
    """Search news articles for confirming/disconfirming evidence.

    TODO: Use existing WatchfulEye article database + external news APIs.

    Implementation:
    1. Search articles table for matching content in date range
    2. Optionally fetch from NewsAPI, Google News for recent events
    3. Score relevance and extract confirming/disconfirming passages

    Returns:
        List of articles with relevance scores
    """
    # TODO: Implement news article search
    return []


# ==========================================
# MANUAL ASSESSMENT HELPERS
# ==========================================

def requires_manual_assessment(forecast: dict[str, Any]) -> bool:
    """Check if forecast requires manual outcome assessment.

    Reasons for manual assessment:
    - No automated method available for claim type
    - Automated methods returned low confidence (< 0.6)
    - Complex claims requiring human judgment
    """
    # If no entity IDs, likely requires manual assessment
    if not forecast.get("entity_ids"):
        return True

    # If claim is very specific or complex
    claim_lower = forecast["claim"].lower()
    manual_indicators = [
        "policy", "decision", "announces", "declares",
        "if", "unless", "conditional"  # Conditional forecasts
    ]

    return any(ind in claim_lower for ind in manual_indicators)

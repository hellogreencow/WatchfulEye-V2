"""WS6.1 TASK 3 & 4: Outcome measurement via market data and event feeds.

This module is intentionally **best-effort**:
- It must never crash request paths.
- It must degrade gracefully when external sources are unavailable.
- It should be deterministic and testable (network calls are mockable).

Sources (MVP):
- Markets: Yahoo Finance (chart endpoint) with optional Alpha Vantage fallback.
- Events: GDELT doc API + internal Postgres article search (FTS).

Outcome status vocabulary (matches DB schema):
- pending: horizon not reached
- resolved: outcome determined (outcome_result is True/False)
- unresolved: horizon reached but measurement failed / insufficient signal (manual review needed)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests


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
    now_utc = datetime.now(timezone.utc)
    if forecast["horizon_date"] > now_utc:
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
            "outcome_status": "unresolved",
            "outcome_result": None,
            "outcome_confidence": 0.0,
            "outcome_method": "manual",
            "outcome_measured_at": now_utc,
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

    Example claims:
    - "TSLA stock rises 10% within 30 days"
    - "Oil prices exceed $100/barrel by end of quarter"
    - "S&P 500 declines below 4000 within 2 weeks"
    """
    entity_ids = forecast.get("entity_ids") or []
    tickers = [eid.split(":")[1] for eid in entity_ids if eid.startswith("ticker:")]

    if not tickers:
        return {
            "outcome_status": "unresolved",
            "outcome_result": None,
            "outcome_confidence": 0.0,
            "outcome_method": "market_data",
            "outcome_measured_at": datetime.now(timezone.utc),
            "outcome_evidence": {"error": "No ticker symbols found"},
        }

    ticker = tickers[0]  # Use first ticker
    created_at = forecast.get("created_at") or datetime.now(timezone.utc)
    horizon_date = forecast["horizon_date"]

    # Try Yahoo Finance first, fallback to Alpha Vantage
    market_data = await _fetch_yahoo_finance_data(ticker, created_at, horizon_date)

    if "error" in market_data:
        market_data = await _fetch_alpha_vantage_data(ticker, created_at, horizon_date)
        if "error" in market_data:
            return {
                "outcome_status": "unresolved",
                "outcome_result": None,
                "outcome_confidence": 0.0,
                "outcome_method": "market_data",
                "outcome_measured_at": datetime.now(timezone.utc),
                "outcome_evidence": market_data,
            }

    # Analyze claim and determine outcome
    claim_lower = forecast["claim"].lower()
    probability = forecast["probability"]
    change_pct = market_data["change_pct"]

    # Determine if forecast was directionally correct
    if "rises" in claim_lower or "gains" in claim_lower or "up" in claim_lower:
        outcome_result = change_pct > 0
    elif "falls" in claim_lower or "declines" in claim_lower or "down" in claim_lower:
        outcome_result = change_pct < 0
    else:
        # Default: check if forecast probability aligns with actual movement
        outcome_result = (probability > 0.5 and change_pct > 0) or (
            probability <= 0.5 and change_pct <= 0
        )

    # Calculate confidence based on data quality
    confidence = 0.9 if len(market_data["prices"]) > 10 else 0.7

    return {
        "outcome_status": "resolved",
        "outcome_result": outcome_result,
        "outcome_confidence": confidence,
        "outcome_method": "market_data",
        "outcome_measured_at": datetime.now(timezone.utc),
        "outcome_evidence": {
            "source": "yahoo_finance" if "yahoo" in str(market_data) else "alpha_vantage",
            "ticker": ticker,
            "start_price": market_data["start_price"],
            "end_price": market_data["end_price"],
            "change_pct": change_pct,
            "data_points": len(market_data["prices"]),
        },
    }


async def _fetch_yahoo_finance_data(
    ticker: str, start_date: datetime, end_date: datetime
) -> dict[str, Any]:
    """Fetch historical daily close data from Yahoo Finance (free chart endpoint).

    Note: We intentionally avoid `yfinance` to keep dependencies minimal and testable.
    """
    import calendar

    try:
        # Yahoo chart endpoint expects unix timestamps in seconds.
        period1 = int(calendar.timegm(start_date.utctimetuple()))
        period2 = int(calendar.timegm(end_date.utctimetuple()))

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        resp = requests.get(
            url,
            params={
                "interval": "1d",
                "period1": str(period1),
                "period2": str(period2),
                "events": "history",
                "includeAdjustedClose": "true",
            },
            headers={"User-Agent": "WatchfulEye/2.0"},
            timeout=20,
        )
        if resp.status_code != 200:
            return {"error": f"Yahoo Finance HTTP {resp.status_code}"}

        data = resp.json() or {}
        chart = (data.get("chart") or {})
        if chart.get("error"):
            return {"error": f"Yahoo Finance error: {chart.get('error')}"}

        result = (chart.get("result") or [])
        if not result:
            return {"error": f"No data found for {ticker}"}

        r0 = result[0] or {}
        timestamps = r0.get("timestamp") or []
        quotes = (((r0.get("indicators") or {}).get("quote") or [None])[0]) or {}
        closes = quotes.get("close") or []

        prices: list[dict[str, Any]] = []
        for ts, c in zip(timestamps, closes):
            if c is None:
                continue
            prices.append({"date": datetime.fromtimestamp(int(ts), tz=timezone.utc), "close": float(c)})

        if len(prices) < 2:
            return {"error": f"Insufficient data for {ticker}"}

        start_price = float(prices[0]["close"])
        end_price = float(prices[-1]["close"])
        change_pct = ((end_price - start_price) / start_price) * 100.0 if start_price else 0.0

        return {
            "ticker": ticker,
            "prices": prices,
            "start_price": start_price,
            "end_price": end_price,
            "change_pct": change_pct,
        }
    except Exception as e:
        return {"error": f"Yahoo Finance error: {str(e)}"}


async def _fetch_alpha_vantage_data(
    symbol: str, start_date: datetime, end_date: datetime
) -> dict[str, Any]:
    """Fetch data from Alpha Vantage (alternative to Yahoo Finance).

    Returns:
        Dict with price/volume data
    """
    import os

    try:
        api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            return {"error": "ALPHA_VANTAGE_API_KEY not configured"}

        url = "https://www.alphavantage.co/query"
        resp = requests.get(
            url,
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                "apikey": api_key,
                "outputsize": "full",
            },
            headers={"User-Agent": "WatchfulEye/2.0"},
            timeout=30,
        )
        if resp.status_code != 200:
            return {"error": f"Alpha Vantage HTTP {resp.status_code}"}

        data = resp.json() or {}
        if "Error Message" in data:
            return {"error": data["Error Message"]}

        ts = data.get("Time Series (Daily)")
        if not isinstance(ts, dict):
            return {"error": "Invalid response from Alpha Vantage"}

        # Filter by date range (inclusive)
        prices: list[dict[str, Any]] = []
        for date_str, values in sorted(ts.items()):
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                if start_date.date() <= date_obj.date() <= end_date.date():
                    prices.append({"date": date_obj, "close": float(values["4. close"])})
            except Exception:
                continue

        if len(prices) < 2:
            return {"error": f"Insufficient data for {symbol}"}

        start_price = float(prices[0]["close"])
        end_price = float(prices[-1]["close"])
        change_pct = ((end_price - start_price) / start_price) * 100.0 if start_price else 0.0

        return {
            "ticker": symbol,
            "prices": prices,
            "start_price": start_price,
            "end_price": end_price,
            "change_pct": change_pct,
        }
    except Exception as e:
        return {"error": f"Alpha Vantage error: {str(e)}"}


# ==========================================
# EVENT FEED METHODS (TASK 4)
# ==========================================

async def _measure_via_event_feeds(forecast: dict[str, Any]) -> dict[str, Any]:
    """Measure outcome via event feeds (GDELT, news).

    Example claims:
    - "Iran increases oil exports within 30 days"
    - "Gaza conflict escalates by end of week"
    - "Russia/Ukraine ceasefire agreement by Q2"
    """
    entity_ids = forecast.get("entity_ids") or []
    countries = [eid.split(":")[1] for eid in entity_ids if eid.startswith("country:")]

    if not countries:
        return {
            "outcome_status": "unresolved",
            "outcome_result": None,
            "outcome_confidence": 0.0,
            "outcome_method": "event_feeds",
            "outcome_measured_at": datetime.now(timezone.utc),
            "outcome_evidence": {"error": "No country entities found"},
        }

    created_at = forecast.get("created_at") or datetime.now(timezone.utc)
    horizon_date = forecast["horizon_date"]
    claim = forecast["claim"]

    # Fetch events from multiple sources
    gdelt_events = await _fetch_gdelt_events(countries, created_at, horizon_date)
    news_articles = await _search_news_articles(claim, created_at, horizon_date)

    # Check for errors
    if gdelt_events and "error" in gdelt_events[0]:
        gdelt_events = []
    if news_articles and "error" in news_articles[0]:
        news_articles = []

    if not gdelt_events and not news_articles:
        return {
            "outcome_status": "unresolved",
            "outcome_result": None,
            "outcome_confidence": 0.0,
            "outcome_method": "event_feeds",
            "outcome_measured_at": datetime.now(timezone.utc),
            "outcome_evidence": {"error": "No events found"},
        }

    # Analyze events to determine outcome
    # Simple heuristic: if significant events found, forecast was likely correct
    claim_lower = claim.lower()
    confirming_keywords = []
    if "escalat" in claim_lower or "conflict" in claim_lower or "war" in claim_lower:
        confirming_keywords = ["escalat", "conflict", "attack", "war", "fight"]
    elif "agreement" in claim_lower or "peace" in claim_lower or "ceasefire" in claim_lower:
        confirming_keywords = ["agreement", "peace", "ceasefire", "treaty", "deal"]
    elif "sanction" in claim_lower:
        confirming_keywords = ["sanction", "embargo", "restrict", "ban"]
    elif "export" in claim_lower or "trade" in claim_lower:
        confirming_keywords = ["export", "trade", "ship", "deliver"]

    # Score confirmation based on matching keywords
    confirmation_score = 0.0
    total_articles = len(news_articles)

    for article in news_articles:
        article_text = (article.get("title", "") + " " + article.get("summary", "")).lower()
        if any(kw in article_text for kw in confirming_keywords):
            confirmation_score += article.get("relevance", 0.5)

    # Normalize score
    if total_articles > 0:
        confirmation_score = min(confirmation_score / total_articles, 1.0)

    # Determine outcome based on forecast probability and evidence
    probability = forecast["probability"]
    outcome_result = (probability > 0.5 and confirmation_score > 0.3) or (
        probability <= 0.5 and confirmation_score <= 0.3
    )

    confidence = min(0.6 + (confirmation_score * 0.3), 0.9)  # Max 0.9 confidence

    return {
        "outcome_status": "resolved",
        "outcome_result": outcome_result,
        "outcome_confidence": confidence,
        "outcome_method": "event_feeds",
        "outcome_measured_at": datetime.now(timezone.utc),
        "outcome_evidence": {
            "gdelt_events": len(gdelt_events),
            "news_articles": len(news_articles),
            "confirmation_score": confirmation_score,
            "sample_articles": [
                {
                    "title": a.get("title", ""),
                    "url": a.get("url", ""),
                    "relevance": a.get("relevance", 0),
                }
                for a in news_articles[:5]
            ],
        },
    }


async def _fetch_gdelt_events(
    countries: list[str], start_date: datetime, end_date: datetime
) -> list[dict[str, Any]]:
    """Fetch events from GDELT Global Knowledge Graph.

    Returns:
        List of events with:
            - date: datetime
            - actors: list[str] (countries/entities)
            - event_type: str (conflict, agreement, etc.)
            - tone: float (sentiment)
            - sources: list[str] (URLs)
    """
    try:
        events: list[dict[str, Any]] = []

        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        # Build query for countries
        country_codes = {
            "IRAN": "IRN",
            "RUSSIA": "RUS",
            "CHINA": "CHN",
            "USA": "USA",
            "ISRAEL": "ISR",
            "UKRAINE": "UKR",
            "SAUDI ARABIA": "SAU",
        }

        url = "https://api.gdeltproject.org/api/v2/doc/doc"
        for country in countries:
            # Keep it simple: query by country string; expand later with entity resolution.
            _ = country_codes.get(country.upper(), country.upper()[:3])  # reserved for later

            resp = requests.get(
                url,
                params={
                    "query": f"{country} (conflict OR sanctions OR agreement OR crisis)",
                    "mode": "ArtList",
                    "maxrecords": "50",
                    "format": "json",
                    "startdatetime": start_str + "000000",
                    "enddatetime": end_str + "235959",
                    "sort": "HybridRel",
                },
                headers={"User-Agent": "WatchfulEye/2.0"},
                timeout=30,
            )
            if resp.status_code != 200:
                continue
            try:
                data = resp.json() or {}
            except Exception:
                continue

            articles = data.get("articles") or data.get("documents") or []
            if not isinstance(articles, list):
                continue

            for article in articles[:10]:
                if not isinstance(article, dict):
                    continue
                seendate = article.get("seendate")
                try:
                    dt = (
                        datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                        if seendate
                        else datetime.now(timezone.utc)
                    )
                except Exception:
                    dt = datetime.now(timezone.utc)
                url_s = article.get("url") or ""
                events.append(
                    {
                        "date": dt,
                        "actors": [country],
                        "event_type": "news_event",
                        "tone": float(article.get("tone", 0) or 0.0),
                        "sources": [url_s] if url_s else [],
                        "title": article.get("title", "") or "",
                    }
                )

        return events
    except Exception as e:
        return [{"error": f"GDELT error: {str(e)}"}]


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

    Implementation:
    1. Search articles table for matching content in date range
    2. Score relevance and extract confirming/disconfirming passages

    Returns:
        List of articles with relevance scores
    """
    import os

    try:
        import psycopg
        from psycopg.rows import dict_row

        pg_dsn = os.environ.get("PG_DSN")
        if not pg_dsn:
            return [{"error": "Database not configured"}]

        with psycopg.connect(pg_dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                # Search articles with full-text search (using generated `search_tsv`)
                cur.execute(
                    """
                    SELECT
                        id,
                        title,
                        description,
                        canonical_url,
                        published_at,
                        ts_rank(
                            search_tsv,
                            plainto_tsquery('english', %s)
                        ) AS relevance
                    FROM articles
                    WHERE published_at BETWEEN %s AND %s
                      AND (
                        search_tsv @@ plainto_tsquery('english', %s)
                      )
                    ORDER BY relevance DESC, published_at DESC
                    LIMIT 20
                    """,
                    (query, start_date, end_date, query),
                )
                articles = cur.fetchall()

                return [
                    {
                        "id": a["id"],
                        "title": a["title"],
                        "summary": a["description"],
                        "url": a["canonical_url"],
                        "date": a["published_at"],
                        "relevance": float(a["relevance"]),
                    }
                    for a in articles
                ]
    except Exception as e:
        return [{"error": f"News search error: {str(e)}"}]


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

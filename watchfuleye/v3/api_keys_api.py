"""WS6.1: Admin API to store API keys and test connector endpoints.

Purpose: Make it easy (and safe) to configure connector credentials and verify
connectivity from the UI without SSHing into servers.

Security:
- Requires `V3_FORECAST_TRACKING=true` (feature surface stays off by default).
- Requires authenticated admin user (validated via existing SQLite sessions).
- API key values are encrypted at rest in SQLite (`DB_PATH`) table `v3_api_keys`.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests
from flask import Blueprint, jsonify, request

from watchfuleye.v3.admin_auth import get_current_user
from watchfuleye.v3.api_keys_store import (
    get_api_key_plaintext,
    is_encryption_configured,
    list_api_keys,
    upsert_api_key,
)
from watchfuleye.v3.flags import is_v3_forecast_tracking_enabled


bp_v3_api_keys = Blueprint("v3_api_keys", __name__, url_prefix="/api/v3/admin")


SUPPORTED_KEYS: dict[str, dict[str, Any]] = {
    "alpha_vantage": {
        "label": "Alpha Vantage",
        "env_var": "ALPHA_VANTAGE_API_KEY",
        "required_for": ["markets_fallback"],
        "docs": "https://www.alphavantage.co/support/#api-key",
    }
}

SUPPORTED_ENDPOINT_TESTS: dict[str, dict[str, Any]] = {
    "yahoo_finance": {"label": "Yahoo Finance (chart)", "docs": "https://query1.finance.yahoo.com/"},
    "gdelt": {"label": "GDELT Doc API", "docs": "https://www.gdeltproject.org/"},
}


@bp_v3_api_keys.route("/api-keys", methods=["GET"])
def list_api_keys_status():
    if not is_v3_forecast_tracking_enabled():
        return ("Not Found", 404)

    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    if user.get("role") != "admin":
        return jsonify({"error": "Unauthorized access"}), 403

    db_path = os.environ.get("DB_PATH", "news_bot.db")
    stored = {row.get("name"): row for row in list_api_keys(db_path)}

    keys_out: list[dict[str, Any]] = []
    for name, meta in SUPPORTED_KEYS.items():
        env_var = meta.get("env_var")
        env_set = bool(env_var and os.environ.get(str(env_var)))
        rec = stored.get(name)
        stored_set = bool(rec)
        keys_out.append(
            {
                "name": name,
                "label": meta.get("label") or name,
                "env_var": env_var,
                "env_configured": env_set,
                "stored_configured": stored_set,
                "configured": env_set or stored_set,
                "updated_at": (rec.get("updated_at") if rec else None),
                "updated_by": (rec.get("updated_by") if rec else None),
                "docs": meta.get("docs"),
            }
        )

    return jsonify(
        {
            "encryption_configured": is_encryption_configured(),
            "keys": keys_out,
            "endpoint_tests": [{"id": k, **v} for (k, v) in SUPPORTED_ENDPOINT_TESTS.items()],
        }
    )


@bp_v3_api_keys.route("/api-keys/<name>", methods=["PUT"])
def set_api_key(name: str):
    if not is_v3_forecast_tracking_enabled():
        return ("Not Found", 404)

    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    if user.get("role") != "admin":
        return jsonify({"error": "Unauthorized access"}), 403

    name_s = (name or "").strip()
    if name_s not in SUPPORTED_KEYS:
        return ("Not Found", 404)

    db_path = os.environ.get("DB_PATH", "news_bot.db")

    payload: Any = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    value = payload.get("value")
    if not isinstance(value, str) or not value.strip():
        return jsonify({"error": "value is required"}), 400

    updated_by = f"user:{user.get('username')}" if user.get("username") else None

    try:
        upsert_api_key(db_path, name=name_s, plaintext=value.strip(), updated_by=updated_by)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"success": True, "name": name_s})


@bp_v3_api_keys.route("/api-keys/<name>/test", methods=["POST"])
def test_api_key(name: str):
    if not is_v3_forecast_tracking_enabled():
        return ("Not Found", 404)

    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    if user.get("role") != "admin":
        return jsonify({"error": "Unauthorized access"}), 403

    name_s = (name or "").strip()
    if name_s not in SUPPORTED_KEYS:
        return ("Not Found", 404)

    meta = SUPPORTED_KEYS[name_s]
    env_var = meta.get("env_var")
    db_path = os.environ.get("DB_PATH", "news_bot.db")

    key = None
    if env_var:
        key = os.environ.get(str(env_var))
    if not key:
        key = get_api_key_plaintext(db_path, name=name_s)
    if not key:
        return jsonify({"ok": False, "error": f"{name_s} key not configured"}), 400

    if name_s == "alpha_vantage":
        return jsonify(_test_alpha_vantage(key))

    return jsonify({"ok": False, "error": "No test available"}), 400


@bp_v3_api_keys.route("/endpoints/test", methods=["POST"])
def test_endpoint():
    if not is_v3_forecast_tracking_enabled():
        return ("Not Found", 404)

    user = get_current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    if user.get("role") != "admin":
        return jsonify({"error": "Unauthorized access"}), 403

    payload: Any = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    endpoint = payload.get("endpoint")
    if not isinstance(endpoint, str) or endpoint not in SUPPORTED_ENDPOINT_TESTS:
        return jsonify({"error": "endpoint is required"}), 400

    if endpoint == "yahoo_finance":
        return jsonify(_test_yahoo_finance())
    if endpoint == "gdelt":
        return jsonify(_test_gdelt())

    return jsonify({"ok": False, "error": "Unsupported endpoint"}), 400


def _test_alpha_vantage(api_key: str) -> dict[str, Any]:
    """Make a minimal Alpha Vantage call to validate connectivity + key."""
    url = "https://www.alphavantage.co/query"
    try:
        resp = requests.get(
            url,
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": "AAPL",
                "apikey": api_key,
                "outputsize": "compact",
            },
            headers={"User-Agent": "WatchfulEye/2.0"},
            timeout=20,
        )
        data = resp.json() if resp.status_code == 200 else {}
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}"}

        if isinstance(data, dict) and "Time Series (Daily)" in data:
            return {"ok": True, "message": "Alpha Vantage OK"}
        if isinstance(data, dict) and "Note" in data:
            # Rate limits often still indicate the key is valid.
            return {"ok": True, "message": "Alpha Vantage reachable (rate-limited)", "note": data.get("Note")}
        if isinstance(data, dict) and "Error Message" in data:
            return {"ok": False, "error": "Alpha Vantage error", "detail": data.get("Error Message")}
        if isinstance(data, dict) and "Information" in data:
            return {"ok": False, "error": "Alpha Vantage info", "detail": data.get("Information")}

        return {"ok": False, "error": "Unexpected Alpha Vantage response"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _test_yahoo_finance() -> dict[str, Any]:
    """Ping Yahoo Finance chart endpoint."""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/AAPL"
        now = datetime.now(timezone.utc)
        # Short window to keep payload small
        period2 = int(now.timestamp())
        period1 = int((now.timestamp()) - (7 * 86400))
        resp = requests.get(
            url,
            params={
                "interval": "1d",
                "period1": str(period1),
                "period2": str(period2),
                "events": "history",
            },
            headers={"User-Agent": "WatchfulEye/2.0"},
            timeout=20,
        )
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        data = resp.json() or {}
        chart = data.get("chart") or {}
        if chart.get("error"):
            return {"ok": False, "error": "Yahoo Finance returned error", "detail": chart.get("error")}
        return {"ok": True, "message": "Yahoo Finance OK"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _test_gdelt() -> dict[str, Any]:
    """Ping GDELT doc API."""
    try:
        resp = requests.get(
            "https://api.gdeltproject.org/api/v2/doc/doc",
            params={
                "query": "geopolitics",
                "mode": "ArtList",
                "format": "json",
                "maxrecords": "1",
                "sort": "HybridRel",
            },
            headers={"User-Agent": "WatchfulEye/2.0"},
            timeout=20,
        )
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        try:
            data = resp.json() or {}
        except Exception:
            return {"ok": False, "error": "Non-JSON response"}
        articles = data.get("articles") or data.get("documents") or []
        if not isinstance(articles, list):
            return {"ok": False, "error": "Unexpected response shape"}
        return {"ok": True, "message": "GDELT OK", "articles": len(articles)}
    except Exception as e:
        return {"ok": False, "error": str(e)}



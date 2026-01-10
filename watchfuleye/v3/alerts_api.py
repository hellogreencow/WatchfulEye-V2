"""WS6: Alerts + Monitoring (minimal API).

This is the server-authoritative surface for creating alert rules and reading alert events.
Delivery (telegram/email) will be implemented incrementally; MVP records in-app events.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import psycopg
from flask import Blueprint, jsonify, request
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from watchfuleye.v3.admin_auth import require_admin
from watchfuleye.v3.flags import is_v3_alerts_enabled


bp_v3_alerts = Blueprint("v3_alerts", __name__, url_prefix="/api/v3/alerts")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_pg_dsn() -> str | None:
    # Keep parity with CI + workers: we use env PG_DSN.
    return os.environ.get("PG_DSN")


@bp_v3_alerts.route("/rules", methods=["GET"])
@require_admin
def list_alert_rules():
    if not is_v3_alerts_enabled():
        return jsonify({"success": False, "error": "V3 alerts disabled"}), 404
    pg_dsn = _get_pg_dsn()
    if not pg_dsn:
        return jsonify({"success": False, "error": "PG_DSN not configured"}), 503

    with psycopg.connect(pg_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, enabled, rule_type, config, channels, created_by,
                       created_at, updated_at, last_evaluated_at
                FROM alert_rules
                ORDER BY updated_at DESC
                LIMIT 200
                """
            )
            rows = cur.fetchall()
    return jsonify({"success": True, "data": rows, "count": len(rows)})


@bp_v3_alerts.route("/rules", methods=["POST"])
@require_admin
def create_alert_rule():
    if not is_v3_alerts_enabled():
        return jsonify({"success": False, "error": "V3 alerts disabled"}), 404
    pg_dsn = _get_pg_dsn()
    if not pg_dsn:
        return jsonify({"success": False, "error": "PG_DSN not configured"}), 503

    body = request.get_json(silent=True) or {}
    rule_id = str(body.get("id") or "").strip()
    name = str(body.get("name") or "").strip()
    rule_type = str(body.get("rule_type") or "").strip()
    enabled = bool(body.get("enabled", True))
    config = body.get("config") or {}
    channels = body.get("channels") or ["in_app"]
    created_by = "admin"

    if not rule_id or not name or not rule_type:
        return jsonify({"success": False, "error": "id, name, rule_type are required"}), 400
    if not isinstance(config, dict):
        return jsonify({"success": False, "error": "config must be an object"}), 400
    if not isinstance(channels, list) or not all(isinstance(c, str) for c in channels):
        return jsonify({"success": False, "error": "channels must be a list of strings"}), 400

    now = _utcnow()
    with psycopg.connect(pg_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alert_rules (id, name, enabled, rule_type, config, channels, created_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                  name=excluded.name,
                  enabled=excluded.enabled,
                  rule_type=excluded.rule_type,
                  config=excluded.config,
                  channels=excluded.channels,
                  created_by=excluded.created_by,
                  updated_at=excluded.updated_at
                """,
                (rule_id, name, enabled, rule_type, Jsonb(config), channels, created_by, now, now),
            )
            conn.commit()
    return jsonify({"success": True, "id": rule_id})


@bp_v3_alerts.route("/events", methods=["GET"])
@require_admin
def list_alert_events():
    if not is_v3_alerts_enabled():
        return jsonify({"success": False, "error": "V3 alerts disabled"}), 404
    pg_dsn = _get_pg_dsn()
    if not pg_dsn:
        return jsonify({"success": False, "error": "PG_DSN not configured"}), 503

    try:
        limit = int(request.args.get("limit", "100"))
    except Exception:
        limit = 100
    limit = max(1, min(limit, 500))

    with psycopg.connect(pg_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.id, e.rule_id, r.name AS rule_name, r.rule_type,
                       e.event_type, e.payload, e.created_at, e.delivered_at, e.delivery_error
                FROM alert_events e
                JOIN alert_rules r ON r.id = e.rule_id
                ORDER BY e.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return jsonify({"success": True, "data": rows, "count": len(rows)})



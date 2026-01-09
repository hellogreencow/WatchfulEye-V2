"""WS0: Entity Resolution stub API (V3).

Contract (from WATCHFULEYE_V3_MASTER_PLAN.md):
  POST /api/v3/entities/resolve
    request: { "q": string, "k": number=10, "types": ["ticker"|"country"|"sanctions_target"] }
    response: { "matches": [...], "trace_id": string }

This is intentionally minimal: it only validates input and returns empty matches.
Real resolver + persistence ships in later WS0 slices.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal, TypedDict

from flask import Blueprint, jsonify, request

from watchfuleye.v3.flags import is_v3_entity_ids_enabled


bp_v3_entities = Blueprint("v3_entities", __name__, url_prefix="/api/v3/entities")

EntityType = Literal["ticker", "country", "sanctions_target"]


class ResolveRequest(TypedDict, total=False):
    q: str
    k: int
    types: list[EntityType]


@bp_v3_entities.route("/resolve", methods=["POST"])
def resolve_entity():
    # Hide surface unless enabled (default OFF).
    if not is_v3_entity_ids_enabled():
        return ("Not Found", 404)

    payload: Any = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    q = payload.get("q")
    if not isinstance(q, str) or not q.strip():
        return jsonify({"error": "q is required"}), 400

    k_raw = payload.get("k", 10)
    try:
        k = int(k_raw)
    except Exception:
        return jsonify({"error": "k must be an integer"}), 400
    k = max(1, min(k, 50))

    types_raw = payload.get("types", ["ticker", "country", "sanctions_target"])
    if not isinstance(types_raw, list) or not all(isinstance(t, str) for t in types_raw):
        return jsonify({"error": "types must be a list of strings"}), 400
    allowed: set[str] = {"ticker", "country", "sanctions_target"}
    types: list[str] = [t for t in types_raw if t in allowed]
    if not types:
        return jsonify({"error": "types must include at least one of: ticker, country, sanctions_target"}), 400

    # Stub: return empty match set with trace ID for auditability.
    trace_id = str(uuid.uuid4())
    return jsonify({"matches": [], "trace_id": trace_id, "q": q, "k": k, "types": types}), 200



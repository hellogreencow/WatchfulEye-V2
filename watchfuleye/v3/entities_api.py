"""WS0: Entity Resolution stub API (V3).

Contract (from WATCHFULEYE_V3_MASTER_PLAN.md):
  POST /api/v3/entities/resolve
    request: { "q": string, "k": number=10, "types": ["ticker"|"country"|"sanctions_target"] }
    response: { "matches": [...], "trace_id": string }

This is intentionally minimal: it only validates input and returns empty matches.
Real resolver + persistence ships in later WS0 slices.
"""

from __future__ import annotations

import os
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

    # Minimal WS0.3 behavior: attempt exact-match resolution via Postgres, but never fail the app.
    matches: list[dict[str, Any]] = []
    try:
        import psycopg
        from watchfuleye.storage.postgres_schema import ensure_postgres_schema

        pg_dsn = os.environ.get("PG_DSN")
        if pg_dsn:
            ensure_postgres_schema(pg_dsn)
            with psycopg.connect(pg_dsn) as conn:
                with conn.cursor() as cur:
                    q_norm = q.strip()
                    # Simple normalizations:
                    # - ticker: uppercase
                    # - country: uppercase for ISO codes; otherwise keep as-is (we'll store names as given)
                    candidates: list[tuple[str, str]] = []
                    if "ticker" in types:
                        candidates.append(("ticker", q_norm.upper()))
                    if "country" in types:
                        if len(q_norm) in (2, 3) and q_norm.isalpha():
                            candidates.append(("iso3166", q_norm.upper()))
                        candidates.append(("name", q_norm))
                    if "sanctions_target" in types:
                        candidates.append(("ofac_id", q_norm))
                        candidates.append(("name", q_norm))

                    for (id_type, id_value) in candidates:
                        cur.execute(
                            """
                            SELECT e.id, e.entity_type, e.label, i.confidence, i.provenance
                            FROM entity_identifiers i
                            JOIN entities e ON e.id = i.entity_id
                            WHERE i.identifier_type = %s AND i.identifier_value = %s
                            LIMIT %s
                            """,
                            (id_type, id_value, k),
                        )
                        for (eid, etype, label, conf, prov) in cur.fetchall():
                            matches.append(
                                {
                                    "entity_id": str(eid),
                                    "entity_type": str(etype),
                                    "label": str(label),
                                    "confidence": float(conf) if conf is not None else 0.0,
                                    "provenance": prov if isinstance(prov, dict) else (prov or {}),
                                }
                            )
                        if matches:
                            break
    except Exception:
        # If Postgres/psycopg isn't available, we fall back to stub.
        matches = []

    return jsonify({"matches": matches[:k], "trace_id": trace_id, "q": q, "k": k, "types": types}), 200



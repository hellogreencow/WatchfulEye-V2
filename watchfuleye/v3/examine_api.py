"""WS0: Contract scaffold for the V3 'Examine X' endpoint.

This deliberately ships as a flag-gated stub so WS4 can build on a stable surface
without risking regressions to V1.

Contract (initial, minimal):
  POST /api/v3/examine
    request: { "q": string, "k": number=10, "types"?: ["ticker"|"country"|"sanctions_target"] }
    response: {
      "investigation_id": string,
      "report_id": string,
      "status": "queued"|"running"|"succeeded"|"failed",
      "trace_id": string,
      "report": { "title": string, "summary": string, "content": object|null }
    }
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from flask import Blueprint, jsonify, request

from watchfuleye.v3.flags import is_v3_examine_mvp_enabled


bp_v3_examine = Blueprint("v3_examine", __name__, url_prefix="/api/v3")


@bp_v3_examine.route("/examine", methods=["POST"])
def v3_examine():
    if not is_v3_examine_mvp_enabled():
        return ("Not Found", 404)

    payload: Any = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    q = payload.get("q")
    if not isinstance(q, str) or not q.strip():
        return jsonify({"error": "q is required"}), 400

    trace_id = str(uuid.uuid4())
    investigation_id = f"inv_{uuid.uuid4().hex[:16]}"
    report_id = f"rep_{uuid.uuid4().hex[:16]}"

    # Minimal stub report (WS4 will replace with real evidence pack + synthesis).
    report = {
        "title": f"Examine: {q.strip()}",
        "summary": "Stub report (WS4 will implement evidence-first synthesis).",
        "content": None,
    }

    # Persist minimal rows when Postgres is available, but never fail the request.
    try:
        import psycopg

        from watchfuleye.storage.postgres_schema import ensure_postgres_schema

        pg_dsn = os.environ.get("PG_DSN")
        if pg_dsn:
            ensure_postgres_schema(pg_dsn)
            with psycopg.connect(pg_dsn, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO v3_investigations (id, query, status, trace_id, meta)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (investigation_id, q.strip(), "queued", trace_id, "{}"),
                    )
                    cur.execute(
                        """
                        INSERT INTO v3_reports (id, investigation_id, title, summary, content)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (report_id, investigation_id, report["title"], report["summary"], "{}"),
                    )
    except Exception:
        pass

    return (
        jsonify(
            {
                "investigation_id": investigation_id,
                "report_id": report_id,
                "status": "queued",
                "trace_id": trace_id,
                "report": report,
            }
        ),
        200,
    )



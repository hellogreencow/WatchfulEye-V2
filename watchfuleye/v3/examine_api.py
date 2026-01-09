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
from watchfuleye.v3.investigations.evidence import fetch_evidence_detailed
from watchfuleye.v3.investigations.report_builder import build_report_content


bp_v3_examine = Blueprint("v3_examine", __name__, url_prefix="/api/v3")


def _dsn_with_connect_timeout(dsn: str, timeout_s: int = 2) -> str:
    """Append a small connect timeout to libpq DSNs (URL or conninfo string).

    This keeps tests and the API handler from hanging when `PG_DSN` is configured
    but the database is unreachable.
    """
    s = (dsn or "").strip()
    if not s:
        return s
    if "connect_timeout=" in s:
        return s
    if "://" in s:
        # URL DSN: add/append query string.
        sep = "&" if "?" in s else "?"
        return f"{s}{sep}connect_timeout={int(timeout_s)}"
    # conninfo string: space-separated key=val pairs.
    return f"{s} connect_timeout={int(timeout_s)}"


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

    q_s = q.strip()

    # Optional params (do not hard-fail; contract allows but WS0 stub is permissive).
    k_raw = payload.get("k", 10)
    try:
        k = int(k_raw)
    except Exception:
        k = 10
    k = max(1, min(int(k), 50))

    trace_id = str(uuid.uuid4())
    investigation_id = f"inv_{uuid.uuid4().hex[:16]}"
    report_id = f"rep_{uuid.uuid4().hex[:16]}"

    pg_dsn = os.environ.get("PG_DSN")
    pg_error: str | None = None
    evidence: list[dict[str, Any]] = []
    if pg_dsn:
        evidence, pg_error = fetch_evidence_detailed(_dsn_with_connect_timeout(pg_dsn, 2), q_s, limit=k)

    content = build_report_content(q_s, evidence)
    if pg_error:
        summary = "Generated report without Postgres-backed evidence (storage unavailable)."
    elif evidence:
        summary = f"Found {len(evidence)} evidence item(s) in the current dataset."
    else:
        summary = "No matching articles found in the current dataset; generated a structure-only report."

    report = {
        "title": f"Examine: {q_s}",
        "summary": summary,
        "content": content,
    }

    # Persist minimal rows when Postgres is available, but never fail the request.
    if pg_dsn:
        try:
            import psycopg
            from psycopg.types.json import Jsonb

            from watchfuleye.storage.postgres_schema import ensure_postgres_schema

            pg_dsn_ct = _dsn_with_connect_timeout(pg_dsn, 2)
            ensure_postgres_schema(pg_dsn_ct)
            meta = {
                "k": k,
                "types": payload.get("types") if isinstance(payload.get("types"), list) else None,
                "evidence_count": len(evidence),
                "pg_error": pg_error,
            }
            with psycopg.connect(pg_dsn_ct, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO v3_investigations (id, query, status, trace_id, meta)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            query = EXCLUDED.query,
                            status = EXCLUDED.status,
                            trace_id = EXCLUDED.trace_id,
                            meta = EXCLUDED.meta,
                            updated_at = now()
                        """,
                        (investigation_id, q_s, "succeeded", trace_id, Jsonb(meta)),
                    )
                    cur.execute(
                        """
                        INSERT INTO v3_reports (id, investigation_id, title, summary, content)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            title = EXCLUDED.title,
                            summary = EXCLUDED.summary,
                            content = EXCLUDED.content
                        """,
                        (report_id, investigation_id, report["title"], report["summary"], Jsonb(report["content"])),
                    )
        except Exception:
            pass

    return (
        jsonify(
            {
                "investigation_id": investigation_id,
                "report_id": report_id,
                "status": "succeeded",
                "trace_id": trace_id,
                "report": report,
            }
        ),
        200,
    )



"""WS4: Deterministic report builder for V3 Examine.

Design goals:
- Evidence-first: bullets and predictions should reference evidence IDs when possible.
- Progressive disclosure: short bullets, structured predictions, explicit dissent.
- Deterministic-ish: no external network calls; no LLM calls in WS4.0.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Optional


def _short(s: str, *, max_len: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3].rstrip() + "..."


def _iso_date(iso_ts: Optional[str]) -> Optional[str]:
    """Best-effort ISO8601 -> YYYY-MM-DD (or None)."""
    if not iso_ts:
        return None
    s = str(iso_ts).strip()
    if not s:
        return None
    # Handle trailing Z (common in API shapes)
    if s.endswith("Z"):
        s = s[:-1]
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    return dt.date().isoformat()


def build_report_content(q: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    q_s = (q or "").strip()
    ev = list(evidence or [])
    bullets = _build_bullets(q_s, ev)
    predictions = _build_predictions(q_s, ev)
    dissent = _build_dissent(q_s, ev)
    return {
        "evidence": ev,
        "bullets": bullets,
        "predictions": predictions,
        "dissent": dissent,
    }


def _build_bullets(q: str, evidence: list[dict[str, Any]]) -> list[str]:
    q_s = (q or "").strip()
    if not evidence:
        bullets_empty = [
            f"No matching articles found for query '{q_s}'.",
            "Evidence-first mode: without evidence, no substantive claims are made.",
            "Next: refine the query (entity + event + timeframe) or re-run after ingestion updates.",
        ]
        return bullets_empty[:5]

    n = len(evidence)
    sources = [str(e.get("source_name") or "Unknown").strip() for e in evidence]
    top_sources = [s for s, _c in Counter([s for s in sources if s]).most_common(3)]
    src_s = ", ".join(top_sources) if top_sources else "Unknown"

    bullets_out: list[str] = [
        f"Found {n} matching article(s) for '{q_s}'.",
        f"Top sources: {src_s}.",
    ]

    # Highlight up to 3 most relevant evidence items (already ranked by DB query).
    for e in evidence[:3]:
        eid = e.get("id")
        title = _short(str(e.get("title") or ""), max_len=140)
        src = _short(str(e.get("source_name") or "Unknown"), max_len=40)
        dt = _iso_date(e.get("published_at"))
        when = f", {dt}" if dt else ""
        if eid is None:
            bullets_out.append(f"{title} — {src}{when}")
        else:
            bullets_out.append(f"[{eid}] {title} — {src}{when}")

    return bullets_out[:5]


def _build_predictions(q: str, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    q_s = (q or "").strip()
    ids = [e.get("id") for e in evidence if isinstance(e.get("id"), int)]
    ids_unique = list(dict.fromkeys(ids))  # stable de-dupe

    def _clamp01(x: float) -> float:
        return max(0.0, min(float(x), 1.0))

    if not evidence:
        # Placeholders that avoid making external-world claims without evidence.
        return [
            {
                "claim": f"It is likely the current dataset does not yet index useful coverage for '{q_s}' (or the query is too broad).",
                "probability": 0.75,
                "horizon": "7d",
                "evidence_ids": [],
            },
            {
                "claim": "Refining the query (specific entity + event + timeframe) will materially improve retrieval quality.",
                "probability": 0.80,
                "horizon": "30d",
                "evidence_ids": [],
            },
            {
                "claim": "Re-running after additional ingestion cycles may surface relevant evidence for this query.",
                "probability": 0.55,
                "horizon": "7d",
                "evidence_ids": [],
            },
        ]

    n = len(evidence)
    source_div = len({str(e.get("source_name") or "").strip() for e in evidence if str(e.get("source_name") or "").strip()})
    p_cycle = _clamp01(0.35 + 0.10 * min(n, 5) + 0.05 * min(source_div, 3))
    p_broaden = _clamp01(0.30 + 0.08 * min(source_div, 5) + 0.04 * min(n, 8))
    p_uncertain = _clamp01(0.65 - 0.05 * min(n, 6))  # more evidence -> less uncertainty

    cite_ids = ids_unique[:8]
    return [
        {
            "claim": f"Additional coverage mentioning '{q_s}' is likely to appear in the dataset.",
            "probability": p_cycle,
            "horizon": "7d",
            "evidence_ids": cite_ids[:5],
        },
        {
            "claim": "Coverage is likely to broaden to at least one additional distinct source.",
            "probability": p_broaden,
            "horizon": "14d",
            "evidence_ids": cite_ids[:8],
        },
        {
            "claim": "Key details may remain uncertain without broader corroboration across sources.",
            "probability": p_uncertain,
            "horizon": "30d",
            "evidence_ids": cite_ids[:5],
        },
    ]


def _build_dissent(q: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    q_s = (q or "").strip()
    if not evidence:
        return {
            "counter_case": f"Relevant evidence for '{q_s}' may exist but was not retrieved due to query/FTS limitations or incomplete indexing; absence of evidence here is not evidence of absence.",
            "evidence": [],
        }
    return {
        "counter_case": "The retrieved evidence may reflect keyword/search bias and incomplete coverage; corroborate across sources and consider synonyms/alternative spellings before drawing strong conclusions.",
        "evidence": [],
    }



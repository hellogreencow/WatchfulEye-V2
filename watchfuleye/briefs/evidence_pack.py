"""Evidence pack builder for Global Brief generation (Phase 6).

The goal is to feed the model a *dense but bounded* representation of what we know,
using:
- Deduped, scored articles from Postgres
- Fulltext excerpts where available (internal use)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import psycopg


@dataclass(frozen=True)
class EvidenceItem:
    source_id: int
    article_id: int
    title: str
    url: str
    source: str
    published_at: Optional[datetime]
    created_at: Optional[datetime]
    trust_score: float
    extraction_confidence: float
    excerpt: str


def _extract_key_numbers(text: str, *, max_items: int = 4) -> List[str]:
    """Pull a few 'key numbers' from text for faster model grounding."""
    if not text:
        return []
    patterns = [
        r"\$\s?\d[\d,]*\.?\d*\s?(?:billion|million|bn|m)?",
        r"\b\d{1,3}(?:\.\d+)?\s?%\b",
        r"\b\d[\d,]*\s?(?:barrels|bpd|tons|tonnes|ships|troops|missiles)\b",
        r"\b\d{4}\b",  # years
    ]
    found: List[str] = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            s = m.group(0).strip()
            if s and s not in found:
                found.append(s)
            if len(found) >= max_items:
                return found
    return found[:max_items]


def fetch_recent_evidence(
    pg_dsn: str,
    *,
    lookback_hours: int = 48,
    limit: int = 80,
    min_trust: float = 0.55,
    bucket: str = "main",
) -> List[Dict[str, Any]]:
    """Fetch candidate articles for evidence pack."""
    with psycopg.connect(pg_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, description, canonical_url, source_name, source_domain,
                       created_at, published_at, excerpt, extracted_text, trust_score, extraction_confidence,
                       quality_score, content_hash
                FROM articles
                WHERE bucket = %s
                  AND trust_score >= %s
                  AND created_at >= now() - (%s || ' hours')::interval
                ORDER BY quality_score DESC, trust_score DESC, created_at DESC
                LIMIT %s
                """,
                (bucket, float(min_trust), int(lookback_hours), int(limit)),
            )
            rows = cur.fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        (
            aid,
            title,
            description,
            url,
            source_name,
            source_domain,
            created_at,
            published_at,
            excerpt,
            extracted_text,
            trust_score,
            extraction_confidence,
            quality_score,
            content_hash,
        ) = row
        out.append(
            {
                "id": int(aid),
                "title": title or "",
                "description": description or "",
                "url": url or "",
                "source": source_name or source_domain or "Unknown",
                "created_at": created_at,
                "published_at": published_at,
                "excerpt": excerpt or "",
                "extracted_text": extracted_text or "",
                "trust_score": float(trust_score or 0.0),
                "extraction_confidence": float(extraction_confidence or 0.0),
                "quality_score": float(quality_score or 0.0),
                "content_hash": content_hash,
            }
        )
    return out


def build_evidence_pack(
    articles: Sequence[Dict[str, Any]],
    *,
    max_items: int = 60,
    max_fulltext_items: int = 12,
    max_fulltext_chars: int = 1200,
    max_excerpt_chars: int = 360,
) -> tuple[List[EvidenceItem], str]:
    """Build evidence items and a prompt-ready evidence pack string."""
    # Dedup by content_hash then url
    seen_hash = set()
    seen_url = set()
    deduped: List[Dict[str, Any]] = []
    for a in articles:
        ch = a.get("content_hash")
        url = (a.get("url") or "").strip()
        if ch and ch in seen_hash:
            continue
        if url and url in seen_url:
            continue
        if ch:
            seen_hash.add(ch)
        if url:
            seen_url.add(url)
        deduped.append(a)
        if len(deduped) >= max_items:
            break

    items: List[EvidenceItem] = []
    lines: List[str] = []
    as_of = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines.append(f"EVIDENCE PACK (as_of={as_of}Z)")
    lines.append("Rules: Use ONLY this evidence. If a detail isn't here, say you don't have it.")
    lines.append("")

    for i, a in enumerate(deduped, 1):
        extracted_text = (a.get("extracted_text") or "").strip()
        excerpt = (a.get("excerpt") or a.get("description") or "").strip()

        # Prefer fulltext for top-N items; else compact excerpt
        use_fulltext = i <= max_fulltext_items and bool(extracted_text)
        if use_fulltext:
            body = extracted_text[:max_fulltext_chars].strip()
        else:
            body = excerpt[:max_excerpt_chars].strip()

        if not body:
            body = (a.get("description") or "")[:max_excerpt_chars].strip()

        key_numbers = _extract_key_numbers(body)
        pn = a.get("published_at")
        cn = a.get("created_at")

        item = EvidenceItem(
            source_id=i,
            article_id=int(a.get("id") or 0),
            title=str(a.get("title") or "").strip(),
            url=str(a.get("url") or "").strip(),
            source=str(a.get("source") or "Unknown").strip(),
            published_at=pn if isinstance(pn, datetime) else None,
            created_at=cn if isinstance(cn, datetime) else None,
            trust_score=float(a.get("trust_score") or 0.0),
            extraction_confidence=float(a.get("extraction_confidence") or 0.0),
            excerpt=body,
        )
        items.append(item)

        # Render card
        ts = item.published_at or item.created_at
        ts_s = ts.astimezone(timezone.utc).isoformat(timespec="seconds") + "Z" if ts else "unknown_time"
        lines.append(f"[{i}] {item.title}")
        lines.append(f"    Source: {item.source} | Time: {ts_s}")
        lines.append(f"    URL: {item.url}")
        lines.append(f"    Trust: {item.trust_score:.2f} | FulltextConf: {item.extraction_confidence:.2f}")
        if key_numbers:
            lines.append(f"    KeyNumbers: {', '.join(key_numbers)}")
        if body:
            lines.append(f"    Excerpt: {body.replace('\\n', ' ')[:max_fulltext_chars]}")
        lines.append("")

    return items, "\n".join(lines)



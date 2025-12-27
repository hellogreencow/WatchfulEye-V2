"""Shared ingestion data types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ArticleCandidate:
    """Normalized candidate article (pre-fulltext).

    Fulltext extraction is handled later; this is the minimal ingest record.
    """

    title: str
    url: str
    published_at: Optional[datetime] = None
    description: Optional[str] = None
    source_name: Optional[str] = None
    source_domain: Optional[str] = None
    ingestion_source: str = "unknown"
    topic: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None



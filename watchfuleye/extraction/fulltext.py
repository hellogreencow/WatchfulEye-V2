"""Fulltext fetch + extraction.

Policy:
- We store fulltext internally for RAG/embeddings.
- UI should only show excerpts + link (handled elsewhere).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests
import trafilatura


@dataclass(frozen=True)
class FulltextResult:
    text: Optional[str]
    confidence: float
    status: str
    error: Optional[str] = None
    method: str = "trafilatura"


def fetch_and_extract(url: str, *, timeout: int = 25) -> FulltextResult:
    if not url:
        return FulltextResult(text=None, confidence=0.0, status="error", error="empty_url")
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "WatchfulEye/2.0"},
            timeout=timeout,
            allow_redirects=True,
        )
        status_code = resp.status_code
        if status_code >= 400:
            return FulltextResult(text=None, confidence=0.0, status=f"http_{status_code}", error=f"http_{status_code}")
        html = resp.text or ""
        if not html.strip():
            return FulltextResult(text=None, confidence=0.0, status="empty", error="empty_html")
        text = trafilatura.extract(html, include_comments=False, include_tables=False)
        if not text:
            return FulltextResult(text=None, confidence=0.0, status="no_extract", error="no_extract")
        # heuristic confidence by length
        n = len(text.strip())
        if n >= 4000:
            conf = 0.95
        elif n >= 1500:
            conf = 0.80
        elif n >= 600:
            conf = 0.55
        else:
            conf = 0.30
        return FulltextResult(text=text.strip(), confidence=conf, status="ok")
    except Exception as e:
        return FulltextResult(text=None, confidence=0.0, status="error", error=str(e))



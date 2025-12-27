"""Ingestors for multiple news sources (free/low-cost).

Phase 2 goal:
- Add RSS + official sources + GDELT discovery
- Keep NewsAPI for breadth
- Normalize into ArticleCandidate for downstream scoring/fulltext.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import feedparser
import requests

from watchfuleye.ingestion.article_types import ArticleCandidate


def _domain(url: str) -> Optional[str]:
    try:
        host = (urlparse(url or "").netloc or "").lower().strip()
        return host or None
    except Exception:
        return None


def _parse_dt(dt: Any) -> Optional[datetime]:
    if not dt:
        return None
    if isinstance(dt, datetime):
        return dt
    s = str(dt).strip()
    if not s:
        return None
    s = s.replace("Z", "+00:00").replace(" ", "T") if " " in s and "T" not in s else s
    try:
        parsed = datetime.fromisoformat(s)
        # Normalize naive to UTC
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


class BaseIngestor:
    name: str = "base"

    def fetch(self, *, limit: int = 100, topic: Optional[str] = None) -> List[ArticleCandidate]:
        raise NotImplementedError


@dataclass(frozen=True)
class NewsAPIIngestor(BaseIngestor):
    api_key: str
    endpoint: str = "https://newsapi.org/v2/everything"

    name: str = "newsapi"

    def fetch(self, *, limit: int = 100, topic: Optional[str] = None, query: Optional[str] = None, days: int = 3) -> List[ArticleCandidate]:
        q = query or topic or "geopolitics OR markets"
        params = {
            "q": q,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(max(limit, 1), 100),
            "from": (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(),
        }
        headers = {"X-Api-Key": self.api_key, "User-Agent": "WatchfulEye/2.0"}
        resp = requests.get(self.endpoint, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json() or {}
        articles = data.get("articles") or []
        out: List[ArticleCandidate] = []
        for a in articles:
            if not isinstance(a, dict):
                continue
            url = a.get("url") or ""
            title = a.get("title") or ""
            if not url or not title:
                continue
            source_name = None
            src = a.get("source")
            if isinstance(src, dict):
                source_name = src.get("name") or None
            out.append(
                ArticleCandidate(
                    title=str(title).strip(),
                    description=(a.get("description") or None),
                    url=str(url).strip(),
                    published_at=_parse_dt(a.get("publishedAt")),
                    source_name=source_name,
                    source_domain=_domain(url),
                    ingestion_source=self.name,
                    topic=topic,
                    raw=a,
                )
            )
        return out


@dataclass(frozen=True)
class RSSIngestor(BaseIngestor):
    """Generic RSS ingestor for a list of feed URLs."""

    feeds: Sequence[Tuple[str, str]]  # (feed_name, feed_url)
    name: str = "rss"

    def fetch(self, *, limit: int = 100, topic: Optional[str] = None) -> List[ArticleCandidate]:
        out: List[ArticleCandidate] = []
        for feed_name, feed_url in self.feeds:
            parsed = feedparser.parse(feed_url)
            for entry in (parsed.entries or [])[: max(0, limit)]:
                link = getattr(entry, "link", None) or (entry.get("link") if isinstance(entry, dict) else None)
                title = getattr(entry, "title", None) or (entry.get("title") if isinstance(entry, dict) else None)
                if not link or not title:
                    continue
                # published / updated are common RSS fields
                published = getattr(entry, "published", None) or getattr(entry, "updated", None) or None
                summary = getattr(entry, "summary", None) or None
                out.append(
                    ArticleCandidate(
                        title=str(title).strip(),
                        description=str(summary).strip()[:500] if isinstance(summary, str) else None,
                        url=str(link).strip(),
                        published_at=_parse_dt(published),
                        source_name=feed_name,
                        source_domain=_domain(str(link)),
                        ingestion_source=self.name,
                        topic=topic,
                        raw=dict(entry) if hasattr(entry, "items") else None,
                    )
                )
                if len(out) >= limit:
                    break
            if len(out) >= limit:
                break
        return out


@dataclass(frozen=True)
class GDELTIngestor(BaseIngestor):
    """GDELT 2.1 doc API ingestor (discovery)."""

    name: str = "gdelt"
    endpoint: str = "https://api.gdeltproject.org/api/v2/doc/doc"

    def fetch(self, *, limit: int = 100, topic: Optional[str] = None, query: Optional[str] = None) -> List[ArticleCandidate]:
        q = query or topic or "geopolitics OR markets"
        params = {
            "query": q,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": min(max(limit, 1), 250),
            "sort": "HybridRel",
        }
        resp = requests.get(
            self.endpoint,
            params=params,
            headers={"User-Agent": "WatchfulEye/2.0"},
            timeout=30,
        )
        resp.raise_for_status()
        try:
            data = resp.json() or {}
        except Exception:
            # GDELT occasionally returns non-JSON (HTML error pages, transient issues).
            return []
        articles = (data.get("articles") or data.get("documents") or [])  # doc API returns 'articles'
        out: List[ArticleCandidate] = []
        for a in articles:
            if not isinstance(a, dict):
                continue
            url = a.get("url") or ""
            title = a.get("title") or ""
            if not url or not title:
                continue
            out.append(
                ArticleCandidate(
                    title=str(title).strip(),
                    description=(a.get("snippet") or a.get("description") or None),
                    url=str(url).strip(),
                    published_at=_parse_dt(a.get("seendate") or a.get("date")),
                    source_name=a.get("sourceCountry") or a.get("domain") or None,
                    source_domain=_domain(url),
                    ingestion_source=self.name,
                    topic=topic,
                    raw=a,
                )
            )
        return out[:limit]


def default_rss_feeds() -> List[Tuple[str, str]]:
    """Curated starter RSS set (can be extended via config later)."""
    return [
        ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
        ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
        ("NPR World", "https://feeds.npr.org/1004/rss.xml"),
        ("The Economist (Free)", "https://www.economist.com/the-world-this-week/rss.xml"),
        ("US Treasury Press", "https://home.treasury.gov/news/press-releases/rss"),
        ("Federal Reserve Press", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ]



"""URL canonicalization helpers for ingestion/dedup."""

from __future__ import annotations

import hashlib
from typing import Iterable, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


DEFAULT_STRIP_QUERY_PARAMS = {
    # tracking
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "utm_name",
    "utm_reader",
    "utm_referrer",
    "utm_pubreferrer",
    "utm_swu",
    # misc common trackers
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "ref_url",
    "source",
    "s",
}


def canonicalize_url(url: str, *, strip_params: Optional[Iterable[str]] = None) -> str:
    """Canonicalize a URL for dedup.

    - Lowercase scheme + hostname
    - Remove fragments
    - Strip common tracking query parameters
    - Preserve order-stable remaining query params
    """
    if not url:
        return ""
    strip = set(strip_params) if strip_params is not None else set(DEFAULT_STRIP_QUERY_PARAMS)
    p = urlparse(url.strip())
    scheme = (p.scheme or "https").lower()
    netloc = (p.netloc or "").lower()
    path = p.path or "/"

    # Normalize query params
    kept = []
    for k, v in parse_qsl(p.query, keep_blank_values=True):
        if k.lower() in strip:
            continue
        kept.append((k, v))
    kept.sort(key=lambda kv: (kv[0].lower(), kv[1]))
    query = urlencode(kept, doseq=True)

    # Remove fragment
    return urlunparse((scheme, netloc, path, "", query, ""))


def url_hash(url: str) -> str:
    """Stable hash for a canonicalized URL."""
    canon = canonicalize_url(url)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()



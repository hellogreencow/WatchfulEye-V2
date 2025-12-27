"""Fulltext fetch + extraction.

Policy:
- We store fulltext internally for RAG/embeddings.
- UI should only show excerpts + link (handled elsewhere).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import ipaddress
import re
from urllib.parse import urlparse

import requests
import trafilatura


@dataclass(frozen=True)
class FulltextResult:
    text: Optional[str]
    confidence: float
    status: str
    error: Optional[str] = None
    method: str = "trafilatura"


_PRIVATE_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_ip_hostname(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
        return True
    except Exception:
        return False


def _is_private_ip(hostname: str) -> bool:
    try:
        ip = ipaddress.ip_address(hostname)
        return any(ip in net for net in _PRIVATE_NETS)
    except Exception:
        return False


def _validate_fetch_url(url: str) -> Optional[str]:
    """Return error string if URL should not be fetched (SSRF/abuse protections)."""
    try:
        p = urlparse(url)
    except Exception:
        return "invalid_url"
    if p.scheme not in ("http", "https"):
        return "bad_scheme"
    if not p.netloc:
        return "missing_host"
    host = (p.hostname or "").strip().lower()
    if not host:
        return "missing_host"
    # Block obvious localhost-like names
    if host in ("localhost", "localhost.localdomain"):
        return "blocked_host"
    # If hostname is an IP, block private/loopback/link-local etc.
    if _is_ip_hostname(host):
        if _is_private_ip(host):
            return "blocked_private_ip"
    return None


def fetch_and_extract(url: str, *, timeout: int = 25, max_bytes: int = 2_000_000) -> FulltextResult:
    if not url:
        return FulltextResult(text=None, confidence=0.0, status="error", error="empty_url")
    err = _validate_fetch_url(url)
    if err:
        return FulltextResult(text=None, confidence=0.0, status="blocked", error=err)
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "WatchfulEye/2.0"},
            timeout=(5, timeout),
            allow_redirects=True,
            stream=True,
        )
        status_code = resp.status_code
        if status_code >= 400:
            return FulltextResult(text=None, confidence=0.0, status=f"http_{status_code}", error=f"http_{status_code}")
        # Size guardrail: read up to max_bytes
        content = b""
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            content += chunk
            if len(content) > max_bytes:
                return FulltextResult(text=None, confidence=0.0, status="too_large", error="too_large")
        try:
            html = content.decode(resp.encoding or "utf-8", errors="replace")
        except Exception:
            html = content.decode("utf-8", errors="replace")
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



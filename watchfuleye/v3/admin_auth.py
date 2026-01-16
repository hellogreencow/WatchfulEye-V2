"""Shared auth helpers for V3 blueprints.

V3 blueprints are auto-registered without touching `web_app.py` (hot file).
Because of that, we cannot import decorators from `web_app.py` without risking
circular imports.

This module implements a minimal, safe auth check:
- Accept Bearer token via `Authorization: Bearer <session_token>`
- Or accept `session_token` cookie (when available)

It validates tokens against the existing SQLite auth tables (`users`, `user_sessions`).
"""

from __future__ import annotations

import os
import sqlite3
from functools import wraps
from typing import Any, Callable

from flask import g, jsonify, request


def get_current_user() -> dict[str, Any] | None:
    """Return the authenticated user dict or None."""
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization") or ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        return None

    db_path = os.environ.get("DB_PATH", "news_bot.db")
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT u.id, u.username, u.email, u.full_name, u.role
                FROM user_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.session_token = ?
                  AND datetime(s.expires_at) > datetime('now')
                  AND u.is_active = TRUE
                """,
                (token,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def require_admin(f: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator: require authenticated admin user."""

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Authentication required"}), 401
        if user.get("role") != "admin":
            return jsonify({"error": "Unauthorized access"}), 403
        g.current_user = user
        return f(*args, **kwargs)

    return decorated


def require_user(f: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator: require any authenticated user (admin or not)."""

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Authentication required"}), 401
        g.current_user = user
        return f(*args, **kwargs)

    return decorated



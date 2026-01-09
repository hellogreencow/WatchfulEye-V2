#!/usr/bin/env python3
"""
Enhanced Flask web application for WatchfulEye Intelligence System.
Features: Security headers, caching, API endpoints, real-time updates, comprehensive monitoring.
"""

from flask import Flask, render_template, jsonify, request, redirect, url_for, session, send_file, g, send_from_directory, Response, stream_with_context
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_compress import Compress
from flask_cors import CORS
import logging
import json
import re
from datetime import datetime, timedelta, timezone
from database import NewsDatabase, DatabaseError
import os
from functools import wraps
import hashlib
import secrets
from typing import Dict, List, Optional, Any, Tuple, Set
import time
import pandas as pd
import io
import csv
import sqlite3
import openai
import requests
from flask import current_app
import math
import psycopg
import psutil  # For load shedding protection
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

try:
    # Optional import; used by admin endpoint
    from chimera_prism_engine import PrismEngine
except Exception:
    PrismEngine = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------
# JSON repair helper
# ----------------------------
def _try_parse_json(raw: str):
    try:
        return json.loads(raw)
    except Exception:
        return None

def _repair_json_text(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith('```'):
        cleaned = cleaned.strip('`')
        if cleaned.lower().startswith('json'):
            cleaned = cleaned[4:].strip()
    # remove trailing commas before ] or }
    cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
    # ensure balanced braces/brackets
    open_braces = cleaned.count('{'); close_braces = cleaned.count('}')
    open_brackets = cleaned.count('['); close_brackets = cleaned.count(']')
    if close_braces < open_braces:
        cleaned = cleaned + ('}' * (open_braces - close_braces))
    if close_brackets < open_brackets:
        cleaned = cleaned + (']' * (open_brackets - close_brackets))
    return cleaned

def _salvage_json_text(raw: str):
    cleaned = _repair_json_text(raw)
    # Try iterative truncation at last comma to drop incomplete tail
    for _ in range(30):
        try:
            return json.loads(cleaned)
        except Exception:
            idx = cleaned.rfind(',')
            if idx == -1:
                break
            cleaned = cleaned[:idx]
            # re-close braces/brackets after truncation
            open_braces = cleaned.count('{'); close_braces = cleaned.count('}')
            open_brackets = cleaned.count('['); close_brackets = cleaned.count(']')
            if close_braces < open_braces:
                cleaned = cleaned + ('}' * (open_braces - close_braces))
            if close_brackets < open_brackets:
                cleaned = cleaned + (']' * (open_brackets - close_brackets))
    return None


def _parse_external_bool(value: Any, default: bool = False) -> bool:
    """Parse truthy query parameters safely."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _parse_json_field(value: Any) -> Any:
    """Best-effort JSON parsing for stringified fields."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _extract_final_intel(raw_response: Any) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Extract the best available summary and final_intel block from the raw response payload.
    Returns (summary, final_intel_section, full_raw_json).
    """
    summary = None
    final_intel = None
    parsed = None

    if not raw_response:
        return summary, final_intel, parsed

    try:
        parsed = raw_response if isinstance(raw_response, dict) else json.loads(raw_response)
    except Exception:
        logger.debug("Failed to parse raw_response_json for external API", exc_info=True)
        return summary, final_intel, parsed

    candidate_keys = [
        'final_intel',
        'final_intelligence',
        'final_analysis',
        'final_brief',
        'intel'
    ]

    for key in candidate_keys:
        if isinstance(parsed.get(key), dict):
            final_intel = parsed[key]
            break

    if final_intel:
        summary = final_intel.get('summary') or final_intel.get('overall_summary') or final_intel.get('headline')

    if not summary:
        summary = parsed.get('summary') or parsed.get('overall_summary')

    return summary, final_intel, parsed


def _format_analysis_for_external(analysis: Dict[str, Any], include_raw: bool = False) -> Dict[str, Any]:
    """Map an analysis row to the compact external payload structure."""
    summary, final_intel, raw_json = _extract_final_intel(analysis.get('raw_response_json'))
    if not summary:
        preview = analysis.get('content_preview') or (analysis.get('content') or '')
        if isinstance(preview, str):
            summary = preview[:500] + ('…' if len(preview) > 500 else '')
        else:
            summary = str(preview)

    formatted: Dict[str, Any] = {
        'id': analysis.get('id'),
        'created_at': analysis.get('created_at'),
        'article_count': analysis.get('article_count'),
        'quality_score': analysis.get('quality_score'),
        'summary': summary,
        'sentiment_summary': _parse_json_field(analysis.get('sentiment_summary')),
        'category_breakdown': _parse_json_field(analysis.get('category_breakdown')),
    }

    if include_raw:
        formatted['final_intel'] = final_intel
        formatted['raw_response'] = raw_json

    return formatted

# Load configuration from environment variables with fallbacks
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', 'your_telegram_bot_token_here')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', 'your_chat_id_here')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', 'your_openai_api_key_here')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
OPENROUTER_MODEL = os.environ.get('OPENROUTER_MODEL', 'anthropic/claude-3.5-sonnet')
# Optional model for political perspectives (Perplexity Sonar)
PERSPECTIVES_MODEL = os.environ.get('PERSPECTIVES_MODEL', 'perplexity/sonar')
EXTERNAL_INTEL_API_KEYS = [
    key.strip() for key in os.environ.get('EXTERNAL_INTEL_API_KEYS', '').split(',')
    if key.strip()
]

# Tool definitions - only RAG since web search is the Perplexity model itself
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_rag",
            "description": "Search WatchfulEye's intelligence database of 40,000+ financial articles for relevant context. Use when the user asks about specific companies, events, or topics that benefit from historical context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant articles"
                    },
                    "timeframe": {
                        "type": "string",
                        "enum": ["2d", "7d", "30d"],
                        "description": "Optional time window: 2d (recent), 7d (week), 30d (month)"
                    }
                },
                "required": ["query"]
            }
        }
    }
]
# voyage-3-large support for embeddings (RAG)
VOYAGE_API_KEY = os.environ.get('VOYAGE_API_KEY', '')
EMBEDDINGS_PROVIDER = os.environ.get('EMBEDDINGS_PROVIDER', 'voyage' if VOYAGE_API_KEY else 'openai').lower()
# allow disabling semantic vector search entirely (e.g., if Postgres/pgvector not available)
DISABLE_SEMANTIC = os.environ.get('DISABLE_SEMANTIC', 'false').lower() == 'true'

# Supabase-only mode (no direct Postgres credentials required)
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
USE_SUPABASE_ONLY = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)
supabase_client = None
if USE_SUPABASE_ONLY:
    try:
        from supabase import create_client
        supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    except Exception as _sup_e:
        supabase_client = None
# Fallback model list to improve resilience if the primary model is unavailable/blocked
OPENROUTER_FALLBACK_MODELS = [
    OPENROUTER_MODEL,
    'openai/gpt-4o-mini',
    'deepseek/deepseek-chat-v3-0324',
    'anthropic/claude-3.5-sonnet'
]
DB_PATH = os.environ.get('DB_PATH', 'news_bot.db')
# Prefer Supabase-managed Postgres if available
_SUPA_URL = os.environ.get('SUPABASE_URL')
_SUPA_HOST = None
if _SUPA_URL:
    try:
        _SUPA_HOST = _SUPA_URL.split('https://',1)[1].split('.',1)[0]
    except Exception:
        _SUPA_HOST = None

# If a Supabase DB is configured, default PG_DSN to its host (password may be managed via platform)
PG_DSN = os.environ.get(
    'PG_DSN',
    f"host=db.{_SUPA_HOST}.supabase.co port=5432 dbname=postgres user=postgres sslmode=require" if _SUPA_HOST else 'dbname=watchfuleye user=watchful password=watchfulpass host=localhost port=5432'
)

# Initialize Flask app with security configurations
from cors_config import configure_cors

app = Flask(__name__, static_folder="frontend/build/static")
# Configure app to trust proxy headers (nginx forwards X-Forwarded-Proto, etc.)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app = configure_cors(app)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
app.config['DB_PATH'] = DB_PATH

# Security configurations
# ProxyFix middleware allows Flask to detect HTTPS from X-Forwarded-Proto header
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initialize extensions
cache = Cache(app, config={'CACHE_TYPE': 'simple', 'CACHE_DEFAULT_TIMEOUT': 300})
compress = Compress(app)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per day", "100 per hour"],  # Adjusted for launch traffic
    storage_uri="memory://"
)
limiter.init_app(app)

# Initialize database
db = NewsDatabase(db_path=DB_PATH)
try:
    # Postgres-backed article access (Phase 4: hybrid search + better news display)
    from watchfuleye.storage.postgres_articles import PostgresArticleStore
    _pg_articles = PostgresArticleStore(PG_DSN)
except Exception:
    _pg_articles = None
try:
    # Postgres-backed analyses (Global Briefs) (Phase 6)
    from watchfuleye.storage.postgres_analyses import PostgresAnalysesStore
    _pg_analyses = PostgresAnalysesStore(PG_DSN)
except Exception:
    _pg_analyses = None

# =====================
# Load Shedding Protection
# =====================
LOAD_SHEDDING_ENABLED = os.environ.get('ENABLE_LOAD_SHEDDING', 'true').lower() != 'false'
LOAD_SHEDDING_CPU_THRESHOLD = int(os.environ.get('LOAD_SHEDDING_CPU_THRESHOLD', '95'))
LOAD_SHEDDING_COOLDOWN_SECONDS = int(os.environ.get('LOAD_SHEDDING_COOLDOWN_SECONDS', '5'))
LOAD_SHEDDING_EXEMPT_PATHS = {
    '/api/health',
    '/api/auth/login',
    '/api/auth/logout',
    '/api/auth/me',
    '/api/auth/register',
    '/api/auth/csrf-token',
    '/api/auth/check-username',
}
LOAD_SHEDDING_EXEMPT_PREFIXES = (
    '/static/',
    '/frontend/',
    '/assets/',
)
_load_shedding_state = {'last_trigger': 0.0}


def _is_exempt_from_load_shedding(path: str) -> bool:
    if path in LOAD_SHEDDING_EXEMPT_PATHS:
        return True
    if any(path.startswith(prefix) for prefix in LOAD_SHEDDING_EXEMPT_PREFIXES):
        return True
    if path.startswith('/api/auth/'):
        return True
    return False


@app.before_request
def check_server_load():
    """Shed load if server is overloaded, but keep critical auth endpoints available."""
    if not LOAD_SHEDDING_ENABLED:
        return None
    # Allow idempotent reads to continue even under stress so dashboard stays usable
    if request.method == 'GET':
        return None
    if request.method == 'OPTIONS':
        return None
    if _is_exempt_from_load_shedding(request.path):
        return None
    
    try:
        # Non-blocking CPU check (interval=0)
        cpu_percent = psutil.cpu_percent(interval=0)
        if cpu_percent >= LOAD_SHEDDING_CPU_THRESHOLD:
            now = time.time()
            last_trigger = _load_shedding_state['last_trigger']
            if now - last_trigger < LOAD_SHEDDING_COOLDOWN_SECONDS:
                logger.warning(f"[LOAD SHEDDING] CPU at {cpu_percent:.1f}% (cooldown hit)")
                return jsonify({
                    'error': 'Server under high load',
                    'message': 'Please retry in 30 seconds',
                    'cpu_percent': cpu_percent
                }), 503
            _load_shedding_state['last_trigger'] = now
            logger.warning(f"[LOAD SHEDDING] CPU at {cpu_percent:.1f}% (triggered)")
            return jsonify({
                'error': 'Server under high load',
                'message': 'Please retry in 30 seconds',
                'cpu_percent': cpu_percent
            }), 503
    except Exception as e:
        logger.error(f"Load check error: {e}")
    
    return None

# =====================
# Vector DB init (pgvector)
# =====================
def _init_postgres_schema():
    """Initialize Postgres schema (tables + pgvector + FTS) for WatchfulEye."""
    try:
        # Local import to avoid hard dependency during environments that don't ship the package.
        from watchfuleye.storage.postgres_schema import ensure_postgres_schema
        ensure_postgres_schema(PG_DSN)
        logger.info("Postgres schema ready")
    except Exception as e:
        logger.error(f"Postgres schema init failed: {e}")

# In Supabase-only mode we typically do not have direct Postgres credentials (password),
# and semantic search is executed via Supabase RPC functions instead.
if not USE_SUPABASE_ONLY:
    _init_postgres_schema()
else:
    logger.info("Supabase-only mode enabled; skipping direct pgvector init")

# =====================
# SQLite FTS5 init for BM25-style lexical search
# =====================
def _init_sqlite_fts() -> None:
    try:
        with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as conn:
            cur = conn.cursor()
            # Determine which columns exist in the articles table to avoid FTS init failures
            try:
                cur.execute("PRAGMA table_info(articles)")
                cols = {r[1] for r in cur.fetchall()}
            except Exception:
                cols = set()

            # Prefer indexing content if the column exists (new schema), otherwise omit it
            fts_columns = ["title", "description", "category", "sentiment_analysis_text"]
            has_content = "content" in cols
            if has_content:
                fts_columns.append("content")
            fts_cols_sql = ", ".join(fts_columns)

            # Create FTS5 table linked to articles
            cur.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                    {fts_cols_sql},
                    content='articles', content_rowid='id'
                );
                """
            )

            # Avoid doing a full 100k-row backfill at import time.
            # We only auto-populate if the corpus is small; otherwise rely on triggers + admin endpoint.
            cur.execute("SELECT COUNT(*) FROM articles")
            total_articles = int(cur.fetchone()[0] or 0)
            auto_populate_max = int(os.environ.get("FTS_AUTO_POPULATE_MAX", "25000"))

            cur.execute("SELECT (SELECT count(*) FROM articles_fts) = 0")
            is_empty = cur.fetchone()[0] == 1
            if is_empty and total_articles > 0 and total_articles <= auto_populate_max:
                # Build column lists for insert/select dynamically
                insert_cols = ["rowid"] + fts_columns
                insert_sql_cols = ", ".join(insert_cols)
                select_exprs = ["id"] + [f"IFNULL({c},'')" for c in fts_columns]
                select_sql = ", ".join(select_exprs)
                cur.execute(
                    f"INSERT INTO articles_fts({insert_sql_cols}) SELECT {select_sql} FROM articles"
                )
                logger.info(f"FTS auto-populated for {total_articles} articles (<= {auto_populate_max})")
            elif is_empty and total_articles > auto_populate_max:
                logger.info(
                    f"FTS table empty; skipping auto-populate for {total_articles} articles (> {auto_populate_max}). "
                    "Use /api/admin/reindex-fts to backfill in batches."
                )

            # Triggers to keep in sync
            insert_cols = ["rowid"] + fts_columns
            insert_sql_cols = ", ".join(insert_cols)
            insert_values = ["new.id"] + [f"IFNULL(new.{c},'')" for c in fts_columns]
            insert_sql_vals = ", ".join(insert_values)

            update_insert_sql = f"INSERT INTO articles_fts({insert_sql_cols}) VALUES ({insert_sql_vals});"

            trigger_sql = f"""
                CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
                  {update_insert_sql}
                END;
                CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
                  INSERT INTO articles_fts(articles_fts, rowid) VALUES('delete', old.id);
                END;
                CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
                  INSERT INTO articles_fts(articles_fts, rowid) VALUES('delete', old.id);
                  {update_insert_sql}
                END;
            """
            cur.executescript(trigger_sql)
            conn.commit()
    except Exception as e:
        logger.warning(f"FTS5 init failed or unavailable: {e}")

_init_sqlite_fts()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _embed_text_openai(text: str) -> list:
    import openai as _openai
    # Prefer text-embedding-3-small (1536 dims) for cost/perf; switch if needed.
    resp = _openai.embeddings.create(model="text-embedding-3-small", input=text[:8000])
    return resp.data[0].embedding

def _embed_text_voyage(text: str) -> list:
    """Embed with voyage-3-large (1024 dims) when configured."""
    if not VOYAGE_API_KEY:
        raise RuntimeError("VOYAGE_API_KEY not configured")
    import voyageai as _voy
    client = _voy.Client(api_key=VOYAGE_API_KEY)
    res = client.embed(texts=[text[:8000]], model="voyage-3-large")
    return res.embeddings[0]

def _embed_text(text: str) -> list:
    """Provider-aware embed with fallback to OpenAI if voyage fails."""
    if EMBEDDINGS_PROVIDER == 'voyage' and VOYAGE_API_KEY:
        try:
            return _embed_text_voyage(text)
        except Exception as e:
            logger.warning(f"voyage embed failed, falling back to OpenAI: {e}")
    return _embed_text_openai(text)

def _vector_literal(vec: list) -> str:
    """Format a Python embedding list into pgvector textual literal."""
    try:
        return "[" + ",".join(f"{float(x):.6f}" for x in (vec or [])) + "]"
    except Exception:
        # last resort: stringify; pgvector accepts bracketed floats
        return "[" + ",".join(str(x) for x in (vec or [])) + "]"

def _get_or_create_article_embedding(article: dict) -> list:
    try:
        if USE_SUPABASE_ONLY and supabase_client:
            table = 'article_embeddings_voyage' if EMBEDDINGS_PROVIDER == 'voyage' and VOYAGE_API_KEY else 'article_embeddings'
            # read
            existing = supabase_client.table(table).select('embedding').eq('article_id', article['id']).limit(1).execute()
            if existing and getattr(existing, 'data', None):
                emb = existing.data[0].get('embedding')
                if emb:
                    return list(emb)
            # embed and upsert
            # Prefer fulltext for embeddings (Phase 5): extracted_text > excerpt > title/description
            fulltext = (article.get('extracted_text') or article.get('content') or article.get('excerpt') or '') or ''
            header = f"{article.get('title','')}. {article.get('description','') or ''}".strip()
            if fulltext:
                text = (header + "\n\n" + str(fulltext)) if header else str(fulltext)
            else:
                text = header
            vec = _embed_text(text)
            supabase_client.table(table).upsert({
                'article_id': article['id'],
                'embedding': vec
            }).execute()
            return vec
        with psycopg.connect(PG_DSN) as conn:
            with conn.cursor() as cur:
                table = 'article_embeddings_voyage' if EMBEDDINGS_PROVIDER == 'voyage' and VOYAGE_API_KEY else 'article_embeddings'
                cur.execute(f"SELECT embedding FROM {table} WHERE article_id=%s", (article['id'],))
                row = cur.fetchone()
                if row and row[0] is not None:
                    emb = row[0]
                    if isinstance(emb, list):
                        return emb
                    if isinstance(emb, str):
                        s = emb.strip().strip('[]')
                        if not s:
                            return []
                        try:
                            return [float(x) for x in s.split(',') if x.strip()]
                        except Exception:
                            return []
                    return []
        # Build text block for embedding
        fulltext = (article.get('extracted_text') or article.get('content') or article.get('excerpt') or '') or ''
        header = f"{article.get('title','')}. {article.get('description','') or ''}".strip()
        if fulltext:
            text = (header + "\n\n" + str(fulltext)) if header else str(fulltext)
        else:
            text = header
        vec = _embed_text(text)
        vec_lit = _vector_literal(vec)
        with psycopg.connect(PG_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                table = 'article_embeddings_voyage' if EMBEDDINGS_PROVIDER == 'voyage' and VOYAGE_API_KEY else 'article_embeddings'
                cur.execute(
                    f"INSERT INTO {table}(article_id, embedding) VALUES (%s, %s::vector) "
                    f"ON CONFLICT (article_id) DO UPDATE SET embedding = EXCLUDED.embedding",
                    (article['id'], vec_lit)
                )
        return vec
    except Exception as e:
        logger.error(f"embedding error for article {article.get('id')}: {e}")
        return []

def _semantic_candidates(query: str, limit: int = 12) -> List[int]:
    try:
        qvec = _embed_text(query)
        qlit = _vector_literal(qvec)
        table = 'article_embeddings_voyage' if EMBEDDINGS_PROVIDER == 'voyage' and VOYAGE_API_KEY else 'article_embeddings'
        if USE_SUPABASE_ONLY and supabase_client and table == 'article_embeddings_voyage':
            res = supabase_client.rpc('semantic_candidates_voyage', {
                'q': qvec,
                'limit_k': limit
            }).execute()
            return [int(r['article_id']) for r in (res.data or [])]
        with psycopg.connect(PG_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT article_id
                    FROM {table}
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (qlit, limit)
                )
                return [r[0] for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"semantic search failed: {e}")
        return []

def _pgvector_count() -> int:
    try:
        table = 'article_embeddings_voyage' if EMBEDDINGS_PROVIDER == 'voyage' and VOYAGE_API_KEY else 'article_embeddings'
        if USE_SUPABASE_ONLY and supabase_client:
            result = supabase_client.table(table).select('article_id', count='exact').limit(1).execute()
            return result.count or 0
        with psycopg.connect(PG_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                return int(cur.fetchone()[0])
    except Exception:
        return 0

def _seed_article_embeddings(max_items: int = 50):
    try:
        # Prefer seeding from Postgres articles table (new ingestion pipeline).
        try:
            with psycopg.connect(PG_DSN) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, title, description, excerpt, extracted_text
                        FROM articles
                        WHERE bucket = 'main'
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (max_items,),
                    )
                    rows = cur.fetchall()
                    for (aid, title, desc, excerpt, extracted_text) in rows:
                        _get_or_create_article_embedding(
                            {
                                'id': int(aid),
                                'title': title,
                                'description': desc,
                                'excerpt': excerpt,
                                'extracted_text': extracted_text,
                            }
                        )
                    return
        except Exception:
            pass

        # Fallback: legacy SQLite
        with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT id, title, description, sentiment_analysis_text FROM articles ORDER BY created_at DESC LIMIT ?", (max_items,))
            rows = cur.fetchall()
            for row in rows:
                _get_or_create_article_embedding({
                    'id': row['id'],
                    'title': row['title'],
                    'description': row['description'],
                    'excerpt': row['sentiment_analysis_text'] if 'sentiment_analysis_text' in row.keys() else None
                })
    except Exception as e:
        logger.warning(f"embedding seed failed: {e}")

def _fts_query_rows(query: str, limit: int = 50, days: int = 0) -> List[sqlite3.Row]:
    try:
        with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            time_filter = "" if days <= 0 else " AND a.created_at >= strftime('%Y-%m-%dT%H:%M:%f', 'now', ?)"
            params: List[Any] = []
            # Robust normalization for FTS MATCH
            # - Normalize curly quotes to ASCII
            # - Replace single and double quotes with spaces to avoid MATCH syntax errors
            # - Tokenize to words and join with AND for safer MATCH semantics
            q_norm = (query or "").strip()
            q_norm = q_norm.replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"').replace('\u201d', '"')
            q_norm = q_norm.replace("'", ' ').replace('"', ' ')
            tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]{1,}", q_norm.lower())
            if tokens:
                q = ' AND '.join(tokens)
            else:
                q = ''
            sql = (
                "SELECT a.*, bm25(articles_fts) AS bm25_score "
                "FROM articles_fts JOIN articles a ON a.id = articles_fts.rowid "
                "WHERE articles_fts MATCH ?" + time_filter + " ORDER BY bm25(articles_fts) LIMIT ?"
            )
            params.append(q)
            if days > 0:
                params.append(f"-{days} days")
            params.append(limit)
            try:
                cur.execute(sql, params)
            except Exception:
                # If MATCH still fails, return empty to allow vector-only path
                return []
            return cur.fetchall()
    except Exception as e:
        logger.warning(f"FTS query failed: {e}")
        return []

def _source_authority_boost(source: str) -> float:
    if not source:
        return 0.0
    s = source.lower()
    high = ['reuters','ap','associated press','bloomberg','wsj','wall street journal','bbc','ft','financial times','nytimes','the new york times','al jazeera','npr','the guardian','economist']
    med = ['cnn','abc','cbs','nbc','the verge','techcrunch','independent','time','axios','politico','washington post','the washington post','fox']
    if any(h in s for h in high):
        return 1.0
    if any(m in s for m in med):
        return 0.6
    return 0.0

def _best_snippet(article: sqlite3.Row, query: str) -> str:
    # Heuristic snippet extraction: pick the sentence with most query term overlap
    blob = (article.get('content') if isinstance(article, dict) else article['content']) if 'content' in article.keys() else ''
    if not blob:
        blob = (article.get('description') if isinstance(article, dict) else article['description']) or ''
    text = (blob or '').strip()
    if not text:
        return ''
    # Split into rough sentences
    parts = re.split(r'(?<=[.!?])\s+', text)
    q_terms = set(t.lower() for t in re.findall(r"[a-zA-Z0-9']{3,}", query))
    best = ''
    best_score = -1
    for p in parts[:10]:
        terms = set(t.lower() for t in re.findall(r"[a-zA-Z0-9']{3,}", p))
        overlap = len(q_terms & terms)
        score = overlap / (1 + len(p))
        if score > best_score:
            best = p
            best_score = score
    return best[:300]

def _hybrid_retrieve(user_message: str, tf: Optional[str], fallback_terms: List[str], limit: int = 12) -> List[sqlite3.Row]:
    # Determine timeframe days
    timeframe_map = {'2d': 2, '7d': 7, '30d': 30}
    days = timeframe_map.get(tf, 0)
    # candidates from semantic and FTS
    semantic_ids: List[int] = []
    if not DISABLE_SEMANTIC and _pgvector_count() == 0:
        _seed_article_embeddings(200)
    semantic_ids = []
    if not DISABLE_SEMANTIC:
        try:
            semantic_ids = _semantic_candidates(user_message, limit=60)
        except Exception:
            semantic_ids = []
    fts_rows = _fts_query_rows(user_message, limit=60, days=days)
    # Build candidate id set
    id_to_feats: Dict[int, Dict[str, Any]] = {}
    for rank, aid in enumerate(semantic_ids):
        id_to_feats.setdefault(aid, {})['sem_rank'] = rank
    for r in fts_rows:
        id_to_feats.setdefault(int(r['id']), {})['bm25'] = float(r['bm25_score']) if 'bm25_score' in r.keys() else 0.0
    # Fetch rows
    if not id_to_feats:
        # fallback: widen timeframe and run basic recency search
        return []
    with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as conn2:
        conn2.row_factory = sqlite3.Row
        cur2 = conn2.cursor()
        ids = list(id_to_feats.keys())
        placeholders = ','.join(['?'] * len(ids))
        cur2.execute(f"SELECT * FROM articles WHERE id IN ({placeholders})", ids)
        rows = cur2.fetchall()
    # Score fusion
    def sem_score(rank: Optional[int]) -> float:
        return 0.0 if rank is None else 1.0 / (1.0 + rank)
    scored: List[Tuple[float, sqlite3.Row]] = []
    for row in rows:
        feats = id_to_feats.get(int(row['id']), {})
        s_sem = sem_score(feats.get('sem_rank'))
        bm25 = feats.get('bm25', 0.0)
        # normalize bm25 to [0,1] roughly
        s_bm = 1.0 / (1.0 + max(0.0, bm25)) if bm25 else 0.0
        # recency from age in days
        try:
            cur_dt = datetime.utcnow()
            age_days = max(0.0, (cur_dt - datetime.fromisoformat((row['created_at'] or '')[:19])).days if row['created_at'] else 999)
        except Exception:
            age_days = 30.0
        s_rec = math.exp(-age_days / 7.0)  # 1 week half-life
        s_src = _source_authority_boost(row['source'] or '') * 0.5
        fused = 0.45 * s_sem + 0.3 * s_bm + 0.2 * s_rec + 0.05 * s_src
        scored.append((fused, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:limit]]

# Background embedding daemon removed - embeddings managed via manual reindex endpoint

# Redundant CORS instance removed; configuration happens in cors_config.configure_cors

# Chimera is deprecated/disabled by default. Keep optional behind a hard flag.
ENABLE_CHIMERA = os.environ.get('ENABLE_CHIMERA', 'false').lower() == 'true'
if ENABLE_CHIMERA:
    try:
        from chimera_api import init_chimera_api
        init_chimera_api(app)
        logger.info("Chimera API initialized successfully")
    except ImportError as e:
        logger.warning(f"Chimera API not available: {e}")
    except Exception as e:
        logger.error(f"Failed to initialize Chimera API: {e}")
else:
    logger.info("Chimera API disabled (ENABLE_CHIMERA=false)")

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

# Authentication middleware
def login_required(f):
    """Decorator to require authentication for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Accept either Bearer token header or httpOnly session cookie
        token = None
        user = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]
            try:
                user = db.validate_session(token)
            except Exception:
                user = None
        # If header missing or invalid, try cookie-based token
        if not user:
            cookie_token = request.cookies.get('session_token')
            if cookie_token:
                try:
                    user = db.validate_session(cookie_token)
                except Exception:
                    user = None
        if user:
            session['user_id'] = user['id']  # Set session for compatibility
            session['username'] = user['username']
            return f(*args, **kwargs)
        
        # Fall back to session check
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function
def get_current_user():
    """Get current user from session token (cookie or header)"""
    # Try to get token from cookie first (secure method)
    token = request.cookies.get('session_token')

    # Fallback to Authorization header for API compatibility
    if not token:
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Remove 'Bearer ' prefix

    if token:
        user = db.validate_session(token)
        if user:
            # Add profile picture to user data
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT preference_value FROM user_preferences
                        WHERE user_id = ? AND preference_key = 'profile_picture'
                    ''', (user['id'],))
                    result = cursor.fetchone()
                    if result:
                        user['profile_picture'] = result['preference_value']
            except Exception as e:
                logger.error(f"Error fetching profile picture: {e}")
        return user
    return None

def generate_csrf_token():
    """Generate a CSRF token for the current session"""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    return session['csrf_token']

def validate_csrf_token():
    """Validate CSRF token from request"""
    token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
    session_token = session.get('csrf_token')

    # Debug logging
    logger.debug(f"CSRF Validation - Token: {token[:20] if token else 'None'}...")
    logger.debug(f"CSRF Validation - Session: {session_token[:20] if session_token else 'None'}...")
    logger.debug(f"CSRF Validation - Origin: {request.headers.get('Origin')}")
    logger.debug(f"CSRF Validation - Referer: {request.headers.get('Referer')}")

    result = token and session_token and token == session_token
    logger.debug(f"CSRF Validation - Result: {result}")

    return result

def _fix_character_encoding_web(text):
    """Fix common UTF-8 encoding issues in AI responses"""
    if not text:
        return text
    
    # Fix common encoding issues
    replacements = {
        'â€"': '–',  # en-dash
        'â€™': "'",  # right single quotation mark
        'â€œ': '"',  # left double quotation mark  
        'â€': '"',   # right double quotation mark
        'â€¢': '•',  # bullet point
        'â€¦': '…',  # horizontal ellipsis
        'â': '-',    # fallback for any remaining â characters
        '\u0080\u0091': '-',  # Unicode en-dash sequence
        '\u0080\u0093': '-',  # Unicode em-dash sequence
        '\u0080\u0092': "'",  # Unicode right single quote
        '\u0080\u0094': '"',  # Unicode left double quote
        '\u0080\u009d': '"',  # Unicode right double quote
        '\u0080\u0099': "'",  # Unicode right single quote variant
        '\u0080\u0098': "'",  # Unicode left single quote variant
        '\u0080\u009c': '"',  # Unicode left double quote variant
        '-¯': '-',   # Broken dash variants
        '--': '-',   # Double dash to single
        'adâhoc': 'ad-hoc',  # Specific broken terms
        'decisionâmaking': 'decision-making',
        'longâterm': 'long-term',
        'president-s': "president's",
        # WTF Currency symbols that shouldn't be there
        '-¥': '$',   # Broken yen to dollar
        '¥': '$',    # Yen to dollar
        '-¤': '',    # Remove broken currency symbol
        '¤': '',     # Remove generic currency symbol
        'article-s': "article's",
        'administration-s': "administration's",
        'president-s': "president's",
        'company-s': "company's",
        'market-s': "market's",
        'sector-s': "sector's",
    }
    
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    
    # Aggressive regex fixes for remaining issues
    import re
    # Fix any remaining broken possessives (word + Unicode garbage + 's')
    text = re.sub(r'(\w+)-[\u0080-\u009f]+s\b', r"\1's", text)
    # Fix any remaining currency symbols to dollars
    text = re.sub(r'[-]?[¥¤€£]', '$', text)
    # Fix any remaining Unicode dash sequences (but not in quotes)
    text = re.sub(r'[\u0080-\u009f]+', '-', text)
    # Clean up any double quotes that got mangled
    text = re.sub(r'-"', ' "', text)
    text = re.sub(r'"-', '" ', text)
    
    return text

# ==============================================================================
# Generate political perspectives on demand (optionally using Perplexity Sonar)
# ==============================================================================
@app.route('/api/perspectives', methods=['POST'])
@limiter.limit("20 per minute")
def generate_perspectives():
    try:
        data = request.json or {}
        title = data.get('title', '')
        description = data.get('description', '')
        source = data.get('source', '')
        category = data.get('category', '')
        targets = data.get('targets', ['democrat', 'republican', 'independent'])

        if not title or not description:
            return jsonify({'success': False, 'error': 'title and description required'}), 400

        # Resolve OpenRouter key the same way as main analysis
        explicit_key = request.headers.get('X-OpenRouter-Key', '').strip()
        auth_header = request.headers.get('Authorization', '')
        if explicit_key:
            effective_key = explicit_key
        elif auth_header.lower().startswith('bearer sk-') or auth_header.lower().startswith('bearer or-'):
            effective_key = auth_header.split(' ', 1)[1].strip()
        else:
            effective_key = OPENROUTER_API_KEY

        if not effective_key:
            return jsonify({'success': False, 'error': 'OpenRouter key missing'}), 500

        origin = request.headers.get('Origin') or request.headers.get('Referer') or "http://localhost:3000"
        headers = {
            "Authorization": f"Bearer {effective_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": origin,
            "X-Title": "WatchfulEye Dev"
        }

        prompt = (
            "Return ONLY a JSON object containing any of the keys democrat, republican, independent.\n"
            "For each present key, provide 3-5 concise, neutral bullets of likely talking points.\n\n"
            f"ARTICLE:\nTitle: {title}\nDescription: {description}\nSource: {source}\nCategory: {category}\n"
            f"Requested: {', '.join(targets)}\n"
            "Example: {\"democrat\":[\"...\"],\"republican\":[\"...\"],\"independent\":[\"...\"]}"
        )

        openrouter_response = None
        last_status = None
        last_text = None
        for model_name in OPENROUTER_FALLBACK_MODELS:
            try:
                openrouter_response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": "You produce concise, neutral talking-point bullets."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 300,
                        "temperature": 0.3
                    },
                    timeout=30
                )
                last_status = openrouter_response.status_code
                last_text = openrouter_response.text
                if openrouter_response.status_code == 200:
                    break
                if openrouter_response.status_code in (402, 403, 429, 500):
                    continue
                else:
                    break
            except requests.exceptions.RequestException as req_err:
                logger.warning(f"perspectives request error for model {model_name}: {req_err}")
                continue

        if openrouter_response is None or openrouter_response.status_code != 200:
            return jsonify({'success': False, 'error': f'Upstream {last_status}', 'body': last_text}), 502

        result = openrouter_response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        parsed = _try_parse_json(content) or _try_parse_json(_repair_json_text(content)) or _salvage_json_text(content)
        if not isinstance(parsed, dict):
            return jsonify({'success': False, 'error': 'Parse failed', 'raw': content}), 500

        # Apply character encoding fixes to all perspective values
        out = {}
        for k, v in parsed.items():
            if k in targets:
                if isinstance(v, list):
                    out[k] = [_fix_character_encoding_web(item) if isinstance(item, str) else item for item in v]
                else:
                    out[k] = _fix_character_encoding_web(v) if isinstance(v, str) else v
        return jsonify({'success': True, 'perspectives': out})
    except Exception as e:
        logger.error(f"perspectives error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Streaming variant for perspectives (single configured model, SSE)
@app.route('/api/perspectives/stream', methods=['POST'])
@limiter.limit("20 per minute")
def generate_perspectives_stream():
    try:
        data = request.json or {}
        title = data.get('title', '')
        description = data.get('description', '')
        source = data.get('source', '')
        category = data.get('category', '')
        targets = data.get('targets', ['democrat', 'republican', 'independent'])

        if not title or not description:
            return jsonify({'success': False, 'error': 'title and description required'}), 400

        prompt = (
            "Return ONLY a JSON object containing any of the keys democrat, republican, independent.\n"
            "For each present key, provide 3-5 concise, neutral bullets of likely talking points.\n\n"
            f"ARTICLE:\nTitle: {title}\nDescription: {description}\nSource: {source}\nCategory: {category}\n"
            f"Requested: {', '.join(targets)}\n"
            "Example: {\"democrat\":[\"...\"],\"republican\":[\"...\"],\"independent\":[\"...\"]}"
        )

        effective_key = OPENROUTER_API_KEY
        if not effective_key:
            return jsonify({'success': False, 'error': 'OpenRouter key missing'}), 500

        headers = {
            "Authorization": f"Bearer {effective_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://diatombot.xyz"
        }

        def generate_stream():
            try:
                with requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": OPENROUTER_MODEL,
                        "messages": [
                            {"role": "system", "content": "You produce concise, neutral talking-point bullets."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 2000,
                        "temperature": 0.3,
                        "stream": True
                    },
                    stream=True,
                    timeout=60
                ) as r:
                    if r.status_code != 200:
                        yield f"data: {json.dumps({'type': 'error', 'status': r.status_code})}\n\n"
                        return
                    buffer = ''
                    for line in r.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        if line.startswith('data: '):
                            payload = line[6:]
                            if payload.strip() == '[DONE]':
                                break
                            try:
                                obj = json.loads(payload)
                                delta = obj.get('choices', [{}])[0].get('delta', {}).get('content')
                                if delta:
                                    # Fix character encoding issues
                                    delta = _fix_character_encoding_web(delta)
                                    buffer += delta
                                    yield f"data: {json.dumps({'type': 'chunk', 'content': delta})}\n\n"
                            except Exception:
                                continue
                    # Fix encoding in complete buffer before parsing
                    buffer = _fix_character_encoding_web(buffer)
                    parsed = _try_parse_json(buffer) or _try_parse_json(_repair_json_text(buffer)) or _salvage_json_text(buffer)
                    if isinstance(parsed, dict):
                        # Apply encoding fixes to parsed perspective values
                        fixed_parsed = {}
                        for k, v in parsed.items():
                            if k in targets:
                                if isinstance(v, list):
                                    fixed_parsed[k] = [_fix_character_encoding_web(item) if isinstance(item, str) else item for item in v]
                                else:
                                    fixed_parsed[k] = _fix_character_encoding_web(v) if isinstance(v, str) else v
                        parsed = fixed_parsed
                    yield f"data: {json.dumps({'type': 'complete', 'perspectives': parsed, 'raw': buffer})}\n\n"
            except requests.exceptions.RequestException as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return Response(stream_with_context(generate_stream()), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
    except Exception as e:
        logger.error(f"perspectives stream error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        g.current_user = user
        return f(*args, **kwargs)
    return decorated_function

def optional_auth(f):
    """Decorator for optional authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        g.current_user = user
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/admin/reindex-embeddings', methods=['POST'])
@require_auth
def admin_reindex_embeddings():
    """Recompute and store embeddings for articles missing them (admin only)."""
    try:
        if g.current_user.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized access'}), 403

        data = request.get_json(silent=True) or {}
        try:
            limit = int(data.get('limit') or 200)
        except (TypeError, ValueError):
            limit = 200
        limit = max(1, min(limit, 5000))

        # Use the proper embedding system (Voyage) instead of deprecated Chimera
        updated = 0
        with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT id, title, description FROM articles ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
            for row in rows:
                _get_or_create_article_embedding({'id': row['id'], 'title': row['title'], 'description': row['description']})
                updated += 1
        return jsonify({'success': True, 'updated': updated})
    except Exception as e:
        logger.error(f"Error during embeddings reindex: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/reindex-fts', methods=['POST'])
@require_auth
def admin_reindex_fts():
    """Backfill SQLite FTS for articles missing FTS rows (admin only)."""
    try:
        if g.current_user.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized access'}), 403

        data = request.get_json(silent=True) or {}
        try:
            limit = int(data.get('limit') or 2000)
        except (TypeError, ValueError):
            limit = 2000
        limit = max(1, min(limit, 20000))

        # Ensure FTS is initialized (table + triggers). This does NOT auto-populate large corpora.
        _init_sqlite_fts()

        updated = 0
        with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Determine if content exists to match FTS schema
            try:
                cur.execute("PRAGMA table_info(articles)")
                cols = {r[1] for r in cur.fetchall()}
            except Exception:
                cols = set()
            has_content = "content" in cols

            select_cols = [
                "a.id", "a.title", "a.description", "a.category", "a.sentiment_analysis_text",
            ]
            if has_content:
                select_cols.append("a.content")
            select_sql = ", ".join(select_cols)

            # Pick only articles not yet present in FTS
            cur.execute(
                f"""
                SELECT {select_sql}
                FROM articles a
                LEFT JOIN articles_fts f ON f.rowid = a.id
                WHERE f.rowid IS NULL
                ORDER BY a.id DESC
                LIMIT ?
                """,
                (limit,)
            )
            rows = cur.fetchall()

            if not rows:
                return jsonify({'success': True, 'updated': 0, 'message': 'FTS already up to date'})

            # Insert missing rows into FTS
            fts_cols = ["rowid", "title", "description", "category", "sentiment_analysis_text"]
            if has_content:
                fts_cols.append("content")
            placeholders = ",".join(["?"] * len(fts_cols))
            ins_cols = ",".join(fts_cols)
            insert_sql = f"INSERT INTO articles_fts({ins_cols}) VALUES ({placeholders})"

            payload = []
            for r in rows:
                vals = [
                    int(r["id"]),
                    r["title"] or "",
                    r["description"] or "",
                    r["category"] or "",
                    r["sentiment_analysis_text"] or "",
                ]
                if has_content:
                    vals.append(r["content"] or "")
                payload.append(tuple(vals))

            cur.executemany(insert_sql, payload)
            conn.commit()
            updated = len(payload)

        return jsonify({'success': True, 'updated': updated})
    except Exception as e:
        logger.error(f"Error during FTS reindex: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/embeddings-status', methods=['GET'])
@require_auth
def admin_embeddings_status():
    """Return embeddings coverage stats (admin only)."""
    try:
        if g.current_user.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized access'}), 403

        # SQLite corpus size
        total_articles = 0
        try:
            with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM articles")
                total_articles = int(cur.fetchone()[0] or 0)
        except Exception:
            total_articles = 0

        # Supabase/pgvector embeddings count (provider-aware)
        try:
            embeddings_count = int(_pgvector_count() or 0)
        except Exception:
            embeddings_count = 0

        coverage = (embeddings_count / total_articles) if total_articles else 0.0

        # Optional progress file (from backfill_embeddings.py)
        progress_path = os.path.join(os.path.dirname(__file__), "state", "embeddings_backfill.json")
        progress_data = None
        try:
            if os.path.exists(progress_path):
                with open(progress_path, "r", encoding="utf-8") as f:
                    progress_data = json.load(f)
        except Exception:
            progress_data = None

        return jsonify({
            'success': True,
            'data': {
                'total_articles': total_articles,
                'embeddings_count': embeddings_count,
                'coverage_ratio': round(coverage, 4),
                'coverage_percent': round(coverage * 100, 2),
                'provider': EMBEDDINGS_PROVIDER,
                'supabase_only': USE_SUPABASE_ONLY,
                'progress': progress_data,
            }
        })
    except Exception as e:
        logger.error(f"Error getting embeddings status: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/performance/overview', methods=['GET'])
@require_auth
def admin_performance_overview():
    """Performance overview for Global Brief idea_desk recommendations (admin only)."""
    try:
        if g.current_user.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized access'}), 403
        try:
            horizon_days = int(request.args.get('horizon_days', 7))
        except (TypeError, ValueError):
            horizon_days = 7
        benchmark = (request.args.get('benchmark', 'SPY') or 'SPY').strip().upper()
        horizon_days = max(1, min(horizon_days, 365))

        with psycopg.connect(PG_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      COUNT(*) FILTER (WHERE alpha IS NOT NULL) AS n,
                      AVG(alpha) AS avg_alpha,
                      AVG(rec_return) AS avg_rec_return,
                      AVG(benchmark_return) AS avg_benchmark_return,
                      CASE
                        WHEN COUNT(*) FILTER (WHERE alpha IS NOT NULL) = 0 THEN NULL
                        ELSE SUM(CASE WHEN alpha > 0 THEN 1 ELSE 0 END)::float
                             / COUNT(*) FILTER (WHERE alpha IS NOT NULL)
                      END AS win_rate
                    FROM recommendation_performance
                    WHERE horizon_days = %s AND benchmark_symbol = %s
                    """,
                    (horizon_days, benchmark),
                )
                n, avg_alpha, avg_rec, avg_bench, win_rate = cur.fetchone()

        return jsonify(
            {
                "success": True,
                "horizon_days": horizon_days,
                "benchmark": benchmark,
                "n": int(n or 0),
                "avg_alpha": float(avg_alpha) if avg_alpha is not None else None,
                "avg_rec_return": float(avg_rec) if avg_rec is not None else None,
                "avg_benchmark_return": float(avg_bench) if avg_bench is not None else None,
                "win_rate": float(win_rate) if win_rate is not None else None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Error in performance overview: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/performance/recommendations', methods=['GET'])
@require_auth
def admin_performance_recommendations():
    """List recent recommendations with attached performance metrics (admin only)."""
    try:
        if g.current_user.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized access'}), 403
        try:
            limit = int(request.args.get('limit', 50))
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 200))
        try:
            horizon_days = int(request.args.get('horizon_days', 7))
        except (TypeError, ValueError):
            horizon_days = 7
        horizon_days = max(1, min(horizon_days, 365))
        benchmark = (request.args.get('benchmark', 'SPY') or 'SPY').strip().upper()

        with psycopg.connect(PG_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      r.id,
                      r.created_at,
                      r.action,
                      r.ticker,
                      r.analysis_id,
                      a.created_at AS analysis_created_at,
                      p.rec_return,
                      p.benchmark_return,
                      p.alpha
                    FROM recommendations r
                    LEFT JOIN analyses a ON a.id = r.analysis_id
                    LEFT JOIN recommendation_performance p
                      ON p.recommendation_id = r.id
                     AND p.horizon_days = %s
                     AND p.benchmark_symbol = %s
                    ORDER BY r.created_at DESC
                    LIMIT %s
                    """,
                    (horizon_days, benchmark, limit),
                )
                rows = cur.fetchall()

        data = []
        for rid, created_at, action, ticker, analysis_id, analysis_created_at, rec_ret, bench_ret, alpha in rows:
            data.append(
                {
                    "recommendation_id": int(rid),
                    "created_at": created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if created_at else None,
                    "action": action,
                    "ticker": ticker,
                    "analysis_id": int(analysis_id) if analysis_id is not None else None,
                    "analysis_created_at": analysis_created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if analysis_created_at else None,
                    "horizon_days": horizon_days,
                    "benchmark": benchmark,
                    "rec_return": float(rec_ret) if rec_ret is not None else None,
                    "benchmark_return": float(bench_ret) if bench_ret is not None else None,
                    "alpha": float(alpha) if alpha is not None else None,
                }
            )

        return jsonify({"success": True, "data": data, "count": len(data), "timestamp": datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        logger.error(f"Error in performance recommendations: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/trends/terms', methods=['GET'])
@require_auth
def admin_trends_terms():
    """Return latest computed term trends (admin only)."""
    try:
        if g.current_user.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized access'}), 403
        try:
            limit = int(request.args.get('limit', 50))
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 500))
        direction = (request.args.get('direction', 'rising') or 'rising').strip().lower()
        order = "ASC" if direction == "falling" else "DESC"

        with psycopg.connect(PG_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(window_end) FROM term_trends")
                w_end = cur.fetchone()[0]
                if not w_end:
                    return jsonify({"success": True, "data": [], "count": 0})
                cur.execute(
                    f"""
                    SELECT term, count, z_score, window_start, window_end
                    FROM term_trends
                    WHERE window_end = %s
                    ORDER BY z_score {order} NULLS LAST, count DESC
                    LIMIT %s
                    """,
                    (w_end, limit),
                )
                rows = cur.fetchall()

        data = []
        for term, count, z_score, w_start, w_end in rows:
            data.append(
                {
                    "term": term,
                    "count": int(count or 0),
                    "z_score": float(z_score) if z_score is not None else None,
                    "window_start": w_start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if w_start else None,
                    "window_end": w_end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if w_end else None,
                }
            )
        return jsonify({"success": True, "data": data, "count": len(data), "timestamp": datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        logger.error(f"Error in term trends: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/trends/topics', methods=['GET'])
@require_auth
def admin_trends_topics():
    """Return latest computed topic trends (admin only)."""
    try:
        if g.current_user.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized access'}), 403
        try:
            limit = int(request.args.get('limit', 50))
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 200))
        direction = (request.args.get('direction', 'rising') or 'rising').strip().lower()
        order = "ASC" if direction == "falling" else "DESC"

        with psycopg.connect(PG_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(window_end) FROM topic_trends")
                w_end = cur.fetchone()[0]
                if not w_end:
                    return jsonify({"success": True, "data": [], "count": 0})
                cur.execute(
                    f"""
                    SELECT topic, count, z_score, window_start, window_end
                    FROM topic_trends
                    WHERE window_end = %s
                    ORDER BY z_score {order} NULLS LAST, count DESC
                    LIMIT %s
                    """,
                    (w_end, limit),
                )
                rows = cur.fetchall()

        data = []
        for topic, count, z_score, w_start, w_end in rows:
            data.append(
                {
                    "topic": topic,
                    "count": int(count or 0),
                    "z_score": float(z_score) if z_score is not None else None,
                    "window_start": w_start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if w_start else None,
                    "window_end": w_end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if w_end else None,
                }
            )
        return jsonify({"success": True, "data": data, "count": len(data), "timestamp": datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        logger.error(f"Error in topic trends: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/insights', methods=['GET'])
@require_auth
def admin_list_insights():
    """List insight drafts/published posts (admin only)."""
    try:
        if g.current_user.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized access'}), 403
        status = (request.args.get('status') or '').strip().lower()
        try:
            limit = int(request.args.get('limit', 50))
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 200))
        where = "1=1"
        params = []
        if status:
            where = "status = %s"
            params.append(status)
        params.append(limit)

        with psycopg.connect(PG_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, created_at, updated_at, status, title, body_md, tags, evidence, published_at, external_url
                    FROM insight_posts
                    WHERE {where}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    params,
                )
                rows = cur.fetchall()

        data = []
        for rid, created_at, updated_at, st, title, body_md, tags, evidence, published_at, external_url in rows:
            data.append(
                {
                    "id": int(rid),
                    "created_at": created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if created_at else None,
                    "updated_at": updated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if updated_at else None,
                    "status": st,
                    "title": title,
                    "body_md": body_md,
                    "tags": tags or [],
                    "evidence": evidence,
                    "published_at": published_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if published_at else None,
                    "external_url": external_url,
                }
            )
        return jsonify({"success": True, "data": data, "count": len(data), "timestamp": datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        logger.error(f"Error listing insights: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/insights', methods=['POST'])
@require_auth
def admin_create_insight():
    """Create a new insight draft (admin only)."""
    try:
        if g.current_user.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized access'}), 403
        data = request.get_json(silent=True) or {}
        title = (data.get('title') or '').strip()
        body_md = (data.get('body_md') or '').strip()
        tags = data.get('tags') or []
        evidence = data.get('evidence') or None
        if not title:
            return jsonify({'success': False, 'error': 'title is required'}), 400

        from psycopg.types.json import Jsonb

        with psycopg.connect(PG_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO insight_posts (status, title, body_md, tags, evidence)
                    VALUES ('draft', %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (title, body_md, tags, Jsonb(evidence) if evidence is not None else None),
                )
                new_id = int(cur.fetchone()[0])
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        logger.error(f"Error creating insight: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/insights/<int:insight_id>', methods=['PATCH'])
@require_auth
def admin_update_insight(insight_id: int):
    """Update an insight draft (admin only)."""
    try:
        if g.current_user.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized access'}), 403
        data = request.get_json(silent=True) or {}
        fields = []
        params = []
        for key in ("title", "body_md", "status", "external_url"):
            if key in data:
                fields.append(f"{key} = %s")
                params.append(data.get(key))
        if "tags" in data:
            fields.append("tags = %s")
            params.append(data.get("tags") or [])
        if "evidence" in data:
            from psycopg.types.json import Jsonb
            fields.append("evidence = %s")
            params.append(Jsonb(data.get("evidence")) if data.get("evidence") is not None else None)
        if not fields:
            return jsonify({"success": False, "error": "no fields to update"}), 400
        params.append(insight_id)

        with psycopg.connect(PG_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE insight_posts SET {', '.join(fields)}, updated_at = now() WHERE id = %s",
                    params,
                )
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error updating insight: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/insights/<int:insight_id>/publish', methods=['POST'])
@require_auth
def admin_publish_insight(insight_id: int):
    """Mark an insight as published (admin only)."""
    try:
        if g.current_user.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized access'}), 403
        with psycopg.connect(PG_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE insight_posts
                    SET status = 'published', published_at = now(), updated_at = now()
                    WHERE id = %s
                    """,
                    (insight_id,),
                )
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error publishing insight: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

# Note: The catch-all route for serving React app is moved to the end of the file
# after all API routes to prevent it from intercepting API calls

def add_security_headers(response):
    """Add comprehensive security headers"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https:; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "connect-src 'self'"
    )
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    return response

app.after_request(add_security_headers)

def handle_database_error(f):
    """Decorator for handling database errors gracefully"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except DatabaseError as e:
            logger.error(f"Database error in {f.__name__}: {e}")
            return jsonify({'error': 'Database temporarily unavailable', 'retry': True}), 503
        except Exception as e:
            logger.error(f"Unexpected error in {f.__name__}: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    return decorated_function

def validate_request_params(required_params: List[str] = None, optional_params: Dict[str, type] = None):
    """Decorator for validating request parameters"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Validate required parameters
            if required_params:
                for param in required_params:
                    if param not in request.args and param not in request.json:
                        return jsonify({'error': f'Missing required parameter: {param}'}), 400
            
            # Validate optional parameter types
            if optional_params:
                for param, expected_type in optional_params.items():
                    value = request.args.get(param) or (request.json or {}).get(param)
                    if value is not None:
                        try:
                            if expected_type == int:
                                int(value)
                            elif expected_type == float:
                                float(value)
                            elif expected_type == bool:
                                str(value).lower() in ['true', 'false', '1', '0']
                        except (ValueError, TypeError):
                            return jsonify({'error': f'Invalid type for parameter {param}'}), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Removed API documentation route to allow React app to serve with OpenGraph tags
# @app.route('/')
# def index():
#     """Root route serving basic information about the API"""
    # Function body removed to allow React app route to take precedence

# =====================
# Function Calling Search Helpers
# =====================

def execute_search_rag(user_message: str, timeframe: Optional[str] = None,
                        limit: int = 12) -> Tuple[List[dict], str]:
    """
    Execute RAG search and return sources + context_text.

    Returns:
        (sources, context_text)
    """
    from typing import List, Tuple, Optional, Dict, Any
    import re

    sources: List[dict] = []
    context_text: str = ""

    try:
        q = (user_message or "").strip()
        if not q:
            return [], ""

        import math

        timeframe_map = {'2d': 2, '7d': 7, '30d': 30}
        days = timeframe_map.get(timeframe, 0) if isinstance(timeframe, str) else 0

        trending_keywords = ['trending', 'today', 'latest', 'recent', 'now', 'current', "what's new", 'what is new', 'changes', 'last 24']
        is_trending_query = any(keyword in q.lower() for keyword in trending_keywords)
        if is_trending_query and days == 0:
            days = 2  # default recency window for "what's happening" questions

        def _best_snippet_text(text: str, query: str) -> str:
            txt = (text or '').strip()
            if not txt:
                return ''
            parts = re.split(r'(?<=[.!?])\s+', txt)
            q_terms = set(t.lower() for t in re.findall(r"[a-zA-Z0-9']{3,}", query))
            best = ''
            best_score = -1.0
            for p in parts[:12]:
                terms = set(t.lower() for t in re.findall(r"[a-zA-Z0-9']{3,}", p))
                overlap = len(q_terms & terms)
                score = overlap / (1.0 + len(p))
                if score > best_score:
                    best = p
                    best_score = score
            return best[:300]

        def _tokenize_query_local(query: str) -> List[str]:
            stop = {
                'the','a','an','and','or','but','of','to','in','on','for','with','by','at','as','is','are','was','were','be','been','being',
                'this','that','these','those','it','its','from','about','into','over','after','before','between','through','during','without','within',
                'what','who','whom','which','when','where','why','how','can','could','should','would','may','might','will','shall','do','does','did'
            }
            toks = re.findall(r"[A-Za-z][A-Za-z\-']{1,}", query.lower())
            return [t for t in toks if t not in stop]

        def _compute_coverage_local(sources_list: List[dict], terms: List[str]) -> Tuple[float, List[str]]:
            matched: List[str] = []
            for s in sources_list:
                blob = " ".join(filter(None, [s.get('title'), s.get('snippet'), s.get('description')]))
                blob_l = (blob or '').lower()
                for t in terms:
                    if t in blob_l:
                        matched.append(t)
            ratio = (len(set(matched)) / max(1, len(terms))) if terms else 1.0
            return ratio, matched

        def _score_candidate(*, sem_sim: float, fts_rank: float, trust: float, recency: float, extraction_conf: float) -> float:
            # normalize fts rank into [0,1] (rank is usually small)
            fts_norm = 1.0 - math.exp(-max(0.0, float(fts_rank)))
            sem = max(0.0, min(1.0, float(sem_sim)))
            trust = max(0.0, min(1.0, float(trust)))
            rec = max(0.0, min(1.0, float(recency)))
            conf = max(0.0, min(1.0, float(extraction_conf)))
            fused = 0.50 * sem + 0.30 * fts_norm + 0.12 * trust + 0.08 * rec
            # boost if we have high-confidence fulltext
            return fused * (0.65 + 0.35 * conf)

        # -----------------------------
        # Primary: Postgres FTS + vector rerank (candidate-restricted)
        # -----------------------------
        try:
            candidate_limit = min(max(int(limit) * 8, 60), 200)
            with psycopg.connect(PG_DSN) as conn:
                with conn.cursor() as cur:
                    if days > 0:
                        cur.execute(
                            """
                            WITH q AS (SELECT websearch_to_tsquery('english', %s) AS tsq)
                            SELECT a.id, a.title, a.description, a.canonical_url, a.source_name, a.source_domain,
                                   a.created_at, a.published_at, a.excerpt, a.extracted_text,
                                   a.trust_score, a.extraction_confidence, a.quality_score,
                                   ts_rank_cd(a.search_tsv, q.tsq) AS rank
                            FROM articles a, q
                            WHERE a.bucket = 'main'
                              AND a.search_tsv @@ q.tsq
                              AND a.created_at >= now() - (%s || ' days')::interval
                            ORDER BY rank DESC, a.created_at DESC
                            LIMIT %s
                            """,
                            (q, int(days), int(candidate_limit)),
                        )
                    else:
                        cur.execute(
                            """
                            WITH q AS (SELECT websearch_to_tsquery('english', %s) AS tsq)
                            SELECT a.id, a.title, a.description, a.canonical_url, a.source_name, a.source_domain,
                                   a.created_at, a.published_at, a.excerpt, a.extracted_text,
                                   a.trust_score, a.extraction_confidence, a.quality_score,
                                   ts_rank_cd(a.search_tsv, q.tsq) AS rank
                            FROM articles a, q
                            WHERE a.bucket = 'main'
                              AND a.search_tsv @@ q.tsq
                            ORDER BY rank DESC, a.created_at DESC
                            LIMIT %s
                            """,
                            (q, int(candidate_limit)),
                        )
                    rows = cur.fetchall()

            candidates: List[Dict[str, Any]] = []
            for row in rows:
                (
                    aid,
                    title,
                    description,
                    canonical_url,
                    source_name,
                    source_domain,
                    created_at,
                    published_at,
                    excerpt,
                    extracted_text,
                    trust_score,
                    extraction_confidence,
                    quality_score,
                    fts_rank,
                ) = row
                candidates.append(
                    {
                        "id": int(aid),
                        "title": title,
                        "description": description,
                        "url": canonical_url,
                        "source_name": source_name,
                        "source_domain": source_domain,
                        "created_at": created_at,
                        "published_at": published_at,
                        "excerpt": excerpt,
                        "extracted_text": extracted_text,
                        "trust_score": float(trust_score or 0.0),
                        "extraction_confidence": float(extraction_confidence or 0.0),
                        "quality_score": float(quality_score or 0.0),
                        "fts_rank": float(fts_rank or 0.0),
                    }
                )

            if candidates:
                # Only ensure embeddings when semantic is enabled (avoids unnecessary costs/errors in FTS-only mode).
                if not DISABLE_SEMANTIC:
                    for c in candidates[: min(24, len(candidates))]:
                        _get_or_create_article_embedding(
                            {
                                "id": c["id"],
                                "title": c.get("title") or "",
                                "description": c.get("description") or "",
                                "excerpt": c.get("excerpt") or "",
                                "extracted_text": c.get("extracted_text") or "",
                            }
                        )

                dist_map: Dict[int, float] = {}
                if not DISABLE_SEMANTIC:
                    try:
                        qvec = _embed_text(q)
                        qlit = _vector_literal(qvec)
                        table = 'article_embeddings_voyage' if EMBEDDINGS_PROVIDER == 'voyage' and VOYAGE_API_KEY else 'article_embeddings'
                        ids = [c["id"] for c in candidates]
                        with psycopg.connect(PG_DSN) as conn:
                            with conn.cursor() as cur:
                                cur.execute(
                                    f"SELECT article_id, (embedding <=> %s::vector) AS dist FROM {table} WHERE article_id = ANY(%s)",
                                    (qlit, ids),
                                )
                                for aid, dist in cur.fetchall():
                                    if aid is not None and dist is not None:
                                        dist_map[int(aid)] = float(dist)
                    except Exception as e:
                        logger.warning(f"[RAG] semantic rerank skipped: {e}")

                now = datetime.now(timezone.utc)
                scored: List[Tuple[float, Dict[str, Any]]] = []
                for c in candidates:
                    dt = c.get("published_at") or c.get("created_at")
                    try:
                        if dt is None:
                            age_days = 30.0
                        else:
                            dt2 = dt if getattr(dt, "tzinfo", None) else dt.replace(tzinfo=timezone.utc)
                            age_days = max(0.0, (now - dt2).total_seconds() / 86400.0)
                    except Exception:
                        age_days = 30.0
                    rec = math.exp(-age_days / 7.0)

                    dist = dist_map.get(c["id"])
                    sem_sim = 0.0 if dist is None else max(0.0, 1.0 - float(dist))
                    score = _score_candidate(
                        sem_sim=sem_sim,
                        fts_rank=c.get("fts_rank", 0.0),
                        trust=c.get("trust_score", 0.0),
                        recency=rec,
                        extraction_conf=c.get("extraction_confidence", 0.0),
                    )
                    scored.append((score, c))
                scored.sort(key=lambda x: x[0], reverse=True)
                top = [c for _, c in scored[: max(1, int(limit))]]

                prompt_source_cap = 10
                query_terms_local = _tokenize_query_local(q)
                for idx, c in enumerate(top, 1):
                    src = c.get("source_name") or c.get("source_domain") or "Unknown"
                    snippet_base = c.get("extracted_text") or c.get("excerpt") or c.get("description") or ""
                    snippet = _best_snippet_text(str(snippet_base), q)
                    preview_base = (c.get("excerpt") or c.get("description") or snippet or "") or ""
                    preview = (str(preview_base)[:150] + ("..." if isinstance(preview_base, str) and len(preview_base) > 150 else ""))
                    created_iso = c["created_at"].astimezone(timezone.utc).isoformat() if c.get("created_at") else None

                    sources.append(
                        {
                            "id": c["id"],
                            "title": c.get("title"),
                            "description": c.get("description"),
                            "source": src,
                            "created_at": created_iso,
                            "category": "main",
                            "category_confidence": float(c.get("trust_score", 0.0)),
                            "sentiment_score": 0.0,
                            "sentiment_confidence": float(c.get("quality_score", 0.0)),
                            "sentiment_analysis_text": c.get("excerpt"),
                            "url": c.get("url"),
                            "preview": preview,
                            "snippet": snippet,
                            "trust_score": float(c.get("trust_score", 0.0)),
                            "extraction_confidence": float(c.get("extraction_confidence", 0.0)),
                        }
                    )

                    if idx <= prompt_source_cap:
                        context_text += f"[{idx}] {c.get('title')} — {src} ({(created_iso or '')[:16]})\n"
                        if snippet:
                            context_text += f"    \"{snippet[:220]}\"\n\n"

                coverage_ratio_local, matched_terms_local = _compute_coverage_local(sources, query_terms_local)
                logger.info(f"[RAG] Postgres: {len(sources)} sources, coverage={coverage_ratio_local:.2f}, matched_terms={matched_terms_local}")
                return sources, context_text
        except Exception as e:
            logger.warning(f"[RAG] Postgres RAG search failed; falling back to SQLite: {e}")

        # -----------------------------
        # Fallback: legacy SQLite search_nodes
        # -----------------------------
        try:
            since_hours = (int(days) * 24) if days else None
            legacy = db.search_nodes(q, limit=max(int(limit), 12), since_hours=since_hours)
            prompt_source_cap = 10
            query_terms_local = _tokenize_query_local(q)
            for idx, article in enumerate(legacy[: max(1, int(limit))], 1):
                snippet = _best_snippet_text(str(article.get('content') or article.get('description') or ''), q)
                preview_base = (article.get('description') or snippet or '') or ''
                preview = (str(preview_base)[:150] + ("..." if isinstance(preview_base, str) and len(preview_base) > 150 else ""))
                sources.append({**article, "snippet": snippet, "preview": preview})
                if idx <= prompt_source_cap:
                    src = article.get('source') or 'Unknown'
                    created_at = (article.get('created_at') or '')[:16]
                    context_text += f"[{idx}] {article.get('title')} — {src} ({created_at})\n"
                    if snippet:
                        context_text += f"    \"{snippet[:220]}\"\n\n"
            coverage_ratio_local, matched_terms_local = _compute_coverage_local(sources, query_terms_local)
            logger.info(f"[RAG] SQLite fallback: {len(sources)} sources, coverage={coverage_ratio_local:.2f}, matched_terms={matched_terms_local}")
        except Exception:
            sources = []
            context_text = ""

    except Exception as e:
        logger.error(f"[RAG] Search failed: {e}")
        sources = []
        context_text = ""

    return sources, context_text

def execute_search_web(user_message: str) -> dict:
    """
    Prepare for web search by returning metadata.
    Web search happens via Perplexity model selection.

    Returns:
        {'enabled': True, 'query': user_message}
    """
    return {'enabled': True, 'query': user_message}

@app.route('/api/health')
@limiter.exempt
def health_check():
    """API health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

# Authentication Endpoints
@app.route('/api/auth/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    """User registration endpoint"""
    try:
        data = request.get_json()
        if not data:
            logger.warning("Registration attempt with no data provided")
            return jsonify({'error': 'No data provided'}), 400
        
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        full_name = data.get('full_name', '').strip()
        
        logger.info(f"Registration attempt for username: {username}, email: {email}")
        
        # Validation
        if not username or len(username) < 3:
            logger.warning(f"Registration failed: Invalid username length: {len(username)}")
            return jsonify({'error': 'Username must be at least 3 characters'}), 400
        
        if not email or '@' not in email:
            logger.warning(f"Registration failed: Invalid email format: {email}")
            return jsonify({'error': 'Valid email required'}), 400
        
        if not password or len(password) < 6:
            logger.warning(f"Registration failed: Password too short: {len(password)} chars")
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        # Create user
        try:
            user_id = db.create_user(username, email, password, full_name)
            session_token = db.create_session(user_id)
            
            logger.info(f"User registered successfully: {username} (ID: {user_id})")
            return jsonify({
                'success': True,
                'message': 'User registered successfully',
                'user': {
                    'id': user_id,
                    'username': username,
                    'email': email,
                    'full_name': full_name
                },
                'session_token': session_token
            })
        except ValueError as e:
            logger.warning(f"User creation failed with ValueError: {str(e)}")
            return jsonify({'error': str(e)}), 400
        
    except ValueError as e:
        logger.error(f"Registration ValueError: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Registration error: {e}", exc_info=True)
        return jsonify({'error': 'Registration failed: An unexpected error occurred'}), 500

@app.route('/api/auth/csrf-token', methods=['GET'])
def get_csrf_token():
    """Get CSRF token for forms"""
    return jsonify({
        'csrf_token': generate_csrf_token()
    })

@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    """User login endpoint"""
    try:
        # Validate CSRF token for POST requests
        if not validate_csrf_token():
            return jsonify({'error': 'CSRF token validation failed'}), 403

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        username = data.get('username', '').strip()
        password = data.get('password', '')

        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400

        # Authenticate user
        user = db.authenticate_user(username, password)
        if not user:
            # Check if account might be locked
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT failed_login_count, account_locked_until
                        FROM users
                        WHERE username = ? AND is_active = TRUE
                    ''', (username,))
                    result = cursor.fetchone()
                    if result and result['account_locked_until']:
                        try:
                            locked_until = datetime.fromisoformat(result['account_locked_until'])
                            if locked_until > datetime.now():
                                return jsonify({'error': 'Account temporarily locked due to too many failed login attempts. Try again later.'}), 429
                        except (ValueError, TypeError):
                            # If date parsing fails, assume account is not locked
                            pass
            except Exception as e:
                logger.error(f"Error checking account lock status: {e}")

            return jsonify({'error': 'Invalid credentials'}), 401

        # Create session
        session_token = db.create_session(user['id'])

        # Get saved articles for user
        saved_article_ids = db.get_user_saved_article_ids(user['id'])

        # Get profile picture from user_preferences
        profile_picture = None
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT preference_value FROM user_preferences
                    WHERE user_id = ? AND preference_key = 'profile_picture'
                ''', (user['id'],))
                result = cursor.fetchone()
                if result:
                    profile_picture = result['preference_value']
        except Exception as e:
            logger.error(f"Error fetching profile picture during login: {e}")

        # Set secure httpOnly cookie for session token
        response = jsonify({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'full_name': user['full_name'],
                'role': user['role'],
                'saved_articles': saved_article_ids,
                'profile_picture': profile_picture
            }
        })

        # Set httpOnly cookie for session token (secure, httpOnly, sameSite)
        response.set_cookie(
            'session_token',
            session_token,
            httponly=True,
            secure=True,
            samesite='Strict',
            max_age=7*24*3600  # 7 days
        )

        return response

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    """User logout endpoint"""
    try:
        # Validate CSRF token for POST requests
        if not validate_csrf_token():
            return jsonify({'error': 'CSRF token validation failed'}), 403

        # Get token from cookie or header
        token = request.cookies.get('session_token')
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]

        if token:
            db.delete_session(token)

        # Create response and clear the session cookie
        response = jsonify({
            'success': True,
            'message': 'Logout successful'
        })
        response.set_cookie('session_token', '', expires=0, httponly=True, secure=True, samesite='Strict')

        return response

    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({'error': 'Logout failed'}), 500

@app.route('/api/auth/me')
@require_auth
def get_current_user_info():
    """Get current user information"""
    try:
        user = g.current_user
        saved_article_ids = db.get_user_saved_article_ids(user['id'])
        
        # Get profile picture from user_preferences
        profile_picture = None
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT preference_value FROM user_preferences 
                WHERE user_id = ? AND preference_key = 'profile_picture'
            ''', (user['id'],))
            result = cursor.fetchone()
            if result:
                profile_picture = result['preference_value']
        
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'full_name': user['full_name'],
                'role': user['role'],
                'saved_articles': saved_article_ids,
                'profile_picture': profile_picture
            }
        })
        
    except Exception as e:
        logger.error(f"Get user info error: {e}")
        return jsonify({'error': 'Failed to get user info'}), 500

# Profile and Saved Articles Endpoints
@app.route('/api/profile/saved-articles')
@require_auth
def get_saved_articles():
    """Get user's saved articles"""
    try:
        limit = min(int(request.args.get('limit', 50)), 100)
        user_id = g.current_user['id']
        
        saved_articles = db.get_saved_articles_for_user(user_id, limit)
        
        return jsonify({
            'success': True,
            'data': saved_articles,
            'count': len(saved_articles)
        })
        
    except Exception as e:
        logger.error(f"Get saved articles error: {e}")
        return jsonify({'error': 'Failed to get saved articles'}), 500

@app.route('/api/profile/save-article', methods=['POST'])
@require_auth
def save_article():
    """Save an article for the current user"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        article_id = data.get('article_id')
        notes = data.get('notes', '')
        
        if not article_id:
            return jsonify({'error': 'Article ID required'}), 400
        
        user_id = g.current_user['id']
        success = db.save_article_for_user(user_id, int(article_id), notes)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Article saved successfully'
            })
        else:
            return jsonify({'error': 'Failed to save article'}), 500
            
    except Exception as e:
        logger.error(f"Save article error: {e}")
        return jsonify({'error': 'Failed to save article'}), 500

@app.route('/api/profile/unsave-article', methods=['POST'])
@require_auth
def unsave_article():
    """Remove an article from user's saved articles"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        article_id = data.get('article_id')
        
        if not article_id:
            return jsonify({'error': 'Article ID required'}), 400
        
        user_id = g.current_user['id']
        success = db.unsave_article_for_user(user_id, int(article_id))
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Article removed from saved articles'
            })
        else:
            return jsonify({'error': 'Article not found in saved articles'}), 404
            
    except Exception as e:
        logger.error(f"Unsave article error: {e}")
        return jsonify({'error': 'Failed to unsave article'}), 500

@app.route('/api/auth/check-username', methods=['GET'])
@limiter.limit("20 per minute")
def check_username():
    """Check if a username is available"""
    try:
        username = request.args.get('username', '').strip()
        
        if not username:
            return jsonify({'error': 'Username is required'}), 400
        
        # Check length
        if len(username) < 3:
            return jsonify({
                'available': False,
                'error': 'Username must be at least 3 characters'
            }), 200
        
        # Check if username exists in database
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            
            if user:
                return jsonify({
                    'available': False,
                    'error': 'Username already taken'
                }), 200
            else:
                return jsonify({
                    'available': True,
                    'message': 'Username is available'
                }), 200
                
    except Exception as e:
        logger.error(f"Check username error: {e}")
        return jsonify({'error': 'Failed to check username'}), 500

@app.route('/api/profile/update', methods=['POST', 'PUT'])
@require_auth
def update_profile():
    """Update user profile information"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        user_id = g.current_user['id']
        
        # Prepare update fields
        updates = {}
        
        # Check if username is being updated
        if 'username' in data and data['username'] != g.current_user['username']:
            new_username = data['username'].strip()
            
            # Validate username
            if len(new_username) < 3:
                return jsonify({'error': 'Username must be at least 3 characters'}), 400
            
            # Check if username is already taken
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM users WHERE username = ? AND id != ?', 
                             (new_username, user_id))
                existing = cursor.fetchone()
                
                if existing:
                    return jsonify({'error': 'Username already exists, please choose another one'}), 400
            
            updates['username'] = new_username
        
        # Update email if provided
        if 'email' in data and data['email'] != g.current_user['email']:
            new_email = data['email'].strip()
            
            # Basic email validation
            if '@' not in new_email or '.' not in new_email:
                return jsonify({'error': 'Invalid email address'}), 400
            
            # Check if email is already taken
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM users WHERE email = ? AND id != ?', 
                             (new_email, user_id))
                existing = cursor.fetchone()
                
                if existing:
                    return jsonify({'error': 'Email already exists'}), 400
            
            updates['email'] = new_email
        
        # Update full name if provided
        if 'full_name' in data:
            updates['full_name'] = data['full_name'].strip()
        
        # Perform the update if there are changes
        if updates:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Build update query
                update_fields = []
                values = []
                for field, value in updates.items():
                    update_fields.append(f"{field} = ?")
                    values.append(value)
                
                values.append(user_id)
                query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
                
                cursor.execute(query, values)
                conn.commit()
                
                # Return updated user data
                cursor.execute('''
                    SELECT id, username, email, full_name, role 
                    FROM users WHERE id = ?
                ''', (user_id,))
                updated_user = cursor.fetchone()
                
                if updated_user:
                    return jsonify({
                        'success': True,
                        'message': 'Profile updated successfully',
                        'user': dict(updated_user)
                    })
        else:
            return jsonify({
                'success': True,
                'message': 'No changes to update'
            })
            
    except Exception as e:
        logger.error(f"Update profile error: {e}")
        return jsonify({'error': 'Failed to update profile'}), 500

@app.route('/api/profile/update-picture', methods=['POST', 'PUT'])
@require_auth
def update_profile_picture():
    """Update user profile picture"""
    try:
        # Check if file is in the request
        if 'profile_picture' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['profile_picture']
        
        # Check if file was selected
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        file_ext = file.filename.rsplit('.', 1)[-1].lower()
        
        if file_ext not in allowed_extensions:
            return jsonify({'error': 'Invalid file type. Allowed: png, jpg, jpeg, gif, webp'}), 400
        
        # Validate file size (5MB limit)
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > 5 * 1024 * 1024:
            return jsonify({'error': 'File size must be less than 5MB'}), 400
        
        # For now, we'll store the profile picture as a base64 string in the database
        # In production, you'd want to store this in a proper file storage service
        import base64
        
        file_data = file.read()
        base64_data = base64.b64encode(file_data).decode('utf-8')
        profile_picture_url = f"data:{file.content_type};base64,{base64_data}"
        
        # Update user's profile picture in database
        user_id = g.current_user['id']
        
        # Since profile_picture column doesn't exist in the users table,
        # we'll store it in user_preferences for now
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_preferences (user_id, preference_key, preference_value)
                VALUES (?, 'profile_picture', ?)
            ''', (user_id, profile_picture_url))
            conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Profile picture updated successfully',
            'profile_picture_url': profile_picture_url
        })
        
    except Exception as e:
        logger.error(f"Update profile picture error: {e}")
        return jsonify({'error': 'Failed to update profile picture'}), 500

@app.route('/api/top-events')
@cache.cached(timeout=300)
@limiter.limit("30 per minute")
def get_top_events():
    """Get top 5 events of the day from latest analysis"""
    try:
        # Get the most recent analysis with structured data
        analyses = db.get_recent_analyses(limit=5)
        
        if not analyses or len(analyses) == 0:
            return jsonify({
                'success': False,
                'message': 'No analyses available',
                'data': []
            })
        
        # Find the most recent analysis with raw_response_json
        latest_analysis = None
        for analysis in analyses:
            if analysis.get('raw_response_json'):
                try:
                    structured_data = json.loads(analysis['raw_response_json'])
                    if structured_data:
                        latest_analysis = {
                            'data': structured_data,
                            'timestamp': analysis.get('created_at'),
                            'id': analysis.get('id')
                        }
                        break
                except json.JSONDecodeError:
                    continue
        
        if not latest_analysis:
            return jsonify({
                'success': False,
                'message': 'No structured analysis available',
                'data': []
            })
            
        # Extract top events
        top_events = []
        
        # Try to extract from different structured formats
        structured_data = latest_analysis['data']
        
        # Try breaking_news format
        if 'breaking_news' in structured_data:
            top_events = structured_data['breaking_news'][:5]
        
        # If not available, try key_developments format
        elif 'key_developments' in structured_data:
            top_events = structured_data['key_developments'][:5]
            
        # If not available, try market_pulse format
        elif 'market_pulse' in structured_data:
            top_events = structured_data['market_pulse'][:5]
            
        # Last resort: try to find any list-like structures with news items
        else:
            for key, value in structured_data.items():
                if isinstance(value, list) and len(value) > 0:
                    # Check if items in the list have headline/title and summary
                    if all(isinstance(item, dict) for item in value[:5]):
                        if any('headline' in item or 'title' in item for item in value[:5]):
                            top_events = value[:5]
                            break
        
        return jsonify({
            'success': True,
            'data': top_events,
            'timestamp': latest_analysis.get('timestamp'),
            'analysis_id': latest_analysis.get('id')
        })
        
    except Exception as e:
        logger.error(f"Error fetching top events: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to fetch top events'
        }), 500

@app.route('/api/market-intelligence', methods=['GET'])
@cache.cached(timeout=300)  # Cache for 5 minutes
@limiter.limit("20 per minute")
def get_market_intelligence():
    """Get sophisticated market sentiment score with multi-factor analysis"""
    try:
        intel = db.get_market_intelligence_score()
        response = jsonify({
            'success': True,
            'data': intel,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        response.headers['Cache-Control'] = 'public, max-age=300'  # 5 minutes
        return response
    except Exception as e:
        logger.error(f"Market intelligence error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sentiment-distribution', methods=['GET'])
@cache.cached(timeout=300)
@limiter.limit("20 per minute")
def get_sentiment_distribution():
    """Get granular sentiment distribution with 7 buckets (not just 3)"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get sentiment distribution with 7 granular buckets
            cursor.execute('''
                SELECT 
                    COUNT(CASE WHEN sentiment_score >= 0.5 THEN 1 END) as very_bullish,
                    COUNT(CASE WHEN sentiment_score >= 0.2 AND sentiment_score < 0.5 THEN 1 END) as bullish,
                    COUNT(CASE WHEN sentiment_score >= 0.05 AND sentiment_score < 0.2 THEN 1 END) as slightly_bullish,
                    COUNT(CASE WHEN sentiment_score > -0.05 AND sentiment_score < 0.05 THEN 1 END) as neutral,
                    COUNT(CASE WHEN sentiment_score > -0.2 AND sentiment_score <= -0.05 THEN 1 END) as slightly_bearish,
                    COUNT(CASE WHEN sentiment_score > -0.5 AND sentiment_score <= -0.2 THEN 1 END) as bearish,
                    COUNT(CASE WHEN sentiment_score <= -0.5 THEN 1 END) as very_bearish,
                    COUNT(*) as total,
                    AVG(sentiment_score) as avg_sentiment,
                    AVG(sentiment_confidence) as avg_confidence
                FROM articles
                WHERE created_at > strftime('%Y-%m-%dT%H:%M:%f', 'now', '-7 days')
                    AND sentiment_score IS NOT NULL
            ''')
            
            result = cursor.fetchone()
            
            # Sentiment by category
            cursor.execute('''
                SELECT 
                    category,
                    COUNT(*) as count,
                    AVG(sentiment_score) as avg_sentiment,
                    AVG(sentiment_confidence) as avg_confidence
                FROM articles
                WHERE created_at > strftime('%Y-%m-%dT%H:%M:%f', 'now', '-7 days')
                    AND sentiment_score IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
            ''')
            
            by_category = [
                {
                    'category': row['category'],
                    'count': row['count'],
                    'avg_sentiment': round(row['avg_sentiment'], 3),
                    'avg_confidence': round(row['avg_confidence'], 3)
                }
                for row in cursor.fetchall()
            ]
            
            # Sentiment trend over last 7 days (by day)
            cursor.execute('''
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as count,
                    AVG(sentiment_score) as avg_sentiment,
                    AVG(sentiment_confidence) as avg_confidence
                FROM articles
                WHERE created_at > strftime('%Y-%m-%dT%H:%M:%f', 'now', '-7 days')
                    AND sentiment_score IS NOT NULL
                GROUP BY DATE(created_at)
                ORDER BY date ASC
            ''')
            
            trend = [
                {
                    'date': row['date'],
                    'count': row['count'],
                    'avg_sentiment': round(row['avg_sentiment'], 3),
                    'avg_confidence': round(row['avg_confidence'], 3)
                }
                for row in cursor.fetchall()
            ]
            
            data = {
                'distribution': {
                    'very_bullish': result['very_bullish'],
                    'bullish': result['bullish'],
                    'slightly_bullish': result['slightly_bullish'],
                    'neutral': result['neutral'],
                    'slightly_bearish': result['slightly_bearish'],
                    'bearish': result['bearish'],
                    'very_bearish': result['very_bearish'],
                    'total': result['total']
                },
                'averages': {
                    'sentiment': round(result['avg_sentiment'], 3),
                    'confidence': round(result['avg_confidence'], 3)
                },
                'by_category': by_category,
                'trend': trend
            }
            
            return jsonify({'success': True, 'data': data})
            
    except Exception as e:
        logger.error(f"Sentiment distribution error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats')
@cache.cached(timeout=300)  # Increase cache time to 5 minutes
@limiter.limit("20 per minute")  # Increase rate limit
def get_stats():
    """Get dashboard statistics"""
    try:
        stats = db.get_stats()
        response = jsonify({
            'success': True,
            'data': stats,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        # Add cache headers for browser caching
        response.headers['Cache-Control'] = 'public, max-age=60'
        return response
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500

@app.route('/api/articles')
@limiter.limit("30 per minute")
def get_articles():
    """Get recent articles API endpoint"""
    try:
        # Get query parameters
        limit = request.args.get('limit', 20, type=int)
        category = request.args.get('category', None)
        sentiment = request.args.get('sentiment', None)
        timeframe = request.args.get('timeframe', None) or request.args.get('timeRange', None) or request.args.get('time_range', None)
        include_analysis = request.args.get('include_analysis', 'true').lower() == 'true'
        
        # Validate limit
        if limit > 100:
            limit = 100

        # Normalize category
        if isinstance(category, str) and category.strip().lower() in ('', 'all', 'any'):
            category = None

        # Sentiment filter mapping
        min_sentiment = request.args.get('min_sentiment', type=float)
        max_sentiment = request.args.get('max_sentiment', type=float)
        if (min_sentiment is None and max_sentiment is None) and isinstance(sentiment, str) and sentiment.strip():
            s = sentiment.strip().lower()
            if s in ('positive', 'bullish'):
                min_sentiment, max_sentiment = 0.1, 1.0
            elif s in ('negative', 'bearish'):
                min_sentiment, max_sentiment = -1.0, -0.1
            elif s in ('neutral',):
                min_sentiment, max_sentiment = -0.1, 0.1

        # Timeframe parsing (e.g., 24h, 7d, 30d)
        since_hours = None
        if isinstance(timeframe, str) and timeframe.strip():
            tf = timeframe.strip().lower()
            m = re.fullmatch(r'(\d+)\s*([hdw])', tf)
            if m:
                n = int(m.group(1))
                unit = m.group(2)
                if unit == 'h':
                    since_hours = n
                elif unit == 'd':
                    since_hours = n * 24
                elif unit == 'w':
                    since_hours = n * 24 * 7

        # Prefer Postgres-backed store for the new ingestion pipeline; fallback to legacy SQLite.
        if _pg_articles is not None:
            try:
                bucket = category if category else None
                articles = _pg_articles.get_recent_articles(limit=limit, bucket=bucket, since_hours=since_hours)
            except Exception:
                articles = db.get_recent_articles(
                    limit=limit,
                    category=category,
                    min_sentiment=min_sentiment,
                    max_sentiment=max_sentiment,
                    since_hours=since_hours
                )
        else:
            articles = db.get_recent_articles(
                limit=limit,
                category=category,
                min_sentiment=min_sentiment,
                max_sentiment=max_sentiment,
                since_hours=since_hours
            )
        
        # Check for user authentication and add saved status
        user = get_current_user()
        if user:
            saved_article_ids = set(db.get_user_saved_article_ids(user['id']))
            for article in articles:
                article['is_saved'] = str(article['id']) in saved_article_ids
        else:
            for article in articles:
                article['is_saved'] = False
        
        # Optionally exclude certain fields to reduce payload size
        if not include_analysis:
            for article in articles:
                if 'sentiment_analysis_text' in article:
                    del article['sentiment_analysis_text']
        
        return jsonify({
            'success': True,
            'data': articles,
            'count': len(articles),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"Unexpected error in get_articles: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch articles',
            'message': str(e)
        }), 500

@app.route('/api/analyses')
@cache.cached(timeout=300)
@limiter.limit("30 per minute")
@handle_database_error
@validate_request_params(optional_params={'limit': int})
def get_analyses():
    """Get recent analyses with caching"""
    limit = min(int(request.args.get('limit', 10)), 50)  # Cap at 50
    # Prefer Postgres analyses (Global Briefs); fallback to legacy SQLite.
    if _pg_analyses is not None:
        try:
            analyses = _pg_analyses.get_recent(limit=limit)
        except Exception:
            analyses = db.get_recent_analyses(limit=limit)
    else:
        analyses = db.get_recent_analyses(limit=limit)
    
    # Format analyses for display
    for analysis in analyses:
        if analysis.get('created_at'):
            try:
                dt = datetime.fromisoformat(analysis['created_at'].replace('Z', '+00:00'))
                analysis['created_at_formatted'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                analysis['time_ago'] = get_time_ago(dt)
            except:
                pass
        
        # Truncate content for list view
        content = analysis.get('content', '')
        if len(content) > 500:
            analysis['content_preview'] = content[:500] + '...'
        else:
            analysis['content_preview'] = content
    
    return jsonify({
        'success': True,
        'data': analyses,
        'count': len(analyses)
    })


@app.route('/api/external/intelligence-reports', methods=['GET'])
@limiter.limit("10 per minute")
def get_external_intelligence_reports():
    """Provide sanitized intelligence reports to external partners via API key."""
    if not EXTERNAL_INTEL_API_KEYS:
        return jsonify({
            'success': False,
            'error': 'External intelligence API is disabled'
        }), 503

    provided_key = request.headers.get('X-API-Key') or request.args.get('api_key')
    if not provided_key or provided_key not in EXTERNAL_INTEL_API_KEYS:
        logger.warning("Unauthorized external intelligence access attempt")
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        limit = int(request.args.get('limit', 5))
    except (TypeError, ValueError):
        limit = 5
    limit = max(1, min(limit, 20))

    include_raw = _parse_external_bool(request.args.get('include_raw', 'false'))

    if _pg_analyses is not None:
        try:
            analyses = _pg_analyses.get_recent(limit=limit)
        except Exception:
            analyses = db.get_recent_analyses(limit=limit)
    else:
        analyses = db.get_recent_analyses(limit=limit)
    payload = [_format_analysis_for_external(analysis, include_raw=include_raw) for analysis in analyses]

    return jsonify({
        'success': True,
        'count': len(payload),
        'data': payload,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


@app.route('/api/analyses', methods=['POST'])
@limiter.limit("10 per minute")
def create_analysis():
    """Create a custom analysis (used for saving chat outputs as analyses)."""
    try:
        data = request.get_json() or {}
        content = data.get('content')
        sources = data.get('sources', [])
        model_used = data.get('model_used', 'chat')

        if not content or not isinstance(content, str):
            return jsonify({'success': False, 'error': 'content is required'}), 400

        content_preview = content[:500]
        article_count = len(sources) if isinstance(sources, list) else 0
        raw_response_json = json.dumps({'sources': sources})

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO analyses (content, content_preview, model_used, article_count, raw_response_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (content, content_preview, model_used, article_count, raw_response_json, datetime.utcnow().isoformat()))
            conn.commit()
            new_id = cursor.lastrowid

        return jsonify({'success': True, 'id': new_id})
    except Exception as e:
        logger.error(f"Error creating analysis: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to create analysis'}), 500

@app.route('/api/analyses/<analysis_id>')
@cache.cached(timeout=300)
@limiter.limit("30 per minute")
def get_analysis_detail(analysis_id):
    """Get detailed analysis content by ID"""
    try:
        # Get the analysis by ID
        analysis = db.get_analysis_by_id(analysis_id)
        
        if not analysis:
            return jsonify({
                'success': False,
                'message': f'Analysis with ID {analysis_id} not found',
                'data': None
            }), 404
        
        # Get formatted content
        formatted_content = ""
        
        if analysis.get('raw_response_json'):
            try:
                # Parse the JSON response
                data = json.loads(analysis.get('raw_response_json'))
                
                # Format the content for display
                formatted_content = format_analysis_for_display(data, analysis)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse raw_response_json for analysis {analysis_id}")
                formatted_content = "Error: Could not parse analysis content."
        
        return jsonify({
            'success': True,
            'data': {
                'id': analysis.get('id'),
                'created_at': analysis.get('created_at'),
                'formatted_content': formatted_content,
                'raw_data': analysis
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching analysis detail: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to fetch analysis detail'
        }), 500

def format_analysis_for_display(data, analysis):
    """Format the analysis data for human-readable display"""
    try:
        output = []
        
        # Add header
        output.append("┏━━ GLOBAL BRIEF ━━┓")
        output.append("#GEOPOLITICS")
        
        # Add date
        created_at = analysis.get('created_at', '').split(' ')[0]
        output.append(f"— {created_at}")
        output.append("┗━━━━━━━━━━━━━━━━┛\n")
        
        # Add breaking news
        if 'breaking_news' in data:
            for i, news in enumerate(data['breaking_news'], 1):
                tier = news.get('tier', 3)
                headline = news.get('headline', 'Breaking News')
                time = news.get('time', '')
                summary = news.get('summary', '')
                key_insight = news.get('key_insight', '')
                actionable_advice = news.get('actionable_advice', '')
                
                output.append(f"⚡{i} BREAKING TIER-{tier} — +++ {time} {headline} +++")
                output.append(f"{summary} {i}")
                
                if key_insight:
                    output.append(f"KEY INSIGHT: {key_insight}")
                
                if actionable_advice:
                    output.append(f"ACTIONABLE ADVICE: {actionable_advice}")
                
                output.append("")
        
        # Add key numbers
        if 'key_numbers' in data:
            output.append("📊 KEY NUMBERS")
            for i, number in enumerate(data['key_numbers'], 1):
                title = number.get('title', '')
                value = number.get('value', '')
                context = number.get('context', '')
                
                output.append(f"• {title} {i+3} — {value}")
                output.append(f"  {context}")
                output.append("")
        
        # Add market pulse
        if 'market_pulse' in data:
            output.append("📈 MARKET PULSE")
            for i, pulse in enumerate(data['market_pulse'], 1):
                asset = pulse.get('asset', '')
                direction = pulse.get('direction', '')
                catalyst = pulse.get('catalyst', '')
                why_it_matters = pulse.get('why_it_matters', '')
                
                output.append(f"• {asset} {direction}")
                output.append(f"  CATALYST: {catalyst}")
                output.append(f"  WHY IT MATTERS: {why_it_matters}")
                output.append("")
        
        # Add crypto barometer
        if 'crypto_barometer' in data:
            output.append("🔮 CRYPTO BAROMETER")
            for crypto in data['crypto_barometer']:
                token = crypto.get('token', '')
                movement = crypto.get('movement', '')
                catalyst = crypto.get('catalyst', '')
                quick_take = crypto.get('quick_take', '')
                
                output.append(f"• {token} {movement}")
                output.append(f"  CATALYST: {catalyst}")
                output.append(f"  QUICK TAKE: {quick_take}")
                output.append("")
        
        # Add idea desk
        if 'idea_desk' in data:
            output.append("💡 IDEA DESK")
            for idea in data['idea_desk']:
                action = idea.get('action', '')
                ticker = idea.get('ticker', '')
                rationale = idea.get('rationale', '')
                
                output.append(f"• {action} {ticker}")
                output.append(f"  RATIONALE: {rationale}")
                output.append("")
        
        # Add final intel
        if 'final_intel' in data:
            output.append("🔍 FINAL INTEL")
            summary = data['final_intel'].get('summary', '')
            investment_horizon = data['final_intel'].get('investment_horizon', '')
            key_risks = data['final_intel'].get('key_risks', [])
            
            output.append(f"{summary}")
            output.append(f"INVESTMENT HORIZON: {investment_horizon}")
            output.append("KEY RISKS:")
            for risk in key_risks:
                output.append(f"• {risk}")
            output.append("")
        
        # Add footer
        article_count = analysis.get('article_count', 0)
        processing_time = analysis.get('processing_time', 0)
        
        output.append("━━━━━━━━━━━━━━━━━")
        output.append(f"📰 {article_count} sources analyzed")
        output.append("🌐 Full analysis: https://watchfuleye.us")
        output.append(f"⚱ Processing: {processing_time:.1f}s")
        output.append("🤖 Powered by WatchfulEye")
        
        return "\n".join(output)
    except Exception as e:
        logger.error(f"Error formatting analysis: {e}")
        return "Error formatting analysis content."

@app.route('/api/categories')
@cache.cached(timeout=600)
@limiter.limit("30 per minute")
@handle_database_error
def get_categories():
    """Get available categories with counts"""
    # Prefer Postgres buckets (main/deals/etc); fallback to legacy SQLite categories.
    if _pg_articles is not None:
        try:
            return jsonify({'categories': _pg_articles.get_buckets()})
        except Exception:
            pass

    stats = db.get_enhanced_stats()
    categories = stats.get('categories', {})
    category_list = []
    for category, data in categories.items():
        category_list.append({
            'name': category,
            'display_name': category.title(),
            'count': data['count'],
            'avg_sentiment': round(data['avg_sentiment'], 2),
            'avg_confidence': round(data['avg_confidence'], 2)
        })
    category_list.sort(key=lambda x: x['count'], reverse=True)
    return jsonify({'categories': category_list})

@app.route('/api/search')
@limiter.limit("10 per minute")
def search_articles():
    """Search articles API endpoint"""
    try:
        # Get search query from URL parameters
        query = request.args.get('q', '')
        limit = request.args.get('limit', 50, type=int)
        category = request.args.get('category', None)
        sentiment = request.args.get('sentiment', None)
        timeframe = request.args.get('timeframe', None) or request.args.get('timeRange', None) or request.args.get('time_range', None)
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Search query is required',
                'data': []
            }), 400

        if limit > 200:
            limit = 200

        if isinstance(category, str) and category.strip().lower() in ('', 'all', 'any'):
            category = None

        # Sentiment filter mapping
        min_sentiment = request.args.get('min_sentiment', type=float)
        max_sentiment = request.args.get('max_sentiment', type=float)
        if (min_sentiment is None and max_sentiment is None) and isinstance(sentiment, str) and sentiment.strip():
            s = sentiment.strip().lower()
            if s in ('positive', 'bullish'):
                min_sentiment, max_sentiment = 0.1, 1.0
            elif s in ('negative', 'bearish'):
                min_sentiment, max_sentiment = -1.0, -0.1
            elif s in ('neutral',):
                min_sentiment, max_sentiment = -0.1, 0.1

        # Timeframe parsing (e.g., 24h, 7d, 30d)
        since_hours = None
        if isinstance(timeframe, str) and timeframe.strip():
            tf = timeframe.strip().lower()
            m = re.fullmatch(r'(\d+)\s*([hdw])', tf)
            if m:
                n = int(m.group(1))
                unit = m.group(2)
                if unit == 'h':
                    since_hours = n
                elif unit == 'd':
                    since_hours = n * 24
                elif unit == 'w':
                    since_hours = n * 24 * 7
        
        # Prefer Postgres FTS search; fallback to legacy SQLite LIKE search.
        if _pg_articles is not None:
            try:
                bucket = category if category else None
                tf = None
                if since_hours:
                    tf = f"{int(since_hours)}h"
                articles = _pg_articles.search(query=query, limit=limit, bucket=bucket, timeframe=tf)
            except Exception:
                articles = db.search_nodes(
                    query,
                    limit=limit,
                    category=category,
                    min_sentiment=min_sentiment,
                    max_sentiment=max_sentiment,
                    since_hours=since_hours,
                )
        else:
            articles = db.search_nodes(
                query,
                limit=limit,
                category=category,
                min_sentiment=min_sentiment,
                max_sentiment=max_sentiment,
                since_hours=since_hours,
            )
        
        return jsonify({
            'success': True,
            'data': articles,
            'query': query,
            'count': len(articles),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"Unexpected error in search_articles: {e}")
        return jsonify({
            'success': False,
            'error': 'Search failed',
            'message': str(e)
        }), 500

@app.route('/api/export')
@limiter.limit("5 per minute")
@handle_database_error
@validate_request_params(optional_params={'format': str, 'days': int})
def export_data():
    """Export data in various formats"""
    format_type = request.args.get('format', 'json').lower()
    days = min(int(request.args.get('days', 7)), 30)  # Cap at 30 days
    
    if format_type not in ['json', 'csv']:
        return jsonify({'error': 'Unsupported format. Use json or csv'}), 400
    
    try:
        # Get data from specified timeframe
        articles = db.get_articles_by_timeframe(hours=days * 24)
        analyses = db.get_recent_analyses(limit=100)
        
        if format_type == 'json':
            export_data = {
                'export_date': datetime.now(timezone.utc).isoformat(),
                'timeframe_days': days,
                'articles': articles,
                'analyses': analyses,
                'stats': db.get_enhanced_stats()
            }
            
            response = jsonify(export_data)
            response.headers['Content-Disposition'] = f'attachment; filename=watchfuleye_export_{datetime.now().strftime("%Y%m%d")}.json'
            return response
        
        elif format_type == 'csv':
            # Create CSV response (simplified)
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write articles
            writer.writerow(['Type', 'ID', 'Title', 'Category', 'Sentiment', 'Created'])
            for article in articles:
                writer.writerow([
                    'Article',
                    article.get('id', ''),
                    article.get('title', ''),
                    article.get('category', ''),
                    article.get('sentiment_score', ''),
                    article.get('created_at', '')
                ])
            
            response = app.response_class(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=watchfuleye_export_{datetime.now().strftime("%Y%m%d")}.csv'}
            )
            return response
            
    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({'error': 'Export failed'}), 500

def get_time_ago(dt):
    """Calculate human-readable time difference"""
    now = datetime.now(timezone.utc)
    if dt.tzinfo:
        dt = dt.replace(tzinfo=None)
    
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"

@app.errorhandler(404)
def not_found(error):
    """Custom 404 handler"""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(429)
def rate_limit_handler(error):
    """Custom rate limit handler"""
    return jsonify({
        'error': 'Rate limit exceeded',
        'message': 'Too many requests, please slow down',
        'retry_after': 60
    }), 429

@app.errorhandler(500)
def internal_error(error):
    """Custom 500 handler"""
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

# Main execution block moved to end of file to ensure all routes are registered

@app.route('/analysis/<int:analysis_id>')
@limiter.limit("30 per minute")
@handle_database_error
def view_structured_analysis(analysis_id):
    """View full structured analysis with beautiful formatting"""
    try:
        analyses = db.get_recent_analyses(limit=1000)
        analysis = next((a for a in analyses if a['id'] == analysis_id), None)
        
        if not analysis:
            return render_template('error.html', 
                                 error_title="Analysis Not Found",
                                 error_message=f"Analysis #{analysis_id} could not be found."), 404
        
        # Parse the raw JSON response if available
        structured_data = None
        if analysis.get('raw_response_json'):
            try:
                structured_data = json.loads(analysis['raw_response_json'])
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse raw_response_json for analysis {analysis_id}")
        
        # Format timestamp
        if analysis.get('timestamp'):
            try:
                dt = datetime.fromisoformat(analysis['timestamp'].replace('Z', '+00:00'))
                analysis['timestamp_formatted'] = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
                analysis['time_ago'] = get_time_ago(dt)
            except:
                pass
        
        return render_template('analysis_detail.html', 
                             analysis=analysis,
                             structured_data=structured_data)
        
    except Exception as e:
        logger.error(f"Error viewing analysis {analysis_id}: {e}")
        return render_template('error.html',
                             error_title="Server Error",
                             error_message="Failed to load analysis details."), 500

@app.route('/api/analysis/<int:analysis_id>/structured')
@limiter.limit("60 per minute")
@handle_database_error
def get_structured_analysis_data(analysis_id):
    """Get structured analysis data as JSON"""
    try:
        analyses = db.get_recent_analyses(limit=1000)
        analysis = next((a for a in analyses if a['id'] == analysis_id), None)
        
        if not analysis:
            return jsonify({'error': 'Analysis not found'}), 404
        
        # Parse structured data
        structured_data = None
        if analysis.get('raw_response_json'):
            try:
                structured_data = json.loads(analysis['raw_response_json'])
            except json.JSONDecodeError:
                pass
        
        return jsonify({
            'analysis_id': analysis_id,
            'structured_data': structured_data,
            'metadata': {
                'timestamp': analysis.get('timestamp'),
                'model_used': analysis.get('model_used'),
                'article_count': analysis.get('article_count'),
                'processing_time': analysis.get('processing_time'),
                'quality_score': analysis.get('quality_score')
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching structured analysis {analysis_id}: {e}")
        return jsonify({'error': 'Failed to fetch structured analysis'}), 500

@app.route('/api/telegram-logs')
@cache.cached(timeout=30)  # Shorter cache for live updates
@limiter.limit("60 per minute")  # More frequent updates allowed
def get_telegram_logs():
    """Get recent Telegram bot logs with enhanced status"""
    try:
        # Read the last 200 lines from the bot log file for better context
        log_lines = []
        log_file = None
        
        # Try different log files in order of preference
        for filename in ['bot.log', 'test.log', 'backend.log']:
            try:
                with open(filename, 'r') as f:
                    log_lines = f.readlines()[-200:]
                    log_file = filename
                break
            except FileNotFoundError:
                continue
        
        if not log_lines:
            return jsonify({
                'success': False,
                'message': 'No log files found (bot.log, test.log, backend.log)',
                'data': [],
                'status': {
                    'bot_running': False,
                    'last_activity': None,
                    'configuration_status': 'unknown'
                }
            })
        
        # Parse and format log entries
        logs = []
        for line in log_lines:
            # Parse the log line (assuming standard format)
            try:
                # Handle different log formats
                if ' - ' in line and len(line.split(' - ')) >= 3:
                    parts = line.split(' - ', 2)
                    timestamp = parts[0].strip()
                    level_logger = parts[1].strip()
                    message = parts[2].strip()
                    
                    # Extract just the level from "logger - LEVEL" format
                    if ' - ' in level_logger:
                        level = level_logger.split(' - ')[-1]
                    else:
                        level = level_logger
                        
                    logs.append({
                        'timestamp': timestamp,
                        'level': level,
                        'message': message
                    })
                else:
                    logs.append({
                        'timestamp': '',
                        'level': 'INFO',
                        'message': line.strip()
                    })
            except Exception:
                # If parsing fails, just add the raw line
                logs.append({
                    'timestamp': '',
                    'level': 'INFO',
                    'message': line.strip()
                })
        
        # Analyze status from logs
        status = analyze_bot_status(logs)
        
        return jsonify({
            'success': True,
            'data': logs,
            'log_file': log_file,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Error fetching Telegram logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to fetch Telegram logs'
        }), 500

def analyze_bot_status(logs):
    """Analyze bot status from logs"""
    # Find recent activity (last 10 minutes)
    recent_cutoff = datetime.now() - timedelta(minutes=10)

    has_recent_activity = False
    last_successful_send = None
    configuration_errors = []
    telegram_errors = []

    for log in reversed(logs):  # Check newest first
        try:
            # Parse timestamp
            if log['timestamp']:
                log_time = datetime.strptime(log['timestamp'], '%Y-%m-%d %H:%M:%S,%f')

                if log_time > recent_cutoff:
                    has_recent_activity = True

                # Check for successful telegram sends
                if 'Telegram message sent successfully' in log['message']:
                    if not last_successful_send:
                        last_successful_send = log['timestamp']

                # Check for configuration errors
                if log['level'] == 'ERROR' and (
                    'Configuration validation failed' in log['message'] or 'Bot token' in log['message']
                ):
                    configuration_errors.append(log['message'])

                # Check for telegram errors
                if log['level'] == 'ERROR' and 'Telegram' in log['message']:
                    telegram_errors.append(log['message'])
        except Exception:
            continue

    # Determine overall status
    if configuration_errors:
        bot_status = 'configuration_error'
    elif telegram_errors:
        bot_status = 'telegram_error'
    elif last_successful_send:
        bot_status = 'active'
    elif has_recent_activity:
        bot_status = 'running'
    else:
        bot_status = 'inactive'

    return {
        'bot_running': has_recent_activity,
        'status': bot_status,
        'last_successful_send': last_successful_send,
        'configuration_errors': configuration_errors[-3:],  # Last 3 errors
        'telegram_errors': telegram_errors[-3:],  # Last 3 errors
        'has_recent_activity': has_recent_activity,
    }

@app.route('/api/chat', methods=['POST'])
def ai_chat():
    """AI Chat endpoint with RAG functionality for querying articles"""
    try:
        data = request.json
        query = data.get('query', '')
        use_rag = data.get('use_rag', True)
        timeframe = data.get('timeframe', None)  # optional: '2d', '7d', '30d'
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        response_text = ""
        sources = []
        
        if use_rag:
            tf = timeframe if isinstance(timeframe, str) else None
            # Auto-recency for "today" queries under search mode
            if bool(data.get('use_search')):
                ql = (query or '').lower()
                if any(k in ql for k in ['today', 'last 24', 'last 24h', 'now', 'this morning', 'this afternoon', 'tonight']):
                    tf = '2d'
            dynamic_limit = 24 if bool(data.get('use_search')) else 12
            sources, context_text = execute_search_rag(query, tf, limit=dynamic_limit)
            
            # Helper: tokenize query and compute simple relevance/coverage
            def _tokenize_query(q: str) -> List[str]:
                stop = {
                    'the','a','an','and','or','but','of','to','in','on','for','with','by','at','as','is','are','was','were','be','been','being',
                    'this','that','these','those','it','its','from','about','into','over','after','before','between','through','during','without','within',
                    'what','who','whom','which','when','where','why','how','can','could','should','would','may','might','will','shall','do','does','did'
                }
                toks = re.findall(r"[A-Za-z][A-Za-z\-']{1,}", q.lower())
                return [t for t in toks if t not in stop]

            def _score_text(text: str, terms: List[str]) -> int:
                text_l = (text or '').lower()
                return sum(1 for t in terms if t in text_l)

            def _compute_coverage(sources_list: List[dict], terms: List[str]) -> Tuple[float, Set[str]]:
                matched: Set[str] = set()
                for s in sources_list:
                    blob = " ".join(filter(None, [s.get('title'), s.get('description'), s.get('preview')]))
                    blob_l = (blob or '').lower()
                    for t in terms:
                        if t in blob_l:
                            matched.add(t)
                ratio = (len(matched) / max(1, len(terms))) if terms else 1.0
                return ratio, matched

            def _contains_market_terms(text: str) -> bool:
                text_l = (text or '').lower()
                market_terms = ['market', 'stock', 'equity', 'bond', 'yield', 'investor', 'risk premium', 'mxn', 'cop', 'currency', 'fx', 'volatility']
                return any(mt in text_l for mt in market_terms)
            query_terms = _tokenize_query(query)
            
            # Generate AI response using OpenAI with RAG context
            try:
                if context_text:
                    # Number the articles for citation
                    numbered_context = ""
                    for i, s in enumerate(sources, 1):
                        numbered_context += f"[{i}] {s['title']} - {s['source']} ({s.get('category')})\n"
                        if s.get('preview'):
                            numbered_context += f"    {s['preview']}\n"
                        if s.get('sentiment_analysis_text'):
                            numbered_context += f"    Analysis: {(s.get('sentiment_analysis_text') or '')[:100]}...\n"
                        numbered_context += "\n"
                    
                    # Evidence-gated prompt
                    coverage_ratio, matched_terms = _compute_coverage(sources, query_terms)
                    market_in_snippets = _contains_market_terms(" ".join([s.get('title','')+" "+(s.get('preview') or '') for s in sources[:6]]))
                    guardrails = []
                    guardrails.append("Only include claims supported by the snippets below. If the entity or detail requested is not present in the snippets, say so briefly and suggest broadening the search; do not infer or speculate.")
                    if not market_in_snippets:
                        guardrails.append("Do not include market or investor implications unless the snippets mention markets/financial context.")
                    guardrails.append("Avoid absolute terms like 'today' unless shown verbatim; prefer timing mentioned in snippets or omit.")

                    prompt = f"""You are WatchfulEye, a premium intelligence platform. Query: "{query}"

SOURCES:
{numbered_context}

Write a concise, conversational briefing:
- 1–2 short paragraphs in clear prose (no bullet lists)
- Objective, fact-first tone; avoid speculation
- Ground every statement in the provided sources; do NOT include bracket citations
- Prefer fresh, time-relevant developments; note timing/recency when useful
- End with one crisp takeaway sentence
 
 Guardrails:
 - {guardrails[0]}
 - {guardrails[1] if len(guardrails) > 1 else ''}
 - {guardrails[2] if len(guardrails) > 2 else ''}
"""
                else:
                    # If no articles found, get recent ones anyway for context
                    conn = sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db'))
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT id, title, source, category, created_at, sentiment_score 
                        FROM articles 
                        ORDER BY created_at DESC 
                        LIMIT 5
                    ''')
                    recent = cursor.fetchall()
                    conn.close()
                    
                    recent_context = "Recent intelligence in our database:\n"
                    for r in recent:
                        recent_context += f"• {r['title']} ({r['source']}) - {r['category']}\n"
                    
                    prompt = f"""You are WatchfulEye, a premium intelligence platform with 36,000+ articles. The user asked: "{query}"

Use the RECENT INTELLIGENCE below as context and respond in 1–2 short paragraphs.
No bullet lists. Objective tone. Do NOT include bracket citations. Be fresh and specific.

RECENT INTELLIGENCE:
{recent_context}
"""

                # Use the single configured OpenRouter model only (no fallbacks)
                if OPENROUTER_API_KEY:
                    headers = {
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://diatombot.xyz"
                    }
                    
                    router_response = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json={
                            "model": OPENROUTER_MODEL,
                                                    "messages": [
                            {"role": "system", "content": "You are WatchfulEye, an expert intelligence analyst assistant."},
                            {"role": "user", "content": prompt}
                        ],
                            "max_tokens": 700,
                            "temperature": 0.3
                        },
                        timeout=30
                    )
                    
                    if router_response.status_code != 200:
                        raise RuntimeError(f"OpenRouter error {router_response.status_code}")
                    result = router_response.json()
                    response_text = result['choices'][0]['message']['content']
                    # Basic post-check: if we had virtually no coverage, force a non-claiming response
                    try:
                        coverage_ratio, matched_terms = _compute_coverage(sources, query_terms)
                        if coverage_ratio < 0.2 and sources:
                            response_text = ("I couldn't find direct evidence in the sources for the specific details you asked about. "
                                             "Consider broadening the search scope or enabling live web search to pull fresher coverage.\n\n"
                                             "Takeaway: Additional sourcing is needed before making claims.")
                    except Exception:
                        pass
                else:
                    raise RuntimeError("OpenRouter API key not configured")
                
            except Exception as ai_error:
                print(f"OpenAI error: {ai_error}")
                # Fallback response if LLM fails – provide concise, well-formatted bullets with citations
                if sources:
                    try:
                        # Build concise trend bullets with bracket citations
                        trend_lines = []
                        for i, article in enumerate(sources[:5], 1):
                            title = (article.get('title') or 'Untitled').strip()
                            desc = (article.get('preview') or article.get('description') or '').strip()
                            if len(desc) > 140:
                                desc = desc[:140].rstrip() + '…'
                            trend_lines.append(f"- {title} [{i}] — {desc}")

                        categories = [s.get('category') for s in sources if s.get('category')]
                        top_category = max(set(categories), key=categories.count) if categories else None
                        sentiments = [s.get('sentiment_score') for s in sources if s.get('sentiment_score') is not None]
                        avg_sent = sum(sentiments)/len(sentiments) if sentiments else 0.0
                        sentiment_label = 'Positive' if avg_sent > 0.1 else 'Negative' if avg_sent < -0.1 else 'Neutral'

                        response_parts = [
                            "Key Trends:",
                            *trend_lines,
                            "",
                            "Key Insights:",
                            f"- {len(sources)} sources across {len(set(categories)) if categories else 0} categories",
                            f"- Overall sentiment: {sentiment_label}",
                        ]
                        if top_category:
                            response_parts.append(f"- Dominant theme: {top_category}")
                        response_text = "\n".join(response_parts)
                    except Exception:
                        # Final minimal fallback
                        response_text = f"Key Trends:\n" + "\n".join([f"- {s.get('title','Untitled')}" for s in sources[:5]])
                else:
                    # Always produce a high-quality answer using the most recent articles as context
                    try:
                        conn = sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db'))
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT id, title, description, source, category, created_at, url
                            FROM articles 
                            ORDER BY created_at DESC 
                            LIMIT 6
                        ''')
                        fallback = cursor.fetchall()
                        conn.close()
                        if fallback:
                            trend_lines = []
                            for i, a in enumerate(fallback, 1):
                                snip = (a['description'] or '')[:140]
                                if snip and len(snip) == 140:
                                    snip = snip.rstrip() + '…'
                                trend_lines.append(f"- {a['title']} [{i}] — {snip}")
                            response_text = "\n".join(["Key Trends:", *trend_lines])
                            sources = [
                                {
                                    'id': a['id'], 'title': a['title'], 'description': a['description'],
                                    'source': a['source'], 'category': a['category'], 'created_at': a['created_at'],
                                    'url': a['url'], 'preview': (a['description'] or '')[:150]
                                } for a in fallback
                            ]
                        else:
                            response_text = "No data available yet. Please try again in a moment."
                    except Exception:
                        response_text = "Temporarily unable to analyze. Please retry."
        
        else:
            # Non-RAG response - still use the single OpenRouter model only
            if not OPENROUTER_API_KEY:
                return jsonify({'error': 'Model unavailable'}), 503
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://diatombot.xyz"
            }
            router_response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={
                    "model": OPENROUTER_MODEL,
                    "messages": [
                        {"role": "system", "content": "You are WatchfulEye, an expert intelligence analyst assistant specializing in news analysis, sentiment tracking, and market intelligence."},
                        {"role": "user", "content": query}
                    ],
                    "max_tokens": 300,
                    "temperature": 0.7
                },
                timeout=30
            )
            if router_response.status_code != 200:
                return jsonify({'error': 'Model unavailable'}), 503
            result = router_response.json()
            response_text = result['choices'][0]['message']['content']
        
        # Attach lightweight verification metadata (UI can ignore safely)
        try:
            terms = _tokenize_query(query)
            cov, matched = _compute_coverage(sources, terms)
            verification = 'verified' if cov >= 0.5 and len(sources) >= 2 else ('partial' if cov >= 0.2 else 'unverified')
        except Exception:
            verification, cov, matched = 'unknown', 0.0, set()

        return jsonify({
            'response': response_text,
            'sources': sources,
            'query': query,
            'use_rag': use_rag,
            'verification': verification,
            'coverage': cov,
            'matched_terms': list(matched),
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        print(f"Error in AI chat: {e}")
        return jsonify({'error': 'Internal server error'}), 500 

# ==============================================================================
# CONVERSATIONAL CHAT ENDPOINTS
# ==============================================================================

@app.route('/api/chat/conversations', methods=['GET'])
@login_required
def get_conversations():
    """Get all conversations for the current user"""
    try:
        user_id = session.get('user_id')
        include_archived = request.args.get('include_archived', 'false').lower() == 'true'
        
        conversations = db.get_conversations(user_id, include_archived=include_archived)
        
        return jsonify({
            'conversations': conversations,
            'count': len(conversations),
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/conversations', methods=['POST'])
@login_required
def create_conversation():
    """Create a new conversation"""
    try:
        user_id = session.get('user_id')
        data = request.json or {}
        
        title = data.get('title')
        metadata = data.get('metadata', {})
        
        # Add default metadata
        metadata['created_via'] = 'web'
        metadata['angle'] = data.get('angle', 'neutral')
        metadata['horizon'] = data.get('horizon', 'medium')
        
        conversation_id = db.create_conversation(user_id, title=title, metadata=metadata)
        
        return jsonify({
            'conversation_id': conversation_id,
            'created': True,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/conversations/<int:conversation_id>', methods=['GET'])
@login_required
def get_conversation(conversation_id):
    """Get a specific conversation with messages"""
    try:
        user_id = session.get('user_id')
        
        # Verify ownership
        conversations = db.get_conversations(user_id, include_archived=True)
        if not any(c['id'] == conversation_id for c in conversations):
            return jsonify({'error': 'Conversation not found'}), 404
        
        messages = db.get_conversation_messages(conversation_id)
        
        return jsonify({
            'conversation_id': conversation_id,
            'messages': messages,
            'count': len(messages),
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/conversations/<int:conversation_id>', methods=['PATCH'])
@login_required
def update_conversation(conversation_id):
    """Update a conversation (rename, archive, etc.)"""
    try:
        user_id = session.get('user_id')
        data = request.json or {}
        
        # Verify ownership
        conversations = db.get_conversations(user_id, include_archived=True)
        if not any(c['id'] == conversation_id for c in conversations):
            return jsonify({'error': 'Conversation not found'}), 404
        
        success = db.update_conversation(
            conversation_id,
            title=data.get('title'),
            archived=data.get('archived'),
            metadata=data.get('metadata')
        )
        
        return jsonify({
            'updated': success,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error updating conversation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/conversations/<int:conversation_id>', methods=['DELETE'])
@login_required
def delete_conversation(conversation_id):
    """Delete a conversation"""
    try:
        user_id = session.get('user_id')
        
        # Verify ownership
        conversations = db.get_conversations(user_id, include_archived=True)
        if not any(c['id'] == conversation_id for c in conversations):
            return jsonify({'error': 'Conversation not found'}), 404
        
        success = db.delete_conversation(conversation_id)
        
        return jsonify({
            'deleted': success,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/conversations/<int:conversation_id>/messages', methods=['POST'])
@login_required
def add_message_to_conversation(conversation_id):
    """Add a message to a conversation and get AI response"""
    try:
        user_id = session.get('user_id')
        data = request.json or {}
        
        # Verify ownership
        conversations = db.get_conversations(user_id, include_archived=True)
        if not any(c['id'] == conversation_id for c in conversations):
            return jsonify({'error': 'Conversation not found'}), 404
        
        user_message = data.get('content', '').strip()
        if not user_message:
            return jsonify({'error': 'Message content is required'}), 400
        
        angle = data.get('angle', 'neutral')
        horizon = data.get('horizon', 'medium')
        use_rag = data.get('use_rag', True)
        
        # Add user message to conversation
        user_message_id = db.add_message(
            conversation_id,
            role='user',
            content=user_message,
            metadata={'angle': angle, 'horizon': horizon}
        )
        
        # Get conversation history for context
        messages = db.get_conversation_messages(conversation_id, limit=10)
        
        # Build context from previous messages
        conversation_context = []
        for msg in messages[-5:]:  # Last 5 messages for context
            if msg['role'] in ['user', 'assistant']:
                conversation_context.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
        
        # Generate AI response
        response_text = ""
        sources = []
        context_text = ""
        
        if use_rag:
            trending_keywords = ['trending', 'today', 'latest', 'recent', 'now', 'current', "what's new"]
            is_trending_query = any(keyword in user_message.lower() for keyword in trending_keywords)
            tf = '2d' if is_trending_query else None
            sources, context_text = execute_search_rag(user_message, tf, limit=10)
        
        # Prepare system prompt based on angle
        angle_prompts = {
            'market': "You are WatchfulEye, focused on market analysis, trading opportunities, and financial implications.",
            'policy': "You are WatchfulEye, focused on policy analysis, regulatory changes, and governmental implications.",
            'tech': "You are WatchfulEye, focused on technology trends, innovation, and technical developments.",
            'neutral': "You are WatchfulEye, an expert intelligence analyst providing comprehensive analysis."
        }
        
        horizon_context = {
            'near': "Focus on immediate impacts and short-term implications (days to weeks).",
            'medium': "Consider medium-term effects and developments (weeks to months).",
            'long': "Analyze long-term strategic implications and trends (months to years)."
        }
        
        system_prompt = angle_prompts.get(angle, angle_prompts['neutral'])
        # Identity for conversational answers
        system_prompt += " You are WatchfulEye, a sharp intelligence assistant."
        system_prompt += f" {horizon_context.get(horizon, horizon_context['medium'])}"
        
        # Core intelligence: be contextually smart
        system_prompt += (
            " INTELLIGENCE RULES:"
            " - Greetings (hey/hi/hello): Respond warmly in <20 words, suggest what you can help with"
            " - Casual questions: Be conversational, not robotic"
            " - No sources? Say 'I don't have data on that' then suggest enabling web search or broadening query"
            " - Always sound confident, never hedge with 'could not confirm' or 'recommend checking elsewhere'"
        )
        
        if data.get('use_search'):
            system_prompt += (
                " LIVE WEB SEARCH ACTIVE:"
                " - Price queries: Give direct answer 'As of [time], [asset] is $X.XX' + 1 sentence why it moved. NO hedging."
                " - Trending queries: Lead with top 2-3 items, be punchy"
                " - Each query is fresh - ignore conversation history for facts/prices"
                " - If search fails: 'Unable to fetch live data, try again' (don't apologize excessively)"
                " - Be assertive and concise. Users want speed, not disclaimers."
            )
        
        # Build the messages for the AI
        ai_messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history
        for ctx_msg in conversation_context[:-1]:  # Exclude the last user message we just added
            ai_messages.append(ctx_msg)
        
        # Add current query with context if available
        if use_rag and context_text:
            current_prompt = f"""Query: {user_message}

INTELLIGENCE SOURCES:
{context_text}

Provide a premium analysis with:
• Direct answers backed by specific article citations [1], [2], etc.
• Key patterns and anomalies detected
• {horizon.capitalize()}-term implications ({angle} focus)
• Actionable recommendations
• Risk factors to monitor

Be concise, insightful, and reference articles by number."""
        else:
            current_prompt = user_message
        
        ai_messages.append({"role": "user", "content": current_prompt})
        
        # Generate AI response
        try:
            if OPENROUTER_API_KEY:
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://diatombot.xyz"
                }
                
                router_response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": OPENROUTER_MODEL,
                        "messages": ai_messages,
                        "max_tokens": 2000,
                        "temperature": 0.7,
                        "stream": False  # We'll implement streaming later
                    },
                    timeout=30
                )
                
                result = router_response.json()
                response_text = result['choices'][0]['message']['content']
                model_used = OPENROUTER_MODEL
            else:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=ai_messages,
                    max_tokens=2000,
                    temperature=0.7
                )
                
                response_text = response.choices[0].message.content
                model_used = "gpt-3.5-turbo"
            
        except Exception as ai_error:
            logger.error(f"AI generation error: {ai_error}")
            response_text = "I apologize, but I'm having trouble generating a response right now. Please try again."
            model_used = "fallback"
        
        # Add assistant message to conversation
        assistant_message_id = db.add_message(
            conversation_id,
            role='assistant',
            content=response_text,
            metadata={
                'sources': sources,
                'angle': angle,
                'horizon': horizon,
                'use_rag': use_rag
            },
            model_used=model_used
        )
        
        return jsonify({
            'user_message_id': user_message_id,
            'assistant_message_id': assistant_message_id,
            'response': response_text,
            'sources': sources,
            'angle': angle,
            'horizon': horizon,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in conversation chat: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/conversations/search', methods=['GET'])
@login_required
def search_conversations():
    """Search conversations"""
    try:
        user_id = session.get('user_id')
        query = request.args.get('q', '').strip()
        
        if not query:
            return jsonify({'error': 'Search query is required'}), 400
        
        results = db.search_conversations(user_id, query)
        
        return jsonify({
            'results': results,
            'query': query,
            'count': len(results),
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error searching conversations: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/conversations/<int:conversation_id>/pin', methods=['POST'])
@login_required
def pin_conversation(conversation_id):
    """Pin a conversation"""
    try:
        user_id = session.get('user_id')
        data = request.json or {}
        position = data.get('position', 0)
        
        success = db.pin_conversation(user_id, conversation_id, position)
        
        return jsonify({
            'pinned': success,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error pinning conversation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/conversations/<int:conversation_id>/unpin', methods=['POST'])
@login_required
def unpin_conversation(conversation_id):
    """Unpin a conversation"""
    try:
        user_id = session.get('user_id')
        
        success = db.unpin_conversation(user_id, conversation_id)
        
        return jsonify({
            'unpinned': success,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error unpinning conversation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/conversations/<int:conversation_id>/messages/stream', methods=['POST'])
@login_required
def stream_message_to_conversation(conversation_id):
    """Stream a message response to a conversation using SSE"""
    try:
        user_id = session.get('user_id')
        data = request.json or {}
        
        # Verify ownership
        conversations = db.get_conversations(user_id, include_archived=True)
        if not any(c['id'] == conversation_id for c in conversations):
            return jsonify({'error': 'Conversation not found'}), 404
        
        user_message = data.get('content', '').strip()
        if not user_message:
            return jsonify({'error': 'Message content is required'}), 400
        
        angle = data.get('angle', 'neutral')
        horizon = data.get('horizon', 'medium')
        use_rag = data.get('use_rag', True)
        
        # Comprehensive logging for debugging chat pipeline
        logger.info(f"[CHAT] New request: query='{user_message[:100]}...', use_rag={use_rag}, use_search={data.get('use_search')}, angle={angle}, horizon={horizon}")
        
        def generate(tf=None):
            """Generator function for SSE streaming with function calling architecture"""
            try:
                start_time = time.time()  # Track response time
                if tf is None:
                    tf = data.get('timeframe')

                # Send initial event
                yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation_id})}\n\n"
                
                # Add user message to conversation
                user_message_id = db.add_message(
                    conversation_id,
                    role='user',
                    content=user_message,
                    metadata={'angle': angle, 'horizon': horizon}
                )
                
                yield f"data: {json.dumps({'type': 'user_message_saved', 'message_id': user_message_id})}\n\n"
                
                # Get conversation history for context
                messages = db.get_conversation_messages(conversation_id, limit=10)
                
                # Build context from previous messages
                conversation_context = []
                for msg in messages[-5:]:  # Last 5 messages for context
                    if msg['role'] in ['user', 'assistant']:
                        conversation_context.append({
                            'role': msg['role'],
                            'content': msg['content']
                        })
                
                # ============================================
                # PHASE 1: TOOL DECISION CALL
                # ============================================

                # Determine which model we'll use (affects behavior, not tools)
                will_use_web_search_model = data.get('use_search', False)

                # Build system prompt explaining capabilities
                if will_use_web_search_model:
                    # Perplexity: Web search is built into the model
                    decision_system_prompt = (
                        "You are WatchfulEye, a financial intelligence assistant with web search capability. "
                        "You have access to a search_rag tool for additional context from our article database. "
                        "Web search is always available through the model itself. "
                        "Decide if you need additional context: "
                        "- For general questions: no tools needed "
                        "- For historical/financial context: use search_rag"
                    )
                else:
                    # Claude: Regular LLM, can use RAG for context
                    decision_system_prompt = (
                        "You are WatchfulEye, a financial intelligence assistant. "
                        "You have access to a search_rag tool for context from our article database. "
                        "Decide if you need additional context from our database: "
                        "- For general questions: no tools needed"
                        "- For historical/financial context: use search_rag"
                    )

                decision_messages = [
                    {"role": "system", "content": decision_system_prompt}
                ]

                # Add conversation history (last 3 messages for context)
                for ctx_msg in conversation_context[-3:]:
                    decision_messages.append(ctx_msg)

                # Add current user message
                decision_messages.append({"role": "user", "content": user_message})

                # Call OpenRouter with tools
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://watchfuleye.us"
                }

                decision_response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": OPENROUTER_MODEL,  # Always use Claude for consistent decision-making
                        "messages": decision_messages,
                        "tools": TOOL_DEFINITIONS,
                        "tool_choice": "auto",  # Let LLM decide
                        "max_tokens": 500,
                        "temperature": 0.3  # Lower temp for more consistent decisions
                    },
                                    timeout=15
                                )

                decision_result = decision_response.json()
                tool_calls = decision_result['choices'][0]['message'].get('tool_calls', [])

                logger.info(f"[CHAT] Tool decision: {len(tool_calls)} tools called: {[t['function']['name'] for t in tool_calls]}")

                # ============================================
                # PHASE 2: EXECUTE TOOLS
                # ============================================

                sources = []
                context_text = ""
                web_search_enabled = data.get('use_search', False)  # Frontend toggle = model choice

                # Execute any called tools (currently only search_rag)
                for tool_call in tool_calls:
                    function_name = tool_call['function']['name']
                    function_args = json.loads(tool_call['function']['arguments'])

                    if function_name == "search_rag":
                        query = function_args.get('query', user_message)
                        timeframe = function_args.get('timeframe')
                        logger.info(f"[CHAT] Executing search_rag: query='{query}', timeframe={timeframe}")
                        sources, context_text = execute_search_rag(query, timeframe)

                # Send sources to frontend
                as_of_iso = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
                mode_label = 'web' if web_search_enabled else 'corpus'
                yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'as_of': as_of_iso, 'mode': mode_label})}\n\n"

                # ============================================
                # PHASE 3: FINAL RESPONSE CALL
                # ============================================

                # Build final system prompt
                if web_search_enabled:
                    # Perplexity: Web search is built into the model
                    final_system_prompt = (
                        "You're WatchfulEye. Talk like a sharp analyst, not a dictionary. "
                        f"Today is {datetime.utcnow().strftime('%A, %B %d, %Y at %I:%M %p UTC')}. "
                        "\n\nSTYLE RULES:"
                        "\n- Write like you're briefing a colleague over coffee, not writing a report"
                        "\n- Lead with the punchline, then explain"
                        "\n- Use 'I' when relevant (e.g., 'I found 12 sources...')"
                        "\n- Short paragraphs (2-3 sentences max)"
                        "\n- No bullet lists, no citations in brackets, no robotic phrasing"
                        "\n- For simple questions (e.g., 'who did X?'), answer in 1-2 sentences first, then context"
                        "\n- Sound confident and conversational, never stiff or formal"
                    )
                else:
                    # Claude: Regular LLM
                    final_system_prompt = (
                        "You're WatchfulEye. Talk like a sharp analyst, not a dictionary. "
                        f"Today is {datetime.utcnow().strftime('%A, %B %d, %Y at %I:%M %p UTC')}. "
                        "\n\nSTYLE RULES:"
                        "\n- Write like you're briefing a colleague over coffee, not writing a report"
                        "\n- Lead with the punchline, then explain"
                        "\n- Use 'I' when relevant (e.g., 'I checked our database...')"
                        "\n- Short paragraphs (2-3 sentences max)"
                        "\n- No bullet lists, no citations in brackets, no robotic phrasing"
                        "\n- For simple questions (e.g., 'who did X?'), answer in 1-2 sentences first, then context"
                        "\n- Sound confident and conversational, never stiff or formal"
                    )

                # Add angle/horizon context
                if angle != 'neutral':
                    final_system_prompt += f" Focus on {angle} implications."
                if horizon != 'medium':
                    horizon_map = {
                        'near': 'short-term (days to weeks)',
                        'long': 'long-term (months to years)'
                    }
                    final_system_prompt += f" Emphasize {horizon_map.get(horizon, 'medium-term')} impacts."

                final_messages = [{"role": "system", "content": final_system_prompt}]

                # Add conversation history (FULL history, LLM decides what's relevant)
                for ctx_msg in conversation_context[:-1]:
                    final_messages.append(ctx_msg)

                # Add current query with context (if any)
                if context_text:
                    current_prompt = f"""Query: {user_message}

INTELLIGENCE SOURCES:
{context_text}

Provide a concise analysis. Reference key details from sources. End with one crisp takeaway sentence."""
                else:
                    current_prompt = user_message
 
                final_messages.append({"role": "user", "content": current_prompt})
                
                # Select model (Perplexity for web search, Claude otherwise)
                model_to_use = PERSPECTIVES_MODEL if web_search_enabled else OPENROUTER_MODEL
                logger.info(f"[CHAT] Final response: model={model_to_use}, sources={len(sources)}, context={len(context_text)} chars")
                
                # Stream final response
                full_response = ""
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": model_to_use,
                        "messages": final_messages,
                        "max_tokens": 2000,
                        "temperature": 0.6,
                        "stream": True
                    },
                    stream=True,
                    timeout=30
                )

                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data: '):
                            data_str = line_str[6:]
                            if data_str == '[DONE]':
                                break
                            try:
                                chunk = json.loads(data_str)
                                if 'choices' in chunk:
                                    delta = chunk['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        content = delta['content']
                                        full_response += content
                                        yield f"data: {json.dumps({'type': 'chunk', 'content': content})}\n\n"
                            except json.JSONDecodeError:
                                continue
                    
                # Save assistant message
                assistant_message_id = db.add_message(
                    conversation_id,
                    role='assistant',
                    content=full_response,
                    metadata={
                        'sources': sources,
                        'tools_used': [t['function']['name'] for t in tool_calls],
                        'mode': mode_label,
                        'model': model_to_use
                    },
                    model_used=model_to_use
                )

                # Log response completion
                elapsed = time.time() - start_time
                logger.info(f"[CHAT] Response complete: {len(full_response)} chars in {elapsed:.2f}s, tools={len(tool_calls)}")
                
                # Send completion event
                yield f"data: {json.dumps({'type': 'complete', 'message_id': assistant_message_id})}\n\n"
                
            except Exception as e:
                logger.error(f"Error in streaming: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive'
            }
        )
        
    except Exception as e:
        logger.error(f"Error in streaming conversation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ollama-analysis', methods=['GET', 'POST', 'OPTIONS'])
@limiter.limit("10 per minute")
def ollama_analysis():
    """Generate AI analysis using OpenRouter instead of Ollama"""
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        return '', 200
        
    # Check if this is a GET request and return documentation
    if request.method == 'GET':
        return jsonify({
            'info': 'AI analysis endpoint',
            'usage': 'Send a POST request with article data in JSON format',
            'required_fields': ['title', 'description'],
            'optional_fields': ['source', 'category', 'sentiment_score']
        })
    
    # Handle POST request
    try:
        data = request.json
        article_title = data.get('title', '')
        article_description = data.get('description', '')
        article_source = data.get('source', '')
        article_category = data.get('category', '')
        sentiment_score = data.get('sentiment_score', 0)
        sentiment_label = 'positive' if sentiment_score > 0.1 else 'negative' if sentiment_score < -0.1 else 'neutral'
        
        if not article_title or not article_description:
            return jsonify({'error': 'Article title and description are required'}), 400
        
        # Prepare prompt for analysis (STRICT JSON schema; concise, pragmatic tone)
        json_schema = r'''
{
  "insights": ["3–5 concise bullets"],
  "market": [
    {"asset": "string", "direction": "up|down|vol ↑", "magnitude": "+2pct", "rationale": "string"}
  ],
  "geopolitics": ["2–4 bullets"],
  "playbook": ["3–5 concrete actions"],
  "risks": ["2–4 bullets"],
  "timeframes": {"near": "days/weeks", "medium": "months", "long": "12m+"},
  "signals": ["3–5 short items"],
  "commentary": "One short paragraph (2–4 sentences) titled Analyst View: provide a clear stance and rationale. Keep it professional and non‑partisan; prefer market‑focused framing."
}
'''

        prompt = (
            "You are an expert intelligence analyst producing market-pragmatic analysis.\n\n"
            "Task: Produce an actionable analysis of the article below. Do not fact-check externally; "
            "treat the article as working context. Avoid generic disclaimers. Keep tone pragmatic, policy-aware, and investor-oriented.\n\n"
            "Hard rules about numbers:\n"
            "- Only output numeric deltas/percentages if explicitly present in the ARTICLE INFORMATION or computed from our database.\n"
            "- Otherwise use categorical signals: up, down, volatile, uncertain.\n"
            "- When you present a number, the bullet must indicate provenance and include a source_id.\n\n"
            "Return ONLY a JSON object with the following keys:\n" + json_schema + "\n\n"
            "Constraints:\n"
            "- Base reasoning on the ARTICLE INFORMATION only.\n"
            "- Be specific and concise; one sentence per bullet; avoid meta.\n"
            "- Ensure the output is valid JSON with double quotes, no trailing text.\n\n"
            f"ARTICLE INFORMATION:\nTitle: {article_title}\nDescription: {article_description}\n"
            f"Source: {article_source}\nCategory: {article_category}\nSentiment: {sentiment_label}\n"
        )
        
        # Use only the server-configured OpenRouter key (single source of truth)
        effective_key = OPENROUTER_API_KEY

        if not effective_key:
            logger.error("OpenRouter API key missing (no Authorization header and no env key)")
            return jsonify({'success': False, 'error': 'OpenRouter API key not configured'}), 500
        
        # Make request to OpenRouter API
        try:
            logger.info(f"Sending request to OpenRouter API for article: {article_title}")
            
            # Match chat endpoint header behavior exactly
            headers = {
                "Authorization": f"Bearer {effective_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://diatombot.xyz"
            }
            
            # Stream response from OpenRouter and forward as SSE
            def generate_stream():
                try:
                    with requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json={
                            "model": OPENROUTER_MODEL,
                            "messages": [
                                {"role": "system", "content": "You are an expert market analyst and intelligence specialist."},
                                {"role": "user", "content": prompt}
                            ],
                            "max_tokens": 700,
                            "temperature": 0.5,
                            "stream": True
                        },
                        stream=True,
                        timeout=60
                    ) as r:
                        if r.status_code != 200:
                            yield f"data: {json.dumps({'type': 'error', 'status': r.status_code})}\n\n"
                            return
                        buffer = ''
                        for line in r.iter_lines(decode_unicode=True):
                            if not line:
                                continue
                            if line.startswith('data: '):
                                payload = line[6:]
                                if payload.strip() == '[DONE]':
                                    break
                                try:
                                    obj = json.loads(payload)
                                    delta = obj.get('choices', [{}])[0].get('delta', {}).get('content')
                                    if delta:
                                        buffer += delta
                                        yield f"data: {json.dumps({'type': 'chunk', 'content': delta})}\n\n"
                                except Exception:
                                    continue
                        # Final parse attempt
                        structured = _try_parse_json(buffer) or _try_parse_json(_repair_json_text(buffer)) or _salvage_json_text(buffer)
                        yield f"data: {json.dumps({'type': 'complete', 'structured': structured, 'raw': buffer})}\n\n"
                except requests.exceptions.RequestException as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

            return Response(stream_with_context(generate_stream()), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
                
        except requests.exceptions.RequestException as e:
            # If OpenRouter server is not reachable
            logger.error(f"OpenRouter server error: {e}")
            return jsonify({
                'success': False,
                'error': f"OpenRouter connection error: {str(e)}",
                'fallback_analysis': "The OpenRouter AI service is not available. Please check your internet connection."
            }), 503
            
    except Exception as e:
        logger.error(f"Error in AI analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'fallback_analysis': "An error occurred while generating the analysis."
        }), 500

@app.route('/api/admin/user-stats')
@require_auth
def get_user_stats():
    """Get user statistics - admin only endpoint"""
    try:
        # Check if user is admin
        if g.current_user.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Get user statistics
        user_stats = db.get_user_statistics()
        
        return jsonify({
            'success': True,
            'data': user_stats
        })
        
    except Exception as e:
        logger.error(f"Error getting user statistics: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get user statistics'}), 500

@app.route('/api/admin/users', methods=['GET'])
@require_auth
def get_all_users():
    """Get list of all users - admin only endpoint"""
    try:
        # Check if user is admin
        if g.current_user.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Get user list
        users = db.get_all_users()
        
        return jsonify({
            'success': True,
            'data': users
        })
        
    except Exception as e:
        logger.error(f"Error getting user list: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get user list'}), 500

@app.route('/api/admin/users/<int:user_id>', methods=['GET'])
@require_auth
def get_user_details(user_id):
    """Get details for a specific user - admin only endpoint"""
    try:
        # Check if user is admin
        if g.current_user.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Get user details
        user = db.get_user_by_id(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'success': True,
            'data': user
        })
        
    except Exception as e:
        logger.error(f"Error getting user details: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get user details'}), 500

@app.route('/api/admin/users/<int:user_id>/status', methods=['POST'])
@require_auth
def update_user_status(user_id):
    """Update user active status - admin only endpoint"""
    try:
        # Check if user is admin
        if g.current_user.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized access'}), 403
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        is_active = data.get('is_active')
        if is_active is None:
            return jsonify({'error': 'Active status not provided'}), 400
        
        # Cannot deactivate your own account
        if user_id == g.current_user.get('id'):
            return jsonify({'error': 'Cannot modify your own account status'}), 400
        
        # Update user status
        success = db.update_user_status(user_id, is_active)
        
        if not success:
            return jsonify({'error': 'User not found or update failed'}), 404
        
        return jsonify({
            'success': True,
            'message': f"User {'activated' if is_active else 'deactivated'} successfully"
        })
        
    except Exception as e:
        logger.error(f"Error updating user status: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update user status'}), 500

# Serve React app in production (moved to very end to prevent intercepting API routes)
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    """Serve React application in production"""
    if path != "" and os.path.exists(os.path.join('frontend/build', path)):
        return send_from_directory('frontend/build', path)
    else:
        return send_from_directory('frontend/build', 'index.html')

# Main execution block - MUST be at the very end after all routes are defined
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"🌐 Starting WatchfulEye Web Interface on port {port}")
    logger.info(f"🔧 Debug mode: {debug}")
    logger.info(f"🛡️  Security headers enabled")
    logger.info(f"⚡ Rate limiting enabled")
    logger.info(f"💾 Caching enabled")
    logger.info(f"📊 Admin routes registered")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        threaded=True
    )
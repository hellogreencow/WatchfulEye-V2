#!/usr/bin/env python3
"""
Enhanced Flask web application for WatchfulEye Intelligence System.
Features: Security headers, caching, API endpoints, real-time updates, comprehensive monitoring.
"""

from flask import Flask, render_template, jsonify, request, redirect, url_for, session, send_file, g, send_from_directory, Response, stream_with_context
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
import dotenv
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
import threading
import math
import psycopg
from tenacity import retry, stop_after_attempt, wait_exponential

# Ensure .env is loaded before reading environment variables
try:
    dotenv.load_dotenv(dotenv_path=os.environ.get('ENV_FILE', '.env'))
except Exception:
    # Non-fatal if dotenv is not present
    pass

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

# Load configuration from environment variables with fallbacks
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', 'your_telegram_bot_token_here')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', 'your_chat_id_here')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', 'your_openai_api_key_here')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
OPENROUTER_MODEL = os.environ.get('OPENROUTER_MODEL', 'anthropic/claude-3.5-sonnet')
# Optional model for political perspectives (Perplexity Sonar)
PERSPECTIVES_MODEL = os.environ.get('PERSPECTIVES_MODEL', 'perplexity/sonar')
# voyage-3-large support for embeddings (RAG)
VOYAGE_API_KEY = os.environ.get('VOYAGE_API_KEY', '')
EMBEDDINGS_PROVIDER = os.environ.get('EMBEDDINGS_PROVIDER', 'voyage' if VOYAGE_API_KEY else 'openai').lower()
# Target embedding dimension for Voyage vectors; must match DB vector length (e.g., article_embeddings_voyage)
# Supabase currently has article_embeddings_voyage as vector(1024)
VOYAGE_EMBED_DIM = int(os.environ.get('VOYAGE_EMBED_DIM', '1024'))
# Enhanced RAG with Rerank-2.5 support
ENABLE_RERANK = os.environ.get('ENABLE_RERANK', 'true').lower() == 'true'
VOYAGE_MODEL = os.environ.get('VOYAGE_MODEL', 'voyage-3.5-lite')  # voyage-3.5-lite, voyage-3.5, voyage-3-large
ENABLE_CHUNK_RAG = os.environ.get('ENABLE_CHUNK_RAG', 'false').lower() == 'true'
# HNSW search effort (higher improves recall with slight latency increase)
HNSW_EF_SEARCH = int(os.environ.get('HNSW_EF_SEARCH', '96'))
# allow disabling semantic vector search entirely (e.g., if Postgres/pgvector not available)
DISABLE_SEMANTIC = os.environ.get('DISABLE_SEMANTIC', 'false').lower() == 'true'

# Supabase-only mode (no direct Postgres credentials required)
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
SUPABASE_DB_PASSWORD = os.environ.get('SUPABASE_DB_PASSWORD')
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

# Respect explicit PG_DSN only. Do not auto-construct DSN to avoid wrong/no-password errors
PG_DSN = os.environ.get('PG_DSN', '').strip()

# If a valid PG_DSN is configured, prefer direct Postgres over Supabase REST for vectors
if PG_DSN:
    USE_SUPABASE_ONLY = False

# Initialize Flask app with security configurations
from cors_config import configure_cors

app = Flask(__name__, static_folder="frontend/build/static")
app = configure_cors(app)
try:
    from werkzeug.middleware.proxy_fix import ProxyFix  # type: ignore
    # Trust Cloudflare Tunnel/Nginx X-Forwarded-* so Flask treats requests as HTTPS
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # type: ignore
except Exception:
    pass
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
app.config['JSON_AS_ASCII'] = False  # ensure UTF-8 JSON
app.config['DB_PATH'] = DB_PATH

# Security configurations
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# Optional cookie domain for cross-subdomain sessions (e.g., .watchfuleye.us)
COOKIE_DOMAIN = os.environ.get('COOKIE_DOMAIN', '').strip()
if COOKIE_DOMAIN:
    app.config['SESSION_COOKIE_DOMAIN'] = COOKIE_DOMAIN

# Initialize extensions
cache = Cache(app, config={'CACHE_TYPE': 'simple', 'CACHE_DEFAULT_TIMEOUT': 300})
compress = Compress(app)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
limiter.init_app(app)

# Initialize database
db = NewsDatabase(db_path=DB_PATH)

# =====================
# Vector DB init (pgvector)
# =====================
def _init_pgvector():
    try:
        with psycopg.connect(PG_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                # OpenAI table (1536 dims)
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS article_embeddings (
                        article_id INTEGER PRIMARY KEY,
                        embedding vector(1536),
                        created_at TIMESTAMPTZ DEFAULT now()
                    );
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_article_embeddings_hnsw ON article_embeddings USING hnsw (embedding);")
                # Voyage table (2048 dims) kept separate to avoid dimension conflict
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS article_embeddings_voyage (
                        article_id INTEGER PRIMARY KEY,
                        embedding vector(2048),
                        created_at TIMESTAMPTZ DEFAULT now()
                    );
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_article_embeddings_voyage_hnsw ON article_embeddings_voyage USING hnsw (embedding);")
        logger.info("pgvector ready")
    except Exception as e:
        logger.error(f"pgvector init failed: {e}")

_init_pgvector()

# =====================
# SQLite FTS5 init for BM25-style lexical search
# =====================
def _init_sqlite_fts() -> None:
    try:
        with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as conn:
            cur = conn.cursor()
            # Create FTS5 table linked to articles
            cur.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                    title, description, category, sentiment_analysis_text, content,
                    content='articles', content_rowid='id'
                );
                """
            )
            # Initial populate if empty
            cur.execute("SELECT (SELECT count(*) FROM articles_fts) = 0")
            is_empty = cur.fetchone()[0] == 1
            if is_empty:
                cur.execute(
                    "INSERT INTO articles_fts(rowid, title, description, category, sentiment_analysis_text, content) "
                    "SELECT id, IFNULL(title,''), IFNULL(description,''), IFNULL(category,''), IFNULL(sentiment_analysis_text,''), IFNULL(content,'') FROM articles"
                )
            # Triggers to keep in sync
            cur.executescript(
                """
                CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
                  INSERT INTO articles_fts(rowid, title, description, category, sentiment_analysis_text, content)
                  VALUES (new.id, IFNULL(new.title,''), IFNULL(new.description,''), IFNULL(new.category,''), IFNULL(new.sentiment_analysis_text,''), IFNULL(new.content,''));
                END;
                CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
                  INSERT INTO articles_fts(articles_fts, rowid) VALUES('delete', old.id);
                END;
                CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
                  INSERT INTO articles_fts(articles_fts, rowid) VALUES('delete', old.id);
                  INSERT INTO articles_fts(rowid, title, description, category, sentiment_analysis_text, content)
                  VALUES (new.id, IFNULL(new.title,''), IFNULL(new.description,''), IFNULL(new.category,''), IFNULL(new.sentiment_analysis_text,''), IFNULL(new.content,''));
                END;
                """
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"FTS5 init failed or unavailable: {e}")

_init_sqlite_fts()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _embed_text_openai(text: str) -> list:
    import openai as _openai
    # Prefer text-embedding-3-small (1536 dims) for cost/perf; switch if needed.
    resp = _openai.embeddings.create(model="text-embedding-3-small", input=text[:8000])
    vec = resp.data[0].embedding
    # Normalize to unit length for cosine distance
    try:
        norm = math.sqrt(sum((x * x) for x in vec)) or 1.0
        vec = [x / norm for x in vec]
    except Exception:
        pass
    return vec

def _embed_text_voyage(text: str) -> list:
    """Embed with enhanced Voyage model (configurable) when configured."""
    if not VOYAGE_API_KEY:
        raise RuntimeError("VOYAGE_API_KEY not configured")
    import voyageai as _voy
    client = _voy.Client(api_key=VOYAGE_API_KEY)
    res = client.embed(texts=[text[:8000]], model=VOYAGE_MODEL)
    vec = res.embeddings[0]
    # Align to configured dimension to match DB column length
    if isinstance(vec, list) and VOYAGE_EMBED_DIM > 0:
        vec = vec[:VOYAGE_EMBED_DIM]
    # Normalize to unit length for cosine distance
    try:
        norm = math.sqrt(sum((x * x) for x in vec)) or 1.0
        vec = [x / norm for x in vec]
    except Exception:
        pass
    return vec

def _rerank_with_voyage(query: str, documents: List[str], top_k: int = 10) -> List[Tuple[int, float]]:
    """Rerank documents using Voyage Rerank-2.5 for improved relevance."""
    if not VOYAGE_API_KEY or not ENABLE_RERANK:
        return list(enumerate([1.0] * len(documents)))[:top_k]
    
    try:
        import voyageai as _voy
        client = _voy.Client(api_key=VOYAGE_API_KEY)
        
        # Prepare query-document pairs for reranking
        query_document_pairs = [(query, doc) for doc in documents]
        
        # Use Rerank-2.5 model
        result = client.rerank(
            query=query,
            documents=documents,
            model="rerank-2.5",
            top_k=top_k
        )
        
        # Extract reranked indices and scores
        reranked_results = []
        for item in result.results:
            reranked_results.append((item.index, item.relevance_score))
        
        logger.info(f"Reranked {len(documents)} documents with Rerank-2.5")
        return reranked_results
        
    except Exception as e:
        logger.warning(f"Rerank-2.5 failed, using original order: {e}")
        return list(enumerate([1.0] * len(documents)))[:top_k]

def _embed_text(text: str) -> list:
    """Provider-aware embed with fallback to OpenAI if voyage fails."""
    if EMBEDDINGS_PROVIDER == 'voyage' and VOYAGE_API_KEY:
        try:
            return _embed_text_voyage(text)
        except Exception as e:
            logger.warning(f"voyage embed failed, falling back to OpenAI: {e}")
    return _embed_text_openai(text)

# -----------------
# Chunking helpers
# -----------------
def _split_into_chunks(text: str, target_tokens: int = 900, overlap_tokens: int = 120) -> List[str]:
    if not text:
        return []
    # Simple token approximation by words; production can switch to tiktoken-compatible tokenizer
    words = text.split()
    step = max(1, target_tokens - overlap_tokens)
    chunks: List[str] = []
    for start in range(0, len(words), step):
        part = words[start:start + target_tokens]
        if not part:
            break
        chunks.append(" ".join(part))
        if start + target_tokens >= len(words):
            break
    return chunks

def _get_or_create_article_chunks(article: dict) -> None:
    if not ENABLE_CHUNK_RAG:
        return
    try:
        # Pull a longer content field if available; fallback to title+description
        body = (article.get('content') or '')
        if not body:
            body = f"{article.get('title','')}. {article.get('description','') or ''}"
        chunks = _split_into_chunks(body)
        if not chunks:
            return
        # Upsert each chunk embedding into Postgres (preferred) or Supabase REST
        if PG_DSN:
            with psycopg.connect(PG_DSN, autocommit=True) as conn:
                with conn.cursor() as cur:
                    for idx, chunk in enumerate(chunks):
                        vec = _embed_text(chunk)
                        if not vec:
                            continue
                        cur.execute(
                            """
                            INSERT INTO public.article_chunks (article_id, chunk_index, content, embedding)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (article_id, chunk_index)
                            DO UPDATE SET content = EXCLUDED.content, embedding = EXCLUDED.embedding
                            """,
                            (article['id'], idx, chunk, vec)
                        )
        elif USE_SUPABASE_ONLY and supabase_client:
            for idx, chunk in enumerate(chunks):
                vec = _embed_text(chunk)
                if not vec:
                    continue
                supabase_client.table('article_chunks').upsert({
                    'article_id': article['id'],
                    'chunk_index': idx,
                    'content': chunk,
                    'embedding': vec
                }).execute()
    except Exception as e:
        logger.warning(f"chunk upsert failed for article {article.get('id')}: {e}")

def _semantic_chunk_candidates(query: str, k: int = 12) -> List[Tuple[int, int]]:
    if not ENABLE_CHUNK_RAG:
        return []
    try:
        qvec = _embed_text(query)
        if PG_DSN:
            with psycopg.connect(PG_DSN) as conn:
                with conn.cursor() as cur:
                    # Tune HNSW search effort
                    try:
                        cur.execute("SET hnsw.ef_search = %s", (HNSW_EF_SEARCH,))
                    except Exception:
                        pass
                    cur.execute(
                        """
                        SELECT article_id, chunk_index
                        FROM public.article_chunks
                        ORDER BY embedding <=> %s
                        LIMIT %s
                        """,
                        (qvec, k)
                    )
                    return [(int(r[0]), int(r[1])) for r in cur.fetchall()]
        elif USE_SUPABASE_ONLY and supabase_client:
            res = supabase_client.rpc('semantic_candidates_chunks', {
                'q': qvec,
                'k': k
            }).execute()
            return [(int(r['article_id']), int(r['chunk_index'])) for r in (res.data or [])]
    except Exception as e:
        logger.warning(f"semantic chunk search failed: {e}")
    return []

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
            text = f"{article.get('title','')}. {article.get('description','') or ''}"
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
                    return list(row[0])
        # Build text block for embedding
        text = f"{article.get('title','')}. {article.get('description','') or ''}"
        vec = _embed_text(text)
        with psycopg.connect(PG_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                table = 'article_embeddings_voyage' if EMBEDDINGS_PROVIDER == 'voyage' and VOYAGE_API_KEY else 'article_embeddings'
                cur.execute(
                    f"INSERT INTO {table}(article_id, embedding) VALUES (%s, %s) ON CONFLICT (article_id) DO UPDATE SET embedding = EXCLUDED.embedding",
                    (article['id'], vec)
                )
        return vec
    except Exception as e:
        logger.error(f"embedding error for article {article.get('id')}: {e}")
        return []

def _semantic_candidates(query: str, limit: int = 12) -> List[int]:
    """Get semantic search candidates using pgvector with optional Rerank-2.5 enhancement."""
    try:
        qvec = _embed_text(query)
        table = 'article_embeddings_voyage' if EMBEDDINGS_PROVIDER == 'voyage' and VOYAGE_API_KEY else 'article_embeddings'
        
        # Get initial candidates (more than needed for reranking)
        initial_limit = min(limit * 3, 50) if ENABLE_RERANK else limit
        
        if USE_SUPABASE_ONLY and supabase_client and table == 'article_embeddings_voyage':
            res = supabase_client.rpc('semantic_candidates_voyage', {
                'q': qvec,
                'limit_k': initial_limit
            }).execute()
            initial_results = [int(r['article_id']) for r in (res.data or [])]
        else:
            with psycopg.connect(PG_DSN) as conn:
                with conn.cursor() as cur:
                    # Set HNSW ef_search for better recall when using direct PG
                    try:
                        cur.execute("SET hnsw.ef_search = %s", (HNSW_EF_SEARCH,))
                    except Exception:
                        pass
                    cur.execute(
                        f"""
                        SELECT article_id
                        FROM {table}
                        ORDER BY embedding <=> %s
                        LIMIT %s
                        """,
                        (qvec, initial_limit)
                    )
                    initial_results = [r[0] for r in cur.fetchall()]
        
        if not initial_results:
            return []
        
        # If reranking is enabled, enhance with Rerank-2.5
        if ENABLE_RERANK and VOYAGE_API_KEY:
            try:
                # Fetch article content for reranking
                with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as sqlite_conn:
                    sqlite_conn.row_factory = sqlite3.Row
                    sqlite_cur = sqlite_conn.cursor()
                    placeholders = ','.join(['?'] * len(initial_results))
                    sqlite_cur.execute(
                        f"SELECT id, title, description FROM articles WHERE id IN ({placeholders})",
                        initial_results
                    )
                    articles = sqlite_cur.fetchall()
                
                # Create document texts for reranking
                documents = []
                for article in articles:
                    doc_text = f"{article['title']}. {article['description'] or ''}"
                    documents.append(doc_text)
                
                # Rerank documents
                reranked_indices = _rerank_with_voyage(query, documents, top_k=limit)
                
                # Map back to article IDs
                reranked_ids = [initial_results[idx] for idx, _ in reranked_indices]
                logger.info(f"Enhanced semantic search with Rerank-2.5: {len(reranked_ids)} results")
                return reranked_ids
                
            except Exception as e:
                logger.warning(f"Reranking failed, using original semantic results: {e}")
                return initial_results[:limit]
        else:
            # Return original semantic results
            return initial_results[:limit]
            
    except Exception as e:
        logger.error(f"semantic search failed: {e}")
        return []

def _pgvector_count() -> int:
    try:
        table = 'article_embeddings_voyage' if EMBEDDINGS_PROVIDER == 'voyage' and VOYAGE_API_KEY else 'article_embeddings'
        with psycopg.connect(PG_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                return int(cur.fetchone()[0])
    except Exception:
        return 0

def _seed_article_embeddings(max_items: int = 50):
    try:
        with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT id, title, description FROM articles ORDER BY created_at DESC LIMIT ?", (max_items,))
            rows = cur.fetchall()
            for row in rows:
                _get_or_create_article_embedding({'id': row['id'], 'title': row['title'], 'description': row['description']})
    except Exception as e:
        logger.warning(f"embedding seed failed: {e}")

def _fts_query_rows(query: str, limit: int = 50, days: int = 0) -> List[sqlite3.Row]:
    try:
        with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            time_filter = "" if days <= 0 else " AND a.created_at >= datetime('now', ?)"
            params: List[Any] = []
            # Simple query string normalization for MATCH
            q = query.replace('"', ' ').strip()
            sql = (
                "SELECT a.*, bm25(articles_fts) AS bm25_score "
                "FROM articles_fts JOIN articles a ON a.id = articles_fts.rowid "
                "WHERE articles_fts MATCH ?" + time_filter + " ORDER BY bm25(articles_fts) LIMIT ?"
            )
            params.append(q)
            if days > 0:
                params.append(f"-{days} days")
            params.append(limit)
            cur.execute(sql, params)
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
    # Optional chunk-level semantic candidates
    chunk_pairs: List[Tuple[int, int]] = []
    if ENABLE_CHUNK_RAG and not DISABLE_SEMANTIC:
        try:
            chunk_pairs = _semantic_chunk_candidates(user_message, k=60)
        except Exception:
            chunk_pairs = []
    fts_rows = _fts_query_rows(user_message, limit=60, days=days)
    # Build candidate id set
    id_to_feats: Dict[int, Dict[str, Any]] = {}
    for rank, aid in enumerate(semantic_ids):
        id_to_feats.setdefault(aid, {})['sem_rank'] = rank
    for rank, (aid, _chunk_idx) in enumerate(chunk_pairs):
        # Keep best (lowest) chunk rank per article
        feats = id_to_feats.setdefault(aid, {})
        feats['chunk_rank'] = min(feats.get('chunk_rank', rank), rank)
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
        s_chunk = sem_score(feats.get('chunk_rank')) if ENABLE_CHUNK_RAG else 0.0
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
        fused = 0.40 * s_sem + (0.05 * s_chunk if ENABLE_CHUNK_RAG else 0.0) + 0.30 * s_bm + 0.20 * s_rec + 0.05 * s_src
        scored.append((fused, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:limit]]

def _backfill_embeddings_daemon():
    # Background thread to backfill embeddings for entire corpus
    while True:
        try:
            with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                # Provider-aware, idempotent backfill: select recent articles and upsert embeddings
                # We intentionally do not rely on a local embeddings table (may not exist in SQLite)
                # _get_or_create_article_embedding will read from/write to the correct provider table
                cur.execute(
                    "SELECT a.id, a.title, a.description FROM articles a ORDER BY a.created_at DESC LIMIT 200"
                )
                rows = cur.fetchall()
            if not rows:
                time.sleep(30)
                continue
            for row in rows:
                art = {'id': row['id'], 'title': row['title'], 'description': row['description']}
                _get_or_create_article_embedding(art)
                # Also generate chunk embeddings if enabled
                try:
                    with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as c2:
                        c2.row_factory = sqlite3.Row
                        curx = c2.cursor()
                        curx.execute('SELECT content FROM articles WHERE id = ? LIMIT 1', (row['id'],))
                        crow = curx.fetchone()
                        if crow:
                            _get_or_create_article_chunks({**art, 'content': crow['content']})
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"embedding backfill loop error: {e}")
            time.sleep(10)

# One-shot reconciliation to populate Voyage embeddings for items present in OpenAI table but missing in Voyage table
def _reconcile_embeddings_once():
    try:
        if not (EMBEDDINGS_PROVIDER == 'voyage' and VOYAGE_API_KEY):
            return
        missing_ids: List[int] = []
        # Prefer direct Postgres if available
        try:
            with psycopg.connect(PG_DSN) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT e.article_id
                        FROM article_embeddings e
                        LEFT JOIN article_embeddings_voyage v ON v.article_id = e.article_id
                        WHERE v.article_id IS NULL
                        ORDER BY e.article_id DESC
                        LIMIT 500
                        """
                    )
                    rows = cur.fetchall()
                    missing_ids = [int(r[0]) for r in rows]
        except Exception:
            # Supabase-only mode: fetch small batches via REST
            if USE_SUPABASE_ONLY and supabase_client:
                try:
                    base = supabase_client.table('article_embeddings').select('article_id').limit(1000).execute()
                    voy = supabase_client.table('article_embeddings_voyage').select('article_id').limit(1000).execute()
                    base_ids = {int(r['article_id']) for r in (getattr(base, 'data', None) or [])}
                    voy_ids = {int(r['article_id']) for r in (getattr(voy, 'data', None) or [])}
                    missing_ids = [i for i in base_ids if i not in voy_ids]
                except Exception:
                    missing_ids = []
            else:
                missing_ids = []
        if not missing_ids:
            return
        # For each missing id, pull title/description from SQLite and upsert via provider-aware helper
        try:
            with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                for aid in missing_ids:
                    try:
                        cur.execute("SELECT id, title, description FROM articles WHERE id = ? LIMIT 1", (aid,))
                        row = cur.fetchone()
                        if row:
                            _get_or_create_article_embedding({'id': row['id'], 'title': row['title'], 'description': row['description']})
                    except Exception:
                        continue
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"reconciliation run error: {e}")

# Start background embedder
try:
    threading.Thread(target=_backfill_embeddings_daemon, daemon=True).start()
    # Kick a one-time reconciliation shortly after startup
    threading.Thread(target=_reconcile_embeddings_once, daemon=True).start()
except Exception as e:
    logger.warning(f"failed to start backfill thread: {e}")

# Redundant CORS instance removed; configuration happens in cors_config.configure_cors

# Initialize Chimera API
try:
    from chimera_api import init_chimera_api
    init_chimera_api(app)
    logger.info("Chimera API initialized successfully")
except ImportError as e:
    logger.warning(f"Chimera API not available: {e}")
except Exception as e:
    logger.error(f"Failed to initialize Chimera API: {e}")

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

# Authentication middleware
def login_required(f):
    """Decorator to require authentication for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check Bearer token first
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Remove 'Bearer ' prefix
            user = db.validate_session(token)
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
    """Get current user from session token"""
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]  # Remove 'Bearer ' prefix
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

        out = {k: v for k, v in parsed.items() if k in targets}
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
                        "max_tokens": 500,
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
                                    buffer += delta
                                    yield f"data: {json.dumps({'type': 'chunk', 'content': delta})}\n\n"
                            except Exception:
                                continue
                    parsed = _try_parse_json(buffer) or _try_parse_json(_repair_json_text(buffer)) or _salvage_json_text(buffer)
                    if isinstance(parsed, dict):
                        parsed = {k: v for k, v in parsed.items() if k in targets}
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

        if PrismEngine is None:
            return jsonify({'error': 'PrismEngine not available'}), 500

        data = request.get_json(silent=True) or {}
        limit = data.get('limit')

        # Reuse existing prism engine if initialized via Chimera API
        prism = getattr(current_app, 'prism_engine', None)
        if prism is None:
            prism = PrismEngine(
                db_path=current_app.config.get('DB_PATH', 'news_bot.db'),
                openai_api_key=OPENAI_API_KEY
            )

        updated = prism.reindex_article_embeddings(limit=limit)
        return jsonify({'success': True, 'updated': updated})
    except Exception as e:
        logger.error(f"Error during embeddings reindex: {e}", exc_info=True)
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

@app.route('/')
def index():
    """Root route serving basic information about the API"""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>WatchfulEye API</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; }
            h1 { color: #333; border-bottom: 1px solid #eee; padding-bottom: 10px; }
            .endpoint { background: #f5f5f5; padding: 10px; border-radius: 5px; margin-bottom: 10px; }
            .method { display: inline-block; background: #4CAF50; color: white; padding: 2px 6px; border-radius: 3px; font-size: 14px; }
            .url { font-family: monospace; margin-left: 10px; }
            .frontend-link { display: block; margin: 20px 0; padding: 10px; background: #2196F3; color: white; text-align: center; text-decoration: none; border-radius: 5px; }
            .frontend-link:hover { background: #0b7dda; }
        </style>
    </head>
    <body>
        <h1>WatchfulEye API</h1>
        <p>This is the backend API server for WatchfulEye Intelligence System. The frontend dashboard is available at:</p>
        <a href="http://localhost:3000" class="frontend-link">Go to Dashboard (http://localhost:3000)</a>
        
        <h2>Available Endpoints:</h2>
        
        <div class="endpoint">
            <span class="method">GET</span>
            <span class="url">/api/health</span>
            <p>Health check endpoint</p>
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span>
            <span class="url">/api/articles</span>
            <p>Get latest news articles</p>
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span>
            <span class="url">/api/analyses</span>
            <p>Get latest AI analyses</p>
        </div>
        
        <div class="endpoint">
            <span class="method">GET</span>
            <span class="url">/api/stats</span>
            <p>Get system statistics</p>
        </div>
    </body>
    </html>
    """

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

@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    """User login endpoint"""
    try:
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
        
        return jsonify({
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
            },
            'session_token': session_token
        })
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    """User logout endpoint"""
    try:
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]
            db.delete_session(token)
        
        return jsonify({
            'success': True,
            'message': 'Logout successful'
        })
        
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
            # Trigger embedding on save (provider-aware) and optional chunk embeddings
            try:
                with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as conn:
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute('SELECT id, title, description, content FROM articles WHERE id = ? LIMIT 1', (int(article_id),))
                    arow = cur.fetchone()
                if arow:
                    _get_or_create_article_embedding({'id': arow['id'], 'title': arow['title'], 'description': arow['description']})
                    _get_or_create_article_chunks({'id': arow['id'], 'title': arow['title'], 'description': arow['description'], 'content': arow['content']})
            except Exception as _emb_e:
                logger.warning(f"post-save embed failed for article {article_id}: {_emb_e}")
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
        include_analysis = request.args.get('include_analysis', 'true').lower() == 'true'
        
        # Validate limit
        if limit > 100:
            limit = 100
        
        articles = db.get_recent_articles(limit=limit, category=category)
        
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
                INSERT INTO analyses (content, content_preview, model_used, article_count, raw_response_json)
                VALUES (?, ?, ?, ?, ?)
            ''', (content, content_preview, model_used, article_count, raw_response_json))
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
    stats = db.get_enhanced_stats()
    categories = stats.get('categories', {})
    
    # Format for frontend
    category_list = []
    for category, data in categories.items():
        category_list.append({
            'name': category,
            'display_name': category.title(),
            'count': data['count'],
            'avg_sentiment': round(data['avg_sentiment'], 2),
            'avg_confidence': round(data['avg_confidence'], 2)
        })
    
    # Sort by count
    category_list.sort(key=lambda x: x['count'], reverse=True)
    
    return jsonify({'categories': category_list})

@app.route('/api/search')
@limiter.limit("10 per minute")
def search_articles():
    """Search articles API endpoint"""
    try:
        # Get search query from URL parameters
        query = request.args.get('q', '')
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Search query is required',
                'data': []
            }), 400
        
        # Use the database search functionality
        articles = db.search_nodes(query)
        
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
            # Vector-first hybrid retrieval (semantic + FTS), fallback to recency
            def _tokenize_simple(q: str) -> List[str]:
                toks = re.findall(r"[A-Za-z][A-Za-z\-']{1,}", (q or '').lower())
                return list({t for t in toks if len(t) > 2})

            terms_simple = _tokenize_simple(query)
            tf = timeframe if isinstance(timeframe, str) else None
            try:
                candidate_rows = _hybrid_retrieve(query, tf, terms_simple, limit=12)
            except Exception:
                candidate_rows = []

            if not candidate_rows:
                try:
                    with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as conn2:
                        conn2.row_factory = sqlite3.Row
                        cur2 = conn2.cursor()
                        cur2.execute('''
                            SELECT id, title, description, source, created_at,
                                   sentiment_score, sentiment_confidence, sentiment_analysis_text,
                                   category, category_confidence, url
                            FROM articles 
                            WHERE created_at >= datetime('now', '-2 days')
                            ORDER BY created_at DESC
                            LIMIT 8
                        ''')
                        candidate_rows = cur2.fetchall()
                except Exception:
                    candidate_rows = []
            
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

            # Convert articles to list of dicts for easier processing
            sources = []
            context_text = ""
            query_terms = _tokenize_query(query)
            
            for article in candidate_rows:
                article_dict = {
                    'id': article['id'],
                    'title': article['title'],
                    'description': article['description'],
                    'source': article['source'],
                    'created_at': article['created_at'],
                    'sentiment_score': article['sentiment_score'] if 'sentiment_score' in article.keys() else None,
                    'sentiment_confidence': article['sentiment_confidence'] if 'sentiment_confidence' in article.keys() else None,
                    'sentiment_analysis_text': article['sentiment_analysis_text'] if 'sentiment_analysis_text' in article.keys() else None,
                    'category': article['category'],
                    'category_confidence': article['category_confidence'] if 'category_confidence' in article.keys() else None,
                    'url': article['url'],
                    'preview': (article['description'] or '')[:150] + ('...' if article['description'] and len(article['description']) > 150 else '')
                }
                sources.append(article_dict)
                
            # Rank and filter sources by relevance to the query
            if sources:
                ranked = []
                for s in sources:
                    blob = " ".join(filter(None, [s.get('title'), s.get('description'), s.get('preview')]))
                    score = _score_text(blob, query_terms)
                    ranked.append((score, s))
                ranked.sort(key=lambda x: x[0], reverse=True)
                # If none match, keep recent order; else keep those with score>=1 at front
                if ranked and ranked[0][0] > 0:
                    sources = [s for sc, s in ranked]
                # Build context from top 6
                for i, s in enumerate(sources[:6], 1):
                    context_text += f"[{i}] {s['title']} — {s['source']} ({(s['created_at'] or '')[:16]})\n"
                    if s.get('preview'):
                        context_text += f"    \"{s['preview'][:220]}\"\n\n"
            
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
        
        if use_rag:
            # Search for relevant articles
            conn = sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db'))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check if this is a trending/today query
            trending_keywords = ['trending', 'today', 'latest', 'recent', 'now', 'current', 'what\'s new']
            is_trending_query = any(keyword in user_message.lower() for keyword in trending_keywords)
            
            if is_trending_query:
                # Get recent articles for trending queries
                cursor.execute('''
                    SELECT id, title, description, source, created_at,
                           sentiment_score, sentiment_confidence, category, url
                    FROM articles 
                    WHERE created_at >= datetime('now', '-2 days')
                    ORDER BY created_at DESC 
                    LIMIT 10
                ''')
            else:
                # Enhanced search with angle and horizon considerations
                search_query = f"%{user_message.lower()}%"
                cursor.execute('''
                SELECT id, title, description, source, created_at, 
                       sentiment_score, sentiment_confidence, sentiment_analysis_text,
                       category, category_confidence, url
                FROM articles 
                WHERE LOWER(title) LIKE ? 
                   OR LOWER(description) LIKE ? 
                   OR LOWER(sentiment_analysis_text) LIKE ?
                   OR LOWER(category) LIKE ?
                ORDER BY created_at DESC 
                LIMIT 5
            ''', (search_query, search_query, search_query, search_query))
            
            articles = cursor.fetchall()
            conn.close()
            
            # Build context from articles
            context_text = ""
            for article in articles:
                article_dict = {
                    'id': article['id'],
                    'title': article['title'],
                    'description': article['description'],
                    'source': article['source'],
                    'created_at': article['created_at'],
                    'category': article['category'],
                    'url': article['url']
                }
                sources.append(article_dict)
                
                context_text += f"Article: {article['title']}\n"
                context_text += f"Description: {article['description']}\n"
                context_text += f"Category: {article['category']}\n\n"
        
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
        system_prompt += f" {horizon_context.get(horizon, horizon_context['medium'])}"
        if data.get('use_search'):
            system_prompt += " You have live web-search backing in addition to our article corpus. Prefer the freshest high-authority sources when relevant and synthesize with in-corpus articles."
        
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
                        "max_tokens": 500,
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
                    max_tokens=500,
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
        
        def generate(tf=None):
            """Generator function for SSE streaming"""
            try:
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
                
                # RAG search if enabled
                sources = []
                context_text = ""
                
                if use_rag:
                    # Helper: expand query with simple synonyms for better recall
                    def expand_query_terms(q: str) -> List[str]:
                        ql = q.lower()
                        terms = set()
                        # Basic tokenization
                        for tok in re.findall(r"[a-zA-Z0-9']{3,}", ql):
                            terms.add(tok)
                        # Ukraine-focused synonyms
                        if 'ukraine' in ql or 'kyiv' in ql or 'kiev' in ql:
                            terms.update(['ukraine', 'kyiv', 'kiev', 'zelensky', 'donbas', 'donetsk', 'luhansk', 'kharkiv', 'odessa', 'odesa', 'crimea', 'black sea', 'dnipro'])
                        if 'russia' in ql or 'kremlin' in ql:
                            terms.update(['russia', 'kremlin', 'moscow'])
                        return list(terms)

                    # Helper: run keyword search with optional timeframe window
                    def search_articles_within(days: int, terms: List[str]) -> List[sqlite3.Row]:
                        with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as conn2:
                            conn2.row_factory = sqlite3.Row
                            cur = conn2.cursor()
                            # Build dynamic WHERE for multiple terms using OR across fields
                            where_clauses = []
                            params: List[str] = []
                            for t in terms:
                                like = f"%{t}%"
                                where_clauses.append("LOWER(title) LIKE ?")
                                params.append(like)
                                where_clauses.append("LOWER(description) LIKE ?")
                                params.append(like)
                                where_clauses.append("LOWER(sentiment_analysis_text) LIKE ?")
                                params.append(like)
                                where_clauses.append("LOWER(category) LIKE ?")
                                params.append(like)
                            where_sql = " OR ".join(where_clauses) if where_clauses else "1=1"
                            time_filter = "created_at >= datetime('now', ?)" if days > 0 else "1=1"
                            time_param = f"-{days} days" if days > 0 else None
                            sql = f'''
                                SELECT 
                                    id, title, description, source, created_at,
                                    sentiment_score, sentiment_confidence, sentiment_analysis_text,
                                    category, category_confidence, url,
                                    julianday('now') - julianday(created_at) as age_days
                                FROM articles 
                                WHERE ({where_sql}) AND {time_filter}
                                ORDER BY created_at DESC
                                LIMIT 12
                            '''
                            if time_param is None:
                                cur.execute(sql, params)
                            else:
                                cur.execute(sql, params + [time_param])
                            return cur.fetchall()

                    # Determine initial mode (semantic first, then keyword/recency fallback)
                    # 1) Vector search for top-k candidate article_ids (ensure we have embeddings to search)
                    semantic_ids: List[int] = []
                    if not DISABLE_SEMANTIC:
                        if _pgvector_count() == 0:
                            # warm start: embed a recent slice so first query doesn't miss
                            _seed_article_embeddings(100)
                        semantic_ids = _semantic_candidates(user_message, limit=12)
                    q_terms = expand_query_terms(user_message)
                    trending_keywords = ['trending', 'today', 'latest', 'recent', 'now', 'current', "what's new", 'what is new', 'changes', 'last 24']
                    is_trending_query = any(keyword in user_message.lower() for keyword in trending_keywords)
                    
                    # For trending queries, always try to fetch fresh articles first
                    if is_trending_query:
                        try:
                            news_api_key = os.environ.get('NEWS_API_KEY')
                            if news_api_key:
                                import requests as req
                                news_response = req.get(
                                    'https://newsapi.org/v2/top-headlines',
                                    params={
                                        'apiKey': news_api_key,
                                        'language': 'en',
                                        'pageSize': 20,
                                        'country': 'us'
                                    },
                                    timeout=5
                                )
                                if news_response.status_code == 200:
                                    news_data = news_response.json()
                                    if news_data.get('articles'):
                                        # Store fresh articles
                                        for article in news_data['articles'][:15]:
                                            if article.get('title') and article.get('description'):
                                                try:
                                                    db.add_article(
                                                        source=article.get('source', {}).get('name', 'Unknown'),
                                                        title=article['title'],
                                                        description=article['description'],
                                                        url=article.get('url', ''),
                                                        published_at=article.get('publishedAt', datetime.utcnow().isoformat()),
                                                        content=article.get('content', article['description']),
                                                        category='general'
                                                    )
                                                except:
                                                    pass
                                        logger.info(f"Fetched {len(news_data['articles'])} fresh articles for trending query")
                        except Exception as e:
                            logger.warning(f"Failed to fetch fresh trending articles: {e}")

                    candidate_rows: List[sqlite3.Row] = []
                    if semantic_ids:
                        # Fetch those rows from SQLite by id, most recent first
                        with sqlite3.connect(app.config.get('DB_PATH', 'news_bot.db')) as conn2:
                            conn2.row_factory = sqlite3.Row
                            cur2 = conn2.cursor()
                            id_placeholders = ",".join(["?"] * len(semantic_ids))
                            cur2.execute(
                                f"SELECT * FROM articles WHERE id IN ({id_placeholders}) ORDER BY created_at DESC",
                                semantic_ids
                            )
                            candidate_rows = cur2.fetchall()
                    # Explicit timeframe override from client
                    timeframe_map = {'2d': 2, '7d': 7, '30d': 30}
                    if isinstance(tf, str) and tf in timeframe_map:
                        days = timeframe_map[tf]
                        candidate_rows = search_articles_within(days, q_terms)
                    elif is_trending_query:
                        # Recent first (2 days) regardless of keywords
                        candidate_rows = search_articles_within(2, q_terms or [''])
                    else:
                        # Progressive fallback: 2d -> 7d -> 30d
                        for days in (2, 7, 30):
                            candidate_rows = search_articles_within(days, q_terms)
                            if candidate_rows:
                                break

                    # If still empty, try on-demand fetch via NewsAPI, then retry 2d
                    if not candidate_rows:
                        try:
                            newsapi_key = os.environ.get('NEWSAPI_KEY')
                            if newsapi_key and len(user_message) >= 3:
                                resp = requests.get(
                                    'https://newsapi.org/v2/everything',
                                    params={
                                        'q': user_message,
                                        'language': 'en',
                                        'pageSize': 10,
                                        'sortBy': 'publishedAt',
                                        'from': (datetime.utcnow() - timedelta(days=2)).isoformat()
                                    },
                                    headers={'X-Api-Key': newsapi_key},
                                    timeout=15
                                )
                                if resp.status_code == 200:
                                    data_json = resp.json()
                                    articles_payload = data_json.get('articles', [])
                                    try:
                                        db.store_articles(articles_payload)
                                    except Exception:
                                        pass
                                    # retry within 2 days
                                    candidate_rows = search_articles_within(2, q_terms)
                        except Exception:
                            pass

                    # Build sources and context (with snippet-level evidence)
                    as_of_iso = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
                    mode_label = 'web' if data.get('use_search') else 'corpus'
                    # Show all sources to UI, but cap how many feed into the prompt for speed
                    prompt_source_cap = 6
                
                # Local helpers for evidence gating and coverage
                def _tokenize_query_local(q: str) -> List[str]:
                    stop = {
                        'the','a','an','and','or','but','of','to','in','on','for','with','by','at','as','is','are','was','were','be','been','being',
                        'this','that','these','those','it','its','from','about','into','over','after','before','between','through','during','without','within',
                        'what','who','whom','which','when','where','why','how','can','could','should','would','may','might','will','shall','do','does','did'
                    }
                    toks = re.findall(r"[A-Za-z][A-Za-z\-']{1,}", q.lower())
                    return [t for t in toks if t not in stop]

                def _compute_coverage_local(sources_list: List[dict], terms: List[str]) -> Tuple[float, Set[str]]:
                    matched: Set[str] = set()
                    for s in sources_list:
                        blob = " ".join(filter(None, [s.get('title'), s.get('description'), s.get('snippet')]))
                        blob_l = (blob or '').lower()
                        for t in terms:
                            if t in blob_l:
                                matched.add(t)
                    ratio = (len(matched) / max(1, len(terms))) if terms else 1.0
                    return ratio, matched

                def _contains_market_terms_local(text: str) -> bool:
                    text_l = (text or '').lower()
                    market_terms = ['market', 'stock', 'equity', 'bond', 'yield', 'investor', 'risk premium', 'mxn', 'cop', 'currency', 'fx', 'volatility']
                    return any(mt in text_l for mt in market_terms)

                query_terms_local = _tokenize_query_local(user_message)
                for idx, article in enumerate(candidate_rows, 1):
                        article_dict = {
                            'id': article['id'],
                            'title': article['title'],
                            'description': article['description'],
                            'source': article['source'],
                            'created_at': article['created_at'],
                            'sentiment_score': article['sentiment_score'] if 'sentiment_score' in article.keys() else None,
                            'sentiment_confidence': article['sentiment_confidence'] if 'sentiment_confidence' in article.keys() else None,
                            'category': article['category'],
                            'category_confidence': article['category_confidence'] if 'category_confidence' in article.keys() else None,
                            'url': article['url'],
                            'snippet': _best_snippet(article, user_message)
                        }
                        sources.append(article_dict)
                        date_str = (article['created_at'] or '')[:16]
                        # Only include top-N items in the prompt context
                        if idx <= prompt_source_cap:
                            snippet = article_dict.get('snippet') or (article['description'] or '')
                            context_text += f"[{idx}] {article['title']} — {article['source']} ({date_str})\n"
                            if snippet:
                                context_text += f"    \"{snippet[:220]}\"\n\n"
                if sources:
                    yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'as_of': as_of_iso, 'mode': mode_label})}\n\n"
                
                # Compute coverage and market gating flags
                coverage_ratio_local, matched_terms_local = _compute_coverage_local(sources, query_terms_local)
                market_flag = _contains_market_terms_local(" ".join([
                    (s.get('title') or '') + ' ' + (s.get('snippet') or '') for s in sources[:prompt_source_cap]
                ]))
                
                # Prepare system prompt (conversational, objective, no bullets, no inline citations)
                angle_prompts = {
                    'market': "You are WatchfulEye, a premium intelligence platform. Focus on market dynamics, trading signals, and financial implications. Write in concise natural paragraphs with an objective tone. No bullet lists, no inline citations, and do not output JSON.",
                    'policy': "You are WatchfulEye, a premium intelligence platform. Focus on policy shifts, regulatory changes, and governmental implications. Write in concise natural paragraphs with an objective tone. No bullet lists, no inline citations, and do not output JSON.",
                    'tech': "You are WatchfulEye, a premium intelligence platform. Focus on technology trends, innovation breakthroughs, and technical developments. Write in concise natural paragraphs with an objective tone. No bullet lists, no inline citations, and do not output JSON.",
                    'neutral': "You are WatchfulEye, a premium intelligence platform with access to 36,000+ real-time articles. Respond in concise natural paragraphs with an objective, fact-first tone. No bullet lists, no inline citations, and do not output JSON. Prefer fresh, time-relevant developments."
                }
                
                horizon_context = {
                    'near': "Focus on immediate impacts and short-term implications (days to weeks).",
                    'medium': "Consider medium-term effects and developments (weeks to months).",
                    'long': "Analyze long-term strategic implications and trends (months to years)."
                }
                
                system_prompt = angle_prompts.get(angle, angle_prompts['neutral'])
                system_prompt += f" {horizon_context.get(horizon, horizon_context['medium'])}"
                if data.get('use_search'):
                    system_prompt += " You have live web-search backing in addition to our article corpus. Prefer the freshest high-authority sources when relevant and synthesize with in-corpus articles."
                # If the request originated from the analysis modal, the user message often contains
                # trusted article context. Allow using that context as primary, and treat SOURCES as support.
                if data.get('origin') == 'analysis_modal':
                    system_prompt += " When the user includes explicit article context in their message, prioritize that context as authoritative and use SOURCES as corroboration. Do not refuse due to snippet limitations when such context is provided; produce the analysis in natural paragraphs."
                
                # Build messages for AI
                ai_messages = [{"role": "system", "content": system_prompt}]
                
                for ctx_msg in conversation_context[:-1]:
                    ai_messages.append(ctx_msg)
                
                if use_rag and context_text:
                    guardrails_lines = [
                        "Only include claims supported by the snippets below; if the requested entity or details are absent, say so briefly and suggest broadening search.",
                        "Avoid absolute timing like 'today' unless shown verbatim; otherwise prefer relative timing from snippets or omit timing.",
                    ]
                    if not market_flag:
                        guardrails_lines.append("Do not include market/investor implications unless the snippets mention financial or market context.")

                    current_prompt = f"""As of {as_of_iso}, answer the user's question strictly based on the SOURCES WITH SNIPPETS below. Do not include citations in-line.

SOURCES WITH SNIPPETS:
{context_text}

User query: {user_message}

Write a concise, conversational briefing:
- Objective, fact-first tone
- Only include claims supported by the snippets above; avoid speculation
- Mention timing if relevant (e.g., last 24 hours)
- End with one crisp takeaway sentence
- Do not output JSON

 Guardrails:
 - {guardrails_lines[0]}
 - {guardrails_lines[1] if len(guardrails_lines) > 1 else ''}
 - {guardrails_lines[2] if len(guardrails_lines) > 2 else ''}"""
                else:
                    # Non-RAG or empty context fallback. Be transparent about evidence absence.
                    current_prompt = f"""{user_message}
 
If you lack source snippets for the requested details, say so briefly and propose enabling live web search or broadening scope. Respond in natural paragraphs with an objective tone. No bullet lists, no inline citations, and do not output JSON. Prefer fresh, time-relevant developments from your corpus."""
                
                ai_messages.append({"role": "user", "content": current_prompt})
                
                # Stream response from OpenRouter/OpenAI
                full_response = ""
                
                if OPENROUTER_API_KEY:
                    headers = {
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://diatombot.xyz"
                    }
                    
                    # Select model: default vs search-backed (Perplexity Sonar)
                    model_to_use = PERSPECTIVES_MODEL if data.get('use_search') else OPENROUTER_MODEL

                    # Stream with the selected model
                    response = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json={
                            "model": model_to_use,
                            "messages": ai_messages,
                            "max_tokens": 600,
                            "temperature": 0.5,
                            "stream": True
                        },
                        stream=True,
                        timeout=30
                    )
                    if response.status_code != 200:
                        raise RuntimeError(f"OpenRouter error {response.status_code}")
                    model_used = model_to_use
                    for line in response.iter_lines():
                        if line:
                            line_str = line.decode('utf-8')
                            if line_str.startswith('data: '):
                                data_str = line_str[6:]
                                if data_str == '[DONE]':
                                    break
                                try:
                                    chunk = json.loads(data_str)
                                    if 'choices' in chunk and len(chunk['choices']) > 0:
                                        delta = chunk['choices'][0].get('delta', {})
                                        if 'content' in delta:
                                            content = delta['content']
                                            full_response += content
                                            yield f"data: {json.dumps({'type': 'chunk', 'content': content})}\n\n"
                                except json.JSONDecodeError:
                                    continue
                    
                else:
                    raise RuntimeError("OpenRouter API key not configured for streaming")
                
                # Save complete assistant message
                assistant_message_id = db.add_message(
                    conversation_id,
                    role='assistant',
                    content=full_response,
                    metadata={
                        'sources': sources,
                        'angle': angle,
                        'horizon': horizon,
                        'use_rag': True,
                        'mode': 'web' if data.get('use_search') else 'corpus',
                        'as_of': as_of_iso,
                        'verification': ('verified' if coverage_ratio_local >= 0.5 and len(sources) >= 2 else ('partial' if coverage_ratio_local >= 0.2 else 'unverified')),
                        'coverage': coverage_ratio_local,
                        'matched_terms': list(matched_terms_local)
                    },
                    model_used=model_used
                )
                
                # Send completion event
                yield f"data: {json.dumps({'type': 'complete', 'message_id': assistant_message_id, 'full_response': full_response})}\n\n"
                
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
    {"asset": "string", "direction": "up|down|volatile|uncertain|vol ↑", "magnitude": "+2pct|optional", "rationale": "string"}
  ],
  "geopolitics": ["2–4 bullets"],
  "playbook": ["3–5 concrete actions"],
  "risks": ["2–4 bullets"],
  "timeframes": {"near": "days/weeks", "medium": "months", "long": "12m+"},
  "societal_ripples": {"short_term": ["2–3 bullets"], "long_term": ["2–3 bullets"]},
  "policy_implications": ["1–3 bullets"],
  "confidence": {"overall": 0.0, "rationale": "one sentence"},
  "signals": ["3–5 short items"],
  "commentary": "One short paragraph (2–4 sentences) titled Analyst View: provide a clear stance and rationale. Keep it professional and non-partisan; prefer market-focused framing."
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

            return Response(
                stream_with_context(generate_stream()),
                mimetype='text/event-stream',
                headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Content-Type': 'text/event-stream; charset=utf-8'}
            )
                
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
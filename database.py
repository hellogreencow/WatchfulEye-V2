#!/usr/bin/env python3
"""
Enhanced database module for storing news articles and AI analyses.
Includes comprehensive error handling, validation, and performance optimizations.
"""

import sqlite3
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Union
import logging
from contextlib import contextmanager
import hashlib
import time
from pathlib import Path

logger = logging.getLogger(__name__)

class DatabaseError(Exception):
    """Custom exception for database operations"""
    pass

class NewsDatabase:
    """Enhanced database manager for news articles and analyses"""
    
    def __init__(self, db_path: str = "news_bot.db"):
        self.db_path = db_path
        self.max_retries = 3
        self.retry_delay = 1.0
        self._ensure_db_directory()
        self.init_database()
        self._setup_maintenance()
    
    def _ensure_db_directory(self):
        """Ensure database directory exists"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    def _setup_maintenance(self):
        """Setup database maintenance settings"""
        with self.get_connection() as conn:
            # Enable WAL mode for better concurrency
            conn.execute('PRAGMA journal_mode=WAL;')
            # Optimize for performance
            conn.execute('PRAGMA synchronous=NORMAL;')
            conn.execute('PRAGMA cache_size=10000;')
            conn.execute('PRAGMA temp_store=memory;')
            conn.commit()
    
    def init_database(self):
        """Initialize database tables with enhanced schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Enhanced articles table with more metadata
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    content TEXT,
                    url TEXT UNIQUE,
                    url_hash TEXT UNIQUE,
                    published_at TEXT,
                    source TEXT,
                    category TEXT,
                    category_confidence REAL DEFAULT 0.0,
                    sentiment_score REAL DEFAULT 0.0,
                    sentiment_confidence REAL DEFAULT 0.0,
                    sentiment_analysis_text TEXT,
                    word_count INTEGER DEFAULT 0,
                    language TEXT DEFAULT 'en',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Enhanced analyses table with better metadata
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    content TEXT NOT NULL,
                    content_hash TEXT UNIQUE,
                    content_preview TEXT,
                    model_used TEXT,
                    article_count INTEGER,
                    processing_time REAL,
                    quality_score REAL,
                    sent_to_telegram BOOLEAN DEFAULT FALSE,
                    sent_successfully BOOLEAN DEFAULT FALSE,
                    raw_response_json TEXT,
                    sentiment_summary TEXT,
                    category_breakdown TEXT
                )
            ''')
            
            # Users table for authentication
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    full_name TEXT,
                    role TEXT DEFAULT 'user',
                    is_active BOOLEAN DEFAULT TRUE,
                    bypass_password_criteria BOOLEAN DEFAULT FALSE,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_login TEXT,
                    login_count INTEGER DEFAULT 0,
                    failed_login_count INTEGER DEFAULT 0,
                    last_failed_login TEXT,
                    account_locked_until TEXT
                )
            ''')
            
            # User sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_token TEXT UNIQUE NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
            
            # Saved articles table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS saved_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    article_id INTEGER NOT NULL,
                    saved_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
                    UNIQUE(user_id, article_id)
                )
            ''')
            
            # User preferences table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    preference_key TEXT NOT NULL,
                    preference_value TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, preference_key)
                )
            ''')
            
            # Add missing columns if they don't exist (migration)
            columns_to_add = [
                ('analyses', 'raw_response_json', 'TEXT'),
                ('analyses', 'created_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
                ('analyses', 'sent_successfully', 'BOOLEAN DEFAULT FALSE'),
                ('analyses', 'content_preview', 'TEXT'),
                ('analyses', 'sentiment_summary', 'TEXT'),
                ('analyses', 'category_breakdown', 'TEXT'),
                ('articles', 'sentiment_analysis_text', 'TEXT'),
                ('articles', 'content', 'TEXT'),
                ('users', 'failed_login_count', 'INTEGER DEFAULT 0'),
                ('users', 'last_failed_login', 'TEXT'),
                ('users', 'account_locked_until', 'TEXT')
            ]
            
            for table, column, definition in columns_to_add:
                try:
                    cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
                    logger.info(f"Added missing {column} column to {table}")
                except sqlite3.OperationalError:
                    # Column already exists
                    pass
            
            # System metadata table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Enhanced indexes for better performance
            indexes = [
                'CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at)',
                'CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category)',
                'CREATE INDEX IF NOT EXISTS idx_articles_sentiment ON articles(sentiment_score)',
                'CREATE INDEX IF NOT EXISTS idx_articles_created ON articles(created_at)',
                'CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source)',
                'CREATE INDEX IF NOT EXISTS idx_articles_hash ON articles(url_hash)',
                'CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(timestamp)',
                'CREATE INDEX IF NOT EXISTS idx_analyses_hash ON analyses(content_hash)',
                'CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)',
                'CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)',
                'CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(session_token)',
                'CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions(expires_at)',
                'CREATE INDEX IF NOT EXISTS idx_saved_articles_user ON saved_articles(user_id)',
                'CREATE INDEX IF NOT EXISTS idx_saved_articles_article ON saved_articles(article_id)'
            ]
            
            for index_sql in indexes:
                try:
                    cursor.execute(index_sql)
                except sqlite3.OperationalError as e:
                    logger.warning(f"Failed to create index: {e}")
            
            # Set database version
            cursor.execute('''
                INSERT OR REPLACE INTO system_metadata (key, value) 
                VALUES ('db_version', '3.1')
            ''')

            # Normalize timestamp formats for robust filtering/ordering (one-time migration)
            # We standardize to ISO-like "YYYY-MM-DDTHH:MM:SS[.ffffff]" to keep lexicographic ordering stable.
            try:
                cursor.execute("SELECT value FROM system_metadata WHERE key = 'timestamps_normalized_v1'")
                row = cursor.fetchone()
                already_done = bool(row and (row['value'] or '').lower() in ('1', 'true', 'yes'))
                if not already_done:
                    # Detect available columns to avoid failing on older schemas.
                    try:
                        cursor.execute("PRAGMA table_info(analyses)")
                        analyses_cols = {r[1] for r in cursor.fetchall()}
                    except Exception:
                        analyses_cols = set()

                    # Articles
                    cursor.execute(
                        "UPDATE articles SET created_at = REPLACE(created_at, ' ', 'T') "
                        "WHERE created_at LIKE '____-__-__ __:%'"
                    )
                    # Analyses
                    if 'created_at' in analyses_cols:
                        cursor.execute(
                            "UPDATE analyses SET created_at = REPLACE(created_at, ' ', 'T') "
                            "WHERE created_at LIKE '____-__-__ __:%'"
                        )
                    if 'timestamp' in analyses_cols:
                        cursor.execute(
                            "UPDATE analyses SET timestamp = REPLACE(timestamp, ' ', 'T') "
                            "WHERE timestamp LIKE '____-__-__ __:%'"
                        )
                    cursor.execute(
                        "INSERT OR REPLACE INTO system_metadata (key, value) VALUES ('timestamps_normalized_v1', 'true')"
                    )
                    logger.info("Normalized timestamp formats (timestamps_normalized_v1)")
            except Exception as e:
                logger.warning(f"Timestamp normalization skipped due to error: {e}")
            
            # Create default admin user (oli/oli) if it doesn't exist
            try:
                self._create_default_users(cursor)
            except Exception as e:
                logger.error(f"Failed to create default users: {e}")
            
            conn.commit()
            logger.info("Enhanced database initialized successfully with authentication support")
    
    def _create_default_users(self, cursor):
        """Create default users including the special oli/oli account"""
        import hashlib
        import secrets
        
        # Check if oli user exists
        cursor.execute('SELECT id FROM users WHERE username = ?', ('oli',))
        if not cursor.fetchone():
            # Create oli user with bypass privileges
            salt = secrets.token_hex(16)
            password_hash = hashlib.pbkdf2_hmac('sha256', 'oli'.encode(), salt.encode(), 100000).hex()
            
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, salt, full_name, role, bypass_password_criteria)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('oli', 'oli@diatoms.ai', password_hash, salt, 'Oli Admin', 'admin', True))
            
            logger.info("Created default admin user: oli/oli")
        
        # Check if todd user exists
        cursor.execute('SELECT id FROM users WHERE username = ?', ('todd',))
        if not cursor.fetchone():
            # Create todd user (regular user role)
            salt = secrets.token_hex(16)
            password_hash = hashlib.pbkdf2_hmac('sha256', 'todd'.encode(), salt.encode(), 100000).hex()
            
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, salt, full_name, role, bypass_password_criteria)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('todd', 'todd@diatoms.ai', password_hash, salt, 'Todd User', 'user', False))
            
            logger.info("Created default user: todd/todd")
        
        # Check if nick user exists
        cursor.execute('SELECT id FROM users WHERE username = ?', ('nick',))
        if not cursor.fetchone():
            # Create nick user (regular user role)
            salt = secrets.token_hex(16)
            password_hash = hashlib.pbkdf2_hmac('sha256', 'nick'.encode(), salt.encode(), 100000).hex()
            
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, salt, full_name, role, bypass_password_criteria)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('nick', 'nick@diatoms.ai', password_hash, salt, 'Nick User', 'user', False))
            
            logger.info("Created default user: nick/nick")
    
    def create_user(self, username: str, email: str, password: str, full_name: str = None, role: str = 'user') -> Optional[int]:
        """Create a new user account"""
        import hashlib
        import secrets
        
        try:
            # Generate salt and hash password
            salt = secrets.token_hex(16)
            password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (username, email, password_hash, salt, full_name, role)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (username, email, password_hash, salt, full_name, role))
                
                conn.commit()
                user_id = cursor.lastrowid
                logger.info(f"Created new user: {username} (ID: {user_id})")
                return user_id
                
        except sqlite3.IntegrityError as e:
            if 'username' in str(e):
                raise ValueError("Username already exists")
            elif 'email' in str(e):
                raise ValueError("Email already exists")
            else:
                raise ValueError("User creation failed")
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            raise DatabaseError(f"User creation failed: {e}")
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user and return user data"""
        import hashlib
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, username, email, password_hash, salt, full_name, role,
                           is_active, bypass_password_criteria, login_count,
                           failed_login_count, last_failed_login, account_locked_until
                    FROM users
                    WHERE username = ? AND is_active = TRUE
                ''', (username,))
                
                user = cursor.fetchone()
                if not user:
                    return None

                # Check if account is locked
                if user['account_locked_until']:
                    try:
                        from datetime import datetime
                        locked_until = datetime.fromisoformat(user['account_locked_until'])
                        if locked_until > datetime.now():
                            return None  # Account is locked
                    except (ValueError, TypeError):
                        # If date parsing fails, assume account is not locked
                        pass

                # Verify password
                stored_hash = user['password_hash']
                salt = user['salt']
                computed_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()

                if computed_hash == stored_hash:
                    # Reset failed login count on successful login
                    cursor.execute('''
                        UPDATE users
                        SET last_login = CURRENT_TIMESTAMP,
                            login_count = login_count + 1,
                            failed_login_count = 0,
                            last_failed_login = NULL,
                            account_locked_until = NULL
                        WHERE id = ?
                    ''', (user['id'],))
                    conn.commit()

                    return dict(user)
                else:
                    # Increment failed login count
                    failed_count = (user['failed_login_count'] or 0) + 1
                    lock_until = None

                    # Lock account after 5 failed attempts for 15 minutes
                    if failed_count >= 5:
                        lock_until = (datetime.now() + timedelta(minutes=15)).isoformat()

                    cursor.execute('''
                        UPDATE users
                        SET failed_login_count = ?,
                            last_failed_login = CURRENT_TIMESTAMP,
                            account_locked_until = ?
                        WHERE id = ?
                    ''', (failed_count, lock_until, user['id']))
                    conn.commit()

                    return None
                
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return None
    
    def create_session(self, user_id: int) -> str:
        """Create a new user session"""
        import secrets
        from datetime import datetime, timedelta
        
        try:
            session_token = secrets.token_urlsafe(32)
            # Store as ISO-like text; comparisons should use SQLite datetime() parsing for correctness.
            expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO user_sessions (user_id, session_token, expires_at)
                    VALUES (?, ?, ?)
                ''', (user_id, session_token, expires_at))
                conn.commit()
                
                return session_token
                
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise DatabaseError(f"Session creation failed: {e}")
    
    def validate_session(self, session_token: str) -> Optional[Dict]:
        """Validate session token and return user data"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT u.id, u.username, u.email, u.full_name, u.role
                    FROM user_sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.session_token = ? 
                      AND datetime(s.expires_at) > datetime('now')
                      AND u.is_active = TRUE
                ''', (session_token,))
                
                user = cursor.fetchone()
                return dict(user) if user else None
                
        except Exception as e:
            logger.error(f"Session validation failed: {e}")
            return None
    
    def delete_session(self, session_token: str):
        """Delete a user session (logout)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM user_sessions WHERE session_token = ?', (session_token,))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
    
    def save_article_for_user(self, user_id: int, article_id: int, notes: str = None) -> bool:
        """Save an article for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO saved_articles (user_id, article_id, notes, saved_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (user_id, article_id, notes))
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to save article: {e}")
            return False
    
    def unsave_article_for_user(self, user_id: int, article_id: int) -> bool:
        """Remove saved article for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM saved_articles 
                    WHERE user_id = ? AND article_id = ?
                ''', (user_id, article_id))
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Failed to unsave article: {e}")
            return False
    
    def get_saved_articles_for_user(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Get saved articles for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.*, sa.saved_at, sa.notes
                    FROM saved_articles sa
                    JOIN articles a ON sa.article_id = a.id
                    WHERE sa.user_id = ?
                    ORDER BY sa.saved_at DESC
                    LIMIT ?
                ''', (user_id, limit))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get saved articles: {e}")
            return []
    
    def get_user_saved_article_ids(self, user_id: int) -> List[str]:
        """Get list of saved article IDs for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT article_id FROM saved_articles WHERE user_id = ?
                ''', (user_id,))
                
                return [str(row[0]) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get saved article IDs: {e}")
            return []
    
    @contextmanager
    def get_connection(self):
        """Get database connection with enhanced error handling and retries"""
        conn = None
        for attempt in range(self.max_retries):
            try:
                conn = sqlite3.connect(
                    self.db_path, 
                    timeout=30.0,
                    check_same_thread=False
                )
                conn.row_factory = sqlite3.Row
                # Set connection pragmas for performance and concurrency
                conn.execute('PRAGMA foreign_keys=ON;')
                conn.execute('PRAGMA journal_mode=WAL;')  # Write-Ahead Logging for concurrent reads
                conn.execute('PRAGMA synchronous=NORMAL;')  # Faster writes, still safe
                conn.execute('PRAGMA cache_size=-64000;')  # 64MB cache
                conn.execute('PRAGMA temp_store=MEMORY;')  # Temp tables in RAM
                conn.execute('PRAGMA mmap_size=268435456;')  # 256MB memory-mapped I/O
                yield conn
                return
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < self.max_retries - 1:
                    logger.warning(f"Database locked, retrying in {self.retry_delay}s (attempt {attempt + 1})")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    raise DatabaseError(f"Database connection failed: {e}")
            except Exception as e:
                raise DatabaseError(f"Unexpected database error: {e}")
            finally:
                if conn:
                    conn.close()
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate hash for content deduplication"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _calculate_quality_score(self, content: str, article_count: int) -> float:
        """Calculate quality score for analysis content"""
        if not content or not content.strip():
            return 0.0
        
        score = 5.0  # Base score
        
        # Length factor
        content_length = len(content)
        if content_length > 1000:
            score += 1.0
        elif content_length < 200:
            score -= 2.0
        
        # Article count factor
        if article_count > 10:
            score += 1.0
        elif article_count < 3:
            score -= 1.0
        
        # Content quality indicators
        quality_indicators = [
            'investment', 'market', 'analysis', 'opportunity', 'risk',
            'trading', 'sector', 'economic', 'geopolitical', 'strategy'
        ]
        
        content_lower = content.lower()
        indicator_count = sum(1 for indicator in quality_indicators if indicator in content_lower)
        score += min(indicator_count * 0.5, 2.0)
        
        # Structure indicators
        if '•' in content or '-' in content:  # Bullet points
            score += 0.5
        if any(section in content for section in ['BREAKING', 'MARKET', 'CRYPTO', 'RISK']):
            score += 1.0
        
        return min(max(score, 0.0), 10.0)  # Clamp between 0 and 10
    
    def _validate_article_data(self, article: Dict) -> Dict:
        """Validate and clean article data"""
        try:
            # Clean and validate title
            title = str(article.get('title', '')).strip()
            if not title or len(title) < 10:
                raise ValueError("Title too short or missing")
            if len(title) > 500:
                title = title[:497] + "..."
            
            # Clean description
            description = str(article.get('description') or '').strip()
            if description and len(description) > 1000:
                description = description[:997] + "..."

            # Clean content (may be truncated by upstream providers)
            content = str(article.get('content') or '').strip()
            if content and len(content) > 10000:
                content = content[:9997] + "..."
            
            # Validate URL
            url = str(article.get('url', '')).strip()
            if not url:
                raise ValueError("URL missing")
            
            # Clean source
            source_obj = article.get('source', {})
            if isinstance(source_obj, dict):
                source = str(source_obj.get('name', '')).strip()
            else:
                source = str(source_obj).strip()
            
            # Validate published date
            published_at = article.get('publishedAt', '')
            if published_at:
                try:
                    # Try to parse the date to validate format
                    datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                except:
                    published_at = datetime.utcnow().isoformat()
            
            return {
                'title': title,
                'description': description,
                'content': content,
                'url': url,
                'url_hash': self._generate_content_hash(url),
                'published_at': published_at,
                'source': source,
                'word_count': len((title + ' ' + description + ' ' + content).split())
            }
            
        except Exception as e:
            logger.error(f"Article validation failed: {e}")
            raise ValueError(f"Invalid article data: {e}")
    
    def _enhanced_categorization(self, title: str, description: str) -> Tuple[str, float]:
        """Enhanced categorization with confidence scoring"""
        text = (title + " " + (description or "")).lower()
        
        # Enhanced category keywords with weights
        categories = {
            'conflict': {
                'keywords': ['war', 'conflict', 'military', 'invasion', 'attack', 'battle', 'defense', 
                           'warfare', 'combat', 'armed', 'weapons', 'missile', 'strike', 'bombing'],
                'weight': 1.0
            },
            'sanctions': {
                'keywords': ['sanctions', 'embargo', 'penalty', 'restrict', 'ban', 'freeze', 
                           'blacklist', 'asset freeze', 'economic pressure', 'punitive'],
                'weight': 1.0
            },
            'trade': {
                'keywords': ['trade', 'tariff', 'export', 'import', 'supply chain', 'commerce', 
                           'wto', 'nafta', 'customs', 'quota', 'trade war', 'bilateral'],
                'weight': 0.9
            },
            'diplomacy': {
                'keywords': ['summit', 'meeting', 'negotiation', 'treaty', 'agreement', 'diplomatic', 
                           'ambassador', 'foreign minister', 'bilateral talks', 'dialogue'],
                'weight': 0.8
            },
            'economics': {
                'keywords': ['economy', 'gdp', 'inflation', 'market', 'financial', 'currency', 
                           'recession', 'growth', 'monetary', 'fiscal', 'central bank'],
                'weight': 0.7
            },
            'energy': {
                'keywords': ['oil', 'gas', 'energy', 'pipeline', 'renewable', 'nuclear', 
                           'petroleum', 'lng', 'crude', 'opec', 'energy crisis'],
                'weight': 0.9
            },
            'technology': {
                'keywords': ['cyber', 'technology', 'ai', 'semiconductor', 'chip', 'tech war', 
                           'innovation', 'digital', 'internet', 'surveillance'],
                'weight': 0.8
            }
        }
        
        category_scores = {}
        total_words = len(text.split())
        
        for category, data in categories.items():
            score = 0
            keyword_matches = 0
            
            for keyword in data['keywords']:
                if keyword in text:
                    # Count occurrences and weight by keyword importance
                    occurrences = text.count(keyword)
                    score += occurrences * data['weight']
                    keyword_matches += 1
            
            # Normalize score by text length and keyword diversity
            if total_words > 0 and keyword_matches > 0:
                normalized_score = (score / total_words) * min(keyword_matches / len(data['keywords']), 1.0)
                category_scores[category] = normalized_score
        
        if not category_scores:
            return 'general', 0.0
        
        # Find best category and confidence
        best_category = max(category_scores.items(), key=lambda x: x[1])
        confidence = min(best_category[1] * 5, 1.0)  # Scale to 0-1 range
        
        return best_category[0], confidence
    
    def _enhanced_sentiment_analysis(self, title: str, description: str) -> Tuple[float, float, str]:
        """
        Perform enhanced sentiment analysis on text
        Returns: (sentiment_score, confidence, analysis_text)
        """
        try:
            # Ensure we have valid input data
            if not title and not description:
                return 0.0, 0.3, "Insufficient content for sentiment analysis."
                
            # Combine title and description for analysis
            text = f"{title} {description}" if description else title
            
            # Simple rule-based approach with enhanced features and negation handling
            positive_words = [
                'success', 'positive', 'achievement', 'advance', 'breakthrough', 'growth', 'improve',
                'increase', 'progress', 'recovery', 'rise', 'strengthen', 'up', 'gain', 'profit',
                'alliance', 'agreement', 'peace', 'cooperation', 'collaboration', 'stability',
                'innovation', 'advantage', 'benefit', 'opportunity', 'solution'
            ]
            
            negative_words = [
                'crisis', 'decline', 'decrease', 'deficit', 'depression', 'disaster', 'downturn',
                'drop', 'fail', 'fall', 'loss', 'negative', 'plummet', 'recession', 'reduction',
                'risk', 'threat', 'war', 'conflict', 'attack', 'tension', 'instability', 'violence',
                'sanction', 'protest', 'terrorism', 'corrupt', 'danger', 'damage', 'problem'
            ]
            
            # Ensure text is properly lowercased for matching
            text_lower = text.lower()
            
            # Tokenize
            tokens = re.findall(r'\b\w+\b', text_lower)
            words = set(tokens)
            pos_count = 0
            neg_count = 0

            # Windowed scan to capture negations (not, no, without) within 2-token window
            negators = {'not', 'no', 'without', "isn't", "wasn't", "aren't", "don't", "didn't"}
            for i, tok in enumerate(tokens):
                # Positive hit
                if tok in positive_words:
                    window = tokens[max(0, i-2):i]
                    if any(n in window for n in negators):
                        neg_count += 1  # Flip
                    else:
                        pos_count += 1
                # Negative hit
                if tok in negative_words:
                    window = tokens[max(0, i-2):i]
                    if any(n in window for n in negators):
                        pos_count += 1  # Flip
                    else:
                        neg_count += 1
            
            # Weigh title tokens more heavily
            title_lower = title.lower()
            title_tokens = re.findall(r'\b\w+\b', title_lower)
            title_set = set(title_tokens)
            pos_count += sum(0.5 for word in positive_words if word in title_set)
            neg_count += sum(0.5 for word in negative_words if word in title_set)
            
            # Calculate sentiment score (-1 to +1)
            total = pos_count + neg_count
            if total == 0:
                sentiment_score = 0.0
                confidence = 0.5  # Neutral with medium confidence
                analysis_text = "The content appears to be neutral, with no strong positive or negative indicators."
            else:
                sentiment_score = (pos_count - neg_count) / total
                # Normalize to ensure we stay in the -1 to 1 range
                sentiment_score = max(min(sentiment_score, 1.0), -1.0)
                
                # Confidence grows sublinearly with evidence; clamp narrower for stability
                confidence = min(0.4 + (total / 25), 0.9)
                
                # Generate analysis text
                if sentiment_score > 0.5:
                    analysis_text = f"Strongly positive content with {pos_count} positive indicators versus {neg_count} negative indicators."
                elif sentiment_score > 0.1:
                    analysis_text = f"Moderately positive content with a slight favorable bias ({pos_count} positive vs {neg_count} negative)."
                elif sentiment_score < -0.5:
                    analysis_text = f"Strongly negative content with {neg_count} negative indicators versus {pos_count} positive indicators."
                elif sentiment_score < -0.1:
                    analysis_text = f"Moderately negative content with a slight unfavorable bias ({neg_count} negative vs {pos_count} positive)."
                else:
                    analysis_text = f"Relatively neutral content with balanced sentiment indicators ({pos_count} positive vs {neg_count} negative)."
            
            logger.debug(f"Sentiment analysis: score={sentiment_score:.2f}, confidence={confidence:.2f}")
            return sentiment_score, confidence, analysis_text
            
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            # Return safe default values in case of error
            return 0.0, 0.3, "Unable to analyze sentiment due to an error."
    
    def _ai_sentiment_analysis(self, title: str, description: str, category: str) -> Tuple[float, float, str]:
        """Use AI for context-aware MARKET sentiment (not article tone)"""
        try:
            prompt = f"""Analyze MARKET SENTIMENT (not article tone) of this {category} news.

Title: {title}
Description: {description}

Return JSON:
{{"sentiment_score": -1.0 to +1.0, "confidence": 0-1, "reasoning": "one sentence"}}

Rules:
- "Risk declining" = bullish (risk↓)
- "Growth concerns" = bearish (despite growth keyword)
- Defense spending up = complex (bullish defense stocks, neutral macro)
- Rate hikes = bearish short-term
- Focus on MARKET IMPACT not tone."""

            # Call OpenRouter with gpt-4o-mini (fast, cheap, context-aware)
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()['choices'][0]['message']['content']
                # Extract JSON from response (may have markdown code blocks)
                import re
                json_match = re.search(r'\{[^}]+\}', result)
                if json_match:
                    import json
                    parsed = json.loads(json_match.group())
                    return (
                        float(parsed['sentiment_score']),
                        float(parsed['confidence']),
                        parsed['reasoning']
                    )
        except Exception as e:
            logger.error(f"AI sentiment failed: {e}")
        
        # Fallback to keyword method
        return self._enhanced_sentiment_analysis(title, description)
    
    def store_articles(self, articles: List[Dict]) -> Tuple[int, List[str]]:
        """Store articles with enhanced validation and error reporting"""
        stored_count = 0
        errors = []
        
        if not articles:
            return 0, ["No articles provided"]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            for i, article in enumerate(articles):
                try:
                    # Validate article data
                    validated_article = self._validate_article_data(article)
                    
                    # Get category and sentiment data
                    category, cat_confidence = self._enhanced_categorization(
                        validated_article['title'], 
                        validated_article['description']
                    )
                    
                    # Use AI sentiment for ALL articles (has fallback to keyword method)
                    sentiment, sent_confidence, analysis_text = self._ai_sentiment_analysis(
                        validated_article['title'], 
                        validated_article['description'],
                        category
                    )
                    logger.info(f"[SENTIMENT] Article '{validated_article['title'][:50]}...' scored {sentiment:.2f} (confidence: {sent_confidence:.2f})")
                    
                    # Get word count
                    word_count = len(
                        (
                            validated_article['title']
                            + " "
                            + (validated_article.get('description') or "")
                            + " "
                            + (validated_article.get('content') or "")
                        ).split()
                    )
                    
                    # Insert article
                    cursor.execute('''
                        INSERT INTO articles 
                        (title, description, content, url, url_hash, published_at, source, 
                         category, category_confidence, sentiment_score, sentiment_confidence, 
                        sentiment_analysis_text, word_count, language, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        validated_article['title'],
                        validated_article['description'],
                        validated_article.get('content'),
                        validated_article['url'],
                        validated_article['url_hash'],
                        validated_article['published_at'],
                        validated_article['source'],
                        category,
                        cat_confidence,
                        sentiment,
                        sent_confidence,
                        analysis_text,
                        word_count,
                        validated_article.get('language', 'en'),
                        datetime.utcnow().isoformat()
                    ))
                    
                    if cursor.rowcount > 0:
                        stored_count += 1
                    
                except Exception as e:
                    error_msg = f"Article {i+1}: {str(e)}"
                    errors.append(error_msg)
                    logger.warning(error_msg)
                    continue
            
            conn.commit()
        
        logger.info(f"Stored {stored_count} new articles with {len(errors)} errors")
        return stored_count, errors
    
    def store_analysis(
        self,
        content: str,
        model_used: str,
        article_count: int,
        processing_time: float,
        raw_response_json: Optional[str] = None
    ) -> Optional[int]:
        """Store AI analysis results with enhanced metadata extraction."""
        try:
            if not content or not content.strip():
                logger.warning("Analysis content is empty, storing with minimal info.")
                content = content or "[No content provided]"
            
            quality_score = self._calculate_quality_score(content, article_count)
            content_hash = self._generate_content_hash(content)
            
            # Generate content preview
            content_preview = self._generate_content_preview(content)
            
            # Extract structured data if available
            sentiment_summary = None
            category_breakdown = None
            
            if raw_response_json:
                try:
                    data = json.loads(raw_response_json)
                    sentiment_summary = self._extract_sentiment_summary(data)
                    category_breakdown = self._extract_category_breakdown(data)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse raw_response_json for metadata extraction")
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO analyses 
                    (content, content_hash, content_preview, model_used, article_count, 
                     processing_time, quality_score, raw_response_json, sentiment_summary, category_breakdown, created_at) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    content.strip(), 
                    content_hash, 
                    content_preview,
                    model_used, 
                    article_count, 
                    processing_time, 
                    quality_score, 
                    raw_response_json,
                    sentiment_summary,
                    category_breakdown,
                    datetime.utcnow().isoformat()
                ))
                conn.commit()
                analysis_id = cursor.lastrowid
                logger.info(f"Stored analysis with ID {analysis_id}, quality score: {quality_score:.2f}")
                return analysis_id
                
        except sqlite3.Error as e:
            logger.error(f"SQLite error storing analysis: {e}")
            raise DatabaseError(f"Failed to store analysis due to SQLite error: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error storing analysis: {e}")
            raise DatabaseError(f"An unexpected error occurred while storing analysis: {e}") from e
    
    def _generate_content_preview(self, content: str, max_length: int = 300) -> str:
        """Generate a preview of the analysis content"""
        if not content:
            return ""
        
        # Clean the content
        lines = content.split('\n')
        important_lines = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('┏') and not line.startswith('┗'):
                # Skip header/footer decorations
                if '⚡' in line or 'BREAKING' in line or '📊' in line or '📈' in line:
                    important_lines.append(line)
                elif len(important_lines) < 3 and len(line) > 20:
                    important_lines.append(line)
        
        preview = ' '.join(important_lines)
        
        if len(preview) > max_length:
            preview = preview[:max_length] + "..."
        
        return preview or content[:max_length] + ("..." if len(content) > max_length else "")
    
    def _extract_sentiment_summary(self, data: dict) -> Optional[str]:
        """Extract sentiment summary from structured analysis data"""
        try:
            summary = None
            
            if 'sentiment_analysis' in data:
                summary = data['sentiment_analysis']
            elif 'market_pulse' in data:
                # Create summary from market pulse data
                pulse_items = data['market_pulse'][:3]  # Top 3 items
                summary = {
                    'overall_sentiment': 'mixed',
                    'key_movers': [item.get('asset', '') for item in pulse_items],
                    'dominant_theme': pulse_items[0].get('catalyst', '') if pulse_items else ''
                }
            
            # If no summary data could be extracted but there's raw data, create default
            if not summary and data:
                summary = {
                    'overall_sentiment': 'neutral',
                    'key_movers': [],
                    'dominant_theme': ''
                }
                
            # Use json.dumps with explicit parameters for safety
            if summary:
                return json.dumps(summary, ensure_ascii=False, separators=(',', ':'))
            return None
            
        except Exception as e:
            logger.warning(f"Failed to extract sentiment summary: {e}")
            # Return a valid JSON object on error
            return json.dumps({"overall_sentiment": "unknown", "error": "Failed to extract sentiment"})
    
    def _extract_category_breakdown(self, data: dict) -> Optional[str]:
        """Extract category breakdown from structured analysis data"""
        try:
            categories = {}
            
            # Count different types of news
            if 'breaking_news' in data:
                for item in data['breaking_news']:
                    # Categorize based on content
                    content = (item.get('headline', '') + ' ' + item.get('summary', '')).lower()
                    if any(word in content for word in ['market', 'trading', 'price', 'crypto']):
                        categories['market'] = categories.get('market', 0) + 1
                    elif any(word in content for word in ['war', 'conflict', 'military', 'attack']):
                        categories['geopolitical'] = categories.get('geopolitical', 0) + 1
                    elif any(word in content for word in ['technology', 'ai', 'tech', 'digital']):
                        categories['technology'] = categories.get('technology', 0) + 1
                    else:
                        categories['general'] = categories.get('general', 0) + 1
            
            # If no categories were found but there's raw data, return a default
            if not categories and data:
                categories = {'general': 1}
                
            # Use json.dumps with explicit parameters for safety
            if categories:
                return json.dumps(categories, ensure_ascii=False, separators=(',', ':'))
            return None
            
        except Exception as e:
            logger.warning(f"Failed to extract category breakdown: {e}")
            # Return a valid but empty JSON object on error
            return json.dumps({"error": "Failed to extract categories"})
    
    def get_recent_articles(
        self,
        limit: int = 20,
        category: str = None,
        min_sentiment: float = None,
        max_sentiment: float = None,
        since_hours: int = None,
    ) -> List[Dict]:
        """Get recent articles with enhanced filtering."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT *, 
                       CASE 
                           WHEN sentiment_score > 0.1 THEN 'positive'
                           WHEN sentiment_score < -0.1 THEN 'negative'
                           ELSE 'neutral'
                       END as sentiment_label
                FROM articles 
                WHERE 1=1
            '''
            params = []
            
            if category:
                query += ' AND category = ?'
                params.append(category)
            
            if min_sentiment is not None:
                query += ' AND sentiment_score >= ?'
                params.append(min_sentiment)
            
            if max_sentiment is not None:
                query += ' AND sentiment_score <= ?'
                params.append(max_sentiment)

            if since_hours is not None:
                try:
                    hours_i = int(since_hours)
                except (TypeError, ValueError):
                    hours_i = None
                if hours_i is not None and hours_i > 0:
                    # created_at is normalized to ISO-like format with 'T' separator
                    query += " AND created_at >= strftime('%Y-%m-%dT%H:%M:%f', 'now', ?)"
                    params.append(f"-{hours_i} hours")
            
            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_articles_by_timeframe(self, hours: int = 24) -> List[Dict]:
        """Get articles from specific timeframe"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM articles 
                WHERE created_at >= strftime('%Y-%m-%dT%H:%M:%f', 'now', '-{} hours')
                ORDER BY created_at DESC
            '''.format(hours))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_enhanced_stats(self) -> Dict:
        """Get comprehensive database statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Category statistics
            cursor.execute('''
                SELECT category, COUNT(*) as count, 
                       AVG(sentiment_score) as avg_sentiment,
                       AVG(category_confidence) as avg_confidence
                FROM articles 
                GROUP BY category 
                ORDER BY count DESC
            ''')
            category_stats = {row['category']: {
                'count': row['count'],
                'avg_sentiment': row['avg_sentiment'] or 0.0,
                'avg_confidence': row['avg_confidence'] or 0.0
            } for row in cursor.fetchall()}
            
            # Get sentiment distribution
            cursor.execute('''
                SELECT 
                    SUM(CASE WHEN sentiment_score > 0.1 THEN 1 ELSE 0 END) as positive,
                    SUM(CASE WHEN sentiment_score < -0.1 THEN 1 ELSE 0 END) as negative,
                    SUM(CASE WHEN sentiment_score >= -0.1 AND sentiment_score <= 0.1 THEN 1 ELSE 0 END) as neutral
                FROM articles
            ''')
            
            sentiment = cursor.fetchone()
            
            # Get articles by time period
            cursor.execute('''
                SELECT 
                    COUNT(*) as count,
                    strftime('%Y-%m-%d', created_at) as date
                FROM articles
                WHERE created_at > strftime('%Y-%m-%dT%H:%M:%f', 'now', '-7 days')
                GROUP BY date
                ORDER BY date DESC
            ''')
            
            daily_counts = cursor.fetchall()
            
            # Get recent analysis count
            cursor.execute('''
                SELECT COUNT(*) 
                FROM analyses 
                WHERE created_at > strftime('%Y-%m-%dT%H:%M:%f', 'now', '-24 hours')
            ''')
            recent_analyses_count = cursor.fetchone()[0]
            
            # Get analysis success rate
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN sent_successfully = 1 THEN 1 ELSE 0 END) as successful
                FROM analyses
                WHERE created_at > strftime('%Y-%m-%dT%H:%M:%f', 'now', '-7 days')
            ''')
            analysis_stats = cursor.fetchone()
            
            return {
                'categories': category_stats,
                'sentiment_distribution': {
                    'positive': sentiment[0] or 0,
                    'negative': sentiment[1] or 0,
                    'neutral': sentiment[2] or 0
                },
                'daily_counts': daily_counts,
                'recent_analyses_count': recent_analyses_count,
                'analysis_stats': {
                    'total': analysis_stats[0] or 0,
                    'successful': analysis_stats[1] or 0
                },
                'total_articles': sum(stat['count'] for stat in category_stats.values()),
                'database_size': Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
            }
    
    def get_market_intelligence_score(self) -> Dict:
        """Calculate robust bullish/bearish score with multiple factors"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Factor 1: Weighted sentiment (recency + category importance)
                cursor.execute('''
                    SELECT 
                        sentiment_score,
                        julianday('now') - julianday(created_at) as days_ago,
                        category
                    FROM articles
                    WHERE created_at > datetime('now', '-7 days')
                        AND sentiment_score IS NOT NULL
                ''')
                articles = cursor.fetchall()
                
                if not articles:
                    # No recent articles, return neutral
                    return {
                        'bullish_percentage': 50,
                        'market_score': 0.0,
                        'momentum': 0.0,
                        'volatility': 0.0,
                        'label': 'Neutral',
                        'confidence': 0.5
                    }
                
                category_weights = {
                    'finance': 1.5, 'economy': 1.5, 'technology': 1.2,
                    'politics': 1.0, 'general': 0.8
                }
                
                weighted_sentiment = 0
                total_weight = 0
                
                for article in articles:
                    # Recency weight: today=1.0, yesterday=0.85, 2d ago=0.7, etc.
                    recency_weight = max(0.3, 1.0 - (article['days_ago'] * 0.15))
                    cat_weight = category_weights.get(article['category'], 1.0)
                    weight = recency_weight * cat_weight
                    
                    weighted_sentiment += article['sentiment_score'] * weight
                    total_weight += weight
                
                avg_sentiment = weighted_sentiment / max(total_weight, 1)
                
                # Factor 2: Momentum (improving or worsening?)
                cursor.execute('''
                    SELECT AVG(sentiment_score) FROM articles
                    WHERE created_at > datetime('now', '-1 days')
                        AND sentiment_score IS NOT NULL
                ''')
                result = cursor.fetchone()
                last_24h = result[0] if result and result[0] is not None else 0
                
                cursor.execute('''
                    SELECT AVG(sentiment_score) FROM articles
                    WHERE created_at BETWEEN datetime('now', '-7 days') 
                        AND datetime('now', '-1 days')
                        AND sentiment_score IS NOT NULL
                ''')
                result = cursor.fetchone()
                prev_6days = result[0] if result and result[0] is not None else 0
                momentum = last_24h - prev_6days
                
                # Factor 3: Volatility (high disagreement = uncertainty)
                cursor.execute('''
                    SELECT 
                        AVG(sentiment_score * sentiment_score) as avg_sq,
                        AVG(sentiment_score) as avg
                    FROM articles
                    WHERE created_at > datetime('now', '-7 days')
                        AND sentiment_score IS NOT NULL
                ''')
                result = cursor.fetchone()
                if result and result['avg_sq'] is not None and result['avg'] is not None:
                    variance = result['avg_sq'] - (result['avg'] ** 2)
                    volatility = min(variance ** 0.5 if variance > 0 else 0, 1.0)
                else:
                    volatility = 0.5
                
                # Composite: 60% sentiment + 25% momentum + 15% stability
                market_score = (
                    avg_sentiment * 0.60 +
                    momentum * 0.25 +
                    (1 - volatility) * avg_sentiment * 0.15
                )
                
                # Convert to percentage (0-100)
                bullish_pct = int((market_score + 1) * 50)
                bullish_pct = max(0, min(100, bullish_pct))
                
                return {
                    'bullish_percentage': bullish_pct,
                    'market_score': round(market_score, 3),
                    'momentum': round(momentum, 3),
                    'volatility': round(volatility, 3),
                    'label': 'Bullish' if market_score > 0.05 else 'Bearish' if market_score < -0.05 else 'Neutral',
                    'confidence': round(1 - volatility, 2)
                }
        except Exception as e:
            logger.error(f"Market intelligence calculation error: {e}")
            return {
                'bullish_percentage': 50,
                'market_score': 0.0,
                'momentum': 0.0,
                'volatility': 0.0,
                'label': 'Neutral',
                'confidence': 0.5
            }
    
    def optimize_database(self):
        """Run database optimization operations"""
        try:
            with self.get_connection() as conn:
                # Analyze tables for better query planning
                conn.execute('ANALYZE;')
                # Vacuum to reclaim space
                conn.execute('VACUUM;')
                # Update statistics
                conn.execute('PRAGMA optimize;')
                conn.commit()
            
            logger.info("Database optimization completed")
        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
    
    def backup_database(self, backup_path: str = None) -> str:
        """Create database backup"""
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.db_path}.backup_{timestamp}"
        
        try:
            with self.get_connection() as conn:
                backup_conn = sqlite3.connect(backup_path)
                conn.backup(backup_conn)
                backup_conn.close()
            
            logger.info(f"Database backup created: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            raise DatabaseError(f"Backup failed: {e}")
    
    def get_system_health(self) -> Dict:
        """Get database health metrics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check database integrity
                cursor.execute('PRAGMA integrity_check;')
                integrity = cursor.fetchone()[0]
                
                # Get database size
                cursor.execute('PRAGMA page_count;')
                page_count = cursor.fetchone()[0]
                
                cursor.execute('PRAGMA page_size;')
                page_size = cursor.fetchone()[0]
                
                db_size = page_count * page_size
                
                # Check recent errors (would need error logging table)
                health_score = 1.0 if integrity == 'ok' else 0.0
                
                return {
                    'integrity': integrity,
                    'size_bytes': db_size,
                    'size_mb': round(db_size / (1024 * 1024), 2),
                    'health_score': health_score,
                    'last_optimized': datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {'error': str(e), 'health_score': 0.0}
    
    def get_recent_analyses(self, limit: int = 10) -> List[Dict]:
        """Get recent AI analyses, including topic for frontend"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM analyses 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            analyses = [dict(row) for row in cursor.fetchall()]
            # Add 'topic' field for frontend, using model_used
            for analysis in analyses:
                analysis['topic'] = analysis.get('model_used', 'unknown')
            return analyses
    
    def get_analysis_by_id(self, analysis_id: int) -> Optional[Dict]:
        """Get a specific analysis by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM analyses WHERE id = ?
                ''', (analysis_id,))
                
                result = cursor.fetchone()
                return dict(result) if result else None
                
        except Exception as e:
            logger.error(f"Failed to get analysis by ID {analysis_id}: {e}")
            return None
    
    def get_category_stats(self) -> Dict[str, int]:
        """Get article count by category (backward compatibility)"""
        stats = self.get_enhanced_stats()
        return {cat: data['count'] for cat, data in stats['categories'].items()}
    
    def mark_analysis_sent(self, analysis_id: int):
        """Mark analysis as notification sent"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE analyses 
                SET sent_to_telegram = TRUE 
                WHERE id = ?
            ''', (analysis_id,))
            
            conn.commit()
    
    def cleanup_old_data(self, days: int = 30) -> Tuple[int, int]:
        """Clean up data older than specified days"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Delete old articles
                cursor.execute('''
                    DELETE FROM articles 
                    WHERE created_at < strftime('%Y-%m-%dT%H:%M:%f', 'now', '-{} days')
                '''.format(days))
                
                articles_deleted = cursor.rowcount
                
                # Delete old analyses
                cursor.execute('''
                    DELETE FROM analyses 
                    WHERE created_at < strftime('%Y-%m-%dT%H:%M:%f', 'now', '-{} days')
                '''.format(days))
                
                analyses_deleted = cursor.rowcount
                conn.commit()
                
                # Optimize after cleanup
                self.optimize_database()
            
            logger.info(f"Cleaned up {articles_deleted} old articles and {analyses_deleted} old analyses")
            return articles_deleted, analyses_deleted
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            raise DatabaseError(f"Cleanup failed: {e}")
    
    def get_total_articles_in_last_run_period(self, hours: int = 6) -> int:
        """Get total count of articles from last run period (default 6 hours)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT COUNT(*) as count FROM articles 
                    WHERE created_at >= strftime('%Y-%m-%dT%H:%M:%f', 'now', '-{} hours')
                '''.format(hours))
                
                result = cursor.fetchone()
                return result['count'] if result else 0
                
        except Exception as e:
            logger.error(f"Failed to get article count for last run period: {e}")
            return 0
    
    def search_nodes(
        self,
        query: str,
        limit: int = 50,
        category: str = None,
        min_sentiment: float = None,
        max_sentiment: float = None,
        since_hours: int = None,
    ) -> List[Dict]:
        """Search for articles based on query string, with optional filters."""
        if not query or len(query.strip()) < 2:
            return []
        
        query = query.strip().lower()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            sql = (
                "SELECT * FROM articles "
                "WHERE 1=1 "
                "AND (LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR LOWER(source) LIKE ? OR LOWER(content) LIKE ?) "
            )
            like = f"%{query}%"
            params: List[Union[str, float, int]] = [like, like, like, like]

            if category:
                sql += " AND category = ? "
                params.append(category)

            if min_sentiment is not None:
                sql += " AND sentiment_score >= ? "
                params.append(float(min_sentiment))

            if max_sentiment is not None:
                sql += " AND sentiment_score <= ? "
                params.append(float(max_sentiment))

            if since_hours is not None:
                try:
                    hours_i = int(since_hours)
                except (TypeError, ValueError):
                    hours_i = None
                if hours_i is not None and hours_i > 0:
                    sql += " AND created_at >= strftime('%Y-%m-%dT%H:%M:%f', 'now', ?) "
                    params.append(f"-{hours_i} hours")

            sql += " ORDER BY created_at DESC LIMIT ? "
            params.append(int(limit))

            cursor.execute(sql, params)
            
            results = [dict(row) for row in cursor.fetchall()]
            
            # Add relevance scoring
            for article in results:
                score = 0
                title = article.get('title', '').lower()
                description = article.get('description', '').lower()
                content = (article.get('content') or '').lower()
                
                # Higher weight for title matches
                if query in title:
                    score += title.count(query) * 2
                if query in description:
                    score += description.count(query)
                if content and query in content:
                    score += content.count(query)
                
                article['relevance_score'] = score
            
            # Sort by relevance
            results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            return results
    
    def get_stats(self) -> Dict:
        """Get simplified stats for the dashboard (React frontend compatible)"""
        try:
            enhanced_stats = self.get_enhanced_stats()
            
            # Get recent articles count (last 24 hours)
            recent_articles = self.get_articles_by_timeframe(hours=24)
            
            # Get recent analyses
            recent_analyses = self.get_recent_analyses(limit=10)
            
            # Simplify categories to just name:count mapping
            articles_by_category = {}
            for cat, data in enhanced_stats.get('categories', {}).items():
                articles_by_category[cat] = data['count']
            
            # Get total analyses count
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM analyses')
                total_analyses = cursor.fetchone()[0]
                
                # Get daily sentiment distribution
                cursor.execute('''
                    SELECT 
                        strftime('%Y-%m-%d', created_at) as date,
                        COUNT(*) as total_count,
                        SUM(CASE WHEN sentiment_score > 0.1 THEN 1 ELSE 0 END) as positive_count,
                        SUM(CASE WHEN sentiment_score < -0.1 THEN 1 ELSE 0 END) as negative_count,
                        SUM(CASE WHEN sentiment_score >= -0.1 AND sentiment_score <= 0.1 THEN 1 ELSE 0 END) as neutral_count
                    FROM articles
                    WHERE created_at > strftime('%Y-%m-%dT%H:%M:%f', 'now', '-7 days')
                    GROUP BY date
                    ORDER BY date DESC
                ''')
                
                daily_sentiment_data = cursor.fetchall()
            
            # Format daily counts with real sentiment percentages
            daily_counts = []
            for row in daily_sentiment_data:
                total = row['total_count']
                if total > 0:
                    daily_counts.append({
                        'date': row['date'],
                        'count': total,
                        'sentiment_positive': round((row['positive_count'] / total) * 100, 1),
                        'sentiment_negative': round((row['negative_count'] / total) * 100, 1),
                        'sentiment_neutral': round((row['neutral_count'] / total) * 100, 1)
                    })
                else:
                    daily_counts.append({
                        'date': row['date'],
                        'count': 0,
                        'sentiment_positive': 0,
                        'sentiment_negative': 0,
                        'sentiment_neutral': 100
                    })
            
            return {
                'total_articles': enhanced_stats.get('total_articles', 0),
                'recent_articles_count': len(recent_articles),
                'total_analyses': total_analyses,
                'articles_by_category': articles_by_category,
                'articles_by_sentiment': enhanced_stats.get('sentiment_distribution', {
                    'positive': 0,
                    'negative': 0,
                    'neutral': 0
                }),
                'recent_analyses': recent_analyses,
                'daily_counts': daily_counts
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            # Return empty stats structure on error
            return {
                'total_articles': 0,
                'recent_articles_count': 0,
                'total_analyses': 0,
                'articles_by_category': {},
                'recent_analyses': [],
                'daily_counts': []
            } 
    
    def get_user_statistics(self) -> Dict:
        """Get comprehensive user statistics and active sessions"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get total user count
                cursor.execute('SELECT COUNT(*) as total_users FROM users')
                total_users = cursor.fetchone()['total_users']
                
                # Get user count by role
                cursor.execute('SELECT role, COUNT(*) as count FROM users GROUP BY role')
                roles = {row['role']: row['count'] for row in cursor.fetchall()}
                
                # Get new users in the last 24 hours
                cursor.execute('''
                    SELECT COUNT(*) as new_users 
                    FROM users 
                    WHERE created_at > datetime('now', '-1 day')
                ''')
                new_users_24h = cursor.fetchone()['new_users']
                
                # Get new users in the last 7 days
                cursor.execute('''
                    SELECT COUNT(*) as new_users 
                    FROM users 
                    WHERE created_at > datetime('now', '-7 days')
                ''')
                new_users_7d = cursor.fetchone()['new_users']
                
                # Get active sessions (not expired)
                cursor.execute('''
                    SELECT COUNT(*) as active_sessions 
                    FROM user_sessions 
                    WHERE datetime(expires_at) > datetime('now')
                ''')
                active_sessions = cursor.fetchone()['active_sessions']
                
                # Get active sessions in the last 24 hours with user info
                cursor.execute('''
                    SELECT u.username, u.email, u.role, s.created_at, s.expires_at
                    FROM user_sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE datetime(s.expires_at) > datetime('now')
                    ORDER BY s.created_at DESC
                    LIMIT 50
                ''')
                recent_sessions = [dict(row) for row in cursor.fetchall()]
                
                # Get daily signups for the last 30 days
                cursor.execute('''
                    SELECT 
                        date(created_at) as date, 
                        COUNT(*) as count 
                    FROM users 
                    WHERE created_at > datetime('now', '-30 days')
                    GROUP BY date(created_at)
                    ORDER BY date
                ''')
                daily_signups = [dict(row) for row in cursor.fetchall()]
                
                # Calculate active users (users who logged in within the last 7 days)
                cursor.execute('''
                    SELECT COUNT(DISTINCT user_id) as active_users
                    FROM user_sessions
                    WHERE created_at > datetime('now', '-7 days')
                ''')
                active_users_7d = cursor.fetchone()['active_users']
                
                return {
                    'total_users': total_users,
                    'users_by_role': roles,
                    'new_users_24h': new_users_24h,
                    'new_users_7d': new_users_7d,
                    'active_sessions': active_sessions,
                    'active_users_7d': active_users_7d,
                    'recent_sessions': recent_sessions,
                    'daily_signups': daily_signups,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to get user statistics: {e}")
            raise DatabaseError(f"Failed to get user statistics: {e}")

    def get_all_users(self) -> List[Dict]:
        """Get a list of all users (excluding password data)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        id, username, email, full_name, role, is_active, 
                        created_at, last_login, login_count
                    FROM users
                    ORDER BY created_at DESC
                ''')
                
                users = [dict(row) for row in cursor.fetchall()]
                
                # Add additional stats for each user
                for user in users:
                    # Get saved article count
                    cursor.execute('''
                        SELECT COUNT(*) as saved_count
                        FROM saved_articles
                        WHERE user_id = ?
                    ''', (user['id'],))
                    user['saved_articles_count'] = cursor.fetchone()['saved_count']
                    
                    # Get last active session
                    cursor.execute('''
                        SELECT created_at
                        FROM user_sessions
                        WHERE user_id = ?
                        ORDER BY created_at DESC
                        LIMIT 1
                    ''', (user['id'],))
                    session = cursor.fetchone()
                    user['last_active'] = session['created_at'] if session else None
                    
                    # Get active session count
                    cursor.execute('''
                        SELECT COUNT(*) as session_count
                        FROM user_sessions
                        WHERE user_id = ? AND datetime(expires_at) > datetime('now')
                    ''', (user['id'],))
                    user['active_sessions'] = cursor.fetchone()['session_count']
                
                return users
                
        except Exception as e:
            logger.error(f"Failed to get all users: {e}")
            raise DatabaseError(f"Failed to get all users: {e}")

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get detailed user information by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        id, username, email, full_name, role, is_active, 
                        created_at, last_login, login_count
                    FROM users
                    WHERE id = ?
                ''', (user_id,))
                
                user = cursor.fetchone()
                if not user:
                    return None
                    
                user = dict(user)
                
                # Get saved articles
                cursor.execute('''
                    SELECT a.id, a.title, sa.saved_at
                    FROM saved_articles sa
                    JOIN articles a ON sa.article_id = a.id
                    WHERE sa.user_id = ?
                    ORDER BY sa.saved_at DESC
                    LIMIT 10
                ''', (user_id,))
                user['saved_articles'] = [dict(row) for row in cursor.fetchall()]
                
                # Get session history
                cursor.execute('''
                    SELECT id, created_at, expires_at
                    FROM user_sessions
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 20
                ''', (user_id,))
                user['sessions'] = [dict(row) for row in cursor.fetchall()]
                
                return user
                
        except Exception as e:
            logger.error(f"Failed to get user by ID: {e}")
            raise DatabaseError(f"Failed to get user by ID: {e}")

    def update_user_status(self, user_id: int, is_active: bool) -> bool:
        """Update a user's active status"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if user exists
                cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,))
                if not cursor.fetchone():
                    return False
                    
                # Update user status
                cursor.execute('''
                    UPDATE users
                    SET is_active = ?
                    WHERE id = ?
                ''', (is_active, user_id))
                
                # If deactivating, invalidate all sessions
                if not is_active:
                    cursor.execute('''
                        DELETE FROM user_sessions
                        WHERE user_id = ?
                    ''', (user_id,))
                    
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to update user status: {e}")
            return False

    # ==============================================================================
    # CHAT/CONVERSATION METHODS
    # ==============================================================================
    
    def init_chat_tables(self):
        """Initialize chat-related tables"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Execute the chat schema SQL
                with open('chat_schema.sql', 'r') as f:
                    chat_schema = f.read()
                    cursor.executescript(chat_schema)
                
                conn.commit()
                logger.info("Chat tables initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize chat tables: {e}")
            raise DatabaseError(f"Failed to initialize chat tables: {e}")
    
    def create_conversation(self, user_id: int, title: Optional[str] = None, metadata: Optional[Dict] = None) -> int:
        """Create a new conversation"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO conversations (user_id, title, metadata)
                    VALUES (?, ?, ?)
                ''', (user_id, title, json.dumps(metadata) if metadata else None))
                
                conn.commit()
                return cursor.lastrowid
                
        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")
            raise DatabaseError(f"Failed to create conversation: {e}")
    
    def get_conversations(self, user_id: int, include_archived: bool = False) -> List[Dict]:
        """Get conversations for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT 
                        c.id, c.title, c.created_at, c.updated_at, c.archived, 
                        c.last_message_at, c.metadata,
                        (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) as message_count,
                        (SELECT content FROM messages 
                         WHERE conversation_id = c.id AND role = 'user'
                         ORDER BY created_at DESC LIMIT 1) as last_message
                    FROM conversations c
                    WHERE c.user_id = ?
                '''
                
                if not include_archived:
                    query += ' AND c.archived = FALSE'
                    
                query += ' ORDER BY c.last_message_at DESC'
                
                cursor.execute(query, (user_id,))
                conversations = []
                
                for row in cursor.fetchall():
                    conv = dict(row)
                    if conv['metadata']:
                        conv['metadata'] = json.loads(conv['metadata'])
                    conversations.append(conv)
                
                return conversations
                
        except Exception as e:
            logger.error(f"Failed to get conversations: {e}")
            raise DatabaseError(f"Failed to get conversations: {e}")
    
    def get_conversation_messages(self, conversation_id: int, limit: int = 100) -> List[Dict]:
        """Get messages for a conversation"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT 
                        id, role, content, created_at, metadata, model_used
                    FROM messages
                    WHERE conversation_id = ?
                    ORDER BY created_at ASC
                    LIMIT ?
                ''', (conversation_id, limit))
                
                messages = []
                for row in cursor.fetchall():
                    msg = dict(row)
                    if msg['metadata']:
                        msg['metadata'] = json.loads(msg['metadata'])
                    messages.append(msg)
                
                return messages
                
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            raise DatabaseError(f"Failed to get messages: {e}")
    
    def add_message(self, conversation_id: int, role: str, content: str, 
                   metadata: Optional[Dict] = None, model_used: Optional[str] = None) -> int:
        """Add a message to a conversation"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Add the message
                cursor.execute('''
                    INSERT INTO messages (conversation_id, role, content, metadata, model_used)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    conversation_id, 
                    role, 
                    content, 
                    json.dumps(metadata) if metadata else None,
                    model_used
                ))
                
                message_id = cursor.lastrowid
                
                # Update conversation's last_message_at and title if needed
                cursor.execute('''
                    UPDATE conversations 
                    SET last_message_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (conversation_id,))
                
                # If this is the first user message and no title, set title to first 50 chars
                if role == 'user':
                    cursor.execute('SELECT title FROM conversations WHERE id = ?', (conversation_id,))
                    conv = cursor.fetchone()
                    if conv and not conv['title']:
                        title = content[:50] + '...' if len(content) > 50 else content
                        cursor.execute('''
                            UPDATE conversations SET title = ? WHERE id = ?
                        ''', (title, conversation_id))
                
                conn.commit()
                return message_id
                
        except Exception as e:
            logger.error(f"Failed to add message: {e}")
            raise DatabaseError(f"Failed to add message: {e}")
    
    def update_conversation(self, conversation_id: int, title: Optional[str] = None, 
                          archived: Optional[bool] = None, metadata: Optional[Dict] = None) -> bool:
        """Update a conversation"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                updates = []
                params = []
                
                if title is not None:
                    updates.append('title = ?')
                    params.append(title)
                    
                if archived is not None:
                    updates.append('archived = ?')
                    params.append(archived)
                    
                if metadata is not None:
                    updates.append('metadata = ?')
                    params.append(json.dumps(metadata))
                    
                if not updates:
                    return True
                    
                updates.append('updated_at = CURRENT_TIMESTAMP')
                params.append(conversation_id)
                
                query = f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Failed to update conversation: {e}")
            return False
    
    def delete_conversation(self, conversation_id: int) -> bool:
        """Delete a conversation and all its messages"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))
                
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Failed to delete conversation: {e}")
            return False
    
    def search_conversations(self, user_id: int, query: str) -> List[Dict]:
        """Search conversations by content"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT DISTINCT c.id, c.title, c.created_at, c.last_message_at
                    FROM conversations c
                    LEFT JOIN messages m ON c.id = m.conversation_id
                    WHERE c.user_id = ? 
                    AND (c.title LIKE ? OR m.content LIKE ?)
                    ORDER BY c.last_message_at DESC
                    LIMIT 20
                ''', (user_id, f'%{query}%', f'%{query}%'))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to search conversations: {e}")
            raise DatabaseError(f"Failed to search conversations: {e}")
    
    def pin_conversation(self, user_id: int, conversation_id: int, position: int = 0) -> bool:
        """Pin a conversation"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO pinned_conversations (user_id, conversation_id, position)
                    VALUES (?, ?, ?)
                ''', (user_id, conversation_id, position))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to pin conversation: {e}")
            return False
    
    def unpin_conversation(self, user_id: int, conversation_id: int) -> bool:
        """Unpin a conversation"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    DELETE FROM pinned_conversations 
                    WHERE user_id = ? AND conversation_id = ?
                ''', (user_id, conversation_id))
                
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Failed to unpin conversation: {e}")
            return False
    
    def get_pinned_conversations(self, user_id: int) -> List[Dict]:
        """Get pinned conversations for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT c.*, p.position
                    FROM pinned_conversations p
                    JOIN conversations c ON p.conversation_id = c.id
                    WHERE p.user_id = ?
                    ORDER BY p.position, p.pinned_at DESC
                ''', (user_id,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get pinned conversations: {e}")
            raise DatabaseError(f"Failed to get pinned conversations: {e}") 
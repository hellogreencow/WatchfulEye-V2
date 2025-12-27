#!/usr/bin/env python3
"""
WatchfulEye: Geo-Political News → Investment Intelligence
Enhanced version with comprehensive error handling, retry logic, and robust operations.
"""

import requests
import json
import logging
import time
import schedule
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import os
from dataclasses import dataclass, field
import sys
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from database import NewsDatabase, DatabaseError
import signal
import threading
from functools import wraps
import random
from urllib.parse import urlparse
import hashlib
import fcntl
import errno
from watchfuleye.briefs.evidence_pack import fetch_recent_evidence, build_evidence_pack
from watchfuleye.contracts.global_brief import validate_global_brief
from watchfuleye.ingestion.article_types import ArticleCandidate
from watchfuleye.storage.postgres_briefs import store_brief_and_recommendations
from watchfuleye.storage.postgres_repo import PostgresRepo
from watchfuleye.storage.postgres_schema import ensure_postgres_schema

# Load environment variables from .env file
load_dotenv()

# Create outputs directory for logging
os.makedirs('outputs', exist_ok=True)
os.makedirs('outputs/formatted', exist_ok=True)
os.makedirs('outputs/raw_analysis', exist_ok=True)
os.makedirs('outputs/metrics', exist_ok=True)

# Create a directory for state tracking
os.makedirs('state', exist_ok=True)

# Telegram API limits
# Official limit: 4,096 characters per message
# Reference: https://limits.tginfo.me/en
TELEGRAM_MAX_MESSAGE_LENGTH = 4096

# Configure enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Add at the top, after imports
TOPICS = [
    ("defense", "defense OR military OR army OR navy OR air force OR defense spending OR weapons OR arms"),
    ("energy", "energy OR oil OR gas OR renewable OR solar OR wind OR nuclear OR power grid OR electricity"),
    ("geopolitics", "geopolitics OR conflict OR sanctions OR diplomacy OR international relations OR global politics"),
    ("AI", "artificial intelligence OR AI OR machine learning OR deep learning OR neural network OR automation"),
    ("tech", "technology OR tech OR semiconductor OR chip OR innovation OR software OR hardware OR IT"),
    ("science", "science OR research OR discovery OR physics OR biology OR chemistry OR space OR NASA OR medicine")
]

# Path to store the last used topic
TOPIC_STATE_FILE = 'state/last_topic.json'
# Path for process lock file
LOCK_FILE = 'state/bot.lock'

def get_next_topic_index() -> int:
    """Get the next topic index with proper rotation, using state file for persistence"""
    try:
        if os.path.exists(TOPIC_STATE_FILE):
            with open(TOPIC_STATE_FILE, 'r') as f:
                state = json.load(f)
                last_index = state.get('last_index', -1)
                last_time = state.get('last_time', None)
        else:
            last_index = -1
            last_time = None
        
        # Calculate next index (rotate through all topics)
        next_index = (last_index + 1) % len(TOPICS)
        
        # Store the new state
        with open(TOPIC_STATE_FILE, 'w') as f:
            json.dump({
                'last_index': next_index,
                'last_time': datetime.utcnow().isoformat()
            }, f)
        
        logger.info(f"Topic rotation: {last_index} → {next_index} ({TOPICS[next_index][0] if next_index >= 0 else 'initial'})")
        return next_index
    except Exception as e:
        logger.error(f"Error managing topic rotation: {e}")
        # Fallback to time-based rotation if file operations fail
        now = datetime.utcnow()
        return (now.hour // 4) % len(TOPICS)

class ProcessLock:
    """Process lock to prevent multiple instances from running simultaneously"""
    
    def __init__(self, lock_file):
        self.lock_file = lock_file
        self.lock_file_handle = None
    
    def acquire(self):
        """Acquire a lock, return True if successful, False otherwise"""
        try:
            # Open the lock file and try to acquire an exclusive lock
            self.lock_file_handle = open(self.lock_file, 'w')
            fcntl.flock(self.lock_file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Write the current PID to the lock file
            self.lock_file_handle.write(str(os.getpid()))
            self.lock_file_handle.flush()
            
            logger.info(f"Process lock acquired (PID: {os.getpid()})")
            return True
        except IOError as e:
            if e.errno == errno.EAGAIN:
                # Another process holds the lock
                try:
                    with open(self.lock_file, 'r') as f:
                        pid = f.read().strip()
                        logger.warning(f"Another process is already running (PID: {pid})")
                except:
                    logger.warning("Another process is already running (unknown PID)")
            else:
                logger.error(f"Failed to acquire process lock: {e}")
            
            if self.lock_file_handle:
                self.lock_file_handle.close()
                self.lock_file_handle = None
            
            return False
    
    def release(self):
        """Release the lock"""
        if self.lock_file_handle:
            try:
                fcntl.flock(self.lock_file_handle, fcntl.LOCK_UN)
                self.lock_file_handle.close()
                self.lock_file_handle = None
                logger.info("Process lock released")
            except Exception as e:
                logger.error(f"Error releasing process lock: {e}")

def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
    """Decorator for retry logic with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts: {e}")
                        raise
                    
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                    logger.warning(f"{func.__name__} attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s")
                    time.sleep(delay)
            
        return wrapper
    return decorator

@dataclass
class Config:
    """Enhanced configuration class with validation"""
    newsapi_key: str
    openai_api_key: str
    
    # Email settings
    email_enabled: bool = False
    email_smtp_server: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_from: str = ""
    email_password: str = ""
    email_to: str = ""
    
    # Telegram bot settings
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    
    # Discord webhook
    discord_enabled: bool = False
    discord_webhook_url: str = ""
    
    # Pushover notifications
    pushover_enabled: bool = False
    pushover_token: str = ""
    pushover_user: str = ""
    
    # Database settings
    db_path: str = "news_bot.db"
    
    # API settings
    newsapi_rate_limit: int = 1000  # requests per day
    openai_rate_limit: int = 60     # requests per minute
    request_timeout: int = 30       # seconds
    
    # Bot settings
    max_articles_per_run: int = 200  # Increased for GPT-4o's larger context
    min_articles_for_analysis: int = 5
    analysis_quality_threshold: float = 0.3
    
    # Notification settings
    notification_retry_attempts: int = 3
    notification_retry_delay: float = 5.0
    
    # OpenRouter API key and model
    openrouter_api_key: str = ""
    openrouter_model: str = ""
    
    # AI Model for analysis
    ai_model: str = ""
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Load and validate configuration from environment variables"""
        config = cls(
            newsapi_key=os.getenv('NEWSAPI_KEY', ''),
            openai_api_key=os.getenv('OPENAI_API_KEY', ''),
            
            # Email config
            email_enabled=os.getenv('EMAIL_ENABLED', 'false').lower() == 'true',
            email_smtp_server=os.getenv('EMAIL_SMTP_SERVER', 'smtp.gmail.com'),
            email_smtp_port=int(os.getenv('EMAIL_SMTP_PORT', '587')),
            email_from=os.getenv('EMAIL_FROM', ''),
            email_password=os.getenv('EMAIL_PASSWORD', ''),
            email_to=os.getenv('EMAIL_TO', ''),
            
            # Telegram config
            telegram_enabled=os.getenv('TELEGRAM_ENABLED', 'false').lower() == 'true',
            telegram_bot_token=os.getenv('TELEGRAM_BOT_TOKEN', ''),
            telegram_chat_id=os.getenv('TELEGRAM_CHAT_ID', ''),
            
            # Discord config
            discord_enabled=os.getenv('DISCORD_ENABLED', 'false').lower() == 'true',
            discord_webhook_url=os.getenv('DISCORD_WEBHOOK_URL', ''),
            
            # Pushover config
            pushover_enabled=os.getenv('PUSHOVER_ENABLED', 'false').lower() == 'true',
            pushover_token=os.getenv('PUSHOVER_TOKEN', ''),
            pushover_user=os.getenv('PUSHOVER_USER', ''),
            
            # Database config
            db_path=os.getenv('DB_PATH', 'news_bot.db'),
            
            # API settings
            newsapi_rate_limit=int(os.getenv('NEWSAPI_RATE_LIMIT', '1000')),
            openai_rate_limit=int(os.getenv('OPENAI_RATE_LIMIT', '60')),
            request_timeout=int(os.getenv('REQUEST_TIMEOUT', '30')),
            
            # Bot settings
            max_articles_per_run=int(os.getenv('MAX_ARTICLES_PER_RUN', '200')),
            min_articles_for_analysis=int(os.getenv('MIN_ARTICLES_FOR_ANALYSIS', '5')),
            analysis_quality_threshold=float(os.getenv('ANALYSIS_QUALITY_THRESHOLD', '0.3')),
            
            # Notification settings
            notification_retry_attempts=int(os.getenv('NOTIFICATION_RETRY_ATTEMPTS', '3')),
            notification_retry_delay=float(os.getenv('NOTIFICATION_RETRY_DELAY', '5.0')),
            
            # OpenRouter config
            openrouter_api_key=os.getenv('OPENROUTER_API_KEY', ''),
            openrouter_model=os.getenv('OPENROUTER_MODEL', ''),
            
            # AI Model config
            ai_model=os.getenv('AI_MODEL', '')
        )
        
        config._validate()
        return config
    
    def _validate(self):
        """Validate configuration values"""
        errors = []
        
        # Validate required API keys
        if not self.newsapi_key:
            errors.append("NEWSAPI_KEY is required")
        elif len(self.newsapi_key) < 20:
            errors.append("NEWSAPI_KEY appears to be invalid (too short)")
            
        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY is required")
        elif not self.openai_api_key.startswith(('sk-', 'sk-proj-')):
            errors.append("OPENAI_API_KEY appears to be invalid (wrong format)")
        
        # Validate notification settings
        notification_methods = []
        
        if self.email_enabled:
            if not all([self.email_from, self.email_password, self.email_to]):
                errors.append("Email enabled but missing credentials (EMAIL_FROM, EMAIL_PASSWORD, EMAIL_TO)")
            elif '@' not in self.email_from or '@' not in self.email_to:
                errors.append("Invalid email addresses")
            else:
                notification_methods.append("Email")
        
        if self.telegram_enabled:
            if not all([self.telegram_bot_token, self.telegram_chat_id]):
                errors.append("Telegram enabled but missing credentials (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)")
            elif not self.telegram_bot_token.count(':') == 1:
                errors.append("Invalid Telegram bot token format")
            else:
                notification_methods.append("Telegram")
        
        if self.discord_enabled:
            if not self.discord_webhook_url:
                errors.append("Discord enabled but missing DISCORD_WEBHOOK_URL")
            elif not self.discord_webhook_url.startswith('https://discord.com/api/webhooks/'):
                errors.append("Invalid Discord webhook URL format")
            else:
                notification_methods.append("Discord")
        
        if self.pushover_enabled:
            if not all([self.pushover_token, self.pushover_user]):
                errors.append("Pushover enabled but missing credentials (PUSHOVER_TOKEN, PUSHOVER_USER)")
            else:
                notification_methods.append("Pushover")
        
        if not notification_methods:
            errors.append("At least one notification method must be enabled and properly configured")
        
        # Validate numeric settings
        if self.email_smtp_port not in [25, 465, 587, 993, 995]:
            errors.append("Invalid SMTP port (should be 25, 465, 587, 993, or 995)")
        
        if self.request_timeout < 5 or self.request_timeout > 300:
            errors.append("REQUEST_TIMEOUT should be between 5 and 300 seconds")
        
        if self.max_articles_per_run < 10 or self.max_articles_per_run > 200:
            errors.append("MAX_ARTICLES_PER_RUN should be between 10 and 200")
        
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
            raise ValueError(error_msg)
        
        logger.info(f"Configuration validated successfully. Notification methods: {', '.join(notification_methods)}")

class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, max_calls: int, time_window: int = 60):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        with self.lock:
            now = time.time()
            # Remove old calls outside the time window
            self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]
            
            if len(self.calls) >= self.max_calls:
                sleep_time = self.time_window - (now - self.calls[0]) + 1
                if sleep_time > 0:
                    logger.info(f"Rate limit reached, waiting {sleep_time:.1f} seconds")
                    time.sleep(sleep_time)
                    # Clean up again after waiting
                    now = time.time()
                    self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]
            
            self.calls.append(now)

class NewsBot:
    """Enhanced main bot class with comprehensive error handling"""
    
    def __init__(self, config: Config):
        self.config = config
        self.db = NewsDatabase(config.db_path)
        # Postgres is the primary truth layer for v2 (search/RAG/briefs/perf). Keep SQLite for legacy compatibility.
        self.pg_dsn = os.environ.get(
            'PG_DSN',
            'dbname=watchfuleye user=watchful password=watchfulpass host=localhost port=5432'
        )
        self.pg_repo = None
        try:
            ensure_postgres_schema(self.pg_dsn)
            self.pg_repo = PostgresRepo(self.pg_dsn)
            logger.info("Postgres backend initialized for ingestion + briefs")
        except Exception as e:
            logger.warning(f"Postgres backend unavailable; continuing in SQLite-only mode: {e}")
        self.newsapi_limiter = RateLimiter(max_calls=100, time_window=3600)  # 100 calls per hour
        self.openai_limiter = RateLimiter(max_calls=config.openai_rate_limit, time_window=60)
        self.shutdown_requested = False
        self._setup_signal_handlers()
        logger.info("Enhanced NewsBot initialized successfully")
    
    def _setup_signal_handlers(self):
        """Setup graceful shutdown handlers"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.shutdown_requested = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def fetch_news(self) -> List[Dict]:
        """Fetch latest news with topic rotation"""
        if self.shutdown_requested:
            return []
        
        # Get next topic using the reliable rotation mechanism
        topic_index = get_next_topic_index()
        chosen_topic, chosen_query = TOPICS[topic_index]
        logger.info(f"Selected topic for this run: {chosen_topic} (index: {topic_index})")
        
        # Rate limiting
        self.newsapi_limiter.wait_if_needed()
        url = "https://newsapi.org/v2/everything"
        params = {
            'q': chosen_query,
            'language': 'en',
            'sortBy': 'publishedAt',
            'pageSize': 100,
            'from': (datetime.utcnow() - timedelta(days=3)).isoformat()
        }
        headers = {
            'X-Api-Key': self.config.newsapi_key,
            'User-Agent': 'WatchfulEye/2.0'
        }
        try:
            logger.info(f"Fetching latest news for topic '{chosen_topic}' from NewsAPI...")
            response = requests.get(
                url, 
                params=params, 
                headers=headers, 
                timeout=self.config.request_timeout
            )
            response.raise_for_status()
            data = response.json()
            if 'status' in data and data['status'] != 'ok':
                raise ValueError(f"NewsAPI error: {data.get('message', 'Unknown error')}")
            articles = data.get('articles', [])
            logger.info(f"Retrieved {len(articles)} articles from NewsAPI for topic '{chosen_topic}'")
            if not articles:
                logger.warning("No articles returned from NewsAPI")
                return self.db.get_recent_articles(limit=50)
            try:
                stored_count, errors = self.db.store_articles(articles)
                # Also upsert to Postgres (best-effort) so briefs/search use the same truth layer.
                if self.pg_repo is not None:
                    try:
                        candidates: List[ArticleCandidate] = []
                        for a in articles:
                            if not a or not isinstance(a, dict):
                                continue
                            url_val = (a.get('url') or '').strip()
                            title_val = (a.get('title') or '').strip()
                            if not url_val or not title_val:
                                continue
                            desc_val = a.get('description') or None
                            src_name = None
                            if isinstance(a.get('source'), dict):
                                src_name = a.get('source', {}).get('name') or None
                            domain = (urlparse(url_val).netloc or '').lower().strip() or None
                            pub = a.get('publishedAt')
                            published_at = None
                            if pub:
                                try:
                                    published_at = datetime.fromisoformat(str(pub).replace('Z', '+00:00'))
                                except Exception:
                                    published_at = None
                            candidates.append(
                                ArticleCandidate(
                                    title=title_val,
                                    url=url_val,
                                    published_at=published_at,
                                    description=desc_val,
                                    source_name=src_name,
                                    source_domain=domain,
                                    ingestion_source='newsapi',
                                    topic=chosen_topic,
                                    raw=a,
                                )
                            )
                        if candidates:
                            self.pg_repo.upsert_sources([c.source_domain for c in candidates if c.source_domain])
                            self.pg_repo.upsert_articles(candidates)
                    except Exception as e:
                        logger.warning(f"Postgres upsert failed: {e}")
                if errors:
                    logger.warning(f"Article storage errors: {len(errors)} articles failed")
                    for error in errors[:5]:
                        logger.warning(f"  {error}")
                recent_articles = self.db.get_recent_articles(limit=80)
                logger.info(f"Using {len(recent_articles)} articles for analysis")
                # Attach topic for downstream use
                for a in recent_articles:
                    a['watchfuleye_topic'] = chosen_topic
                return recent_articles
            except DatabaseError as e:
                logger.error(f"Database error while storing articles: {e}")
                return articles[:50]
        except requests.exceptions.Timeout:
            logger.error("NewsAPI request timed out")
            raise
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.error("NewsAPI rate limit exceeded")
                raise
            elif e.response.status_code == 401:
                logger.error("NewsAPI authentication failed - check your API key")
                raise
            else:
                logger.error(f"NewsAPI HTTP error: {e}")
                raise
        except requests.exceptions.RequestException as e:
            logger.error(f"NewsAPI request failed: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse NewsAPI response: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching news: {e}")
            raise

    def build_evidence_pack_prompt(self, evidence_pack_text: str) -> str:
        """Build a prompt for Global Brief generation using an Evidence Pack.

        This is the v2 path: Postgres-backed evidence + strict JSON contract.
        """
        if not evidence_pack_text or len(evidence_pack_text.strip()) < 100:
            logger.warning("Evidence pack too short for prompt building")
            return ""
        ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        return f"""INTELLIGENCE BRIEFING - {ts}

{evidence_pack_text}

DELIVER THE GLOBAL BRIEF JSON NOW. Output ONLY valid JSON (no markdown, no commentary)."""
    
    def build_enhanced_prompt(self, articles: List[Dict], topic: str = None) -> str:
        """Build enhanced LLM prompt with topic focus"""
        if not articles:
            logger.warning("No articles provided for prompt building")
            return ""
        if len(articles) < self.config.min_articles_for_analysis:
            logger.warning(f"Only {len(articles)} articles available, minimum is {self.config.min_articles_for_analysis}")
        # Use topic if provided
        topic_focus = topic or (articles[0].get('watchfuleye_topic') if articles and 'watchfuleye_topic' in articles[0] else None)
        topic_str = f"\nFOCUS TOPIC: {topic_focus.upper()}\n" if topic_focus else ""
        # Group articles by category with enhanced metadata
        categories = {}
        total_sentiment = 0
        sentiment_count = 0
        
        for article in articles:
            category = article.get('category', 'general')
            if category not in categories:
                categories[category] = []
            categories[category].append(article)
            
            # Track overall sentiment
            sentiment = article.get('sentiment_score', 0)
            if sentiment != 0:
                total_sentiment += sentiment
                sentiment_count += 1
        
        # Calculate overall market sentiment
        avg_sentiment = total_sentiment / max(sentiment_count, 1)
        sentiment_label = "BULLISH" if avg_sentiment > 0.1 else "BEARISH" if avg_sentiment < -0.1 else "NEUTRAL"
        
        prompt = f"""You are an elite geopolitical intelligence analyst with 20+ years of experience in financial markets, defense analysis, and global trade patterns. Your analysis has guided Fortune 500 companies and hedge funds through multiple crises.\n\nINTELLIGENCE BRIEFING - {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}{topic_str}Market Sentiment: {sentiment_label} | {len(articles)} verified sources analyzed

===== CURRENT DEVELOPMENTS =====
"""
        
        # Add categorized articles with enhanced formatting
        article_count = 0
        for category, cat_articles in sorted(categories.items()):
            if not cat_articles or article_count >= 50:  # Limit total articles for context
                continue
                
            prompt += f"\n🔥 {category.upper()} SECTOR:\n"
            
            for idx, article in enumerate(cat_articles[:8], 1):  # Max 8 per category
                if article_count >= 50:
                    break
                    
                title = article.get('title', 'No title')[:120]  # Truncate long titles
                description = article.get('description', '')[:200]  # Truncate descriptions
                sentiment = article.get('sentiment_score', 0)
                source = article.get('source', 'Unknown')
                url = article.get('url', '')
                
                # Sentiment indicator
                if sentiment > 0.1:
                    sentiment_emoji = "📈 BULLISH"
                elif sentiment < -0.1:
                    sentiment_emoji = "📉 BEARISH"
                else:
                    sentiment_emoji = "➡️ NEUTRAL"
                
                prompt += f"{idx}. {sentiment_emoji} | {source}\n"
                prompt += f"   HEADLINE: {title}\n"
                if description:
                    prompt += f"   DETAILS: {description}\n"
                if url:
                    prompt += f"   SOURCE: {url}\n"
                prompt += "\n"
                
                article_count += 1
            
            prompt += "\n"
        
        prompt += f"""
===== ANALYSIS REQUIREMENTS =====

You are to produce a world-class intelligence brief that rivals Goldman Sachs, McKinsey, and Stratfor analysis. This MUST be institutional-grade quality.

STRUCTURE YOUR RESPONSE EXACTLY AS FOLLOWS:

1. BREAKING TIER-1 ALERT: Most critical development (70+ char headline, 2-3 sentence analysis)
2. BREAKING TIER-2 ALERT: Secondary critical development (70+ char headline, 2-3 sentence analysis) 
3. BREAKING TIER-3 ALERT: Third development (70+ char headline, 2-3 sentence analysis)

4. KEY NUMBERS (3 items):
   - Critical data points with specific figures
   - Include percentage changes, dollar amounts, timeline data
   - Source each number with specific outlet

5. MARKET PULSE (3 items):
   - Asset class movements with direction (↑↓↔)
   - Specific reasoning tied to news
   - "Why it matters" explanation for each

6. CRYPTO CORRELATION (2 items):
   - How crypto markets are reacting to geopolitical events
   - Specific token movements if relevant
   - Risk-on/risk-off sentiment

7. TECH IMPLICATIONS (1-2 items):
   - How technology sectors are affected
   - Supply chain, semiconductor, defense tech impacts

8. INVESTMENT DESK (4 ideas):
   - Specific actionable trades: BUY/SELL/HEDGE with tickers
   - Include rationale tied to specific news events
   - Mix of equity, commodity, currency, and volatility plays

9. RISK RADAR (2 risks):
   - Specific systemic risks with probability estimates
   - Tail risks that could cascade

10. EXECUTIVE SUMMARY:
    - 2-3 sentence bottom-line-up-front synthesis
    - What C-suite executives need to know immediately

===== QUALITY STANDARDS =====

- Every claim must be tied to specific source material provided above
- Use precise language: "according to [Source Name]" or "Reuters reports"
- Include specific data, percentages, dollar amounts, timeframes
- No generic statements - everything must be specific and actionable
- Think like you're briefing the Treasury Secretary or Fed Chairman
- Your analysis will be used for billion-dollar trading decisions

Current market sentiment: {sentiment_label}
Primary catalyst: [Identify the #1 market-moving story from the data]

DELIVER INSTITUTIONAL-GRADE INTELLIGENCE NOW."""
        
        return prompt
    
    @retry_with_backoff(max_retries=3, base_delay=3.0)
    def generate_investment_ideas(self, prompt: str) -> Optional[Dict]:
        """Generate investment ideas as a structured JSON object with enhanced error handling and validation"""
        if not prompt or len(prompt.strip()) < 100:
            logger.error("Prompt too short or empty for analysis")
            return None
        
        if self.shutdown_requested:
            return None
        
        self.openai_limiter.wait_if_needed()
        
        # Determine which API to use based on AI_MODEL
        if self.config.ai_model:
            # Check if AI_MODEL is an OpenRouter model (has provider prefix like openai/, anthropic/, etc.)
            if "/" in self.config.ai_model and self.config.openrouter_api_key:
                # Use OpenRouter for models with provider prefix
                url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.config.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://watchfuleye.us"  # Required by OpenRouter
                }
                model = self.config.ai_model
                masked_key = f"...{self.config.openrouter_api_key[-6:]}" if len(self.config.openrouter_api_key) > 6 else "***"
                logger.info(f"Using OpenRouter with AI_MODEL: {model}, key: {masked_key}")
            else:
                # Use direct OpenAI for simple model names like gpt-4o-mini
                url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.config.openai_api_key}",
                    "Content-Type": "application/json"
                }
                model = self.config.ai_model
                masked_key = f"...{self.config.openai_api_key[-6:]}" if len(self.config.openai_api_key) > 6 else "***"
                logger.info(f"Using OpenAI with AI_MODEL: {model}, key: {masked_key}")
        elif self.config.openrouter_api_key and self.config.openrouter_model:
            # Fallback to OpenRouter if AI_MODEL not set
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.config.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://watchfuleye.us"  # Required by OpenRouter
            }
            model = self.config.openrouter_model
            masked_key = f"...{self.config.openrouter_api_key[-6:]}" if len(self.config.openrouter_api_key) > 6 else "***"
            logger.info(f"Using OpenRouter with model: {model}, key: {masked_key}")
        else:
            # Final fallback to default OpenAI
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.config.openai_api_key}",
                "Content-Type": "application/json"
            }
            model = "gpt-4-1106-preview"
            masked_key = f"...{self.config.openai_api_key[-6:]}" if len(self.config.openai_api_key) > 6 else "***"
            logger.info(f"Using OpenAI default with model: {model}, key: {masked_key}")
        
        # Enhanced system prompt for institutional-grade analysis
        system_content = f"""You are a Senior Managing Director at Goldman Sachs with 25+ years of experience analyzing geopolitical risk and its market implications. Your analysis directly influences billion-dollar trading decisions.

CRITICAL REQUIREMENTS - FAILURE TO FOLLOW WILL RESULT IN REJECTION:
1. Every single field MUST be filled with specific, detailed content - NO empty fields, NO "No headline", NO placeholders
2. Headlines must be 70+ characters and capture the actual news event with specifics
3. Use ONLY information explicitly provided in the source material 
4. Include specific figures, percentages, dollar amounts, and timeframes from the sources
5. Reference specific outlets by name (Reuters, Bloomberg, CNN, etc.)
6. Each section must contain substantive, actionable intelligence

JSON STRUCTURE REQUIRED - ALL FIELDS MANDATORY:
{{
    "brief_topic": "MOST DOMINANT THEME from the news (e.g., UKRAINE_CONFLICT, ENERGY_CRISIS, CHINA_TENSIONS)",
    "breaking_news": [
        {{
            "tier": 1,
            "headline": "DETAILED 70+ character headline with specific facts (e.g., 'Putin Orders Military Response to Ukraine Drone Strikes on Russian Territory')",
            "time": "HH:MM format",
            "summary": "2-3 sentences with specific facts, numbers, locations, and source attribution",
            "key_insight": "Single sentence analytical insight linking to market impact with specifics",
            "actionable_advice": "Specific trading/investment recommendation with asset classes or tickers"
        }},
        {{
            "tier": 2,
            "headline": "DETAILED 70+ character headline for second most critical development", 
            "time": "HH:MM",
            "summary": "2-3 sentences with specific facts, numbers, and source attribution",
            "key_insight": "Single sentence analytical insight with market implications",
            "actionable_advice": "Specific trading recommendation"
        }},
        {{
            "tier": 3,
            "headline": "DETAILED 70+ character headline for third development",
            "time": "HH:MM", 
            "summary": "2-3 sentences with specific facts and source attribution",
            "key_insight": "Single sentence analytical insight",
            "actionable_advice": "Investment recommendation"
        }}
    ],
    "key_numbers": [
        {{
            "title": "Specific data point with actual number/percentage from sources",
            "value": "The actual number with units (e.g., '$4.5 billion', '23%', '500,000 barrels')",
            "context": "What this number means for markets with source attribution"
        }},
        {{
            "title": "Second critical data point with specific number",
            "value": "Actual numerical value with units", 
            "context": "Market context with source"
        }},
        {{
            "title": "Third critical data point",
            "value": "Numerical value with units",
            "context": "Context with source attribution"
        }}
    ],
    "market_pulse": [
        {{
            "asset": "Specific market/sector (e.g., 'European Defense Stocks', 'WTI Crude Oil')",
            "direction": "↑ or ↓ or ↔",
            "catalyst": "Specific news event driving movement",
            "why_it_matters": "Detailed explanation of impact on investors with specifics"
        }},
        {{
            "asset": "Second market/sector with specifics",
            "direction": "↑ or ↓ or ↔", 
            "catalyst": "Specific catalyst from news",
            "why_it_matters": "Why investors should care with details"
        }},
        {{
            "asset": "Third market/sector",
            "direction": "↑ or ↓ or ↔",
            "catalyst": "News catalyst", 
            "why_it_matters": "Investment implication with specifics"
        }}
    ],
    "crypto_barometer": [
        {{
            "token": "BITCOIN or specific crypto",
            "movement": "↑ or ↓ or ↔",
            "catalyst": "Link to geopolitical event with specifics",
            "quick_take": "Risk-on vs risk-off assessment with details"
        }},
        {{
            "token": "ETHEREUM or relevant crypto",
            "movement": "↑ or ↓ or ↔",
            "catalyst": "Geopolitical link with specifics",
            "quick_take": "Market sentiment assessment with reasoning"
        }}
    ],
    "tech_emergence": [
        {{
            "innovation": "Technology development mentioned in sources with specifics",
            "potential_impact": "Commercial/market impact with details",
            "adoption_outlook": "Investment implications with timeline if available"
        }}
    ],
    "idea_desk": [
        {{
            "action": "BUY/SELL/HEDGE/LONG/SHORT",
            "ticker": "Specific ticker or asset class (e.g., 'XLE', 'GLD', 'VIX')",
            "rationale": "Detailed rationale based on specific news analysis"
        }},
        {{
            "action": "Action type",
            "ticker": "Specific asset", 
            "rationale": "News-based rationale with specifics"
        }},
        {{
            "action": "Action",
            "ticker": "Asset with specifics",
            "rationale": "Detailed rationale"
        }}
    ],
    "final_intel": {{
        "summary": "2-3 sentence BLUF summary of most critical takeaways for C-suite",
        "investment_horizon": "Short-term/Medium-term/Long-term with reasoning",
        "key_risks": ["Risk 1 with specifics", "Risk 2 with details", "Risk 3"]
    }}
}}

QUALITY CONTROL - MANDATORY:
- NO generic statements - everything must be source-specific
- NO invented data - use only what's provided in the news sources
- NO empty fields or placeholder text
- Include specific outlet names, numbers, dates, locations
- Focus on immediate trading/investment implications
- Think: "What would Larry Fink need to know to make a $1B decision RIGHT NOW?"

REMEMBER: Any response with empty fields, "No headline", or placeholder content will be REJECTED. Every field must contain substantive, specific content based on the provided sources.

OUTPUT ONLY VALID JSON - NO OTHER TEXT."""
        
        data = {
            'model': model,
            'messages': [
                {
                    'role': 'system',
                    'content': system_content
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.2,  # Lower for more factual consistency
            'max_tokens': 4000,
            'top_p': 0.8
        }
        
        # Add response format only for OpenAI
        if "openrouter.ai" not in url:
            data['response_format'] = {"type": "json_object"}
        
        start_time = time.time()
        
        # Log request details
        logger.info(f"Request model: {data['model']}")
        logger.info(f"Prompt length: {len(prompt)} characters")
        
        try:
            logger.info("Generating INSTITUTIONAL-GRADE intelligence brief with OpenAI...")
            
            # Use the EXACT same approach as our working curl tests
            import subprocess
            import tempfile
            
            # Create the exact JSON payload
            json_payload = {
                'model': model,
                'messages': data['messages'],
                'max_tokens': data['max_tokens']
            }
            
            # Write to temp file and use curl (since curl works but requests doesn't)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                import json as json_lib
                json_lib.dump(json_payload, f)
                temp_file = f.name
            
            try:
                # Use curl with the exact same parameters that work
                curl_cmd = [
                    'curl', '-X', 'POST', url,
                    '-H', f'Authorization: Bearer {self.config.openrouter_api_key}',
                    '-H', 'Content-Type: application/json',
                    '-H', 'HTTP-Referer: https://watchfuleye.us',
                    '-d', f'@{temp_file}',
                    '--silent'
                ]
                
                result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=60)
                
                if result.returncode != 0:
                    logger.error(f"Curl failed with return code {result.returncode}: {result.stderr}")
                    raise Exception(f"Curl request failed: {result.stderr}")
                
                response_text = result.stdout
                response_data = json_lib.loads(response_text)
                
                # Check for API errors
                if 'error' in response_data:
                    error_msg = response_data['error'].get('message', 'Unknown error')
                    logger.error(f"API error: {error_msg}")
                    raise Exception(f"API error: {error_msg}")
                
                result_text = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                
            finally:
                # Clean up temp file
                import os
                try:
                    os.unlink(temp_file)
                except:
                    pass
            
            processing_time = time.time() - start_time
            
            # Parse JSON response - handle markdown code blocks
            try:
                # Remove markdown code blocks if present
                clean_text = result_text.strip()
                if clean_text.startswith('```json'):
                    clean_text = clean_text[7:]  # Remove ```json
                if clean_text.startswith('```'):
                    clean_text = clean_text[3:]   # Remove ```
                if clean_text.endswith('```'):
                    clean_text = clean_text[:-3]  # Remove trailing ```
                clean_text = clean_text.strip()
                
                structured_data = json.loads(clean_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI JSON response: {e}")
                logger.error(f"Raw response text: {result_text[:1000]}...")
                raise ValueError(f"OpenAI response was not valid JSON. Error: {e}")

            # Enhanced validation - reject poor quality responses
            if self._validate_structured_data(structured_data):
                logger.info(f"Generated HIGH-QUALITY structured intelligence in {processing_time:.1f}s")
            else:
                logger.error("OpenAI response failed quality validation - contains empty fields or placeholders")
                raise ValueError("Response quality too low - contains empty fields or placeholder content")

            usage = response_data.get('usage', {})
            if usage:
                logger.info(f"OpenAI usage - Prompt: {usage.get('prompt_tokens', 0)}, "
                          f"Completion: {usage.get('completion_tokens', 0)}, "
                          f"Total: {usage.get('total_tokens', 0)} tokens")
            
            return structured_data
            
        except requests.exceptions.Timeout:
            logger.error("OpenAI request timed out")
            raise
        except requests.exceptions.HTTPError as e:
            error_content = "No error content."
            try:
                error_content = e.response.json()
            except json.JSONDecodeError:
                error_content = e.response.text
            logger.error(f"OpenAI/OpenRouter HTTP error: {e}. Status: {e.response.status_code}. Response: {error_content}")
            if e.response.status_code == 402:
                logger.error("💳 PAYMENT REQUIRED - Insufficient credits on OpenRouter")
                logger.error(f"   Current model: {model}")
                logger.error(f"   Masked key: {masked_key}")
                logger.error("   Solutions:")
                logger.error("   1. Add more credits at https://openrouter.ai/settings/credits")
                logger.error("   2. Change to a cheaper model (e.g., anthropic/claude-3-haiku)")
                logger.error("   3. Reduce MAX_ARTICLES_PER_RUN or max_tokens")
            elif e.response.status_code == 429:
                logger.error("Rate limit exceeded")
            elif e.response.status_code == 401:
                logger.error("Authentication failed - check API key")
            elif e.response.status_code == 400:
                logger.error(f"Bad request: {error_content}")
            raise
        except ValueError as e:
             logger.error(f"Error processing OpenAI response: {e}")
             raise
        except Exception as e:
            logger.error(f"Unexpected error generating structured ideas: {e}", exc_info=True)
            raise
    
    def _validate_structured_data(self, data: Dict) -> bool:
        """Validate structured data quality to reject poor responses"""
        if not isinstance(data, dict):
            return False
        
        # Check breaking news
        breaking_news = data.get('breaking_news', [])
        if not isinstance(breaking_news, list) or len(breaking_news) < 3:
            logger.warning("Missing or insufficient breaking news items")
            return False
        
        for i, item in enumerate(breaking_news):
            headline = item.get('headline', '')
            summary = item.get('summary', '')
            if not headline or not summary or len(headline) < 50:
                logger.warning(f"Breaking news item {i+1} has empty or short headline/summary")
                return False
            if 'No headline' in headline or 'no headline' in headline.lower():
                logger.warning(f"Breaking news item {i+1} contains placeholder headline")
                return False
        
        # Check key numbers
        key_numbers = data.get('key_numbers', [])
        if not isinstance(key_numbers, list) or len(key_numbers) < 2:
            logger.warning("Missing or insufficient key numbers")
            return False
        
        for i, item in enumerate(key_numbers):
            if not item.get('title') or not item.get('value'):
                logger.warning(f"Key number {i+1} missing title or value")
                return False
        
        # Check market pulse
        market_pulse = data.get('market_pulse', [])
        if not isinstance(market_pulse, list) or len(market_pulse) < 2:
            logger.warning("Missing or insufficient market pulse items")
            return False
        
        for i, item in enumerate(market_pulse):
            if not item.get('asset') or not item.get('catalyst'):
                logger.warning(f"Market pulse item {i+1} missing asset or catalyst")
                return False
        
        # Check final intel
        final_intel = data.get('final_intel', {})
        if not isinstance(final_intel, dict) or not final_intel.get('summary'):
            logger.warning("Missing or empty final intel summary")
            return False
        
        return True
    
    def format_message(self, structured_data: Dict, processing_time: float = 0) -> str:
        """Format the structured intelligence data with numbered source references."""
        if not structured_data or not isinstance(structured_data, dict):
            logger.error("Invalid or empty structured_data received for formatting.")
            return "Error: Could not generate brief due to missing analysis data."

        now_utc = datetime.utcnow()
        current_date_str = now_utc.strftime('%Y-%m-%d')

        # Get topic for header
        topic_display = (
            structured_data.get('topic') or
            structured_data.get('brief_topic') or
            'geopolitics'
        ).upper()

        # Get actual article URLs from database
        recent_articles = self.db.get_recent_articles(limit=100)
        
        # Create a list of actual URLs to rotate through
        actual_urls = []
        for article in recent_articles:
            if article.get('url') and 'http' in article['url']:
                actual_urls.append(article['url'])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in actual_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        logger.info(f"Using {len(unique_urls)} unique article URLs for attribution")
        
        # URL tracking for numbered references
        url_references = {}
        url_counter = 1
        
        def get_next_url_ref() -> str:
            """Get next URL reference number"""
            nonlocal url_counter
            if not unique_urls:
                return ""
            
            url = unique_urls[(url_counter - 1) % len(unique_urls)]
            ref = f"[{url_counter}]"
            url_references[ref] = url
            url_counter += 1
            return ref

        message_parts = []
        
        # Header with proper formatting
        message_parts.extend([
            "┏━━ *GLOBAL BRIEF* ━━┓",
            f"*#{topic_display}*",
            f"— {current_date_str}",
            "┗━━━━━━━━━━━━━━━━┛\n"
        ])
        
        # Breaking news items with numbered references
        if 'breaking_news' in structured_data:
            for i, item in enumerate(structured_data['breaking_news'][:3], 1):
                tier = item.get('tier', i)
                time_str = item.get('time', datetime.utcnow().strftime('%H:%M'))
                headline = item.get('headline', 'Breaking News Update')
                summary = item.get('summary', '')
                insight = item.get('key_insight', '')
                advice = item.get('actionable_advice', '')
                
                # Get reference number
                ref = get_next_url_ref()
                
                message_parts.extend([
                    f"⚡{i} *BREAKING TIER-{tier}* — +++ {time_str} {headline} +++",
                    f"{summary} {ref}",
                    f"*KEY INSIGHT:* {insight}",
                    f"*ACTIONABLE ADVICE:* {advice}\n"
                ])
        
        # Key numbers with numbered references
        if 'key_numbers' in structured_data:
            message_parts.append("📊 *KEY NUMBERS*")
            for number in structured_data['key_numbers'][:3]:
                title = number.get('title', 'Market Data')
                value = number.get('value', '')
                context = number.get('context', '')
                
                # Get reference number
                ref = get_next_url_ref()
                
                message_parts.extend([
                    f"• *{title}* {ref} — {value}",
                    f"  {context}"
                ])
            message_parts.append("")
        
        # Market pulse with numbered references
        if 'market_pulse' in structured_data:
            message_parts.append("📈 *MARKET PULSE*")
            for market in structured_data['market_pulse'][:3]:
                asset = market.get('asset', 'Market Sector')
                direction = market.get('direction', '↔')
                catalyst = market.get('catalyst', '')
                impact = market.get('why_it_matters', '')
                
                # Get reference number
                ref = get_next_url_ref()
                
                message_parts.extend([
                    f"• *{asset} {direction}* — {catalyst} {ref}",
                    f"  Why it matters: {impact}"
                ])
            message_parts.append("")
        
        # Crypto barometer with numbered references
        if 'crypto_barometer' in structured_data:
            message_parts.append("₿ *CRYPTO BAROMETER*")
            for crypto in structured_data['crypto_barometer'][:2]:
                token = crypto.get('token', 'BITCOIN')
                movement = crypto.get('movement', '↔')
                catalyst = crypto.get('catalyst', '')
                take = crypto.get('quick_take', '')
                
                # Get reference number
                ref = get_next_url_ref()
                
                message_parts.extend([
                    f"• *{token} {movement}* — {catalyst} {ref}",
                    f"  {take}"
                ])
            message_parts.append("")
        
        # Tech emergence with numbered references
        if 'tech_emergence' in structured_data:
            message_parts.append("🔬 *TECH EMERGENCE*")
            for tech in structured_data['tech_emergence'][:2]:
                innovation = tech.get('innovation', 'Technology Development')
                impact = tech.get('potential_impact', '')
                outlook = tech.get('adoption_outlook', '')
                
                # Get reference number
                ref = get_next_url_ref()
                
                message_parts.extend([
                    f"*{innovation}* {ref}",
                    f"Impact: {impact}",
                    f"Outlook: {outlook}\n"
                ])
        
        # Investment ideas with numbered references
        if 'idea_desk' in structured_data:
            message_parts.append("💡 *IDEA DESK*")
            for idea in structured_data['idea_desk'][:3]:
                action = idea.get('action', 'WATCH')
                ticker = idea.get('ticker', 'MARKET')
                rationale = idea.get('rationale', '')
                
                # Get reference number
                ref = get_next_url_ref()
                
                message_parts.append(f"• *{action} {ticker}* — {rationale} {ref}")
            message_parts.append("")
        
        # Final intel
        if 'final_intel' in structured_data:
            intel = structured_data['final_intel']
            summary = intel.get('summary', '')
            horizon = intel.get('investment_horizon', '')
            risks = intel.get('key_risks', [])
            
            message_parts.extend([
                "🎯 *FINAL INTEL*",
                f"{summary}",
                f"*Investment Horizon:* {horizon}",
                f"*Key Risks:* {', '.join(risks[:3])}\n"
            ])
        
        # Footer with updated website
        message_parts.extend([
            "━━━━━━━━━━━━━━━━━",
            f"📰 *{len(unique_urls)} sources analyzed*",
            f"🌐 *Full analysis:* https://watchfuleye.us",
            f"⚱ *Processing:* {processing_time:.1f}s",
            "*🔍 Powered by WatchfulEye*"
        ])
        
        # Add source references at the end
        if url_references:
            message_parts.extend([
                "\n━━━━━━━━━━━━━━━━━",
                "*📎 SOURCES:*"
            ])
            
            # Add first 10 source URLs (to keep message manageable)
            for ref, url in list(url_references.items())[:10]:
                # Shorten URLs for cleaner display
                display_url = url
                if len(url) > 50:
                    domain = url.split('/')[2] if '/' in url else url
                    display_url = f"{domain}/..."
                message_parts.append(f"{ref} {display_url}")
            
            if len(url_references) > 10:
                message_parts.append(f"... +{len(url_references) - 10} more sources")
        
        message_parts.append("━━━━━━━━━━━━━━━━━")
        
        final_message = '\n'.join(message_parts)
        
        # Log the message details for debugging
        logger.info(f"Formatted message: {len(final_message)} characters, {len(url_references)} numbered references")
        
        return final_message
    
    def log_output(self, formatted_message: str, raw_analysis_data: Dict, article_count: int, processing_time: float, articles_used_in_brief: List[Dict]):
        """Comprehensive output logging for analysis and debugging (handles structured raw_analysis_data)."""
        try:
            timestamp = datetime.utcnow()
            timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')
            date_str = timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
            
            # 1. Save formatted output
            formatted_file = f"outputs/formatted/brief_{timestamp_str}.txt"
            with open(formatted_file, 'w', encoding='utf-8') as f:
                f.write(f"=== WATCHFULEYE INTELLIGENCE BRIEF ===\n")
                f.write(f"Generated: {date_str}\n")
                f.write(f"Articles Analyzed (approx for prompt): {self.db.get_total_articles_in_last_run_period()} | Brief Articles: {article_count} | Processing: {processing_time:.1f}s\n")
                f.write(f"Length: {len(formatted_message)} chars\n")
                f.write("=" * 50 + "\n\n")
                f.write(formatted_message)
            
            # 2. Save raw analysis (now a JSON object)
            raw_file = f"outputs/raw_analysis/analysis_structured_{timestamp_str}.json"
            with open(raw_file, 'w', encoding='utf-8') as f:
                json.dump(raw_analysis_data, f, indent=2, ensure_ascii=False)
            
            # 3. Quality metrics and analysis (pass the structured data)
            quality_metrics = self.analyze_output_quality(formatted_message, raw_analysis_data, articles_used_in_brief)
            
            # 4. Save metrics as JSON
            metrics_file = f"outputs/metrics/metrics_{timestamp_str}.json"
            metrics_data = {
                "timestamp": date_str,
                "timestamp_unix": timestamp.timestamp(),
                "formatted_message_path": formatted_file,
                "raw_analysis_path": raw_file, # Path to the structured JSON
                "article_count_prompt": self.db.get_total_articles_in_last_run_period(),
                "article_count_brief": article_count,
                "processing_time": processing_time,
                "message_length": len(formatted_message),
                "analysis_raw_content": raw_analysis_data, # Store the dict itself
                "quality_metrics": quality_metrics,
                "articles_used_in_brief": [
                    {
                        "title": article.get('title', ''),
                        "summary": article.get('summary', ''),
                        "key_insight": article.get('key_insight', ''),
                        # Add other relevant fields if available from structured_data's breaking_news items
                    } for article in articles_used_in_brief[:3]
                ]
            }
            
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(metrics_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📊 Output logged: {formatted_file} & {raw_file}")
            logger.info(f"📈 Quality score: {quality_metrics['overall_score']:.2f}/10")
            
            if quality_metrics['issues']:
                logger.warning(f"⚠️ Quality issues detected: {', '.join(quality_metrics['issues'])}")
            
        except Exception as e:
            logger.error(f"Failed to log output: {e}", exc_info=True)
    
    def analyze_output_quality(self, formatted_message: str, raw_analysis_data: Dict, articles_in_brief: List[Dict]) -> Dict:
        """Analyze output quality (handles structured raw_analysis_data) and detect potential issues"""
        issues = []
        score = 10.0

        # Check message length
        if len(formatted_message) > TELEGRAM_MAX_MESSAGE_LENGTH:
            issues.append("Message too long for Telegram")
            score -= 2.0
        elif len(formatted_message) < 1000: # Expecting more detailed briefs now
            issues.append("Message too short (expected >1000 chars for detailed brief)")
            score -= 1.0

        # Check for basic formatting (placeholder, more checks can be added)
        if "N/A" in formatted_message or "No summary available" in formatted_message or "Insight pending" in formatted_message:
            issues.append("Placeholder content detected (N/A, etc.)")
            score -= 1.5

        # Check for presence of key sections in the raw_analysis_data (the JSON from LLM)
        required_top_level_keys = ["brief_topic", "breaking_news", "key_numbers", "market_pulse", "crypto_barometer", "tech_emergence", "idea_desk", "risk_radar", "executive_summary"]
        missing_top_keys = [key for key in required_top_level_keys if key not in raw_analysis_data]
        if missing_top_keys:
            issues.append(f"Missing top-level keys in AI JSON response: {', '.join(missing_top_keys)}")
            score -= 2.0 * len(missing_top_keys)
        
        # Check if breaking news has at least 1 item, ideally 3
        breaking_news = raw_analysis_data.get("breaking_news", [])
        if not isinstance(breaking_news, list) or len(breaking_news) == 0:
            issues.append("Missing or empty 'breaking_news' in AI JSON")
            score -= 2.0
        elif len(breaking_news) < 3:
            issues.append(f"Insufficient breaking news items (got {len(breaking_news)}, expected 3)")
            score -= 1.0
        else: # Check content of breaking news items
            for i, bn_item in enumerate(breaking_news[:3]):
                if not bn_item.get("headline") or not bn_item.get("summary") or not bn_item.get("key_insight"):
                    issues.append(f"Breaking news item {i+1} missing headline, summary, or insight.")
                    score -= 0.5
                    break # Stop after first problematic item
        
        # Check executive summary length
        executive_summary = raw_analysis_data.get("executive_summary", "")
        if not executive_summary or len(executive_summary) < 50:
            issues.append("Executive summary too short or missing in AI JSON")
            score -= 1.0
        
        # Rough check for list lengths for other sections if they exist
        for section_name, min_items in [("key_numbers",1), ("market_pulse",1), ("idea_desk",1), ("risk_radar",1)]:
            items = raw_analysis_data.get(section_name, [])
            if not isinstance(items, list) or len(items) < min_items:
                issues.append(f"Insufficient items in '{section_name}' (got {len(items)}, expected >={min_items})")
                score -= 0.5

        return {
            "overall_score": max(0, score),
            "issues": list(set(issues)), # Remove duplicate issue messages
            "message_length": len(formatted_message),
            "analysis_json_valid_structure": not missing_top_keys,
            "breaking_news_count": len(breaking_news),
            "executive_summary_length": len(executive_summary),
            "sections_present_in_json": [k for k in required_top_level_keys if k in raw_analysis_data]       
        }
    
    @retry_with_backoff(max_retries=3, base_delay=2.0)
    def send_email(self, subject: str, message: str) -> bool:
        """Send email notification with enhanced error handling"""
        if not self.config.email_enabled:
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config.email_from
            msg['To'] = self.config.email_to
            msg['Subject'] = subject
            
            # Add both plain text and HTML versions
            html_message = message.replace('\n', '<br>').replace('**', '<strong>').replace('**', '</strong>')
            msg.attach(MIMEText(message, 'plain'))
            msg.attach(MIMEText(f"<html><body><pre>{html_message}</pre></body></html>", 'html'))
            
            server = smtplib.SMTP(self.config.email_smtp_server, self.config.email_smtp_port)
            server.starttls()
            server.login(self.config.email_from, self.config.email_password)
            text = msg.as_string()
            server.sendmail(self.config.email_from, self.config.email_to, text)
            server.quit()
            
            logger.info(f"Email sent successfully to {self.config.email_to}")
            return True
            
        except smtplib.SMTPAuthenticationError:
            logger.error("Email authentication failed - check credentials")
            raise
        except smtplib.SMTPRecipientsRefused:
            logger.error("Email recipient refused - check email address")
            raise
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected email error: {e}")
            raise
    
    @retry_with_backoff(max_retries=3, base_delay=2.0)
    def send_telegram(self, message: str) -> bool:
        """Send Telegram message with enhanced formatting and intelligent truncation"""
        if not self.config.telegram_enabled:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
            
            telegram_message = message
            
            # Intelligent truncation for Telegram limits (4096 chars)
            if len(telegram_message) > TELEGRAM_MAX_MESSAGE_LENGTH:
                logger.warning(f"Message too long ({len(telegram_message)} chars), truncating intelligently")
                
                # Find the footer and preserve it
                footer_start = telegram_message.find("━━━━━━━━━━━━━━━━━")
                if footer_start > 0:
                    footer = telegram_message[footer_start:]
                    content = telegram_message[:footer_start]
                else:
                    footer = "\n\n*🔍 Powered by WatchfulEye* ✂️*(truncated)*"
                    content = telegram_message
                
                # Calculate available space for content
                available_space = TELEGRAM_MAX_MESSAGE_LENGTH - len(footer) - 50  # 50 char buffer
                
                if len(content) > available_space:
                    # Truncate at a complete section boundary
                    # Try to find a good truncation point that won't break markdown
                    truncation_candidates = [
                        content.rfind('\n\n💡', 0, available_space),  # Before IDEA DESK
                        content.rfind('\n\n🔬', 0, available_space),  # Before TECH
                        content.rfind('\n\n₿', 0, available_space),   # Before CRYPTO
                        content.rfind('\n\n📈', 0, available_space),  # Before MARKET PULSE
                        content.rfind('\n\n📊', 0, available_space),  # Before KEY NUMBERS
                        content.rfind('\n\n⚡', 0, available_space),  # Before a breaking news item
                    ]
                    
                    # Find the best truncation point (highest valid position)
                    truncation_point = max([p for p in truncation_candidates if p > available_space * 0.5] or [available_space])
                    
                    content = content[:truncation_point]
                    content += "\n\n... *(analysis continues online)*"
                
                telegram_message = content + "\n\n" + footer
                logger.info(f"Truncated to {len(telegram_message)} characters")
            
            data = {
                'chat_id': self.config.telegram_chat_id,
                'text': telegram_message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True,
                'disable_notification': False
            }
            
            response = requests.post(url, json=data, timeout=self.config.request_timeout)
            response.raise_for_status()
            
            result = response.json()
            if not result.get('ok'):
                # If markdown parsing failed, try sending without parse_mode
                logger.warning("Telegram markdown parsing failed, retrying without formatting")
                data['parse_mode'] = None
                response = requests.post(url, json=data, timeout=self.config.request_timeout)
                response.raise_for_status()
                result = response.json()
                
                if not result.get('ok'):
                    raise ValueError(f"Telegram API error: {result.get('description', 'Unknown error')}")
            
            logger.info(f"Telegram message sent successfully to chat {self.config.telegram_chat_id}")
            return True
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                logger.error("Telegram bad request - check bot token and chat ID")
                # Try to get more details from response
                try:
                    error_data = e.response.json()
                    logger.error(f"Telegram error details: {error_data}")
                except:
                    pass
            elif e.response.status_code == 401:
                logger.error("Telegram unauthorized - check bot token")
            else:
                logger.error(f"Telegram HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            raise
    
    @retry_with_backoff(max_retries=3, base_delay=2.0)
    def send_discord(self, message: str) -> bool:
        """Send Discord webhook message with enhanced formatting"""
        if not self.config.discord_enabled:
            return False
        
        try:
            # Format for Discord
            discord_message = message.replace('**', '**').replace('🌍 **', '🌍 **')
            
            data = {
                'content': discord_message,
                'username': 'WatchfulEye Intelligence',
                'avatar_url': 'https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f30d.png'
            }
            
            response = requests.post(
                self.config.discord_webhook_url, 
                json=data, 
                timeout=self.config.request_timeout
            )
            response.raise_for_status()
            
            logger.info("Discord message sent successfully")
            return True
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                logger.error("Discord bad request - check webhook URL")
            elif e.response.status_code == 404:
                logger.error("Discord webhook not found - check URL")
            else:
                logger.error(f"Discord HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Discord error: {e}")
            raise
    
    @retry_with_backoff(max_retries=3, base_delay=2.0)
    def send_pushover(self, message: str) -> bool:
        """Send Pushover notification with enhanced formatting"""
        if not self.config.pushover_enabled:
            return False
        
        try:
            data = {
                'token': self.config.pushover_token,
                'user': self.config.pushover_user,
                'message': message,
                'title': '🌍 WatchfulEye Intelligence Alert',
                'priority': 0,
                'html': 1  # Enable HTML formatting
            }
            
            response = requests.post(
                'https://api.pushover.net/1/messages.json', 
                data=data, 
                timeout=self.config.request_timeout
            )
            response.raise_for_status()
            
            result = response.json()
            if result.get('status') != 1:
                raise ValueError(f"Pushover error: {result.get('errors', 'Unknown error')}")
            
            logger.info("Pushover notification sent successfully")
            return True
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                logger.error("Pushover bad request - check token and user key")
            else:
                logger.error(f"Pushover HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Pushover error: {e}")
            raise
    
    def send_notifications(self, structured_analysis_data: Dict, processing_time: float = 0) -> Tuple[bool, List[str]]:
        """Send notifications with structured data via all enabled channels"""
        try:
            # Format data for notifications
            message = self.format_message(structured_analysis_data, processing_time)
            subject = "WatchfulEye Intelligence: " + structured_analysis_data.get('executive_summary', '')[:50] + "..."
            
            logger.info(f"Sending notifications with structured data ({len(message)} chars)...")
            
            success_count = 0
            errors = []
            
            # Get article breakdown
            articles_in_brief = []
            for headline in structured_analysis_data.get('breaking_news', []):
                article_id = headline.get('article_id')
                if article_id and isinstance(article_id, int):
                    articles_in_brief.append(article_id)
            
            # Store the specific articles used in this analysis
            article_count = len(articles_in_brief)
            
            # Log the formatted output
            try:
                self.log_output(
                    formatted_message=message,
                    raw_analysis_data=structured_analysis_data,
                    article_count=article_count,
                    processing_time=processing_time,
                    articles_used_in_brief=articles_in_brief
                )
            except Exception as e:
                logger.warning(f"Failed to log output: {e}")
            
            # Try each enabled notification method
            notification_methods = [
                ('Email', self.config.email_enabled, lambda: self.send_email(subject, message)),
                ('Telegram', self.config.telegram_enabled, lambda: self.send_telegram(message)),
                ('Discord', self.config.discord_enabled, lambda: self.send_discord(message)),
                ('Pushover', self.config.pushover_enabled, lambda: self.send_pushover(message))
            ]
            
            for method_name, enabled, send_func in notification_methods:
                if not enabled:
                    continue
                    
                try:
                    if send_func():
                        success_count += 1
                        logger.info(f"{method_name} notification sent successfully")
                    else:
                        errors.append(f"{method_name}: Failed to send")
                        
                except Exception as e:
                    error_msg = f"{method_name}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"Failed to send {method_name} notification: {e}")
            
            overall_success = success_count > 0
            
            if overall_success:
                logger.info(f"Notifications sent successfully via {success_count} method(s)")
                # Calculate and log time until next post
                next_run_time = datetime.now() + timedelta(hours=4)
                time_until_next = (next_run_time - datetime.now())
                hours = time_until_next.seconds // 3600
                minutes = (time_until_next.seconds % 3600) // 60
                logger.info(f"📅 Next post scheduled in {hours} hours and {minutes} minutes (at {next_run_time.strftime('%Y-%m-%d %H:%M:%S')})")
            else:
                logger.error("All notification methods failed")
            
            return overall_success, errors
            
        except Exception as e:
            logger.error(f"Failed to send notifications: {e}")
            return False, [f"Failed to send notifications: {e}"]
    
    def perform_maintenance(self):
        """Perform database and system maintenance"""
        try:
            logger.info("Performing system maintenance...")
            
            # Database maintenance
            self.db.optimize_database()
            
            # Cleanup old data (keep 30 days)
            articles_deleted, analyses_deleted = self.db.cleanup_old_data(days=30)
            
            # Health check
            health = self.db.get_system_health()
            logger.info(f"System health score: {health.get('health_score', 0):.2f}")
            
            # Create backup if needed (weekly)
            if datetime.now().weekday() == 0:  # Monday
                try:
                    backup_path = self.db.backup_database()
                    logger.info(f"Weekly backup created: {backup_path}")
                except Exception as e:
                    logger.warning(f"Backup failed: {e}")
            
            logger.info("Maintenance completed successfully")
            
        except Exception as e:
            logger.error(f"Maintenance failed: {e}")
    
    def run_workflow(self):
        """Execute the complete workflow with comprehensive error handling"""
        if self.shutdown_requested:
            logger.info("Shutdown requested, skipping workflow")
            return
        workflow_start = time.time()
        logger.info("=" * 60)
        logger.info("Starting enhanced geo-political news workflow...")
        try:
            # Step 1: Build evidence from Postgres truth layer (fallback to NewsAPI ingestion if needed)
            evidence_articles: List[Dict] = []
            if self.pg_repo is not None:
                try:
                    evidence_articles = fetch_recent_evidence(
                        self.pg_dsn,
                        lookback_hours=48,
                        limit=80,
                        min_trust=0.45,
                        bucket='main',
                    )
                except Exception as e:
                    logger.warning(f"Failed to fetch Postgres evidence: {e}")

            if not evidence_articles or len(evidence_articles) < self.config.min_articles_for_analysis:
                logger.info("Not enough Postgres evidence; ingesting via NewsAPI as fallback...")
                articles = self.fetch_news()
                if not articles:
                    logger.warning("No articles found, skipping this run")
                    return
                if self.pg_repo is not None:
                    try:
                        evidence_articles = fetch_recent_evidence(
                            self.pg_dsn,
                            lookback_hours=48,
                            limit=80,
                            min_trust=0.35,
                            bucket='main',
                        )
                    except Exception:
                        evidence_articles = []

            if not evidence_articles:
                logger.warning("No evidence articles found, skipping this run")
                return

            evidence_items, evidence_pack_text = build_evidence_pack(
                evidence_articles,
                max_items=60,
                max_fulltext_items=12,
                max_fulltext_chars=1200,
                max_excerpt_chars=360,
            )

            # Step 2: Build evidence-pack prompt
            prompt = self.build_evidence_pack_prompt(evidence_pack_text)
            if not prompt:
                logger.error("Failed to build analysis prompt")
                return
            # Step 3: Generate Global Brief JSON (contract preserved)
            analysis_start = time.time()
            investment_ideas = self.generate_investment_ideas(prompt)
            analysis_time = time.time() - analysis_start
            if not investment_ideas:
                logger.error("Failed to generate investment ideas, skipping this run")
                return

            # Step 3b: Validate schema; attempt repair once if needed
            errors = validate_global_brief(investment_ideas)
            if errors:
                logger.warning("Global Brief JSON failed schema validation; attempting repair...")
                repair_prompt = (
                    "Your previous JSON failed our schema validation.\n"
                    f"Errors:\n{chr(10).join(errors[:25])}\n\n"
                    "Use ONLY the evidence pack below. Return ONLY fixed JSON.\n\n"
                    f"{evidence_pack_text}\n\n"
                    "BROKEN_JSON:\n"
                    f"{json.dumps(investment_ideas)}"
                )
                repaired = self.generate_investment_ideas(repair_prompt)
                if not repaired:
                    logger.error("Repair attempt failed; aborting this run.")
                    return
                errors2 = validate_global_brief(repaired)
                if errors2:
                    logger.error("Repair attempt failed schema validation; aborting this run.")
                    return
                investment_ideas = repaired

            # Step 4: Store analysis to Postgres (truth layer) and extract recommendations
            brief_topic = investment_ideas.get('brief_topic') if isinstance(investment_ideas, dict) else None
            model_used = self.config.ai_model or self.config.openrouter_model or "unknown"
            try:
                if self.pg_repo is not None:
                    store_brief_and_recommendations(
                        self.pg_dsn,
                        prompt=prompt,
                        model_used=model_used,
                        article_count=len(evidence_items),
                        processing_time=analysis_time,
                        topic=brief_topic,
                        brief_json=investment_ideas,
                    )
            except Exception as e:
                logger.warning(f"Failed to store Postgres analysis: {e}")

            # Step 4b: Store to legacy SQLite for backward compatibility (best-effort)
            try:
                # Store topic in model_used or as a new field if needed
                self.db.store_analysis(
                    content=prompt,  # or the formatted message if preferred
                    model_used=brief_topic or "unknown",
                    article_count=len(evidence_items),
                    processing_time=analysis_time,
                    raw_response_json=json.dumps(investment_ideas)
                )
            except Exception as e:
                logger.warning(f"Failed to store analysis: {e}")
            # Step 5: Send notifications (passing the structured data)
            workflow_time = time.time() - workflow_start
            success, errors = self.send_notifications(investment_ideas, workflow_time)
            if success:
                logger.info(f"Workflow completed successfully in {workflow_time:.1f}s with structured JSON!")
                if errors:
                    logger.warning(f"Some notification methods failed: {errors}")
            else:
                logger.error(f"Workflow completed but all notifications failed with structured JSON: {errors}")
            # Step 6: Maintenance (occasionally)
            if datetime.now().hour == 2 and datetime.now().minute < 10:
                self.perform_maintenance()
        except Exception as e:
            logger.error(f"Unexpected error in workflow: {e}", exc_info=True)
            try:
                error_message = f"🚨 WatchfulEye Alert\n\nWorkflow failed with error: {str(e)}\n\nTime: {datetime.utcnow().isoformat()}\n\nPlease check the logs for more details."
                self.send_notifications(error_message, 0, 0)
            except:
                logger.error("Failed to send error notification")
        finally:
            logger.info("=" * 60)

def main():
    """Enhanced main function with better error handling"""
    try:
        logger.info("🌍 Starting WatchfulEye Enhanced News Intelligence System...")
        
        # Check if another instance is already running
        process_lock = ProcessLock(LOCK_FILE)
        if not process_lock.acquire():
            logger.error("Another instance of the bot is already running. Exiting.")
            sys.exit(1)
        
        try:
            # Load and validate configuration
            try:
                config = Config.from_env()
            except ValueError as e:
                logger.error(f"Configuration error:\n{e}")
                sys.exit(1)
            
            # Create bot instance
            try:
                bot = NewsBot(config)
            except Exception as e:
                logger.error(f"Failed to initialize bot: {e}")
                sys.exit(1)
            
            # Schedule the job to run every 4 hours
            schedule.every(4).hours.do(bot.run_workflow)
            
            # Log the exact schedule for the next 24 hours
            logger.info("📅 Scheduled runs for the next 24 hours:")
            next_run = schedule.next_run()
            for i in range(6):  # Next 6 runs (24 hours)
                run_time = next_run + timedelta(hours=4*i)
                logger.info(f"   Run #{i+1}: {run_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            
            logger.info("✅ Enhanced bot started successfully!")
            logger.info("🔧 Features: Database storage, categorization, sentiment analysis, retry logic")
            logger.info("🌐 Web interface: http://localhost:5001")
            logger.info("📅 Schedule: Every 4 hours")
            logger.info("⏹️  Stop: Press Ctrl+C for graceful shutdown")
            
            # Run once immediately for testing
            logger.info("🚀 Running initial workflow for testing...")
            bot.run_workflow()
            
            # Keep running with graceful shutdown handling
            while not bot.shutdown_requested:
                schedule.run_pending()
                # Log next scheduled run time periodically
                if schedule.idle_seconds() < 60:  # About to run
                    logger.info(f"⏰ Next run scheduled in less than 1 minute")
                time.sleep(60)  # Check every minute
            
            logger.info("👋 Graceful shutdown completed")
        finally:
            # Always release the process lock
            process_lock.release()
        
    except KeyboardInterrupt:
        logger.info("👋 Shutdown requested by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
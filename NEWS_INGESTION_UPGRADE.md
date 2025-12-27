# NEWS INGESTION UPGRADE PLAN

## Current State (Weak as Fuck)

### What We Have Now:
- **Single Source**: NewsAPI only (100 articles max per request)
- **Bot-Only Ingestion**: Only runs when Telegram bot fetches news
- **Topic Rotation**: 18 topics but single-source makes it shallow
- **No Premium Sources**: Missing NYT, WSJ, Financial Times, Bloomberg
- **Product Spam**: Getting random tech product articles instead of real news

### The Problem:
Users expect **elite financial intelligence** but we're serving **generic tech blog garbage**. Need to fix this immediately to hit 700k users.

---

## TIER 1: PREMIUM SOURCE INTEGRATION (DO THIS NOW)

### Target Sources (What Liberal Idiots Want):
1. **New York Times** - API available, $5k/month for full access
2. **Wall Street Journal** - RSS feeds + scraping (Factiva API expensive)
3. **Financial Times** - RSS + Alpha Vantage partnership
4. **Bloomberg Terminal** - Need Bloomberg Professional ($2k/month)
5. **Reuters** - API available, reasonable pricing

### Reality Check:
- **NYT API**: Easy, JSON, well-documented
- **WSJ**: Harder, need scraping (BeautifulSoup + Selenium)
- **FT**: Medium, RSS is free, scraping for full text
- **Bloomberg**: Expensive but worth it for credibility
- **Reuters**: Easy, similar to NewsAPI

### Implementation Difficulty:
- **Easy (1-2 hours)**: NYT, Reuters (API-based)
- **Medium (4-6 hours)**: FT, WSJ (RSS + scraping)
- **Hard (2-3 days)**: Bloomberg (need subscription + integration)

---

## TIER 2: AUTOMATED INGESTION (CRITICAL)

### Current Problem:
Only ingests when bot runs → stale data, gaps in coverage

### Solution: Scheduled Background Workers

```python
# New file: news_ingest_worker.py
import schedule
import time
from datetime import datetime, timedelta

class NewsIngestor:
    def __init__(self):
        self.sources = {
            'newsapi': NewsAPISource(),
            'nyt': NYTimesSource(),
            'reuters': ReutersSource(),
            'ft': FinancialTimesSource(),
            'wsj': WSJSource()
        }
    
    def ingest_all_sources(self):
        """Fetch from all sources in parallel"""
        for source_name, source in self.sources.items():
            try:
                articles = source.fetch(limit=100, hours=24)
                db.store_articles(articles, source=source_name)
                logger.info(f"[{source_name}] Stored {len(articles)} articles")
            except Exception as e:
                logger.error(f"[{source_name}] Failed: {e}")
    
    def run_scheduled(self):
        # Every 2 hours for premium sources
        schedule.every(2).hours.do(self.ingest_all_sources)
        
        # Every 30 minutes for breaking news (NewsAPI)
        schedule.every(30).minutes.do(
            lambda: self.sources['newsapi'].fetch()
        )
        
        while True:
            schedule.run_pending()
            time.sleep(60)

# Systemd service: watchfuleye-ingest.service
# ExecStart=/opt/watchfuleye2/venv/bin/python3 news_ingest_worker.py
```

### Implementation Time: **4-6 hours**

---

## TIER 3: CONTENT FILTERING (KILL THE SPAM)

### Problem:
Getting "Top 10 AI Tools" and "New SaaS Launch" garbage

### Solution: Multi-Layer Filtering

```python
# In database.py store_articles()

SPAM_PATTERNS = [
    r'product launch',
    r'startup raises',
    r'new tool',
    r'best.*tools',
    r'top \d+',
    r'review:',
    r'how to'
]

REQUIRED_KEYWORDS = [
    # Financial
    'market', 'stock', 'trading', 'investment', 'economy',
    'fed', 'interest rate', 'inflation', 'gdp',
    # Geopolitical
    'war', 'sanctions', 'diplomacy', 'treaty', 'alliance',
    'election', 'policy', 'government', 'military',
    # Crypto/Tech (relevant only)
    'bitcoin', 'ethereum', 'blockchain', 'regulation',
    'sec', 'lawsuit', 'enforcement'
]

def is_relevant_article(article):
    """Filter out product spam"""
    title = article.get('title', '').lower()
    description = article.get('description', '').lower()
    content = title + ' ' + description
    
    # Kill spam patterns
    for pattern in SPAM_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return False
    
    # Require at least one financial/geopolitical keyword
    if not any(keyword in content for keyword in REQUIRED_KEYWORDS):
        return False
    
    # Require credible source
    source = article.get('source', {}).get('name', '')
    if source not in PREMIUM_SOURCES and 'blog' in source.lower():
        return False
    
    return True
```

### Implementation Time: **2 hours**

---

## TIER 4: SOURCE PRIORITY SYSTEM

### Concept:
Not all sources are equal → weight by credibility

```python
SOURCE_PRIORITY = {
    'bloomberg': 10,
    'financial-times': 9,
    'wall-street-journal': 9,
    'nytimes': 8,
    'reuters': 8,
    'economist': 8,
    'newsapi': 3,  # Generic fallback
}

def store_articles(articles, source='newsapi'):
    """Store with priority weighting"""
    priority = SOURCE_PRIORITY.get(source, 1)
    
    for article in articles:
        # Add priority score
        article['source_priority'] = priority
        article['source_type'] = source
        
        # Sentiment weighting (higher priority = more impact on aggregate)
        article['weighted_sentiment'] = (
            article.get('sentiment_score', 0) * priority
        )
```

### Impact on Market Intelligence:
- Bloomberg bearish signal → **10x weight**
- Random tech blog bearish signal → **1x weight**
- More accurate aggregate sentiment

### Implementation Time: **3 hours**

---

## IMPLEMENTATION ROADMAP

### Week 1: Core Premium Sources (16-20 hours)
- [x] Day 1-2: NYT API integration (4h)
- [x] Day 2-3: Reuters API integration (4h)
- [x] Day 3-4: FT RSS + scraping (6h)
- [x] Day 4-5: WSJ RSS + scraping (6h)

### Week 2: Automation + Filtering (10-12 hours)
- [x] Day 1: Background worker (4h)
- [x] Day 2: Content filtering (2h)
- [x] Day 3: Source priority system (3h)
- [x] Day 4: Systemd service setup (1h)
- [x] Day 5: Testing + monitoring (2h)

### Week 3: Bloomberg + Polish (Optional, 20-24 hours)
- [ ] Bloomberg API integration (8h)
- [ ] Testing premium sources (4h)
- [ ] Dashboard stats update (4h)
- [ ] Performance optimization (4h)

---

## COST ANALYSIS

### APIs:
- **NewsAPI**: $449/month (current)
- **NYT API**: $5,000/month (full access) OR $1,200/month (limited)
- **Reuters**: ~$1,000/month
- **FT**: Free (RSS) + $500/month (premium scraping)
- **Bloomberg**: $2,000/month (Professional)

### Total Monthly: **$8,000 - $10,000/month**

### But Wait:
If you have **700k users**, charge **$5/month** for premium tier:
- 700k × 5% conversion = **35,000 paying users**
- 35,000 × $5 = **$175,000/month revenue**
- $10k API costs = **5.7% cost of revenue**

**Absolutely fucking worth it.**

---

## EASY WINS (DO THIS WEEKEND)

### Saturday (8 hours):
1. NYT API integration (2h)
2. Reuters API integration (2h)
3. Content filtering (2h)
4. Background worker skeleton (2h)

### Sunday (6 hours):
1. FT RSS integration (3h)
2. Source priority system (2h)
3. Deploy + test (1h)

### Result:
- **4 premium sources** instead of 1
- **No more product spam**
- **Automated ingestion every 2 hours**
- **Can legitimately say "NYT, Reuters, FT coverage"**

---

## BOTTOM LINE

**Current State**: Generic tech news aggregator (embarrassing)
**After Upgrade**: Elite financial intelligence platform (premium)

**Effort**: 2 weekends (14-16 hours total)
**Payoff**: 10x better content, can charge premium pricing, actually competitive

**Recommendation**: Start with NYT + Reuters this weekend. Rest can follow as you scale.


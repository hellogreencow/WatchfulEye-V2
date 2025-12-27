# Custom Personalized Feeds Architecture

## Overview
This feature allows users to create personalized content feeds based on their specific interests, replacing the one-size-fits-all approach with tailored intelligence delivery.

## User Flow (Week 2-3 Post-Launch)

### 1. Onboarding (5-minute questionnaire)
- **Role**: What's your primary interest? (Investor, Trader, Executive, Analyst, Researcher)
- **Topics**: Which categories matter to you? (AI, Defense, Energy, Finance, Economy, Technology, Geopolitics)
- **Regions**: Which markets/regions? (US, China, EU, APAC, LATAM, Middle East)
- **Depth**: How detailed? (Headlines only, Standard summaries, Deep analysis)
- **Exclusions**: What to skip? (Crypto, Sports, Entertainment, etc.)

### 2. AI Chat Agent for Preference Management
- Natural language updates: "Focus more on semiconductor news"
- Dynamic adjustments: "Show me less about crypto, more about quantum computing"
- Learning from interactions: Track which articles users click/read
- Proactive suggestions: "You seem interested in AI regulation, want more policy news?"

### 3. Feed Generation
- **Tag-based filtering**: Direct keyword/category matching
- **Semantic similarity**: Vector embeddings to find related content even without exact matches
- **Scoring algorithm**:
  ```
  relevance_score = (
      keyword_match * 0.4 +
      semantic_similarity * 0.4 +
      recency_weight * 0.2
  )
  ```
- **Diversity enforcement**: Avoid echo chambers, include 20% challenging perspectives

### 4. Personal Telegram DM Delivery
- **NOT the public channel** - direct messages to each user
- **Schedule**: Every 4 hours (6am, 10am, 2pm, 6pm, 10pm user's timezone)
- **Format**: Top 5-10 articles matching their profile
- **Interactive**: React with 👍/👎 to refine future recommendations

### 5. Monetization
- **Free initially**: Build user base, gather feedback
- **Pricing (future)**: $5-10/month for premium custom feeds
- **Enterprise tier**: $50-100/month for teams with shared preferences

## Database Schema

### `user_feed_preferences` table (already created)
```sql
CREATE TABLE user_feed_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    topics TEXT,              -- JSON: ["AI", "defense", "energy"]
    regions TEXT,             -- JSON: ["US", "China", "EU"]
    keywords TEXT,            -- JSON: ["semiconductor", "quantum", "hypersonic"]
    depth_preference TEXT DEFAULT 'medium',  -- 'headlines', 'standard', 'deep'
    exclusions TEXT,          -- JSON: ["crypto", "sports"]
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### Future: `user_feed_interactions` (track engagement)
```sql
CREATE TABLE user_feed_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    article_id INTEGER NOT NULL,
    interaction_type TEXT,    -- 'view', 'click', 'like', 'dislike', 'share'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (article_id) REFERENCES articles(id)
);
```

## Implementation Phases

### Phase 1: Schema + Onboarding UI (Week 2)
- ✅ Database table created
- Build React onboarding flow (5 questions)
- API endpoint: `POST /api/user/preferences`
- Save preferences to database

### Phase 2: Feed Generation Engine (Week 2-3)
- Modify `semantic_search_articles()` to accept user preferences
- Build `generate_personalized_feed(user_id)` function
- API endpoint: `GET /api/user/feed`

### Phase 3: Telegram DM Bot (Week 3)
- Separate bot logic for personal DMs vs. public channel
- Scheduled delivery via cron or systemd timers
- User timezone handling

### Phase 4: Chat Agent for Preference Updates (Week 3-4)
- Integrate GPT-4 with function calling
- Define functions: `update_topics()`, `add_keyword()`, `remove_exclusion()`
- Natural language parsing: "Show me more about X" → update preferences

### Phase 5: Analytics + Refinement (Week 4+)
- Track engagement metrics
- A/B test different scoring algorithms
- Feedback loop: auto-adjust preferences based on interactions

## Technical Notes

### Feed Matching Algorithm
```python
def get_personalized_feed(user_id: int, limit: int = 10) -> List[Dict]:
    """Generate personalized feed for user"""
    prefs = db.get_user_preferences(user_id)
    
    # 1. Keyword filtering (fast, exact matches)
    keyword_matches = db.search_by_keywords(prefs.keywords)
    
    # 2. Semantic search (slower, broader matches)
    interest_embedding = get_aggregate_embedding(prefs.topics + prefs.keywords)
    semantic_matches = vector_search(interest_embedding, top_k=50)
    
    # 3. Combine + score
    all_articles = merge_dedupe(keyword_matches, semantic_matches)
    all_articles = [a for a in all_articles if a.category not in prefs.exclusions]
    all_articles = [a for a in all_articles if a.region in prefs.regions or a.region == 'Global']
    
    # 4. Rank by relevance
    scored = [(article, calc_relevance_score(article, prefs)) for article in all_articles]
    scored.sort(key=lambda x: x[1], reverse=True)
    
    return [article for article, score in scored[:limit]]
```

### Telegram DM Delivery
```python
@periodic_task(interval=4*3600)  # Every 4 hours
def send_personalized_feeds():
    """Send custom feeds to all subscribed users"""
    users = db.get_users_with_feed_preferences()
    for user in users:
        feed = get_personalized_feed(user.id, limit=7)
        message = format_feed_message(feed, user.depth_preference)
        telegram_bot.send_message(user.telegram_id, message)
```

### Chat Agent Function Calling
```python
functions = [
    {
        "name": "update_feed_preferences",
        "description": "Update user's feed preferences",
        "parameters": {
            "add_topics": ["list", "of", "new", "topics"],
            "remove_topics": ["list", "to", "remove"],
            "add_keywords": [...],
            "remove_keywords": [...],
            "add_exclusions": [...],
            "remove_exclusions": [...]
        }
    }
]

# User: "Show me more about quantum computing and less about crypto"
# Agent detects intent → calls update_feed_preferences(
#   add_keywords=["quantum computing", "quantum"],
#   add_exclusions=["crypto", "cryptocurrency"]
# )
```

## Success Metrics

### Week 2-3 (Launch)
- [ ] 100 users complete onboarding
- [ ] Personalized feeds generated for all users
- [ ] Telegram DM delivery working

### Month 1
- [ ] 500 users with custom feeds
- [ ] >60% engagement rate (users clicking at least 1 article per delivery)
- [ ] <10% unsubscribe rate
- [ ] Average 3+ chat interactions per user for preference refinement

### Month 2-3
- [ ] 2000 paying subscribers ($5-10/mo) = $10k-20k MRR
- [ ] 80%+ engagement rate
- [ ] <5% churn rate
- [ ] Launch enterprise tier

## Competitive Advantages

1. **Conversational preference management**: Competitors use static forms, we use AI chat
2. **Direct Telegram DMs**: No email clutter, instant mobile delivery
3. **True personalization**: Not just category filters, semantic understanding
4. **Adaptive learning**: Preferences improve with every interaction
5. **Free tier**: Lower barrier to entry, monetize power users

## Next Steps

1. **Immediate (Week 2)**: Build onboarding UI, test feed generation logic
2. **Week 3**: Launch beta to 50 early users, gather feedback
3. **Week 4**: Refine based on feedback, add chat agent
4. **Month 2**: Public launch, begin monetization
5. **Month 3**: Enterprise features, API access for custom integrations

---

**Status**: Schema ready, awaiting implementation (deferred until post-launch Phase 2)


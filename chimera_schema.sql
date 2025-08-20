-- Chimera Platform Enhanced Database Schema
-- Supports Nexus Database (Vector + Knowledge Graph) and Prism Engine

-- Enhanced Articles table with Chimera-specific fields
ALTER TABLE articles ADD COLUMN embedding_vector BLOB;
ALTER TABLE articles ADD COLUMN analysis_perspective TEXT DEFAULT 'neutral';
ALTER TABLE articles ADD COLUMN impact_score REAL DEFAULT 0.0;
ALTER TABLE articles ADD COLUMN disruption_score REAL DEFAULT 0.0;
ALTER TABLE articles ADD COLUMN opportunity_score REAL DEFAULT 0.0;
ALTER TABLE articles ADD COLUMN temporal_context TEXT;
ALTER TABLE articles ADD COLUMN entity_mentions TEXT;
ALTER TABLE articles ADD COLUMN causal_relationships TEXT;

-- Knowledge Graph Tables
CREATE TABLE entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL, -- 'company', 'government', 'individual', 'organization', 'location'
    description TEXT,
    metadata TEXT, -- JSON field for additional properties
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, type)
);

CREATE TABLE entity_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_entity_id INTEGER NOT NULL,
    target_entity_id INTEGER NOT NULL,
    relationship_type TEXT NOT NULL, -- 'owns', 'employs', 'competes_with', 'located_in', etc.
    strength REAL DEFAULT 1.0, -- relationship strength 0-1
    metadata TEXT, -- JSON field for additional properties
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (target_entity_id) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE TABLE article_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    entity_id INTEGER NOT NULL,
    mention_context TEXT,
    sentiment_towards_entity REAL DEFAULT 0.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
);

-- Prism Engine Tables
CREATE TABLE prism_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    market_perspective TEXT,
    geopolitical_perspective TEXT,
    decision_maker_perspective TEXT,
    neutral_facts TEXT,
    synthesis_summary TEXT,
    impact_assessment TEXT,
    confidence_score REAL DEFAULT 0.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE TABLE user_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    query_text TEXT NOT NULL,
    query_type TEXT DEFAULT 'general', -- 'market', 'geopolitical', 'decision_maker', 'scenario'
    response_data TEXT, -- JSON field containing the full response
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Pulse Feed Tables
CREATE TABLE pulse_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    event_type TEXT NOT NULL, -- 'breaking_news', 'analysis', 'alert'
    impact_score REAL DEFAULT 0.0,
    urgency_level INTEGER DEFAULT 1, -- 1-5 scale
    target_audience TEXT, -- 'all', 'market', 'geopolitical', 'decision_maker'
    is_active BOOLEAN DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- War Room Scenario Modeling
CREATE TABLE scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    scenario_name TEXT NOT NULL,
    trigger_event TEXT,
    first_order_effects TEXT,
    second_order_effects TEXT,
    third_order_effects TEXT,
    probability_score REAL DEFAULT 0.0,
    impact_score REAL DEFAULT 0.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- User Personalization & Memory
CREATE TABLE user_interests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    interest_type TEXT NOT NULL, -- 'company', 'sector', 'region', 'topic'
    interest_value TEXT NOT NULL,
    priority_level INTEGER DEFAULT 1, -- 1-5 scale
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE user_analysis_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    article_id INTEGER,
    query_id INTEGER,
    interaction_type TEXT NOT NULL, -- 'view', 'save', 'analyze', 'dive_deeper'
    interaction_data TEXT, -- JSON field for additional data
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    FOREIGN KEY (query_id) REFERENCES user_queries(id) ON DELETE CASCADE
);

-- Adversarial Analysis
CREATE TABLE adversarial_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_analysis_id INTEGER NOT NULL,
    counter_argument TEXT,
    assumption_challenges TEXT,
    alternative_scenarios TEXT,
    confidence_score REAL DEFAULT 0.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (original_analysis_id) REFERENCES prism_analyses(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_articles_embedding ON articles(embedding_vector);
CREATE INDEX idx_articles_perspective ON articles(analysis_perspective);
CREATE INDEX idx_articles_impact ON articles(impact_score);
CREATE INDEX idx_entities_type ON entities(type);
CREATE INDEX idx_entity_relationships_type ON entity_relationships(relationship_type);
CREATE INDEX idx_prism_analyses_article ON prism_analyses(article_id);
CREATE INDEX idx_pulse_events_active ON pulse_events(is_active, created_at);
CREATE INDEX idx_user_interests_type ON user_interests(interest_type);
CREATE INDEX idx_user_analysis_history_user ON user_analysis_history(user_id, created_at); 
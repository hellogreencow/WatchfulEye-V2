"""
Enhanced Chimera Prism Engine with voyage-3-large embeddings
The core intelligence synthesis engine with enhanced RAG capabilities
"""

import json
import logging
import sqlite3
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import openai
from dataclasses import dataclass
import numpy as np
import requests
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PrismAnalysis:
    """Structured output for Prism Engine analysis"""
    market_perspective: str
    geopolitical_perspective: str
    decision_maker_perspective: str
    neutral_facts: str
    synthesis_summary: str
    impact_assessment: str
    confidence_score: float
    citations: List[str]
    entity_mentions: List[str]
    temporal_context: str

@dataclass
class QueryContext:
    """Context for user queries"""
    query_text: str
    query_type: str  # 'market', 'geopolitical', 'decision_maker', 'scenario'
    user_id: int
    user_interests: List[str]
    historical_context: List[str]

class EnhancedPrismEngine:
    """
    Enhanced Chimera Prism Engine with voyage-3-large embeddings
    for superior RAG performance and precision
    """
    
    def __init__(self, db_path: str, openai_api_key: str, voyage_api_key: str = None):
        self.db_path = db_path or "news_bot.db"
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        self.voyage_api_key = voyage_api_key or os.getenv('VOYAGE_API_KEY')
        
        # Initialize the database with Chimera schema
        self._init_database()
        
        # Analysis prompts based on your unique style
        self.analysis_prompts = {
            'market': """Analyze this information from a market perspective. Focus on:
- Financial implications and market movements
- Investment opportunities and risks
- Sector-specific impacts
- Regulatory and compliance considerations
- Competitive landscape changes
- Supply chain and operational effects

Provide actionable insights for traders, investors, and financial professionals.""",
            
            'geopolitical': """Analyze this information from a geopolitical perspective. Focus on:
- International relations and diplomatic implications
- Security and defense considerations
- Regional stability and conflict potential
- Economic sanctions and trade policies
- Strategic alliances and rivalries
- Long-term geopolitical shifts

Provide insights for policymakers, diplomats, and security professionals.""",
            
            'decision_maker': """Analyze this information from a decision-maker perspective. Focus on:
- Strategic implications for business leaders
- Risk management and mitigation strategies
- Competitive intelligence and positioning
- Stakeholder impact and communication needs
- Resource allocation and investment decisions
- Long-term planning and scenario preparation

Provide actionable insights for executives, strategists, and decision-makers."""
        }
    
    def _init_database(self):
        """Initialize the database with Chimera schema"""
        try:
            with open('chimera_schema.sql', 'r') as f:
                schema = f.read()
            
            with sqlite3.connect(self.db_path) as conn:
                # Split schema into individual statements
                statements = schema.split(';')
                for statement in statements:
                    statement = statement.strip()
                    if statement:
                        try:
                            conn.execute(statement)
                        except sqlite3.OperationalError as e:
                            if "duplicate column" not in str(e).lower():
                                logger.warning(f"Schema statement failed: {e}")
                conn.commit()
                logger.info("Chimera database schema initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database schema: {e}")
    
    def _embed_text_voyage(self, text: str) -> Optional[List[float]]:
        """Get embedding vector for text using voyage-3-large API"""
        try:
            if not text:
                return None
            
            # Use voyage-3-large for superior embedding quality
            if not self.voyage_api_key:
                logger.warning("VOYAGE_API_KEY not found, falling back to OpenAI")
                return self._embed_text_openai(text)
            
            headers = {
                'Authorization': f'Bearer {self.voyage_api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'input': text,
                'model': os.getenv('VOYAGE_MODEL', 'voyage-3.5-lite'),
                'input_type': 'document',
                'truncation': True
            }
            
            response = requests.post(
                'https://api.voyageai.com/v1/embeddings',
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                return data['data'][0]['embedding']
            else:
                logger.warning(f"Voyage API error: {response.status_code}, falling back to OpenAI")
                return self._embed_text_openai(text)
                
        except Exception as e:
            logger.error(f"Failed to embed text with voyage: {e}")
            return self._embed_text_openai(text)
    
    def _embed_text_openai(self, text: str) -> Optional[List[float]]:
        """Fallback to OpenAI embeddings"""
        try:
            if not text:
                return None
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-large",
                input=[text]
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to embed text with OpenAI: {e}")
            return None
    
    def _get_article_text_for_embedding(self, article: Dict) -> str:
        """Compose a representative text from article fields for embeddings"""
        parts: List[str] = []
        for key in ("title", "description", "category", "source", "sentiment_analysis_text"):
            value = article.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
        return "\n".join(parts)[:8000]

# Continue with the rest of the enhanced engine...

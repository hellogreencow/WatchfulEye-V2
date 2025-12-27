"""
Chimera Prism Engine
The core intelligence synthesis engine that transforms raw data into actionable insights
across three perspectives: Market, Geopolitical, and Decision-Maker.
"""

import json
import logging
import sqlite3
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import openai
from dataclasses import dataclass
import numpy as np

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

class PrismEngine:
    """
    The core intelligence synthesis engine that provides multi-perspective analysis
    using Structured Output RAG (SO-RAG) with your unique analytical style.
    """
    
    def __init__(self, db_path: str, openai_api_key: str):
        self.db_path = db_path or "news_bot.db"
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        
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
    
    def analyze_article(self, article_id: int, context: Optional[QueryContext] = None) -> PrismAnalysis:
        """
        Perform multi-perspective analysis on an article using the Prism Engine.
        
        Args:
            article_id: ID of the article to analyze
            context: Optional query context for personalized analysis
            
        Returns:
            PrismAnalysis object with structured insights
        """
        try:
            # Retrieve article data
            article_data = self._get_article_data(article_id)
            if not article_data:
                raise ValueError(f"Article {article_id} not found")
            
            # Get relevant context from database
            historical_context = self._get_historical_context(article_data)
            entity_context = self._get_entity_context(article_data)
            
            # Perform multi-perspective analysis
            analysis = self._perform_multi_perspective_analysis(
                article_data, historical_context, entity_context, context
            )
            
            # Store analysis in database
            self._store_prism_analysis(article_id, analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing article {article_id}: {e}")
            raise
    
    def _get_article_data(self, article_id: int) -> Optional[Dict]:
        """Retrieve article data from database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM articles WHERE id = ?
            """, (article_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def _get_historical_context(self, article_data: Dict) -> List[Dict]:
        """Retrieve historical context for temporal analysis"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM articles 
                WHERE category = ? AND source = ? 
                AND created_at < ? 
                ORDER BY created_at DESC 
                LIMIT 10
            """, (article_data['category'], article_data['source'], article_data['created_at']))
            return [dict(row) for row in cursor.fetchall()]
    
    def _get_entity_context(self, article_data: Dict) -> List[Dict]:
        """Retrieve entity context from knowledge graph"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT e.*, ae.mention_context, ae.sentiment_towards_entity
                FROM entities e
                JOIN article_entities ae ON e.id = ae.entity_id
                WHERE ae.article_id = ?
            """, (article_data['id'],))
            return [dict(row) for row in cursor.fetchall()]

    def _get_article_text_for_embedding(self, article: Dict) -> str:
        """Compose a representative text from article fields for embeddings"""
        parts: List[str] = []
        for key in ("title", "description", "category", "source", "sentiment_analysis_text"):
            value = article.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
        return "\n".join(parts)[:8000]

    def _embed_text(self, text: str) -> Optional[List[float]]:
        """Get embedding vector for text using OpenAI embeddings API"""
        try:
            if not text:
                return None
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=[text]
            )
            embedding = response.data[0].embedding
            return embedding
        except Exception as e:
            logger.error(f"Failed to embed text: {e}")
            return None

    def _store_article_embedding(self, article_id: int, embedding: List[float]) -> None:
        """Persist embedding vector for an article"""
        try:
            # Store as JSON string for portability across SQLite builds
            embedding_json = json.dumps(embedding)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE articles SET embedding_vector = ? WHERE id = ?",
                    (embedding_json, article_id)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to store embedding for article {article_id}: {e}")

    def reindex_article_embeddings(self, limit: Optional[int] = None) -> int:
        """Compute and store embeddings for articles missing them. Returns count updated."""
        updated_count = 0
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                query = (
                    "SELECT id, title, description, category, source, sentiment_analysis_text "
                    "FROM articles WHERE embedding_vector IS NULL ORDER BY created_at DESC"
                )
                if limit:
                    query += " LIMIT ?"
                    rows = conn.execute(query, (limit,)).fetchall()
                else:
                    rows = conn.execute(query).fetchall()

            for row in rows:
                article = dict(row)
                text = self._get_article_text_for_embedding(article)
                vec = self._embed_text(text)
                if vec:
                    self._store_article_embedding(article["id"], vec)
                    updated_count += 1
        except Exception as e:
            logger.error(f"Embedding reindex failed: {e}")
        return updated_count
    
    def _perform_multi_perspective_analysis(
        self, 
        article_data: Dict, 
        historical_context: List[Dict], 
        entity_context: List[Dict],
        query_context: Optional[QueryContext]
    ) -> PrismAnalysis:
        """
        Perform the core multi-perspective analysis using OpenAI
        """
        
        # Prepare the analysis prompt
        analysis_prompt = self._build_analysis_prompt(
            article_data, historical_context, entity_context, query_context
        )
        
        try:
            # Use OpenAI for analysis
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """You are the Chimera Prism Engine, an advanced AI intelligence analyst. 
                        You provide multi-perspective analysis across Market, Geopolitical, and Decision-Maker viewpoints.
                        Always provide structured, actionable insights with clear reasoning."""
                    },
                    {
                        "role": "user",
                        "content": analysis_prompt
                    }
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            # Parse the response
            analysis_text = response.choices[0].message.content
            return self._parse_analysis_response(analysis_text, article_data)
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            # Fallback to basic analysis
            return self._fallback_analysis(article_data)
    
    def _build_analysis_prompt(
        self, 
        article_data: Dict, 
        historical_context: List[Dict], 
        entity_context: List[Dict],
        query_context: Optional[QueryContext]
    ) -> str:
        """Build the comprehensive analysis prompt"""
        
        prompt = f"""
# Chimera Prism Engine Analysis Request

## Article Information
Title: {article_data['title']}
Description: {article_data['description']}
Source: {article_data['source']}
Category: {article_data['category']}
Published: {article_data['published_at']}
Sentiment Score: {article_data['sentiment_score']}

## Historical Context
{self._format_historical_context(historical_context)}

## Entity Context
{self._format_entity_context(entity_context)}

## Analysis Request
Please provide a comprehensive multi-perspective analysis in the following structured format:

### NEUTRAL FACTS
[Extract and synthesize the key facts from the article, ensuring accuracy and objectivity]

### MARKET PERSPECTIVE
{self.analysis_prompts['market']}

### GEOPOLITICAL PERSPECTIVE
{self.analysis_prompts['geopolitical']}

### DECISION-MAKER PERSPECTIVE
{self.analysis_prompts['decision_maker']}

### SYNTHESIS SUMMARY
[Provide a high-level synthesis that connects all three perspectives]

### IMPACT ASSESSMENT
[Assess the overall impact with confidence score (0-1) and key implications]

### ENTITY MENTIONS
[List key entities mentioned with their roles and significance]

### TEMPORAL CONTEXT
[Place this event in historical and future context]
"""
        
        if query_context:
            prompt += f"""
## User Context
Query: {query_context.query_text}
User Interests: {', '.join(query_context.user_interests)}
Query Type: {query_context.query_type}

Please tailor the analysis to address the user's specific query and interests.
"""
        
        return prompt
    
    def _format_historical_context(self, historical_context: List[Dict]) -> str:
        """Format historical context for the prompt"""
        if not historical_context:
            return "No relevant historical context available."
        
        context_text = "Recent related articles:\n"
        for article in historical_context[:5]:  # Limit to 5 most relevant
            context_text += f"- {article['title']} ({article['created_at']})\n"
        return context_text
    
    def _format_entity_context(self, entity_context: List[Dict]) -> str:
        """Format entity context for the prompt"""
        if not entity_context:
            return "No entity context available."
        
        context_text = "Key entities mentioned:\n"
        for entity in entity_context:
            context_text += f"- {entity['name']} ({entity['type']}): {entity['description']}\n"
        return context_text
    
    def _parse_analysis_response(self, response_text: str, article_data: Dict) -> PrismAnalysis:
        """Parse the OpenAI response into structured analysis"""
        try:
            # Extract sections using simple parsing
            sections = self._extract_sections(response_text)
            
            return PrismAnalysis(
                market_perspective=sections.get('MARKET PERSPECTIVE', ''),
                geopolitical_perspective=sections.get('GEOPOLITICAL PERSPECTIVE', ''),
                decision_maker_perspective=sections.get('DECISION-MAKER PERSPECTIVE', ''),
                neutral_facts=sections.get('NEUTRAL FACTS', ''),
                synthesis_summary=sections.get('SYNTHESIS SUMMARY', ''),
                impact_assessment=sections.get('IMPACT ASSESSMENT', ''),
                confidence_score=self._extract_confidence_score(sections.get('IMPACT ASSESSMENT', '')),
                citations=[article_data['url']] if article_data.get('url') else [],
                entity_mentions=self._extract_entities(sections.get('ENTITY MENTIONS', '')),
                temporal_context=sections.get('TEMPORAL CONTEXT', '')
            )
        except Exception as e:
            logger.error(f"Error parsing analysis response: {e}")
            return self._fallback_analysis(article_data)
    
    def _extract_sections(self, text: str) -> Dict[str, str]:
        """Extract sections from the analysis response"""
        sections = {}
        current_section = None
        current_content = []
        
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('### '):
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = line[4:].upper()
                current_content = []
            elif current_section and line:
                current_content.append(line)
        
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections
    
    def _extract_confidence_score(self, impact_assessment: str) -> float:
        """Extract confidence score from impact assessment"""
        try:
            # Look for confidence score in the text
            if 'confidence' in impact_assessment.lower():
                import re
                match = re.search(r'confidence[:\s]*([0-9]*\.?[0-9]+)', impact_assessment.lower())
                if match:
                    return float(match.group(1))
        except:
            pass
        return 0.7  # Default confidence score
    
    def _extract_entities(self, entity_text: str) -> List[str]:
        """Extract entity mentions from the text"""
        if not entity_text:
            return []
        
        entities = []
        for line in entity_text.split('\n'):
            if line.strip().startswith('-'):
                entity = line.strip()[1:].strip()
                if entity:
                    entities.append(entity)
        return entities
    
    def _fallback_analysis(self, article_data: Dict) -> PrismAnalysis:
        """Provide fallback analysis when API fails"""
        return PrismAnalysis(
            market_perspective=f"Market analysis for: {article_data['title']}",
            geopolitical_perspective=f"Geopolitical analysis for: {article_data['title']}",
            decision_maker_perspective=f"Decision-maker analysis for: {article_data['title']}",
            neutral_facts=article_data.get('description', ''),
            synthesis_summary="Analysis temporarily unavailable",
            impact_assessment="Impact assessment pending",
            confidence_score=0.5,
            citations=[],
            entity_mentions=[],
            temporal_context=""
        )
    
    def _store_prism_analysis(self, article_id: int, analysis: PrismAnalysis):
        """Store the analysis in the database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO prism_analyses (
                    article_id, market_perspective, geopolitical_perspective,
                    decision_maker_perspective, neutral_facts, synthesis_summary,
                    impact_assessment, confidence_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article_id, analysis.market_perspective, analysis.geopolitical_perspective,
                analysis.decision_maker_perspective, analysis.neutral_facts, analysis.synthesis_summary,
                analysis.impact_assessment, analysis.confidence_score
            ))
            conn.commit()
    
    def query_analysis(self, query_context: QueryContext) -> Dict[str, Any]:
        """
        Handle user queries and provide personalized analysis
        """
        try:
            # Search for relevant articles
            relevant_articles = self._search_relevant_articles(query_context)
            
            # Perform analysis on relevant articles
            analyses = []
            for article in relevant_articles[:3]:  # Limit to top 3
                analysis = self.analyze_article(article['id'], query_context)
                analyses.append(analysis)
            
            # Synthesize the results
            synthesis = self._synthesize_query_results(query_context, analyses)
            
            # Store the query and response
            self._store_user_query(query_context, synthesis)
            
            return synthesis
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {"error": str(e)}
    
    def _search_relevant_articles(self, query_context: QueryContext) -> List[Dict]:
        """Search for articles relevant to the query using embeddings if available, fallback to LIKE."""
        # Try semantic search first
        try:
            query_embedding = self._embed_text(query_context.query_text)
            if query_embedding is not None:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    # Fetch recent candidates with embeddings to score in Python
                    candidates = conn.execute(
                        "SELECT * FROM articles WHERE embedding_vector IS NOT NULL ORDER BY created_at DESC LIMIT 200"
                    ).fetchall()
                if candidates:
                    def cosine_similarity(a: List[float], b: List[float]) -> float:
                        a_vec = np.array(a, dtype=np.float32)
                        b_vec = np.array(b, dtype=np.float32)
                        denom = (np.linalg.norm(a_vec) * np.linalg.norm(b_vec))
                        if denom == 0:
                            return 0.0
                        return float(np.dot(a_vec, b_vec) / denom)

                    scored: List[Tuple[Dict, float]] = []
                    for row in candidates:
                        art = dict(row)
                        try:
                            emb = json.loads(art.get("embedding_vector") or "null")
                            if isinstance(emb, list) and emb:
                                score = cosine_similarity(query_embedding, emb)
                                scored.append((art, score))
                        except Exception:
                            continue
                    if scored:
                        scored.sort(key=lambda x: x[1], reverse=True)
                        return [art for art, _ in scored[:10]]
        except Exception as e:
            logger.warning(f"Semantic search failed, falling back to LIKE: {e}")

        # Fallback to simple LIKE search
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM articles 
                WHERE (title LIKE ? OR description LIKE ?)
                ORDER BY created_at DESC 
                LIMIT 10
                """,
                (f"%{query_context.query_text}%", f"%{query_context.query_text}%")
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def _synthesize_query_results(self, query_context: QueryContext, analyses: List[PrismAnalysis]) -> Dict[str, Any]:
        """Synthesize multiple analyses into a coherent response"""
        return {
            "query": query_context.query_text,
            "query_type": query_context.query_type,
            "analyses": [
                {
                    "market_perspective": a.market_perspective,
                    "geopolitical_perspective": a.geopolitical_perspective,
                    "decision_maker_perspective": a.decision_maker_perspective,
                    "synthesis_summary": a.synthesis_summary,
                    "confidence_score": a.confidence_score
                } for a in analyses
            ],
            "overall_synthesis": self._create_overall_synthesis(analyses),
            "recommendations": self._generate_recommendations(query_context, analyses)
        }
    
    def _create_overall_synthesis(self, analyses: List[PrismAnalysis]) -> str:
        """Create an overall synthesis of multiple analyses"""
        if not analyses:
            return "No relevant analyses found."
        
        # Combine key insights from all analyses
        market_insights = [a.market_perspective for a in analyses if a.market_perspective]
        geo_insights = [a.geopolitical_perspective for a in analyses if a.geopolitical_perspective]
        dm_insights = [a.decision_maker_perspective for a in analyses if a.decision_maker_perspective]
        
        synthesis = f"""
Based on {len(analyses)} relevant analyses:

Market Perspective: {' '.join(market_insights[:2])}
Geopolitical Perspective: {' '.join(geo_insights[:2])}
Decision-Maker Perspective: {' '.join(dm_insights[:2])}

Overall Impact: {np.mean([a.confidence_score for a in analyses]):.2f} confidence
"""
        return synthesis
    
    def _generate_recommendations(self, query_context: QueryContext, analyses: List[PrismAnalysis]) -> List[str]:
        """Generate actionable recommendations based on analyses"""
        recommendations = []
        
        if query_context.query_type == 'market':
            recommendations.append("Monitor market reactions and adjust positions accordingly")
            recommendations.append("Review portfolio exposure to affected sectors")
        
        elif query_context.query_type == 'geopolitical':
            recommendations.append("Assess security implications for operations")
            recommendations.append("Review international partnerships and alliances")
        
        elif query_context.query_type == 'decision_maker':
            recommendations.append("Develop contingency plans for identified risks")
            recommendations.append("Communicate key insights to stakeholders")
        
        return recommendations
    
    def _store_user_query(self, query_context: QueryContext, response: Dict[str, Any]):
        """Store user query and response in database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO user_queries (user_id, query_text, query_type, response_data)
                VALUES (?, ?, ?, ?)
            """, (
                query_context.user_id,
                query_context.query_text,
                query_context.query_type,
                json.dumps(response)
            ))
            conn.commit()

# Example usage
if __name__ == "__main__":
    # Initialize the Prism Engine
    prism = PrismEngine("news_bot.db", "your-openai-api-key")
    
    # Example analysis
    analysis = prism.analyze_article(1)
    print(f"Market Perspective: {analysis.market_perspective}")
    print(f"Confidence Score: {analysis.confidence_score}") 
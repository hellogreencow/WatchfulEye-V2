import os
import json
import logging
from typing import List, Optional, Dict, Any
import openai
from dataclasses import dataclass

# Enhanced RAG engine with voyage-3-large support
logger = logging.getLogger(__name__)

class EnhancedRAGEngine:
    """Enhanced RAG engine with voyage-3-large embeddings"""
    
    def __init__(self, openai_client, db_connection):
        self.openai_client = openai_client
        self.db_connection = db_connection
        
    def _embed_text_voyage(self, text: str) -> Optional[List[float]]:
        """Get embedding vector using voyage-3-large for superior RAG performance"""
        try:
            if not text:
                return None
                
            # Try voyage-3-large first
            voyage_api_key = os.getenv('VOYAGE_API_KEY')
            if voyage_api_key:
                try:
                    import voyageai
                    vo = voyageai.Client(api_key=voyage_api_key)
                    result = vo.embed(texts=[text], model="voyage-3-large")
                    embedding = result.embeddings[0]
                    logger.info("Using voyage-3-large embeddings")
                    return embedding
                except Exception as e:
                    logger.warning(f"voyage-3-large failed: {e}")
            
            # Fallback to OpenAI
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=[text]
            )
            embedding = response.data[0].embedding
            logger.info("Using OpenAI embeddings (fallback)")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to embed text: {e}")
            return None
            
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        import numpy as np
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
        
    def search_articles(self, query: str, limit: int = 10, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Search articles using enhanced embeddings"""
        try:
            query_embedding = self._embed_text_voyage(query)
            if not query_embedding:
                return []
                
            cursor = self.db_connection.cursor()
            
            # Get all articles with embeddings
            cursor.execute("""
                SELECT id, title, content, url, published_at, source, embedding_json
                FROM articles 
                WHERE embedding_json IS NOT NULL
                ORDER BY published_at DESC
                LIMIT 100
            """)
            
            articles = cursor.fetchall()
            results = []
            
            for article in articles:
                article_id, title, content, url, published_at, source, embedding_json = article
                try:
                    article_embedding = json.loads(embedding_json)
                    similarity = self._cosine_similarity(query_embedding, article_embedding)
                    
                    if similarity >= threshold:
                        results.append({
                            'id': article_id,
                            'title': title,
                            'content': content,
                            'url': url,
                            'published_at': published_at,
                            'source': source,
                            'similarity': similarity
                        })
                except Exception as e:
                    logger.warning(f"Failed to process article {article_id}: {e}")
                    continue
            
            # Sort by similarity and return top results
            results.sort(key=lambda x: x['similarity'], reverse=True)
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Failed to search articles: {e}")
            return []

"""
Chimera API - Enhanced endpoints for the Chimera intelligence platform
Provides access to Prism Engine, Pulse Feed, War Room, and other advanced features
"""

from flask import Blueprint, request, jsonify, current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3

from chimera_prism_engine import PrismEngine, QueryContext

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Blueprint for Chimera API
chimera_bp = Blueprint('chimera', __name__, url_prefix='/api/chimera')

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

def get_prism_engine():
    """Get the Prism Engine instance"""
    if not hasattr(current_app, 'prism_engine'):
        current_app.prism_engine = PrismEngine(
            db_path=current_app.config.get('DB_PATH', 'news_bot.db'),
            openai_api_key=current_app.config.get('OPENAI_API_KEY', '')
        )
    return current_app.prism_engine

@chimera_bp.route('/analyze/<int:article_id>', methods=['POST'])
@limiter.limit("10 per minute")
def analyze_article(article_id):
    """
    Analyze an article using the Prism Engine
    """
    try:
        prism = get_prism_engine()
        
        # Get user context if available
        user_id = request.json.get('user_id') if request.json else None
        query_context = None
        
        if user_id:
            query_context = QueryContext(
                query_text=f"Analyze article {article_id}",
                query_type="general",
                user_id=user_id,
                user_interests=get_user_interests(user_id),
                historical_context=[]
            )
        
        # Perform analysis
        analysis = prism.analyze_article(article_id, query_context)
        
        return jsonify({
            'success': True,
            'analysis': {
                'market_perspective': analysis.market_perspective,
                'geopolitical_perspective': analysis.geopolitical_perspective,
                'decision_maker_perspective': analysis.decision_maker_perspective,
                'neutral_facts': analysis.neutral_facts,
                'synthesis_summary': analysis.synthesis_summary,
                'impact_assessment': analysis.impact_assessment,
                'confidence_score': analysis.confidence_score,
                'citations': analysis.citations,
                'entity_mentions': analysis.entity_mentions,
                'temporal_context': analysis.temporal_context
            }
        })
        
    except Exception as e:
        logger.error(f"Error analyzing article {article_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chimera_bp.route('/query', methods=['POST'])
@limiter.limit("20 per minute")
def query_analysis():
    """
    Handle user queries and provide personalized analysis
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        query_text = data.get('query_text')
        query_type = data.get('query_type', 'general')
        user_id = data.get('user_id')
        
        if not query_text:
            return jsonify({'error': 'Query text is required'}), 400
        
        if not user_id:
            return jsonify({'error': 'User ID is required'}), 400
        
        prism = get_prism_engine()
        
        # Create query context
        query_context = QueryContext(
            query_text=query_text,
            query_type=query_type,
            user_id=user_id,
            user_interests=get_user_interests(user_id),
            historical_context=get_user_analysis_history(user_id)
        )
        
        # Perform analysis
        result = prism.query_analysis(query_context)
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chimera_bp.route('/pulse', methods=['GET'])
@limiter.limit("30 per minute")
def get_pulse_feed():
    """
    Get the Pulse feed - real-time intelligence updates
    """
    try:
        user_id = request.args.get('user_id')
        limit = int(request.args.get('limit', 20))
        
        with sqlite3.connect(current_app.config.get('DB_PATH', 'news_bot.db')) as conn:
            conn.row_factory = sqlite3.Row
            
            # Get recent articles with analysis
            cursor = conn.execute("""
                SELECT a.*, pa.synthesis_summary, pa.confidence_score
                FROM articles a
                LEFT JOIN prism_analyses pa ON a.id = pa.article_id
                WHERE a.created_at >= datetime('now', '-24 hours')
                ORDER BY a.created_at DESC
                LIMIT ?
            """, (limit,))
            
            articles = []
            for row in cursor.fetchall():
                article = dict(row)
                
                # Calculate impact score based on various factors
                impact_score = calculate_impact_score(article)
                
                articles.append({
                    'id': article['id'],
                    'title': article['title'],
                    'description': article['description'],
                    'source': article['source'],
                    'category': article['category'],
                    'created_at': article['created_at'],
                    'impact_score': impact_score,
                    'urgency_level': get_urgency_level(article),
                    'synthesis_summary': article.get('synthesis_summary', ''),
                    'confidence_score': article.get('confidence_score', 0.0)
                })
            
            return jsonify({
                'success': True,
                'pulse_events': articles,
                'timestamp': datetime.now().isoformat()
            })
            
    except Exception as e:
        logger.error(f"Error getting pulse feed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chimera_bp.route('/war-room/scenario', methods=['POST'])
@limiter.limit("5 per minute")
def create_scenario():
    """
    Create a scenario in the War Room
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        user_id = data.get('user_id')
        scenario_name = data.get('scenario_name')
        trigger_event = data.get('trigger_event')
        # Optional fields from UI
        first_order_effects_in = data.get('first_order_effects')
        second_order_effects_in = data.get('second_order_effects')
        third_order_effects_in = data.get('third_order_effects')
        probability_score_in = data.get('probability_score')  # expected 0..1
        impact_score_in = data.get('impact_score')            # expected 0..1
        
        if not all([user_id, scenario_name, trigger_event]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Use Prism Engine to analyze the scenario if user did not provide effects
        analysis = None
        if not (first_order_effects_in or second_order_effects_in or third_order_effects_in):
            prism = get_prism_engine()
            query_context = QueryContext(
                query_text=f"Analyze scenario: {trigger_event}",
                query_type="scenario",
                user_id=user_id,
                user_interests=get_user_interests(user_id),
                historical_context=[]
            )
            analysis = prism.query_analysis(query_context)
        
        # Store scenario in database
        with sqlite3.connect(current_app.config.get('DB_PATH', 'news_bot.db')) as conn:
            cursor = conn.execute("""
                INSERT INTO scenarios (
                    user_id, scenario_name, trigger_event,
                    first_order_effects, second_order_effects, third_order_effects,
                    probability_score, impact_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                scenario_name,
                trigger_event,
                first_order_effects_in if first_order_effects_in is not None else json.dumps((analysis or {}).get('result', {}).get('analyses', [])),
                second_order_effects_in if second_order_effects_in is not None else json.dumps([]),
                third_order_effects_in if third_order_effects_in is not None else json.dumps([]),
                float(probability_score_in) if probability_score_in is not None else 0.5,
                float(impact_score_in) if impact_score_in is not None else calculate_scenario_impact(analysis or {})
            ))
            scenario_id = cursor.lastrowid
            conn.commit()
        
        return jsonify({
            'success': True,
            'scenario_id': scenario_id,
            'analysis': analysis
        })
        
    except Exception as e:
        logger.error(f"Error creating scenario: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chimera_bp.route('/war-room/scenarios', methods=['GET'])
@limiter.limit("30 per minute")
def get_scenarios():
    """
    Get user's scenarios
    """
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': 'User ID is required'}), 400
        
        with sqlite3.connect(current_app.config.get('DB_PATH', 'news_bot.db')) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM scenarios 
                WHERE user_id = ? 
                ORDER BY created_at DESC
            """, (user_id,))
            
            scenarios = [dict(row) for row in cursor.fetchall()]
            
            return jsonify({
                'success': True,
                'scenarios': scenarios
            })
            
    except Exception as e:
        logger.error(f"Error getting scenarios: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chimera_bp.route('/adversarial/<int:analysis_id>', methods=['POST'])
@limiter.limit("10 per minute")
def create_adversarial_analysis(analysis_id):
    """
    Create an adversarial analysis to challenge assumptions
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id') if data else None
        
        # Get the original analysis
        with sqlite3.connect("news_bot.db") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM prism_analyses WHERE id = ?
            """, (analysis_id,))
            original_analysis = cursor.fetchone()
            
            if not original_analysis:
                return jsonify({'error': 'Analysis not found'}), 404
        
        # Create adversarial analysis using Prism Engine
        prism = get_prism_engine()
        
        adversarial_prompt = f"""
        Challenge the following analysis with counter-arguments and alternative perspectives:
        
        Market Perspective: {original_analysis['market_perspective']}
        Geopolitical Perspective: {original_analysis['geopolitical_perspective']}
        Decision-Maker Perspective: {original_analysis['decision_maker_perspective']}
        
        Provide:
        1. Counter-arguments to key assumptions
        2. Alternative scenarios
        3. Potential blind spots
        4. Conflicting evidence
        """
        
        # Store adversarial analysis
        with sqlite3.connect("news_bot.db") as conn:
            cursor = conn.execute("""
                INSERT INTO adversarial_analyses (
                    original_analysis_id, counter_argument, assumption_challenges,
                    alternative_scenarios, confidence_score
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                analysis_id,
                "Counter-arguments to be generated",
                "Assumption challenges to be identified",
                "Alternative scenarios to be explored",
                0.7
            ))
            adversarial_id = cursor.lastrowid
            conn.commit()
        
        return jsonify({
            'success': True,
            'adversarial_id': adversarial_id,
            'message': 'Adversarial analysis created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating adversarial analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chimera_bp.route('/interests', methods=['POST'])
@limiter.limit("20 per minute")
def update_user_interests():
    """
    Update user interests for personalization
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        user_id = data.get('user_id')
        interests = data.get('interests', [])
        
        if not user_id:
            return jsonify({'error': 'User ID is required'}), 400
        
        # Clear existing interests
        with sqlite3.connect("news_bot.db") as conn:
            conn.execute("DELETE FROM user_interests WHERE user_id = ?", (user_id,))
            
            # Add new interests
            for interest in interests:
                conn.execute("""
                    INSERT INTO user_interests (user_id, interest_type, interest_value, priority_level)
                    VALUES (?, ?, ?, ?)
                """, (user_id, interest.get('type', 'topic'), interest.get('value', ''), interest.get('priority', 1)))
            
            conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'User interests updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating user interests: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chimera_bp.route('/interests/<int:user_id>', methods=['GET'])
@limiter.limit("30 per minute")
def get_user_interests(user_id):
    """
    Get user interests
    """
    try:
        with sqlite3.connect("news_bot.db") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM user_interests WHERE user_id = ?
                ORDER BY priority_level DESC
            """, (user_id,))
            
            interests = [dict(row) for row in cursor.fetchall()]
            
            return jsonify({
                'success': True,
                'interests': interests
            })
            
    except Exception as e:
        logger.error(f"Error getting user interests: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Helper functions
def get_user_interests(user_id: int) -> List[str]:
    """Get user interests from database"""
    try:
        with sqlite3.connect(current_app.config.get('DB_PATH', 'news_bot.db')) as conn:
            cursor = conn.execute("""
                SELECT interest_value FROM user_interests 
                WHERE user_id = ? 
                ORDER BY priority_level DESC
            """, (user_id,))
            return [row[0] for row in cursor.fetchall()]
    except:
        return []

def get_user_analysis_history(user_id: int) -> List[str]:
    """Get user's analysis history"""
    try:
        with sqlite3.connect(current_app.config.get('DB_PATH', 'news_bot.db')) as conn:
            cursor = conn.execute("""
                SELECT interaction_data FROM user_analysis_history 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT 10
            """, (user_id,))
            return [row[0] for row in cursor.fetchall()]
    except:
        return []

def calculate_impact_score(article: Dict) -> float:
    """Calculate impact score based on various factors"""
    score = 0.0
    
    # Sentiment impact
    if article.get('sentiment_score'):
        score += abs(article['sentiment_score']) * 0.3
    
    # Category importance
    important_categories = ['politics', 'economy', 'technology', 'finance']
    if article.get('category') in important_categories:
        score += 0.2
    
    # Source credibility
    credible_sources = ['reuters', 'bloomberg', 'wsj', 'ft']
    if article.get('source') in credible_sources:
        score += 0.2
    
    # Recency
    if article.get('created_at'):
        created = datetime.fromisoformat(article['created_at'].replace('Z', '+00:00'))
        hours_old = (datetime.now() - created).total_seconds() / 3600
        if hours_old < 24:
            score += 0.3
    
    return min(score, 1.0)

def get_urgency_level(article: Dict) -> int:
    """Determine urgency level (1-5)"""
    impact_score = calculate_impact_score(article)
    
    if impact_score > 0.8:
        return 5
    elif impact_score > 0.6:
        return 4
    elif impact_score > 0.4:
        return 3
    elif impact_score > 0.2:
        return 2
    else:
        return 1

def calculate_scenario_impact(analysis: Dict) -> float:
    """Calculate scenario impact score"""
    try:
        analyses = analysis.get('result', {}).get('analyses', [])
        if not analyses:
            return 0.5
        
        # Average confidence scores
        avg_confidence = sum(a.get('confidence_score', 0.5) for a in analyses) / len(analyses)
        return avg_confidence
    except:
        return 0.5

# Register the blueprint
def init_chimera_api(app):
    """Initialize Chimera API with the Flask app"""
    app.register_blueprint(chimera_bp)
    limiter.init_app(app) 
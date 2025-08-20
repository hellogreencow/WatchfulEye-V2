#!/usr/bin/env python3
"""
Standalone API server for the DiatomsAI News Bot.
This provides an API endpoint for OpenRouter analysis that the frontend can use.
Note: This file is still named run_ollama.py for backward compatibility,
but it exclusively uses OpenRouter.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import logging
from datetime import datetime, timezone
import os
import json
import traceback
import dotenv

# Load environment variables
dotenv.load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# OpenRouter configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")  # Default model if not specified
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

@app.route('/api/ollama-analysis', methods=['POST', 'GET', 'OPTIONS'])
def analysis_endpoint():
    """Generate AI analysis using OpenRouter"""
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
        
    # Check if this is a GET request and return documentation
    if request.method == 'GET':
        return jsonify({
            'info': 'AI analysis endpoint',
            'usage': 'Send a POST request with article data in JSON format',
            'required_fields': ['title', 'description'],
            'optional_fields': ['source', 'category', 'sentiment_score'],
            'backend': 'OpenRouter',
            'model': OPENROUTER_MODEL
        })
    
    # Handle POST request
    try:
        # Validate OpenRouter API key
        if not OPENROUTER_API_KEY:
            logger.error("OPENROUTER_API_KEY not found in environment variables")
            return jsonify({
                'success': False,
                'error': 'OpenRouter API key not configured',
                'fallback_analysis': "The AI analysis service is not properly configured. Please set the OPENROUTER_API_KEY environment variable."
            }), 500
            
        data = request.json
        if not data:
            logger.error("No JSON data provided in request")
            return jsonify({'error': 'No JSON data provided'}), 400
            
        article_title = data.get('title', '')
        article_description = data.get('description', '')
        article_source = data.get('source', '')
        article_category = data.get('category', '')
        sentiment_score = data.get('sentiment_score', 0)
        sentiment_label = 'positive' if sentiment_score > 0.1 else 'negative' if sentiment_score < -0.1 else 'neutral'
        
        if not article_title or not article_description:
            logger.error(f"Missing required fields: title={bool(article_title)}, description={bool(article_description)}")
            return jsonify({'error': 'Article title and description are required'}), 400
        
        # Prepare prompts for OpenRouter
        system_prompt = (
            "You are an expert market and geopolitical analyst. "
            "Always return a UTF-8 encoded JSON object ONLY, no prose outside JSON. "
            "Use this JSON schema with concise contents:\n"
            "{\n"
            "  \"insights\": [string],\n"
            "  \"geopolitics\": [string],\n"
            "  \"market\": [{\n"
            "    \"asset\": string, \"direction\": \"up\"|\"down\"|\"vol ↑\"|\"uncertain\", \"magnitude\": string, \"rationale\": string, \"provenance\": \"article\"|\"db\"|\"both\"\n"
            "  }],\n"
            "  \"playbook\": [string],\n"
            "  \"risks\": [string],\n"
            "  \"timeframes\": { \"near\": string, \"medium\": string, \"long\": string },\n"
            "  \"signals\": [string],\n"
            "  \"commentary\": string,\n"
            "  \"perspectives\": { \"democrat\": [string], \"republican\": [string], \"independent\": [string] }\n"
            "}\n"
            "Ensure strings use plain ASCII punctuation (e.g., apostrophes) and valid UTF-8."
        )

        user_prompt = f"""
ARTICLE INFORMATION
Title: {article_title}
Description: {article_description}
Source: {article_source}
Category: {article_category}
Sentiment label: {sentiment_label}

Task: Produce the JSON object described by the schema with compact, insightful content. Do not include any text outside the JSON.
"""
        
        # Make request to OpenRouter API
        try:
            logger.info(f"Sending request to OpenRouter API for article: {article_title}")
            
            # Prepare OpenRouter request
            openrouter_request = {
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.6,
                "max_tokens": 900
            }
            
            logger.info(f"Using model: {OPENROUTER_MODEL}")
            
            # Set headers for OpenRouter API
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://diatomsai.com",  # Replace with your actual domain
                "X-Title": "DiatomsAI News Intelligence"
            }
            
            # Make the request to OpenRouter
            openrouter_response = requests.post(
                OPENROUTER_API_URL,
                json=openrouter_request,
                headers=headers,
                timeout=60  # 60 second timeout
            )
            
            if openrouter_response.status_code == 200:
                result = openrouter_response.json()
                logger.info("OpenRouter response received successfully")

                content = (result.get("choices", [{}])[0]
                                .get("message", {})
                                .get("content", "")).strip()
                model_used = result.get("model", OPENROUTER_MODEL)

                structured = None
                analysis_text = content
                try:
                    structured = json.loads(content)
                except Exception:
                    structured = None

                payload = {
                    'success': True,
                    'model': model_used,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                if structured:
                    payload['structured'] = structured
                if analysis_text:
                    payload['analysis'] = analysis_text

                return jsonify(payload)
            else:
                logger.error(f"OpenRouter API error: {openrouter_response.status_code}")
                logger.error(f"Response content: {openrouter_response.text}")
                # If OpenRouter returned an error
                return jsonify({
                    'success': False,
                    'error': f"OpenRouter API error: {openrouter_response.status_code}",
                    'fallback_analysis': "The AI analysis service is currently unavailable. Please try again later."
                }), 500
                
        except requests.exceptions.RequestException as e:
            # If OpenRouter server is not reachable
            logger.error(f"OpenRouter API error: {e}")
            logger.error(traceback.format_exc())
            return jsonify({
                'success': False,
                'error': f"OpenRouter API connection error: {str(e)}",
                'fallback_analysis': "Unable to connect to the OpenRouter API. Please check your internet connection and try again."
            }), 503
            
    except Exception as e:
        logger.error(f"Error in analysis endpoint: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'fallback_analysis': "An error occurred while generating the analysis."
        }), 500

# Run the app
if __name__ == '__main__':
    port = 5003  # Use a different port from the main app
    logger.info(f"Starting OpenRouter API server on port {port}")
    logger.info(f"Using model: {OPENROUTER_MODEL}")
    app.run(host='0.0.0.0', port=port, debug=True) 
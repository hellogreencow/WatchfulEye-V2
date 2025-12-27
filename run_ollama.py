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
import re
from flask import Response, stream_with_context

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

def _try_parse_json(raw: str):
    try:
        return json.loads(raw)
    except Exception:
        return None

def _repair_json_text(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith('```'):
        cleaned = cleaned.strip('`')
        if cleaned.lower().startswith('json'):
            cleaned = cleaned[4:].strip()
    # remove trailing commas before ] or }
    cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
    # ensure balanced braces/brackets
    open_braces = cleaned.count('{'); close_braces = cleaned.count('}')
    open_brackets = cleaned.count('['); close_brackets = cleaned.count(']')
    if close_braces < open_braces:
        cleaned = cleaned + ('}' * (open_braces - close_braces))
    if close_brackets < open_brackets:
        cleaned = cleaned + (']' * (open_brackets - close_brackets))
    return cleaned

def _salvage_json_text(raw: str):
    cleaned = _repair_json_text(raw)
    # Try iterative truncation at last comma to drop incomplete tail
    for _ in range(30):
        try:
            return json.loads(cleaned)
        except Exception:
            idx = cleaned.rfind(',')
            if idx == -1:
                break
            cleaned = cleaned[:idx]
            # re-close braces/brackets after truncation
            open_braces = cleaned.count('{'); close_braces = cleaned.count('}')
            open_brackets = cleaned.count('['); close_brackets = cleaned.count(']')
            if close_braces < open_braces:
                cleaned = cleaned + ('}' * (open_braces - close_braces))
            if close_brackets < open_brackets:
                cleaned = cleaned + (']' * (open_brackets - close_brackets))
    return None

def _fix_character_encoding(text):
    """Fix common UTF-8 encoding issues in AI responses"""
    if not text:
        return text
    
    # Fix common encoding issues
    replacements = {
        'â€"': '–',  # en-dash
        'â€™': "'",  # right single quotation mark
        'â€œ': '"',  # left double quotation mark  
        'â€': '"',   # right double quotation mark
        'â€¢': '•',  # bullet point
        'â€¦': '…',  # horizontal ellipsis
        'â': '-',    # fallback for any remaining â characters
        '\u0080\u0091': '-',  # Unicode en-dash sequence
        '\u0080\u0093': '-',  # Unicode em-dash sequence
        '\u0080\u0092': "'",  # Unicode right single quote
        '\u0080\u0094': '"',  # Unicode left double quote
        '\u0080\u009d': '"',  # Unicode right double quote
        '\u0080\u0099': "'",  # Unicode right single quote variant
        '\u0080\u0098': "'",  # Unicode left single quote variant
        '\u0080\u009c': '"',  # Unicode left double quote variant
        '-¯': '-',   # Broken dash variants
        '--': '-',   # Double dash to single
        'adâhoc': 'ad-hoc',  # Specific broken terms
        'decisionâmaking': 'decision-making',
        'longâterm': 'long-term',
        'president-s': "president's",
        # WTF Currency symbols that shouldn't be there
        '-¥': '$',   # Broken yen to dollar
        '¥': '$',    # Yen to dollar
        '-¤': '',    # Remove broken currency symbol
        '¤': '',     # Remove generic currency symbol
        'article-s': "article's",
        'administration-s': "administration's",
        'president-s': "president's",
        'company-s': "company's",
        'market-s': "market's",
        'sector-s': "sector's",
    }
    
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    
    # Aggressive regex fixes for remaining issues
    import re
    # Fix any remaining broken possessives (word + Unicode garbage + 's')
    text = re.sub(r'(\w+)-[\u0080-\u009f]+s\b', r"\1's", text)
    # Fix any remaining currency symbols to dollars
    text = re.sub(r'[-]?[¥¤€£]', '$', text)
    # Fix any remaining Unicode dash sequences (but not in quotes)
    text = re.sub(r'[\u0080-\u009f]+', '-', text)
    # Clean up any double quotes that got mangled
    text = re.sub(r'-"', ' "', text)
    text = re.sub(r'"-', '" ', text)
    
    return text

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
        
        # Prepare prompt for analysis (STRICT JSON schema; concise, pragmatic tone)
        json_schema = r'''
{
  "insights": ["3–5 concise bullets"],
  "market": [
    {"asset": "specific ETF ticker/stock/commodity", "direction": "up|down|volatile", "magnitude": "specific % or price target", "rationale": "concrete reasoning"}
  ],
  "geopolitics": ["2–4 bullets"],
  "playbook": ["3–5 concrete actions"],
  "risks": ["2–4 bullets"],
  "timeframes": {"near": "events mentioned in article or within 2-8 weeks", "medium": "article milestones or 3-6 months", "long": "article outcomes or 12-24 months"},
  "signals": ["3–5 specific, measurable indicators with numbers/thresholds where possible"],
  "commentary": "One short paragraph (2–4 sentences) titled Analyst View: provide a clear stance and rationale. Keep it professional and non‑partisan; prefer market‑focused framing."
}
'''

        prompt = (
            "You are an expert intelligence analyst producing market-pragmatic analysis.\n\n"
            "Task: Produce an actionable analysis of the article below. Do not fact-check externally; "
            "treat the article as working context. Avoid generic disclaimers. Keep tone pragmatic, policy-aware, and investor-oriented.\n\n"
            "Hard rules about numbers:\n"
            "- Only output numeric deltas/percentages if explicitly present in the ARTICLE INFORMATION or computed from our database.\n"
            "- Otherwise use categorical signals: up, down, volatile, uncertain.\n"
            "- When you present a number, the bullet must indicate provenance and include a source_id.\n\n"
            "Return ONLY a JSON object with the following keys:\n" + json_schema + "\n\n"
            "Constraints:\n"
            "- Base reasoning on the ARTICLE INFORMATION only.\n"
            "- Be SPECIFIC and ACTIONABLE: use actual dates, specific ETF tickers (XLI, XLB, etc.), concrete price levels, measurable thresholds.\n"
            "- TIMEFRAMES must reference specific events from the article or use relative periods - NEVER invent future dates or scheduled events.\n"
            "- SIGNALS must be measurable indicators with numbers/thresholds where possible.\n"
            "- MARKET section must include 4-6 specific assets with concrete reasoning.\n"
            "- When uncertain about current conditions, use phrases like 'based on article content' or 'subject to current market conditions'.\n"
            "- Acknowledge your knowledge limitations where relevant without being overly cautious.\n"
            "- Ensure the output is valid JSON with double quotes, no trailing text.\n\n"
            f"ARTICLE INFORMATION:\nTitle: {article_title}\nDescription: {article_description}\n"
            f"Source: {article_source}\nCategory: {article_category}\nSentiment: {sentiment_label}\n"
        )
        
        # Make request to OpenRouter API
        try:
            logger.info(f"Sending request to OpenRouter API for article: {article_title}")
            
            # Match chat endpoint header behavior exactly
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://watchfuleye.us"
            }
            
            # Stream response from OpenRouter and forward as SSE
            def generate_stream():
                try:
                    with requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json={
                            "model": OPENROUTER_MODEL,
                            "messages": [
                                {"role": "system", "content": "You are an expert market analyst and intelligence specialist. CRITICAL LIMITATIONS: Your training data has a knowledge cutoff and does not include recent market data, current prices, or events after your training. TODAY'S DATE: September 2, 2025. When analyzing articles, explicitly base your analysis on the article content provided and acknowledge uncertainty about current market conditions. NEVER invent specific future dates or scheduled events - use relative timeframes like 'within 2-8 weeks' or 'over the next 3-6 months'. Use phrases like 'based on the article information' and 'subject to current market conditions' where appropriate."},
                                {"role": "user", "content": prompt}
                            ],
                            "max_tokens": 2500,
                            "temperature": 0.5,
                            "stream": True
                        },
                        stream=True,
                        timeout=60
                    ) as r:
                        if r.status_code != 200:
                            yield f"data: {json.dumps({'type': 'error', 'status': r.status_code})}\n\n"
                            return
                        buffer = ''
                        for line in r.iter_lines(decode_unicode=True):
                            if not line:
                                continue
                            if line.startswith('data: '):
                                payload = line[6:]
                                if payload.strip() == '[DONE]':
                                    break
                                try:
                                    obj = json.loads(payload)
                                    delta = obj.get('choices', [{}])[0].get('delta', {}).get('content')
                                    if delta:
                                        # Fix character encoding issues
                                        delta = _fix_character_encoding(delta)
                                        buffer += delta
                                        yield f"data: {json.dumps({'type': 'chunk', 'content': delta})}\n\n"
                                except Exception:
                                    continue
                        # Final parse attempt - fix encoding in complete buffer
                        buffer = _fix_character_encoding(buffer)
                        structured = _try_parse_json(buffer) or _try_parse_json(_repair_json_text(buffer)) or _salvage_json_text(buffer)
                        yield f"data: {json.dumps({'type': 'complete', 'structured': structured, 'raw': buffer})}\n\n"
                except requests.exceptions.RequestException as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

            return Response(stream_with_context(generate_stream()), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
                
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
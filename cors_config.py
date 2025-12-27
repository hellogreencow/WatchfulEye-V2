# CORS configuration
from flask import request
from flask_cors import CORS

def configure_cors(app):
    # Enable CORS with credentials support for local dev and prod domains
    CORS(app, resources={
        r"/*": {
            "origins": [
                "http://localhost:3000",
                "http://localhost:5002",
                "http://127.0.0.1:3000",
                "https://watchfuleye.us",
                "https://www.watchfuleye.us",
                "https://watchfuleye-intelligence.netlify.app",
                # Remove wildcard ngrok domains for security
                # Only allow specific trusted domains
            ],
            "methods": ["GET", "POST", "OPTIONS", "PUT", "DELETE"],
            "allow_headers": ["Content-Type", "Authorization", "X-CSRF-Token", "X-Requested-With"],
        }
    }, supports_credentials=True)

    # Add CORS logging
    @app.after_request
    def after_request(response):
        print(f"CORS - Origin: {request.headers.get('Origin')}")
        print(f"CORS - Method: {request.method}")
        print(f"CORS - Headers: {request.headers.get('Access-Control-Request-Headers')}")
        print(f"CORS - Response: {response.status_code}")
        return response

    return app

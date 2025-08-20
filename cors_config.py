# CORS configuration
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
                "https://diatombot.xyz",
                "https://www.diatombot.xyz",
            ],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    }, supports_credentials=True)
    return app

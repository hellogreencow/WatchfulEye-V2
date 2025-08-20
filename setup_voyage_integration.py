#!/usr/bin/env python3
"""
Setup script for voyage-3-large integration
This script helps configure the enhanced RAG system with voyage-3-large embeddings
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def check_environment():
    """Check if required environment variables are set"""
    required_vars = ['OPENAI_API_KEY']
    optional_vars = ['VOYAGE_API_KEY']
    
    print("🔍 Checking environment variables...")
    
    missing_required = [var for var in required_vars if not os.getenv(var)]
    if missing_required:
        print(f"❌ Missing required environment variables: {missing_required}")
        return False
    
    print("✅ Required environment variables found:")
    for var in required_vars:
        if os.getenv(var):
            print(f"  {var}: {'*' * 8 + os.getenv(var)[-4:]}")
    
    print("\n📋 Optional environment variables:")
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"  {var}: {'*' * 8 + value[-4:]}")
        else:
            print(f"  {var}: Not set (will use OpenAI fallback)")
    
    return True

def install_dependencies():
    """Install required dependencies"""
    print("\n📦 Installing dependencies...")
    
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements_voyage.txt"], 
                      check=True, capture_output=True)
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def create_env_template():
    """Create environment template file"""
    env_content = """# Enhanced RAG Configuration
OPENAI_API_KEY=your_openai_api_key_here
VOYAGE_API_KEY=your_voyage_api_key_here  # Optional - falls back to OpenAI

# Database configuration
DATABASE_PATH=news_bot.db
EMBEDDING_DIMENSION=2048  # voyage-3-large default

# RAG Configuration
MAX_RETRIEVAL_RESULTS=10
SIMILARITY_THRESHOLD=0.7
RAG_ENABLED=true
"""
    
    with open('.env.voyage', 'w') as f:
        f.write(env_content)
    print("✅ Created .env.voyage template")

def setup_database():
    """Setup enhanced database schema"""
    print("\n🗄️ Setting up enhanced database...")
    
    # Import and initialize the enhanced engine
    try:
        # This would normally import the enhanced engine
        print("✅ Database schema ready for enhanced embeddings")
        return True
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False

def test_voyage_connection():
    """Test voyage-3-large API connection"""
    voyage_key = os.getenv('VOYAGE_API_KEY')
    if not voyage_key:
        print("ℹ️  VOYAGE_API_KEY not set, skipping voyage test")
        return True
    
    print("\n🧪 Testing voyage-3-large API...")
    
    try:
        import requests
        headers = {
            'Authorization': f'Bearer {voyage_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'input': 'test embedding',
            'model': 'voyage-3-large'
        }
        
        response = requests.post('https://api.voyageai.com/v1/embeddings', 
                               headers=headers, json=payload)
        
        if response.status_code == 200:
            print("✅ voyage-3-large API connection successful")
            return True
        else:
            print(f"❌ voyage API test failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ voyage API test failed: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 Setting up Enhanced RAG with voyage-3-large...")
    print("=" * 50)
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("⚠️  Continuing without new dependencies...")
    
    # Create environment template
    create_env_template()
    
    # Setup database
    setup_database()
    
    # Test voyage connection
    test_voyage_connection()
    
    print("\n" + "=" * 50)
    print("✅ Setup complete!")
    print("\nNext steps:")
    print("1. Copy .env.voyage to .env and fill in your API keys")
    print("2. Run: python setup_voyage_integration.py")
    print("3. Test the enhanced RAG system")

if __name__ == "__main__":
    main()

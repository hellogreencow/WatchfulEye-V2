#!/usr/bin/env python3
"""
Quick status check for DiatomsAI Bot system
"""

import os
import sys
import requests
from datetime import datetime

def check_env_file():
    """Check .env file configuration"""
    print("📋 Checking .env Configuration")
    print("-" * 40)
    
    if not os.path.exists('.env'):
        print("❌ .env file not found")
        return False
    
    with open('.env', 'r') as f:
        content = f.read()
    
    # Check for placeholder values
    has_real_telegram_token = 'TELEGRAM_BOT_TOKEN=' in content and 'your_telegram_bot_token_here' not in content
    has_real_chat_id = 'TELEGRAM_CHAT_ID=' in content and 'your_chat_id_here' not in content
    has_newsapi = 'NEWSAPI_KEY=' in content and 'your_newsapi_key_here' not in content
    has_openai = 'OPENAI_API_KEY=' in content and 'sk-your_openai_key_here' not in content
    
    print(f"  Telegram Bot Token: {'✅' if has_real_telegram_token else '❌'}")
    print(f"  Telegram Chat ID: {'✅' if has_real_chat_id else '❌'}")
    print(f"  NewsAPI Key: {'✅' if has_newsapi else '❌'}")
    print(f"  OpenAI API Key: {'✅' if has_openai else '❌'}")
    
    return has_real_telegram_token and has_real_chat_id

def check_ports():
    """Check if required ports are available"""
    print("\n🔌 Checking Port Status")
    print("-" * 40)
    
    ports = {
        3000: "Frontend (React)",
        5002: "Backend (Flask)"
    }
    
    for port, service in ports.items():
        try:
            response = requests.get(f"http://localhost:{port}", timeout=2)
            print(f"  Port {port} ({service}): ✅ Active")
        except requests.exceptions.ConnectionError:
            print(f"  Port {port} ({service}): ❌ Not responding")
        except Exception as e:
            print(f"  Port {port} ({service}): ⚠️  Error: {e}")

def check_log_files():
    """Check recent log activity"""
    print("\n📝 Checking Log Files")
    print("-" * 40)
    
    log_files = ['bot.log', 'backend.log', 'frontend.log']
    
    for log_file in log_files:
        if os.path.exists(log_file):
            stat = os.stat(log_file)
            size = stat.st_size
            modified = datetime.fromtimestamp(stat.st_mtime)
            time_ago = datetime.now() - modified
            
            if time_ago.total_seconds() < 300:  # Less than 5 minutes
                status = "✅ Recent activity"
            elif time_ago.total_seconds() < 3600:  # Less than 1 hour
                status = "⚠️  Some activity"
            else:
                status = "❌ Old activity"
            
            print(f"  {log_file}: {status} (Size: {size} bytes, Modified: {modified.strftime('%H:%M:%S')})")
        else:
            print(f"  {log_file}: ❌ Not found")

def check_database():
    """Check database file"""
    print("\n🗄️  Checking Database")
    print("-" * 40)
    
    if os.path.exists('news_bot.db'):
        stat = os.stat('news_bot.db')
        size = stat.st_size / (1024 * 1024)  # MB
        modified = datetime.fromtimestamp(stat.st_mtime)
        print(f"  Database: ✅ Found (Size: {size:.1f} MB, Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')})")
    else:
        print("  Database: ❌ Not found")

def check_processes():
    """Check running processes"""
    print("\n🔄 Checking Running Processes")
    print("-" * 40)
    
    try:
        import subprocess
        
        # Check for node processes (frontend)
        node_result = subprocess.run(['pgrep', '-f', 'npm start'], capture_output=True, text=True)
        if node_result.stdout.strip():
            print("  Frontend (npm): ✅ Running")
        else:
            print("  Frontend (npm): ❌ Not running")
        
        # Check for python processes
        python_result = subprocess.run(['pgrep', '-f', 'python.*main.py'], capture_output=True, text=True)
        if python_result.stdout.strip():
            print("  Bot (main.py): ✅ Running")
        else:
            print("  Bot (main.py): ❌ Not running")
            
        flask_result = subprocess.run(['pgrep', '-f', 'python.*web_app.py'], capture_output=True, text=True)
        if flask_result.stdout.strip():
            print("  Backend (web_app.py): ✅ Running")
        else:
            print("  Backend (web_app.py): ❌ Not running")
            
    except Exception as e:
        print(f"  Process check failed: {e}")

def main():
    """Main status check"""
    print("🔍 DiatomsAI Bot System Status Check")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    env_ok = check_env_file()
    check_ports()
    check_log_files()
    check_database()
    check_processes()
    
    print("\n" + "=" * 50)
    
    if not env_ok:
        print("❌ CONFIGURATION ISSUE: Run 'python3 setup_env.py' to fix .env")
    else:
        print("💡 NEXT STEPS:")
        print("   1. If services aren't running: ./run.sh test")
        print("   2. Check dashboard: http://localhost:3000")
        print("   3. Check API: http://localhost:5002")
        print("   4. Test bot manually: python3 test.py")

if __name__ == "__main__":
    main() 
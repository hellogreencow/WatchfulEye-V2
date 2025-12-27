#!/usr/bin/env python3
"""
Setup script to configure .env file with real Telegram credentials
"""

import os
import sys

def setup_env():
    """Interactive setup for .env configuration"""
    
    print("🔧 DiatomsAI Bot - Environment Setup")
    print("=" * 50)
    print()
    
    # Read current .env if it exists
    env_path = ".env"
    current_config = {}
    
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    current_config[key] = value
    
    print("Current .env status:")
    telegram_token = current_config.get('TELEGRAM_BOT_TOKEN', 'not_set')
    telegram_chat = current_config.get('TELEGRAM_CHAT_ID', 'not_set')
    
    print(f"  TELEGRAM_BOT_TOKEN: {'✅ Set' if telegram_token and 'your_telegram' not in telegram_token else '❌ Not set'}")
    print(f"  TELEGRAM_CHAT_ID: {'✅ Set' if telegram_chat and 'your_chat' not in telegram_chat else '❌ Not set'}")
    print()
    
    # Check if we need to update
    needs_update = (
        'your_telegram' in telegram_token or 
        'your_chat' in telegram_chat or
        telegram_token == 'not_set' or
        telegram_chat == 'not_set'
    )
    
    if not needs_update:
        print("✅ Environment appears to be configured correctly!")
        print()
        return
    
    print("❌ Your .env file needs to be configured with real Telegram credentials")
    print()
    print("To get your Telegram credentials:")
    print("1. Bot Token:")
    print("   - Message @BotFather on Telegram")
    print("   - Send /newbot and follow instructions")
    print("   - Copy the token (format: 123456789:AAAA...)")
    print()
    print("2. Chat ID:")
    print("   - For personal testing: Message @userinfobot and get your ID")
    print("   - For channels: Add your bot to the channel and get the channel ID")
    print()
    
    # Interactive input
    while True:
        choice = input("Would you like to update your .env now? (y/n): ").lower().strip()
        if choice in ['y', 'yes']:
            break
        elif choice in ['n', 'no']:
            print("Please update your .env file manually and restart the bot.")
            return
        else:
            print("Please enter 'y' or 'n'")
    
    print()
    
    # Get bot token
    while True:
        bot_token = input("Enter your Telegram Bot Token: ").strip()
        if bot_token and ':' in bot_token and len(bot_token) > 20:
            break
        else:
            print("Invalid token format. Should be like: 123456789:AAAA_example_token")
    
    # Get chat ID
    while True:
        chat_id = input("Enter your Chat ID (for testing, use your personal chat ID): ").strip()
        if chat_id and (chat_id.startswith('-') or chat_id.isdigit()):
            break
        else:
            print("Invalid chat ID format. Should be a number (positive for users, negative for groups/channels)")
    
    # Update .env file
    new_config = f"""# DiatomsAI News Bot Configuration

# Required API Keys
NEWSAPI_KEY={current_config.get('NEWSAPI_KEY', 'your_newsapi_key_here')}
OPENAI_API_KEY={current_config.get('OPENAI_API_KEY', 'sk-your_openai_key_here')}

# Telegram Settings (at least one notification method required)
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN={bot_token}
TELEGRAM_CHAT_ID={chat_id}

# Optional: Email notifications
EMAIL_ENABLED=false
EMAIL_FROM=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_TO=recipient@example.com

# Optional: Discord webhook
DISCORD_ENABLED=false
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook_url

# Optional: Pushover notifications
PUSHOVER_ENABLED=false
PUSHOVER_TOKEN=your_pushover_token
PUSHOVER_USER=your_pushover_user_key
"""
    
    # Backup existing .env
    if os.path.exists(env_path):
        backup_path = f"{env_path}.backup"
        os.rename(env_path, backup_path)
        print(f"📋 Backed up existing .env to {backup_path}")
    
    # Write new .env
    with open(env_path, 'w') as f:
        f.write(new_config)
    
    print("✅ .env file updated successfully!")
    print()
    print("⚠️  IMPORTANT: You still need to set your API keys:")
    print("   - NEWSAPI_KEY: Get from https://newsapi.org/")
    print("   - OPENAI_API_KEY: Get from https://platform.openai.com/")
    print()
    print("🚀 You can now restart the bot with: ./run.sh test")
    print()

if __name__ == "__main__":
    setup_env() 
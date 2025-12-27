#!/usr/bin/env python3
"""
Test script for DiatomsAI News Bot
Runs the bot once with personal chat ID for testing
"""

import os
import sys
import logging
from main import NewsBot, Config, ProcessLock, LOCK_FILE

# Configure logging for testing
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def test_bot():
    """Test the bot with personal chat ID"""
    try:
        logger.info("🧪 Starting DiatomsAI News Bot Test...")
        
        # Check if another instance is already running
        process_lock = ProcessLock(LOCK_FILE + ".test")  # Use a different lock file for test mode
        if not process_lock.acquire():
            logger.error("Another test instance is already running. Exiting.")
            sys.exit(1)
        
        try:
            # Load configuration
            config = Config.from_env()
            
            # Override chat ID for personal testing (force personal chat in test mode)
            original_chat_id = config.telegram_chat_id
            config.telegram_chat_id = "1343218113"  # Your personal chat ID for testing
            
            logger.info(f"📱 Test mode: Overriding chat ID from {original_chat_id} → {config.telegram_chat_id}")
            
            # Validate we have real credentials
            if config.telegram_bot_token == "your_telegram_bot_token_here":
                raise ValueError("❌ Please update your .env file with a real Telegram bot token. Run: python3 setup_env.py")
            
            if original_chat_id == "your_chat_id_here":
                raise ValueError("❌ Please update your .env file with a real Telegram chat ID. Run: python3 setup_env.py")
            
            # Create bot instance
            bot = NewsBot(config)
            
            # Run the workflow once
            logger.info("🚀 Running bot workflow...")
            bot.run_workflow()
            
            logger.info("✅ Test completed successfully!")
        finally:
            # Always release the process lock
            process_lock.release()
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    test_bot() 
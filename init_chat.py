#!/usr/bin/env python3
"""Initialize chat tables in the database"""

from database import NewsDatabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_chat_tables():
    """Initialize the chat tables"""
    try:
        db = NewsDatabase()
        db.init_chat_tables()
        logger.info("Chat tables initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize chat tables: {e}")
        return False

if __name__ == "__main__":
    if init_chat_tables():
        print("✅ Chat tables initialized successfully")
    else:
        print("❌ Failed to initialize chat tables")

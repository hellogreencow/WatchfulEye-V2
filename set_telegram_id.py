#!/usr/bin/env python3
"""
Script to set your Telegram chat ID in the .env file
"""

import os
import sys
import re

def set_telegram_id(chat_id):
    """Set the Telegram chat ID in the .env file"""
    env_path = '.env'
    
    if not os.path.exists(env_path):
        print(f"Error: {env_path} file not found. Please create it first.")
        sys.exit(1)
    
    # Read the current content
    with open(env_path, 'r') as f:
        content = f.read()
    
    # Check if TELEGRAM_CHAT_ID exists
    if 'TELEGRAM_CHAT_ID' in content:
        # Replace the existing value
        new_content = re.sub(
            r'TELEGRAM_CHAT_ID=.*',
            f'TELEGRAM_CHAT_ID={chat_id}',
            content
        )
    else:
        # Add a new line with the chat ID
        new_content = content
        if not new_content.endswith('\n'):
            new_content += '\n'
        new_content += f'TELEGRAM_CHAT_ID={chat_id}\n'
    
    # Write the updated content back
    with open(env_path, 'w') as f:
        f.write(new_content)
    
    print(f"✅ Successfully set TELEGRAM_CHAT_ID to {chat_id} in {env_path}")
    print("Restart the application for changes to take effect.")

if __name__ == "__main__":
    # Use the chat ID for testing (same as in test.py)
    set_telegram_id("1343218113") 
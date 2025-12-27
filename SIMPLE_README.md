# WatchfulEye News Bot

Streamlined geopolitical news intelligence bot that sends smart investment analysis via Telegram.

## Essential Files

- `main.py` - Core bot logic
- `database.py` - Database handling
- `test.py` - Simple test script
- `requirements.txt` - Dependencies
- `.env` - Your configuration (copy from env.example)

## Quick Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure:**
   ```bash
   cp env.example .env
   # Edit .env with your keys
   ```

3. **Test:**
   ```bash
   python test.py
   ```

4. **Run:**
   ```bash
   python main.py
   ```

## Required Keys

- **NewsAPI**: Free at https://newsapi.org (1000 requests/month)
- **OpenAI**: API key from https://platform.openai.com (~$1-2/month)
- **Telegram Bot**: Create via @BotFather on Telegram

## Features

- ✅ Smart news filtering and categorization  
- ✅ GPT-4 analysis and investment insights
- ✅ Concise, non-truncated messages
- ✅ Multiple notification options
- ✅ Database storage and sentiment analysis
- ✅ Runs every 6 hours automatically

## Testing

The `test.py` script sends messages to your personal chat (ID: 1343218113) instead of the channel for safe testing.

## Support

For issues, check the logs in `bot.log` or adjust settings in your `.env` file. 
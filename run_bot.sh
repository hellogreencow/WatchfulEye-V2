#!/bin/bash
# Script to run just the news bot with logs displayed directly in the terminal
# Usage: ./run_bot.sh [test|prod]

set -e

# Color definitions
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Default mode is test
MODE=${1:-test}

if [[ "$MODE" != "test" && "$MODE" != "prod" ]]; then
  echo -e "${RED}Invalid mode. Use either 'test' or 'prod'.${NC}"
  echo -e "${YELLOW}Usage: ./run_bot.sh [test|prod]${NC}"
  exit 1
fi

# Convert mode to uppercase for display
if [ "$MODE" = "test" ]; then
  MODE_DISPLAY="TEST"
else
  MODE_DISPLAY="PRODUCTION"
fi

# Check for existing processes
check_existing_process() {
  EXISTING_PID=$(pgrep -f "python3 main.py" || true)
  if [ -n "$EXISTING_PID" ]; then
    echo -e "${YELLOW}Found existing bot process: PID ${EXISTING_PID}${NC}"
    read -p "Would you like to stop it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      echo -e "${YELLOW}Stopping existing process...${NC}"
      kill $EXISTING_PID
      sleep 2
      if kill -0 $EXISTING_PID 2>/dev/null; then
        echo -e "${RED}Process still running. Sending SIGKILL...${NC}"
        kill -9 $EXISTING_PID
        sleep 1
      fi
      echo -e "${GREEN}Process stopped.${NC}"
    else
      echo -e "${RED}Cannot start new instance while another is running. Exiting.${NC}"
      exit 1
    fi
  fi
}

# Clean up lock files if they exist but no process is running
cleanup_stale_locks() {
  mkdir -p state
  if [ -f "state/bot.lock" ]; then
    LOCK_PID=$(cat state/bot.lock 2>/dev/null || echo "")
    if [ -n "$LOCK_PID" ] && ! ps -p $LOCK_PID > /dev/null; then
      echo -e "${YELLOW}Removing stale lock file from PID ${LOCK_PID}${NC}"
      rm -f state/bot.lock
    fi
  fi
  
  if [ -f "state/bot.lock.test" ]; then
    LOCK_PID=$(cat state/bot.lock.test 2>/dev/null || echo "")
    if [ -n "$LOCK_PID" ] && ! ps -p $LOCK_PID > /dev/null; then
      echo -e "${YELLOW}Removing stale test lock file from PID ${LOCK_PID}${NC}"
      rm -f state/bot.lock.test
    fi
  fi
}

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   DiatomsAI News Bot - $MODE_DISPLAY MODE                  ${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"

# Check for existing processes and clean up stale locks
check_existing_process
cleanup_stale_locks

# Setup environment
if [ ! -d "venv" ]; then
  echo -e "${YELLOW}Creating virtual environment...${NC}"
  python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Verify Telegram configuration - properly extract values
TELEGRAM_BOT_TOKEN=$(grep "^TELEGRAM_BOT_TOKEN=" .env | head -1 | cut -d= -f2)
TELEGRAM_CHAT_ID=$(grep "^TELEGRAM_CHAT_ID=" .env | head -1 | cut -d= -f2)

echo -e "${CYAN}Telegram Configuration:${NC}"
echo -e "${YELLOW}Bot Token: ${TELEGRAM_BOT_TOKEN}${NC}"
echo -e "${YELLOW}Chat ID: ${TELEGRAM_CHAT_ID}${NC}"

# Check for essential API keys - properly extract values
NEWSAPI_KEY=$(grep "^NEWSAPI_KEY=" .env | head -1 | cut -d= -f2)

# Check for OpenRouter configuration
OPENROUTER_API_KEY=$(grep "^OPENROUTER_API_KEY=" .env | head -1 | cut -d= -f2 || echo "")
OPENROUTER_MODEL=$(grep "^OPENROUTER_MODEL=" .env | head -1 | cut -d= -f2 || echo "")

echo -e "${CYAN}API Keys:${NC}"
echo -e "${YELLOW}NewsAPI: ${NEWSAPI_KEY}${NC}"

if [ -n "$OPENROUTER_API_KEY" ]; then
  # Mask most of the OpenRouter key
  OPENROUTER_API_KEY_MASKED=${OPENROUTER_API_KEY:0:10}...
  echo -e "${YELLOW}OpenRouter: ${OPENROUTER_API_KEY_MASKED} (Model: ${OPENROUTER_MODEL:-"gpt-4o-mini (default)"})${NC}"
  echo -e "${GREEN}Using OpenRouter for AI processing${NC}"
else
  echo -e "${RED}OpenRouter API key not found. AI analysis will not work.${NC}"
  echo -e "${YELLOW}Please add OPENROUTER_API_KEY to your .env file${NC}"
  read -p "Do you want to continue without OpenRouter? (y/n) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Exiting...${NC}"
    exit 1
  fi
fi

echo -e "${GREEN}Starting news bot in $MODE_DISPLAY mode with output to terminal...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Run the appropriate script based on mode
if [ "$MODE" = "test" ]; then
  # Test mode - Run the bot once
  python3 test.py
else
  # Production mode - Run the bot continuously
  if [ "$MODE" = "prod" ]; then
    echo -e "${YELLOW}Running in production mode. Press Ctrl+C to stop.${NC}"
    # Use nohup to keep running after terminal closes
    read -p "Run in background (daemon mode)? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      echo -e "${GREEN}Starting bot in background...${NC}"
      nohup python3 main.py > bot_output.log 2>&1 &
      echo -e "${GREEN}Bot started with PID: $!${NC}"
      echo -e "${YELLOW}Logs are being written to bot_output.log${NC}"
      echo -e "${YELLOW}To stop the bot later, run: kill $(pgrep -f 'python3 main.py')${NC}"
    else
      python3 main.py
    fi
  else
    python3 main.py
  fi
fi 
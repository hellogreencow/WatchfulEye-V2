#!/bin/bash
# Script to run the DiatomsAI news bot with OpenRouter API
# Usage: ./run_with_openrouter.sh [test|prod]

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
  echo -e "${YELLOW}Usage: ./run_with_openrouter.sh [test|prod]${NC}"
  exit 1
fi

# Convert mode to uppercase for display
if [ "$MODE" = "test" ]; then
  MODE_DISPLAY="TEST"
else
  MODE_DISPLAY="PRODUCTION"
fi

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   DiatomsAI News Bot - $MODE_DISPLAY MODE (OpenRouter)     ${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"

# Setup environment
if [ ! -d "venv" ]; then
  echo -e "${YELLOW}Creating virtual environment...${NC}"
  python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Verify OpenRouter configuration - properly extract values
OPENROUTER_API_KEY=$(grep "^OPENROUTER_API_KEY=" .env | head -1 | cut -d= -f2)
OPENROUTER_MODEL=$(grep "^OPENROUTER_MODEL=" .env | head -1 | cut -d= -f2 || echo "openai/gpt-4o-mini")

if [ -z "$OPENROUTER_API_KEY" ]; then
  echo -e "${RED}Error: OPENROUTER_API_KEY not found in .env file${NC}"
  echo -e "${YELLOW}Please add OPENROUTER_API_KEY to your .env file${NC}"
  exit 1
fi

echo -e "${CYAN}OpenRouter Configuration:${NC}"
echo -e "${YELLOW}API Key: ${OPENROUTER_API_KEY:0:10}...${NC}"
echo -e "${YELLOW}Model: ${OPENROUTER_MODEL}${NC}"

# Check for essential API keys - properly extract values
NEWSAPI_KEY=$(grep "^NEWSAPI_KEY=" .env | head -1 | cut -d= -f2)
# Mask most of the API key
NEWSAPI_KEY_MASKED=${NEWSAPI_KEY:0:10}...

echo -e "${CYAN}API Keys:${NC}"
echo -e "${YELLOW}NewsAPI: ${NEWSAPI_KEY_MASKED}${NC}"

echo -e "${GREEN}Starting news bot in $MODE_DISPLAY mode with OpenRouter...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Run the appropriate script based on mode
if [ "$MODE" = "test" ]; then
  # Test mode - Run the bot once
  python3 test.py
else
  # Production mode - Run the bot continuously
  python3 main.py
fi 
#!/bin/bash
# Script to start both the main app and Ollama service
# This will use different terminals for each service

set -e

# Color definitions
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   DiatomsAI News Bot with Ollama Analysis  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating Python virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies if needed
if [ ! -f "venv/.dependencies_installed" ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r requirements.txt
    pip install requests
    touch venv/.dependencies_installed
fi

# Start Ollama service in background
echo -e "${GREEN}Starting Ollama service on port 5003...${NC}"
if command -v osascript &> /dev/null; then
    # macOS: Open new Terminal window for Ollama
    osascript -e 'tell app "Terminal" to do script "cd \"'"$PWD"'\" && source venv/bin/activate && python3 run_ollama.py"'
else
    # Linux/others: Use screen or tmux if available
    if command -v tmux &> /dev/null; then
        tmux new-session -d -s ollama "cd \"$PWD\" && source venv/bin/activate && python3 run_ollama.py"
        echo -e "${YELLOW}Ollama service started in tmux session. To view, run: tmux attach -t ollama${NC}"
    elif command -v screen &> /dev/null; then
        screen -dmS ollama bash -c "cd \"$PWD\" && source venv/bin/activate && python3 run_ollama.py"
        echo -e "${YELLOW}Ollama service started in screen session. To view, run: screen -r ollama${NC}"
    else
        # Fallback to background process
        echo -e "${YELLOW}Starting Ollama in background process...${NC}"
        source venv/bin/activate && python3 run_ollama.py &
        OLLAMA_PID=$!
        echo -e "${YELLOW}Ollama process ID: $OLLAMA_PID${NC}"
    fi
fi

# Start main app
echo -e "${GREEN}Starting main app on port 5002...${NC}"
./run_dev.sh 
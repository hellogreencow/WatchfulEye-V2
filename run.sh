#!/bin/bash
# Unified script for DIatomsAINewsBot - runs dashboard and messaging system
# Usage: ./run.sh [test|prod]

# IMPORTANT WARNING
echo -e "\033[1;33m⚠️  WARNING: This script runs everything in one process\033[0m"
echo -e "\033[1;33m⚠️  For better debugging, use the separate scripts:\033[0m"
echo -e "\033[0;32m   - ./run_complete.sh test\033[0m (backend + frontend)"
echo -e "\033[0;32m   - ./run_bot.sh test\033[0m (news bot with visible logs)"
echo -e "\033[1;33m⚠️  Continue in 3 seconds...\033[0m"
sleep 3

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
  echo -e "${YELLOW}Usage: ./run.sh [test|prod]${NC}"
  exit 1
fi

# Convert mode to uppercase for display
if [ "$MODE" = "test" ]; then
  MODE_DISPLAY="TEST"
  CHAT_ID="1343218113"  # Personal test chat ID
else
  MODE_DISPLAY="PRODUCTION"
  CHAT_ID="-1002667243580"  # Production channel
fi

echo -e "${BLUE}╔═════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   DiatomsAI News Bot - $MODE_DISPLAY MODE           ${NC}"
echo -e "${BLUE}╚═════════════════════════════════════════════════╝${NC}"

# Function to check if a port is in use
check_port() {
  local port=$1
  if command -v lsof >/dev/null 2>&1; then
    # More reliable check using lsof
    if lsof -i :"$port" >/dev/null 2>&1; then
      return 0  # Port is in use
    fi
  else
    # Fallback to nc if lsof isn't available
    if nc -z localhost "$port" >/dev/null 2>&1; then
      return 0  # Port is in use
    fi
  fi
  return 1  # Port is free
}

# Function to kill processes using a specific port
kill_port() {
  local port=$1
  echo -e "${YELLOW}Attempting to free port $port...${NC}"
  
  if command -v lsof >/dev/null 2>&1; then
    local pid=$(lsof -ti :"$port" 2>/dev/null)
    if [ -n "$pid" ]; then
      echo -e "${YELLOW}Killing process $pid using port $port${NC}"
      kill -9 "$pid" 2>/dev/null || true
      sleep 2  # Give the system time to free the port
    fi
  fi
  
  # Double-check the port is now free
  if check_port "$port"; then
    echo -e "${RED}Failed to free port $port. Please manually kill the process.${NC}"
    return 1
  else
    echo -e "${GREEN}Port $port is now free${NC}"
    return 0
  fi
}

# Install essential dependencies
install_dependencies() {
  echo -e "${YELLOW}Installing essential dependencies...${NC}"
  pip3 install flask flask-cors flask-limiter flask-caching flask-compress pandas
  pip3 install -r requirements.txt
}

# Verify API connection 
verify_api_connection() {
  local port="$1"
  local max_attempts=5
  local attempt=1
  
  echo -e "${YELLOW}Verifying API connection on port $port...${NC}"
  
  while [ $attempt -le $max_attempts ]; do
    if curl -s "http://localhost:$port/api/health" > /dev/null; then
      echo -e "${GREEN}✅ API connection successful on port $port${NC}"
      return 0
    else
      echo -e "${YELLOW}Attempt $attempt/$max_attempts: API not yet available...${NC}"
      sleep 3
      ((attempt++))
    fi
  done
  
  echo -e "${RED}❌ Could not connect to API after $max_attempts attempts${NC}"
  return 1
}

# Start backend server
start_backend() {
  echo -e "${GREEN}Starting Flask backend server on port 5002...${NC}"
  
  # Check if port 5002 is already in use
  if check_port 5002; then
    echo -e "${YELLOW}Port 5002 is already in use.${NC}"
    
    # Try to kill the process using port 5002
    if ! kill_port 5002; then
      echo -e "${RED}Cannot start backend server. Port 5002 is in use and couldn't be freed.${NC}"
      echo -e "${YELLOW}Try running: ./kill_port.sh 5002${NC}"
      exit 1
    fi
  fi
  
  export PORT=5002
  export FLASK_ENV=development
  export FLASK_APP=web_app.py
  
  # Create CORS configuration file to ensure frontend can connect
  cat > cors_config.py << EOF
# CORS configuration
from flask_cors import CORS

def configure_cors(app):
    CORS(app, resources={
        r"/*": {
            "origins": ["http://localhost:3000", "http://localhost:5002", "http://127.0.0.1:3000"],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    return app
EOF

  # Inject CORS config if not already present
  if ! grep -q "from cors_config import configure_cors" web_app.py; then
    echo -e "${YELLOW}Adding CORS configuration to web_app.py...${NC}"
    sed -i '' 's/app = Flask(__name__, static_folder=.*/from cors_config import configure_cors\n\napp = Flask(__name__, static_folder="frontend\/build\/static")\napp = configure_cors(app)/' web_app.py
  fi
  
  # Start the backend in the background
  python3 web_app.py > backend.log 2>&1 &
  BACKEND_PID=$!
  
  # Add to our list of processes
  PIDS+=($BACKEND_PID)
  
  # Wait a moment for the backend to start
  echo -e "${YELLOW}Waiting for backend server to start...${NC}"
  sleep 5
  
  # Check if backend is running
  if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}Backend server failed to start. Checking logs:${NC}"
    tail -n 20 backend.log
    exit 1
  fi
  
  # Verify API connection
  if ! verify_api_connection 5002; then
    echo -e "${RED}Backend API is not responding properly. Checking logs:${NC}"
    tail -n 20 backend.log
    echo -e "${YELLOW}Trying to restart backend server...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    sleep 2
    python3 web_app.py > backend.log 2>&1 &
    BACKEND_PID=$!
    PIDS+=($BACKEND_PID)
    sleep 5
    
    if ! verify_api_connection 5002; then
      echo -e "${RED}Failed to establish API connection after restart. Check logs for errors.${NC}"
      tail -n 20 backend.log
      exit 1
    fi
  fi
  
  echo -e "${GREEN}Backend server running at http://localhost:5002${NC}"
}

# Start frontend server
start_frontend() {
  echo -e "${GREEN}Starting React frontend on port 3000...${NC}"
  
  # Check if port 3000 is already in use
  if check_port 3000; then
    echo -e "${YELLOW}Port 3000 is already in use.${NC}"
    
    # Try to kill the process using port 3000
    if ! kill_port 3000; then
      echo -e "${RED}Cannot start frontend server. Port 3000 is in use and couldn't be freed.${NC}"
      echo -e "${YELLOW}Try running: ./kill_port.sh 3000${NC}"
      exit 1
    fi
  fi
  
  # Create or update .env file in frontend directory to ensure correct API URL
  echo -e "${YELLOW}Setting up frontend API connection...${NC}"
  echo "REACT_APP_API_URL=http://localhost:5002" > frontend/.env
  echo "PORT=3000" >> frontend/.env
  
  # Check if node_modules exists
  if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}Installing frontend dependencies (this may take a moment)...${NC}"
    cd frontend && npm install && cd ..
  fi
  
  # Start the frontend in the background
  cd frontend && PORT=3000 npm start > ../frontend.log 2>&1 &
  FRONTEND_PID=$!
  
  # Add to our list of processes
  PIDS+=($FRONTEND_PID)
  
  # Give the frontend a moment to start
  sleep 3
  
  echo -e "${GREEN}Frontend server running at http://localhost:3000${NC}"
  
  # Go back to root directory
  cd ..
}

# Start Ollama API server
start_ollama_server() {
  echo -e "${GREEN}Starting Ollama API server on port 5003...${NC}"
  
  # Check if port 5003 is already in use
  if check_port 5003; then
    echo -e "${YELLOW}Port 5003 is already in use.${NC}"
    
    # Try to kill the process using port 5003
    if ! kill_port 5003; then
      echo -e "${RED}Cannot start Ollama API server. Port 5003 is in use and couldn't be freed.${NC}"
      echo -e "${YELLOW}Try running: ./kill_port.sh 5003${NC}"
      exit 1
    fi
  fi
  
  # Check if Ollama is running
  if ! curl -s "http://localhost:11434/api/version" > /dev/null; then
    echo -e "${YELLOW}Warning: Ollama server doesn't seem to be running.${NC}"
    echo -e "${YELLOW}Please make sure Ollama is installed and running before using AI Analysis.${NC}"
    echo -e "${YELLOW}Visit https://ollama.ai to download Ollama.${NC}"
  else
    echo -e "${GREEN}✅ Ollama server is running${NC}"
  fi
  
  # Start the Ollama API server in the background
  python3 run_ollama.py > ollama_api.log 2>&1 &
  OLLAMA_PID=$!
  
  # Add to our list of processes
  PIDS+=($OLLAMA_PID)
  
  # Wait a moment for the Ollama API server to start
  echo -e "${YELLOW}Waiting for Ollama API server to start...${NC}"
  sleep 3
  
  # Check if Ollama API server is running
  if ! kill -0 $OLLAMA_PID 2>/dev/null; then
    echo -e "${RED}Ollama API server failed to start. Checking logs:${NC}"
    tail -n 20 ollama_api.log
    echo -e "${YELLOW}Warning: Ollama API service is not available. AI Analysis using Ollama will not work.${NC}"
    echo -e "${YELLOW}The rest of the application will continue to function.${NC}"
  else
    # Verify Ollama API connection
    if curl -s "http://localhost:5003/api/ollama-analysis" > /dev/null; then
      echo -e "${GREEN}✅ Ollama API server running at http://localhost:5003${NC}"
    else
      echo -e "${YELLOW}Warning: Ollama API server is running but not responding correctly.${NC}"
      echo -e "${YELLOW}AI Analysis using Ollama may not work properly.${NC}"
    fi
  fi
}

# Run the bot
run_bot() {
  if [ "$MODE" == "test" ]; then
    echo -e "${CYAN}Running bot in TEST mode (sending to test chat)...${NC}"
    echo -e "${PURPLE}🔔 Telegram messages will be sent to YOUR PERSONAL CHAT (ID: $CHAT_ID)${NC}"
    python3 test.py > bot.log 2>&1 &
  else
    echo -e "${CYAN}Running bot in PRODUCTION mode (sending to real channel)...${NC}"
    echo -e "${PURPLE}🔔 Telegram messages will be sent to PUBLIC CHANNEL (ID: $CHAT_ID)${NC}"
    python3 main.py > bot.log 2>&1 &
  fi
  
  BOT_PID=$!
  PIDS+=($BOT_PID)
}

# Function to be executed on script exit
cleanup() {
  echo -e "\n${YELLOW}Shutting down all services...${NC}"
  for pid in "${PIDS[@]}"; do
    if kill -0 $pid 2>/dev/null; then
      kill $pid
      echo -e "${GREEN}Stopped process $pid${NC}"
    fi
  done
  echo -e "${GREEN}All services stopped.${NC}"
  exit 0
}

# Store all process IDs
PIDS=()

# Set up trap to call cleanup function on script exit
trap cleanup EXIT INT TERM

# Check for essential dependencies
install_dependencies

# Start all services
start_backend
start_frontend
start_ollama_server
run_bot

echo -e "\n${GREEN}All services started successfully!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Dashboard: ${NC}http://localhost:3000"
echo -e "${BLUE}Backend API: ${NC}http://localhost:5002"
echo -e "${BLUE}Ollama API: ${NC}http://localhost:5003"
echo -e "${BLUE}API Health Check: ${NC}http://localhost:5002/api/health"
echo -e "${BLUE}Bot Mode: ${NC}$MODE_DISPLAY"
if [ "$MODE" == "test" ]; then
  echo -e "${BLUE}Telegram: ${NC}Sending to ${PURPLE}YOUR PERSONAL CHAT${NC}"
else
  echo -e "${BLUE}Telegram: ${NC}Sending to ${PURPLE}PUBLIC CHANNEL${NC}"
fi
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"

# Keep the script running
wait 
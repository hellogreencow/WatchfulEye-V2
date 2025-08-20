#!/bin/bash
# Complete startup script for WatchfulEye Intelligence System
# Starts web server, OpenRouter API, and frontend - Bot must be started manually
# Usage: ./run_complete.sh [test|prod]

set -e

# Color definitions
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Store the script directory to ensure we always return to it
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Default mode is test
MODE=${1:-test}

if [[ "$MODE" != "test" && "$MODE" != "prod" ]]; then
  echo -e "${RED}Invalid mode. Use either 'test' or 'prod'.${NC}"
  echo -e "${YELLOW}Usage: ./run_complete.sh [test|prod]${NC}"
  exit 1
fi

# Convert mode to uppercase for display
if [ "$MODE" = "test" ]; then
  MODE_DISPLAY="TEST"
else
  MODE_DISPLAY="PRODUCTION"
fi

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   WatchfulEye System (No Bot) - $MODE_DISPLAY MODE        ${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo -e "${CYAN}Starting servers (backend, OpenRouter API, frontend)...${NC}"

# Function to check if a port is in use
check_port() {
  local port=$1
  if command -v lsof >/dev/null 2>&1; then
    if lsof -i :"$port" >/dev/null 2>&1; then
      return 0  # Port is in use
    fi
  else
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
  
  # Attempt up to 3 times with escalation
  for attempt in 1 2 3; do
    if command -v lsof >/dev/null 2>&1; then
      local pids=$(lsof -ti :"$port" 2>/dev/null | tr '\n' ' ')
      if [ -n "$pids" ]; then
        echo -e "${YELLOW}[Attempt $attempt] Killing process(es) $pids using port $port${NC}"
        # Try graceful then force
        kill $pids 2>/dev/null || true
        sleep 1
        kill -9 $pids 2>/dev/null || true
      fi
    fi

    # fuser fallback if available
    if command -v fuser >/dev/null 2>&1; then
      fuser -k ${port}/tcp 2>/dev/null || true
    fi

    sleep 2
    if ! check_port "$port"; then
      echo -e "${GREEN}Port $port is now free${NC}"
      return 0
    fi
  done
  
  echo -e "${RED}Failed to free port $port after multiple attempts. Please kill the process manually and retry.${NC}"
  return 1
}

# Check for virtual environment and create if needed
setup_environment() {
  echo -e "${YELLOW}Setting up Python environment...${NC}"
  
  # Ensure we're in the correct directory
  cd "$SCRIPT_DIR"
  
  if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
  fi
  
  # Activate virtual environment
  source venv/bin/activate
  
  # Install dependencies
  echo -e "${YELLOW}Installing dependencies...${NC}"
  pip install -r requirements.txt
  
  echo -e "${GREEN}Environment setup complete.${NC}"
}

# Start the main backend server
start_backend() {
  echo -e "${GREEN}Starting main backend server on port 5002...${NC}"
  
  # Ensure we're in the correct directory
  cd "$SCRIPT_DIR"
  
  # Check if port is in use
  if check_port 5002; then
    if ! kill_port 5002; then
      echo -e "${RED}Cannot start backend server. Port 5002 is in use.${NC}"
      exit 1
    fi
  fi
  
  # Start the backend server
  python3 web_app.py > backend.log 2>&1 &
  BACKEND_PID=$!
  PIDS+=($BACKEND_PID)
  
  # Wait for server to start
  echo -e "${YELLOW}Waiting for backend server to start...${NC}"
  sleep 5
  
  # Check if backend is running
  if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}Backend server failed to start. Checking logs:${NC}"
    tail -n 20 backend.log
    exit 1
  fi
  
  # Verify backend is responding
  if curl -s "http://localhost:5002/api/health" > /dev/null; then
    echo -e "${GREEN}✅ Backend server running at http://localhost:5002${NC}"
  else
    echo -e "${RED}Backend server is not responding. Checking logs:${NC}"
    tail -n 20 backend.log
    exit 1
  fi
}

# Start the AI Analysis API server (OpenRouter)
start_openrouter_api() {
  echo -e "${GREEN}Starting AI Analysis server on port 5003...${NC}"
  
  # Ensure we're in the correct directory
  cd "$SCRIPT_DIR"
  
  # Check if port is in use
  if check_port 5003; then
    echo -e "${YELLOW}Port 5003 is in use. Attempting to terminate existing process...${NC}"
    if ! kill_port 5003; then
      echo -e "${RED}Cannot free port 5003 automatically. Aborting to prevent port conflicts.${NC}"
      exit 1
    fi
  fi
  
  # Check for OpenRouter configuration
  OPENROUTER_API_KEY=$(grep "^OPENROUTER_API_KEY=" .env | head -1 | cut -d= -f2 || echo "")
  OPENROUTER_MODEL=$(grep "^OPENROUTER_MODEL=" .env | head -1 | cut -d= -f2 || echo "")
  
  if [ -n "$OPENROUTER_API_KEY" ]; then
    echo -e "${BLUE}=== Using OpenRouter for AI Analysis ===${NC}"
    echo -e "${GREEN}OpenRouter is configured with model: ${CYAN}${OPENROUTER_MODEL:-"gpt-4o-mini (default)"}${NC}"
    
    # Mask most of the OpenRouter key for display
    OPENROUTER_API_KEY_MASKED=${OPENROUTER_API_KEY:0:10}...
    echo -e "${GREEN}OpenRouter API Key: ${CYAN}${OPENROUTER_API_KEY_MASKED}${NC}"
    
    # Start the OpenRouter API server (script is still named run_ollama.py for backward compatibility)
    python3 run_ollama.py > openrouter_api.log 2>&1 &
    API_PID=$!
    PIDS+=($API_PID)
    
    # Wait for server to start
    echo -e "${YELLOW}Waiting for AI Analysis server to start...${NC}"
    sleep 3
    
    # Check if API server is running
    if ! kill -0 $API_PID 2>/dev/null; then
      echo -e "${RED}AI Analysis server failed to start. Checking logs:${NC}"
      tail -n 20 openrouter_api.log
      echo -e "${YELLOW}Warning: AI Analysis with OpenRouter will not be available. Continuing without it.${NC}"
      return 0
    else
      # Verify API is responding
      if curl -s "http://localhost:5003/api/ollama-analysis" > /dev/null; then
        echo -e "${GREEN}✅ AI Analysis server running at http://localhost:5003${NC}"
      else
        echo -e "${YELLOW}Warning: AI Analysis server is not responding correctly. Continuing without it.${NC}"
        return 0
      fi
    fi
  else
    echo -e "${RED}Error: OpenRouter API key not found in .env file${NC}"
    echo -e "${YELLOW}Please add the following to your .env file:${NC}"
    echo -e "${YELLOW}OPENROUTER_API_KEY=your_api_key_here${NC}"
    echo -e "${YELLOW}OPENROUTER_MODEL=openai/gpt-4o-mini${NC}"
    
    echo -e "${YELLOW}Continuing without AI Analysis functionality...${NC}"
  fi
}

# Start the frontend
start_frontend() {
  echo -e "${GREEN}Building and serving React frontend on port 3000...${NC}"

  # Ensure we're in the correct directory
  cd "$SCRIPT_DIR"

  # Check if port is in use
  if check_port 3000; then
    if ! kill_port 3000; then
      echo -e "${RED}Cannot start frontend. Port 3000 is in use.${NC}"
      exit 1
    fi
  fi

  # Set up frontend environment (used during build time)
  # For test mode we point directly to the backend at :5002.
  # For production builds (served through Nginx/Cloudflare), use relative /api to avoid CORS/mixed-content.
  if [ "$MODE" = "test" ]; then
    echo "REACT_APP_API_URL=http://localhost:5002" > frontend/.env
  else
    # Empty .env so the app falls back to relative /api (see Dashboard.tsx)
    : > frontend/.env
  fi

  # Install dependencies if needed
  if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    cd frontend && npm install && cd ..
  fi

  # Build the production bundle with memory limit to prevent tmux crashes
  echo -e "${YELLOW}Building production assets with memory optimization...${NC}"
  cd frontend
  if ! NODE_OPTIONS="--max-old-space-size=1024" npm run build; then
    echo -e "${RED}Frontend build failed. Check the error messages above.${NC}"
    echo -e "${YELLOW}You may need to free up memory or check for Node.js conflicts.${NC}"
    cd ..
    exit 1
  fi
  cd ..

  # Serve the static build with a lightweight server on port 3000
  echo -e "${YELLOW}Starting static file server...${NC}"
  cd frontend && npx --yes serve -s build -l 3000 --listen tcp://0.0.0.0:3000 > ../frontend.log 2>&1 &
  FRONTEND_PID=$!
  PIDS+=($FRONTEND_PID)
  cd ..

  echo -e "${GREEN}✅ Frontend available at http://localhost:3000${NC}"
  # Try to open browser automatically
  open_browser "http://localhost:3000"
}

# Function to run the news bot manually (for reference only)
show_run_bot_instructions() {
  echo -e "\n${CYAN}✦✦✦ HOW TO RUN THE NEWS BOT MANUALLY ✦✦✦${NC}"
  echo -e "${YELLOW}To run the news bot, open a new terminal and run:${NC}"
  if [ "$MODE" == "test" ]; then
    echo -e "${GREEN}python3 test.py${NC}"
    echo -e "${YELLOW}This will run the bot in TEST mode and show the logs in the terminal${NC}"
  else
    echo -e "${GREEN}python3 main.py${NC}"
    echo -e "${YELLOW}This will run the bot in PRODUCTION mode and show the logs in the terminal${NC}"
  fi
  echo -e "${YELLOW}The bot will send messages to Telegram chat ID: ${CYAN}$(grep TELEGRAM_CHAT_ID .env | cut -d= -f2)${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Open browser helper
open_browser() {
  local url="$1"
  echo -e "${YELLOW}Opening ${url} in your default browser...${NC}"
  if command -v open >/dev/null 2>&1; then
    # macOS
    open "$url" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    # Linux
    xdg-open "$url" >/dev/null 2>&1 || true
  fi
}

# Function to clean up on exit
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

# Store all PIDs
PIDS=()

# Set up cleanup on exit
trap cleanup EXIT INT TERM

# Kill all previous processes related to the application
kill_previous_processes() {
  echo -e "${YELLOW}Killing all previous application processes...${NC}"
  
  # Kill backend processes on port 5002
  echo -e "${YELLOW}Stopping any running backend servers...${NC}"
  pkill -f "python3 web_app.py" || true
  # Force kill any process using port 5002
  if command -v lsof >/dev/null 2>&1; then
    local pid=$(lsof -ti :5002 2>/dev/null)
    if [ -n "$pid" ]; then
      echo -e "${YELLOW}Force killing process $pid using port 5002${NC}"
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi
  
  # Kill OpenRouter API processes on port 5003
  echo -e "${YELLOW}Stopping any running API servers...${NC}"
  pkill -f "python3 run_ollama.py" || true
  # Force kill any process using port 5003
  if command -v lsof >/dev/null 2>&1; then
    local pid=$(lsof -ti :5003 2>/dev/null)
    if [ -n "$pid" ]; then
      echo -e "${YELLOW}Force killing process $pid using port 5003${NC}"
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi
  
  # Kill frontend processes on port 3000
  echo -e "${YELLOW}Stopping any running frontend servers...${NC}"
  pkill -f "serve -s build" || true
  # Force kill any process using port 3000
  if command -v lsof >/dev/null 2>&1; then
    local pid=$(lsof -ti :3000 2>/dev/null)
    if [ -n "$pid" ]; then
      echo -e "${YELLOW}Force killing process $pid using port 3000${NC}"
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi
  
  # Extra sleep to ensure processes have time to shut down
  sleep 3
  
  # Double check ports are free
  for port in 3000 5002 5003; do
    if check_port $port; then
      echo -e "${YELLOW}Warning: Port $port is still in use after cleanup attempts${NC}"
    else
      echo -e "${GREEN}Port $port is free${NC}"
    fi
  done
  
  echo -e "${GREEN}All previous processes stopped.${NC}"
}

# Function to check and update Nginx configuration
update_nginx_config() {
  echo -e "${YELLOW}Checking Nginx configuration for API proxy...${NC}"
  
  # Check if we're running as root or have sudo privileges
  if [ "$(id -u)" -ne 0 ]; then
    echo -e "${YELLOW}Not running as root. Skipping Nginx configuration update.${NC}"
    return
  fi
  
  # Check if nginx is installed
  if ! command -v nginx >/dev/null 2>&1; then
    echo -e "${YELLOW}Nginx not found. Skipping configuration update.${NC}"
    return
  fi
  
  NGINX_CONF="/etc/nginx/sites-available/default"
  if [ ! -f "$NGINX_CONF" ]; then
    echo -e "${YELLOW}Nginx default configuration not found. Skipping.${NC}"
    return
  fi
  
  # Check if we need to update the configuration
  if grep -q "proxy_pass http://localhost:5002/api/" "$NGINX_CONF"; then
    echo -e "${GREEN}Nginx API proxy configuration is correct.${NC}"
  else
    echo -e "${YELLOW}Updating Nginx configuration to correctly proxy API requests...${NC}"
    
    # Create a backup
    cp "$NGINX_CONF" "${NGINX_CONF}.bak"
    
    # Update the configuration
    # Look for the proxy_pass line and update it
    sed -i 's|proxy_pass http://localhost:5002/;|proxy_pass http://localhost:5002/api/;|g' "$NGINX_CONF"
    
    echo -e "${GREEN}Nginx configuration updated. Restarting Nginx...${NC}"
    systemctl restart nginx
    
    echo -e "${GREEN}Nginx restarted successfully.${NC}"
  fi
}

# Check system resources before starting
check_system_resources() {
  echo -e "${YELLOW}Checking system resources...${NC}"
  
  # Check available memory (in MB)
  available_mem=$(free -m | awk '/^Mem:/{print $7}')
  if [ "$available_mem" -lt 1000 ]; then
    echo -e "${YELLOW}Warning: Only ${available_mem}MB of memory available.${NC}"
    echo -e "${YELLOW}Frontend build may be slow or fail. Consider freeing up memory.${NC}"
  else
    echo -e "${GREEN}Memory check passed: ${available_mem}MB available.${NC}"
  fi
  
  # Check disk space
  available_disk=$(df / | awk 'NR==2 {print $4}')
  if [ "$available_disk" -lt 2000000 ]; then  # Less than 2GB
    echo -e "${YELLOW}Warning: Low disk space. Available: $(df -h / | awk 'NR==2 {print $4}')${NC}"
  else
    echo -e "${GREEN}Disk space check passed.${NC}"
  fi
}

# Run all steps
check_system_resources
kill_previous_processes
update_nginx_config
setup_environment
start_backend
start_openrouter_api
start_frontend
show_run_bot_instructions

# Check for OpenRouter configuration for summary
OPENROUTER_API_KEY=$(grep "^OPENROUTER_API_KEY=" .env | head -1 | cut -d= -f2 || echo "")
OPENROUTER_MODEL=$(grep "^OPENROUTER_MODEL=" .env | head -1 | cut -d= -f2 || echo "")

# Summary
echo -e "\n${GREEN}WatchfulEye system is now running (without bot)!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Dashboard: ${NC}http://localhost:3000"
echo -e "${BLUE}Backend API: ${NC}http://localhost:5002"
if [ -n "$OPENROUTER_API_KEY" ]; then
  echo -e "${BLUE}AI Analysis API: ${NC}http://localhost:5003 ${GREEN}(OpenRouter: ${OPENROUTER_MODEL:-"gpt-4o-mini (default)"})${NC}"
else
  echo -e "${BLUE}AI Analysis API: ${NC}http://localhost:5003 ${RED}(No OpenRouter API key configured)${NC}"
fi
echo -e "${BLUE}Mode: ${NC}$MODE_DISPLAY"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"

# Interactive control loop
echo -e "${CYAN}Press 'r' + Enter to restart all services, or Ctrl+C to stop${NC}"
while true; do
  read -p "Command (r=restart, q=quit): " -r input
  case $input in
    r|R|restart)
      echo -e "${YELLOW}Restarting all services...${NC}"
      
      # Stop all current services
      echo -e "${YELLOW}Stopping current services...${NC}"
      for pid in "${PIDS[@]}"; do
        if kill -0 $pid 2>/dev/null; then
          kill $pid
          echo -e "${GREEN}Stopped process $pid${NC}"
        fi
      done
      
      # Clear the PIDs array
      PIDS=()
      
      # Kill any lingering processes
      kill_previous_processes
      
      # Restart all services
      echo -e "${GREEN}Restarting services...${NC}"
      start_backend
      start_openrouter_api
      start_frontend
      
      # Show summary again
      echo -e "\n${GREEN}WatchfulEye system restarted successfully!${NC}"
      echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
      echo -e "${BLUE}Dashboard: ${NC}http://localhost:3000"
      echo -e "${BLUE}Backend API: ${NC}http://localhost:5002"
      if [ -n "$OPENROUTER_API_KEY" ]; then
        echo -e "${BLUE}AI Analysis API: ${NC}http://localhost:5003 ${GREEN}(OpenRouter: ${OPENROUTER_MODEL:-"gpt-4o-mini (default)"})${NC}"
      else
        echo -e "${BLUE}AI Analysis API: ${NC}http://localhost:5003 ${RED}(No OpenRouter API key configured)${NC}"
      fi
      echo -e "${BLUE}Mode: ${NC}$MODE_DISPLAY"
      echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
      echo -e "${CYAN}Press 'r' + Enter to restart all services, or Ctrl+C to stop${NC}"
      ;;
    q|Q|quit|exit)
      echo -e "${YELLOW}Shutting down...${NC}"
      cleanup
      ;;
    *)
      echo -e "${YELLOW}Unknown command. Use 'r' to restart or 'q' to quit.${NC}"
      ;;
  esac
done 
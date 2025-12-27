#!/bin/bash
# Reset script for DIatomsAINewsBot - Completely resets the server and clears caches

# Color definitions
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔═════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   DiatomsAI News Bot - RESET SERVER             ║${NC}"
echo -e "${BLUE}╚═════════════════════════════════════════════════╝${NC}"

# Kill any processes using the required ports
echo -e "${YELLOW}Freeing ports 3000 and 5002...${NC}"

# Kill processes on port 5002 (backend)
echo -e "${YELLOW}Checking port 5002 (backend)...${NC}"
BACKEND_PIDS=$(lsof -ti :5002)
if [ -n "$BACKEND_PIDS" ]; then
  echo -e "${YELLOW}Killing processes on port 5002: $BACKEND_PIDS${NC}"
  kill -9 $BACKEND_PIDS
  sleep 1
fi

# Kill processes on port 3000 (frontend)
echo -e "${YELLOW}Checking port 3000 (frontend)...${NC}"
FRONTEND_PIDS=$(lsof -ti :3000)
if [ -n "$FRONTEND_PIDS" ]; then
  echo -e "${YELLOW}Killing processes on port 3000: $FRONTEND_PIDS${NC}"
  kill -9 $FRONTEND_PIDS
  sleep 1
fi

# Also kill Python processes
echo -e "${YELLOW}Stopping any running Python/Node processes...${NC}"

# Kill Python processes
pkill -f "python.*web_app.py" || true
pkill -f "python3.*web_app.py" || true
pkill -f "python.*main.py" || true
pkill -f "python3.*main.py" || true
pkill -f "python.*test.py" || true
pkill -f "python3.*test.py" || true

# Kill Node/NPM processes for the frontend
pkill -f "node.*start" || true
pkill -f "npm.*start" || true
pkill -f "npm.*run.*start" || true

# Give processes time to shut down
sleep 2

# Verify ports are free
BACKEND_PIDS_AFTER=$(lsof -ti :5002)
FRONTEND_PIDS_AFTER=$(lsof -ti :3000)

if [ -n "$BACKEND_PIDS_AFTER" ]; then
  echo -e "${RED}Warning: Port 5002 is still in use by PID(s): $BACKEND_PIDS_AFTER${NC}"
else
  echo -e "${GREEN}Port 5002 is free ✓${NC}"
fi

if [ -n "$FRONTEND_PIDS_AFTER" ]; then
  echo -e "${RED}Warning: Port 3000 is still in use by PID(s): $FRONTEND_PIDS_AFTER${NC}"
else
  echo -e "${GREEN}Port 3000 is free ✓${NC}"
fi

# Clear frontend cache
echo -e "${YELLOW}Clearing frontend cache...${NC}"

# Remove node_modules cache
rm -rf frontend/node_modules/.cache || true

# Clear React build files
echo -e "${YELLOW}Cleaning React build artifacts...${NC}"
rm -rf frontend/build || true

# Clear browser cache instructions
echo -e "${YELLOW}Please clear your browser cache manually:${NC}"
echo -e "1. Chrome: Open DevTools (F12) → Network tab → check 'Disable Cache'"
echo -e "2. Or use incognito/private window to access the application"

# Create a fresh .env file
echo -e "${YELLOW}Creating fresh .env file for frontend...${NC}"
echo "REACT_APP_API_URL=http://localhost:5002" > frontend/.env

# Ensure CORS config is created
echo -e "${YELLOW}Creating fresh CORS configuration...${NC}"
cat > cors_config.py << EOF
# CORS configuration
from flask_cors import CORS

def configure_cors(app):
    CORS(app, resources={
        r"/*": {
            "origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })
    return app
EOF

# Make scripts executable
chmod +x run.sh
chmod +x kill_port.sh

echo -e "${GREEN}Reset complete! Run the application with:${NC}"
echo -e "${BLUE}./run.sh test${NC} or ${BLUE}./run.sh prod${NC}"
echo -e ""
echo -e "${YELLOW}IMPORTANT: Access the dashboard in a new incognito/private window${NC}"
echo -e "${YELLOW}to avoid browser cache issues.${NC}"
echo -e ""
echo -e "${YELLOW}NOTE: The 'UNIQUE constraint failed: articles.url_hash' warnings${NC}"
echo -e "${YELLOW}are normal and just indicate the article already exists in the database.${NC}" 
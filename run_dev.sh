#!/bin/bash
# Development script for DIatomsAINewsBot
# Starts the React frontend on port 3000 and Flask backend on port 5002

set -e

# Color definitions
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   DiatomsAI News Bot - Development Mode    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo -e "${RED}Error: Node.js is not installed. Please install Node.js and npm first.${NC}"
    exit 1
fi

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed. Please install Python 3 first.${NC}"
    exit 1
fi

# Function to install Python dependencies directly
install_direct_dependencies() {
    echo -e "${YELLOW}Installing Python dependencies directly...${NC}"
    python3 -m pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to install dependencies. Trying to install essential packages directly...${NC}"
        python3 -m pip install flask flask-cors flask-limiter flask-caching flask-compress
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to install essential packages. Please install them manually:${NC}"
            echo -e "${YELLOW}pip install flask flask-cors flask-limiter flask-caching flask-compress${NC}"
            return 1
        fi
    fi
    return 0
}

# Function to start the backend server
start_backend() {
    echo -e "${GREEN}Starting Flask backend server on port 5002...${NC}"
    cd "$(dirname "$0")"
    
    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
        echo -e "${YELLOW}Creating Python virtual environment...${NC}"
        python3 -m venv venv
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to create virtual environment. Will try to use system Python.${NC}"
            USE_SYSTEM_PYTHON=1
        else
            USE_SYSTEM_PYTHON=0
        fi
    else
        USE_SYSTEM_PYTHON=0
    fi
    
    if [ $USE_SYSTEM_PYTHON -eq 0 ]; then
        # Activate virtual environment
        echo -e "${GREEN}Activating virtual environment...${NC}"
        source venv/bin/activate
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to activate virtual environment. Will try to use system Python.${NC}"
            USE_SYSTEM_PYTHON=1
        fi
    
        # Install dependencies if needed
        echo -e "${YELLOW}Installing/updating Python dependencies in virtual environment...${NC}"
        pip install -r requirements.txt
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to install dependencies in virtual environment. Will try to use system Python.${NC}"
            deactivate 2>/dev/null || true
            USE_SYSTEM_PYTHON=1
        fi
    fi
    
    if [ $USE_SYSTEM_PYTHON -eq 1 ]; then
        echo -e "${YELLOW}Using system Python instead of virtual environment...${NC}"
        install_direct_dependencies
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to start backend. Please fix dependency issues first.${NC}"
            return 1
        fi
    fi
    
    # Set the port for the Flask app
    export PORT=5002
    export FLASK_ENV=development
    
    # Start the Flask server
    echo -e "${GREEN}Backend server starting at http://localhost:5002${NC}"
    if [ $USE_SYSTEM_PYTHON -eq 1 ]; then
        python3 web_app.py
    else
        python web_app.py
    fi
}

# Function to start the frontend server
start_frontend() {
    echo -e "${GREEN}Starting React frontend on port 3000...${NC}"
    cd "$(dirname "$0")/frontend"
    
    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}Installing frontend dependencies...${NC}"
        npm install
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to install frontend dependencies. Please run 'npm install' in the frontend directory.${NC}"
            return 1
        fi
    fi
    
    # Start the React development server
    echo -e "${GREEN}Frontend server starting at http://localhost:3000${NC}"
    npm start
}

# Function to be executed on script exit
cleanup() {
    echo -e "${YELLOW}Shutting down servers...${NC}"
    # Kill any background processes started by this script
    jobs -p | xargs -r kill
    echo -e "${GREEN}Servers stopped.${NC}"
    exit 0
}

# Set up trap to call cleanup function on script exit
trap cleanup EXIT INT TERM

# Start the backend in the background
start_backend || { echo -e "${RED}Backend failed to start. Exiting.${NC}"; exit 1; } &
BACKEND_PID=$!

# Give the backend a moment to start
sleep 2

# Check if backend is still running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}Backend server failed to start. Please check the error messages above.${NC}"
    exit 1
fi

# Start the frontend in the background
start_frontend || { echo -e "${RED}Frontend failed to start. Exiting.${NC}"; exit 1; } &
FRONTEND_PID=$!

echo -e "${GREEN}All servers started successfully!${NC}"
echo -e "${BLUE}Backend URL: ${NC}http://localhost:5002"
echo -e "${BLUE}Frontend URL: ${NC}http://localhost:3000"
echo -e "${YELLOW}Press Ctrl+C to stop all servers${NC}"

# Wait for any process to exit
wait

# Exit
exit 0 
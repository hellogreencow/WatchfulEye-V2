#!/bin/bash

# Start the main analysis bot in background
echo "Starting DiatomsAI analysis bot..."
python3 main.py --mode continuous &
BOT_PID=$!

# Give the bot a moment to initialize
sleep 5

# Start the Flask backend (this will run in foreground)
echo "Starting web server on port ${PORT:-5002}..."
python3 web_app.py 
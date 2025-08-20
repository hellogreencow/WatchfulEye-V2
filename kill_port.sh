#!/bin/bash
# Kill any process using a specific port

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <port_number>"
    echo "Example: $0 5002"
    exit 1
fi

PORT=$1

echo "Finding processes using port $PORT..."
PIDS=$(lsof -ti :$PORT)

if [ -z "$PIDS" ]; then
    echo "No processes found using port $PORT."
    exit 0
fi

echo "Found process(es) using port $PORT: $PIDS"
echo "Killing process(es)..."

for PID in $PIDS; do
    echo "Killing PID $PID..."
    kill -9 $PID
done

sleep 1

# Verify port is free
NEW_PIDS=$(lsof -ti :$PORT)
if [ -z "$NEW_PIDS" ]; then
    echo "Success! Port $PORT is now free."
else
    echo "Warning: Port $PORT is still in use by PID(s): $NEW_PIDS"
fi 
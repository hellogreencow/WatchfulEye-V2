# Multi-stage build for DiatomsAI News Bot

# Stage 1: Build React frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime with both backend and bot
FROM python:3.12-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/frontend/build ./frontend/build

# Create logs directory
RUN mkdir -p logs

# Expose ports
EXPOSE 5002

# Create startup script
RUN echo '#!/bin/bash\n\
# Start the main analysis bot in background\n\
python3 main.py --mode continuous &\n\
BOT_PID=$!\n\
\n\
# Start the Flask backend\n\
python3 web_app.py &\n\
BACKEND_PID=$!\n\
\n\
# Function to handle shutdown\n\
cleanup() {\n\
    echo "Shutting down services..."\n\
    kill $BOT_PID $BACKEND_PID 2>/dev/null\n\
    exit 0\n\
}\n\
\n\
# Trap shutdown signals\n\
trap cleanup SIGTERM SIGINT\n\
\n\
# Wait for processes\n\
wait $BOT_PID $BACKEND_PID\n\
' > /app/start.sh && chmod +x /app/start.sh

# Set environment variables
ENV PORT=5002
ENV FLASK_ENV=production

# Run both services
CMD ["/app/start.sh"] 
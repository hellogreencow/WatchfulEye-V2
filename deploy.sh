#!/bin/bash

# DiatomsAI One-Command Deployment Script
set -e

echo "🚀 DiatomsAI News Bot Deployment"
echo "================================"

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy env.example to .env and configure your API keys."
    exit 1
fi

# Check Docker installation
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed!"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check docker-compose installation
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: docker-compose is not installed!"
    echo "Installing docker-compose..."
    pip install docker-compose
fi

# Build frontend production build
echo "📦 Building React frontend..."
cd frontend
npm install
npm run build
cd ..

echo "🐳 Building Docker containers..."
docker-compose build

echo "🔄 Starting services..."
docker-compose up -d

echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check health
if curl -f http://localhost:5002/api/health > /dev/null 2>&1; then
    echo "✅ Backend API is healthy!"
else
    echo "⚠️  Backend API health check failed, checking logs..."
    docker-compose logs diatoms-ai
fi

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "📍 Access your application at:"
echo "   - Dashboard: http://localhost"
echo "   - API: http://localhost:5002/api"
echo ""
echo "📊 View logs:"
echo "   docker-compose logs -f"
echo ""
echo "🛑 Stop services:"
echo "   docker-compose down"
echo ""
echo "💡 The bot is now:"
echo "   - Fetching news every 30 minutes"
echo "   - Analyzing with OpenAI"
echo "   - Posting to Telegram"
echo "   - Serving the web dashboard" 
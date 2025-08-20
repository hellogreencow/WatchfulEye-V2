## RAG Embeddings Provider

Set the embeddings provider and keys in your environment:

```
VOYAGE_API_KEY=your_key_here           # enables voyage-3-large by default
# or force selection
EMBEDDINGS_PROVIDER=voyage             # voyage | openai

# Postgres for pgvector
PG_DSN=dbname=watchfuleye user=watchful password=watchfulpass host=postgres port=5432
```

Install dependencies:

```
pip install -r requirements.txt
```

Ensure Postgres with pgvector is running (see docker-compose.yml).
# WatchfulEye Intelligence Platform - Deployment Guide

## One-Command Deployment Options

### Option 1: Docker (Recommended for VPS/Cloud)

**Requirements**: Docker and docker-compose installed

```bash
# Clone the repository
git clone <your-repo-url>
cd watchfuleye

# Configure environment
cp env.example .env
# Edit .env with your API keys

# Deploy with one command
./deploy.sh
```

That's it! Your platform is now running at `http://localhost` with:
- ✅ Web dashboard
- ✅ News fetching every 30 minutes
- ✅ OpenAI analysis
- ✅ Telegram posting

### Option 2: Railway (Easiest Cloud Deployment)

Railway supports both Python and Node.js, perfect for our stack!

1. **Install Railway CLI**:
```bash
npm install -g @railway/cli
```

2. **Create `railway.json`**:
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "cd frontend && npm install && npm run build && cd .. && pip install -r requirements.txt"
  },
  "deploy": {
    "startCommand": "python3 main.py --mode continuous & python3 web_app.py",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

3. **Deploy**:
```bash
railway login
railway up
```

Railway will automatically:
- Detect Python + Node.js
- Build your frontend
- Run both the bot and web server
- Provide a public URL

### Option 3: Render

1. **Create `render.yaml`**:
```yaml
services:
  - type: web
    name: watchfuleye
    env: python
    buildCommand: |
      cd frontend && npm install && npm run build && cd ..
      pip install -r requirements.txt
    startCommand: |
      python3 main.py --mode continuous &
      python3 web_app.py
    envVars:
      - fromGroup: watchfuleye-env
```

2. **Connect GitHub repo to Render**
3. **Deploy with one click**

### Option 4: Fly.io

1. **Install Fly CLI**:
```bash
curl -L https://fly.io/install.sh | sh
```

2. **Create `fly.toml`**:
```toml
app = "watchfuleye"

[build]
  dockerfile = "Dockerfile"

[env]
  PORT = "5002"

[http_service]
  internal_port = 5002
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true

[[services]]
  internal_port = 5002
  protocol = "tcp"

  [[services.ports]]
    port = 80
    handlers = ["http"]
    
  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]
```

3. **Deploy**:
```bash
fly auth login
fly launch
fly deploy
```

### Option 5: Traditional VPS (DigitalOcean, AWS EC2, etc.)

```bash
# SSH into your server
ssh user@your-server

# Install Docker
curl -fsSL https://get.docker.com | sh

# Clone and deploy
git clone <your-repo-url>
cd watchfuleye
cp env.example .env
nano .env  # Add your API keys
./deploy.sh
```

## Environment Variables

Make sure to set these in your `.env` file or platform settings:

```env
# Required
NEWSAPI_KEY=your_newsapi_key
OPENAI_API_KEY=your_openai_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHANNEL_ID=@your_channel

# Optional
PORT=5002
ANALYSIS_INTERVAL=30
```

## Post-Deployment Checklist

- [ ] Check dashboard at your deployment URL
- [ ] Verify `/api/health` returns healthy
- [ ] Check Telegram channel for posts
- [ ] Monitor logs for any errors

## Monitoring

View logs:
```bash
# Docker
docker-compose logs -f

# Railway
railway logs

# Fly.io
fly logs
```

## Troubleshooting

1. **Bot not posting to Telegram?**
   - Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID
   - Ensure bot is admin in channel

2. **No news analysis?**
   - Verify OPENAI_API_KEY is valid
   - Check you have API credits

3. **Dashboard not loading?**
   - Ensure frontend build completed
   - Check nginx/proxy configuration

## Production Tips

1. **Use environment variables** instead of .env file in production
2. **Set up monitoring** (e.g., UptimeRobot)
3. **Configure backups** for the SQLite database
4. **Use a proper domain** with SSL certificate
5. **Set up log rotation** to prevent disk filling

## Quick Commands

```bash
# Start everything
./deploy.sh

# Stop everything
docker-compose down

# View logs
docker-compose logs -f

# Restart services
docker-compose restart

# Update and redeploy
git pull
./deploy.sh
```

## Support

Having issues? Check:
- Logs: `docker-compose logs`
- Health: `curl http://localhost:5002/api/health`
- Database: `sqlite3 news_bot.db "SELECT COUNT(*) FROM articles;"` 
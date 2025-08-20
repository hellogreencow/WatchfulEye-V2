# 🌍 WatchfulEye News Intelligence System

**Advanced Geopolitical News Analysis & Investment Intelligence Platform**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![AI Powered](https://img.shields.io/badge/AI-GPT--4o--mini-purple.svg)](https://openai.com/)

## 📋 Table of Contents

- [🎯 Overview](#-overview)
- [✨ Features](#-features)
- [🏗️ Architecture](#️-architecture)
- [🚀 Quick Start](#-quick-start)
- [📦 Installation](#-installation)
- [⚙️ Configuration](#️-configuration)
- [🔧 Usage](#-usage)
- [🌐 Web Dashboard](#-web-dashboard)
- [🤖 Bot Features](#-bot-features)
- [🛡️ Security](#️-security)
- [📊 Monitoring](#-monitoring)
- [🔄 API Reference](#-api-reference)
- [🧪 Testing](#-testing)
- [🐛 Troubleshooting](#-troubleshooting)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)
- [Ollama Integration for Enhanced AI Analysis](#ollama-integration-for-enhanced-ai-analysis)

## 🎯 Overview

WatchfulEye is a sophisticated platform that automatically:

1. **Fetches** real-time geopolitical news from multiple sources
2. **Analyzes** content using advanced AI categorization and sentiment analysis
3. **Generates** actionable investment insights using GPT-4o-mini
4. **Delivers** intelligence via multiple notification channels
5. **Provides** a comprehensive web dashboard for data exploration

### 🎯 Use Cases

- **Investment Research**: Get AI-powered investment ideas based on geopolitical events
- **Risk Assessment**: Monitor global conflicts, sanctions, and trade developments
- **Market Intelligence**: Track sentiment shifts and emerging themes
- **News Aggregation**: Centralized dashboard for geopolitical news
- **Alert System**: Real-time notifications for critical developments

## ✨ Features

### 🧠 AI-Powered Analysis
- **GPT-4o-mini Integration**: Advanced natural language processing
- **Multi-Category Classification**: Conflict, sanctions, trade, diplomacy, economics, energy, technology
- **Sentiment Analysis**: Positive/negative/neutral sentiment scoring with confidence metrics
- **Investment Insights**: Actionable recommendations with risk assessment

### 📊 Enhanced Database
- **SQLite with Advanced Schema**: Optimized for performance and analytics
- **Content Deduplication**: Hash-based duplicate detection
- **Automatic Cleanup**: Configurable data retention policies
- **Database Health Monitoring**: Integrity checks and optimization

### 🌐 Professional Web Interface
- **Responsive Design**: Mobile-first approach with Tailwind CSS
- **Real-time Updates**: Live data refreshing and notifications
- **Advanced Filtering**: Category, sentiment, time-based filters
- **Interactive Charts**: Category distribution and sentiment visualization
- **Search Functionality**: Full-text search across articles
- **Export Capabilities**: JSON and CSV export options

### 🔄 Process Management
- **Auto-restart**: Intelligent process monitoring and recovery
- **Health Checks**: HTTP and system-level health monitoring
- **Resource Monitoring**: CPU, memory, and performance tracking
- **Graceful Shutdown**: Clean process termination
- **Statistics Logging**: Comprehensive system metrics

### 🛡️ Enterprise Security
- **Rate Limiting**: API protection with configurable limits
- **Security Headers**: OWASP-compliant HTTP security headers
- **Input Validation**: Comprehensive parameter validation
- **Error Handling**: Robust exception management
- **Audit Logging**: Complete action tracking

### 📬 Multi-Channel Notifications
- **Email**: SMTP with HTML formatting
- **Telegram**: Bot integration with Markdown support
- **Discord**: Webhook integration with rich formatting
- **Pushover**: Mobile-optimized notifications
- **Retry Logic**: Automatic retry with exponential backoff

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   News Sources  │────│   Data Pipeline  │────│   AI Analysis   │
│                 │    │                  │    │                 │
│ • NewsAPI       │    │ • Fetch & Store  │    │ • GPT-4o-mini   │
│ • RSS Feeds     │    │ • Categorization │    │ • Sentiment     │
│ • Web Scraping  │    │ • Deduplication  │    │ • Investment    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       ▼                       │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Notifications  │    │    Database      │    │  Web Dashboard  │
│                 │    │                  │    │                 │
│ • Email         │    │ • SQLite         │    │ • Flask App     │
│ • Telegram      │    │ • Health Checks  │    │ • REST API      │
│ • Discord       │    │ • Optimization   │    │ • Real-time UI  │
│ • Pushover      │    │ • Backup         │    │ • Analytics     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Core Components

1. **`main.py`**: News bot with AI analysis engine
2. **`web_app.py`**: Flask web application with REST API
3. **`database.py`**: Enhanced SQLite database manager
4. **`run_all.py`**: Process manager with monitoring
5. **`templates/index.html`**: Responsive web dashboard

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- NewsAPI key (free at [newsapi.org](https://newsapi.org/))
- OpenAI API key (from [platform.openai.com](https://platform.openai.com/))

### 1-Minute Setup

```bash
# Clone the repository
git clone https://github.com/your-repo/watchfuleye.git
cd watchfuleye

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp config.example .env
# Edit .env with your API keys

# Start the system (choose one):
# Option 1: All-in-one (backend, frontend, OpenRouter API, optional bot)
./run_complete.sh test

# Option 2: Dev mode (hot reload for frontend + backend)
./run_dev.sh

# Option 3: Single command (backend + frontend + Ollama/OpenRouter + bot)
./run.sh test
```

🎉 **That's it!**
- Dashboard: http://localhost:3000
- Backend API: http://localhost:5002
- AI Analysis API: http://localhost:5003 (if OpenRouter configured)

## 📦 Installation

### Method 1: pip install (Recommended)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Method 2: Docker (Coming Soon)

```bash
# Build and run with Docker
docker-compose up -d

### Environment

Add these to `.env` or export as env vars:

```
OPENAI_API_KEY=...
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=openai/gpt-4o-mini
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
DB_PATH=news_bot.db
```
```

### Method 3: Setup Script

```bash
# Run automated setup script
chmod +x setup.sh
./setup.sh
```

### Verify Installation

```bash
# Test API keys and dependencies
python -c "
import requests, openai, flask
print('✅ All dependencies installed successfully')
"
```

## ⚙️ Configuration

### Environment Variables

Copy `config.example` to `.env` and configure the following:

#### Required Settings
```bash
# API Keys (REQUIRED)
NEWSAPI_KEY=your_newsapi_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Notification Method (At least one REQUIRED)
EMAIL_ENABLED=true
EMAIL_FROM=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_TO=recipient@example.com
```

#### Optional Settings
```bash
# Bot Behavior
MAX_ARTICLES_PER_RUN=50
MIN_ARTICLES_FOR_ANALYSIS=5
ANALYSIS_QUALITY_THRESHOLD=0.3

# Rate Limiting
NEWSAPI_RATE_LIMIT=1000
OPENAI_RATE_LIMIT=60
REQUEST_TIMEOUT=30

# Database
DB_PATH=news_bot.db
DATA_RETENTION_DAYS=30

# Web Application
PORT=5001
FLASK_ENV=development
```

### Notification Setup

#### Email (Gmail)
1. Enable 2-factor authentication on your Gmail account
2. Generate an App Password: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Use the App Password (not your regular password)

#### Telegram
1. Message @BotFather on Telegram
2. Create a new bot with `/newbot`
3. Get your bot token and chat ID

#### Discord
1. Go to Server Settings → Integrations → Webhooks
2. Create New Webhook
3. Copy the webhook URL

#### Pushover
1. Sign up at [pushover.net](https://pushover.net/)
2. Create an application to get your token
3. Get your user key from the dashboard

## 🔧 Usage

### Starting the System

```bash
# Start both bot and web interface
python run_all.py

# Start components separately
python main.py      # Bot only
python web_app.py   # Web interface only
```

### Command Line Options

```bash
# Enable debug mode
FLASK_ENV=development python run_all.py

# Custom configuration file
CONFIG_FILE=custom.env python run_all.py

# Run once without scheduling
python main.py --run-once
```

### Monitoring

The system provides comprehensive monitoring:

```bash
# View real-time logs
tail -f bot.log
tail -f process_manager.log

# Check system health
curl http://localhost:5001/api/health

# View process statistics
cat process_stats.json
```

## 🌐 Web Dashboard

Access the web dashboard at **http://localhost:5001**

### Features

- **📊 Real-time Statistics**: Live counters and metrics
- **📰 Article Feed**: Categorized and filterable news articles
- **🧠 AI Analyses**: Investment insights and recommendations
- **📈 Charts**: Category distribution and sentiment analysis
- **🔍 Search**: Full-text search across all content
- **📱 Mobile Responsive**: Optimized for all devices
- **⚡ Real-time Updates**: Auto-refreshing content
- **💾 Export**: Download data in JSON/CSV formats

## 🎨 React Frontend (New!)

A modern, responsive React dashboard with real-time data visualization and dark mode support.

### React Dashboard Features

- **🌓 Dark Mode**: Toggle between light and dark themes
- **📊 Interactive Charts**: Real-time sentiment and category visualizations using Recharts
- **🔄 Auto-refresh**: Data updates every 5 minutes
- **🎯 Smart Search**: Instant article search with highlighting
- **📱 Fully Responsive**: Optimized for all screen sizes
- **⚡ Performance**: Fast loading with React 18 optimizations
- **🎨 Modern UI**: Built with Tailwind CSS for beautiful aesthetics

### Frontend Setup

1. **Navigate to frontend directory**:
```bash
cd frontend
```

2. **Install dependencies**:
```bash
npm install
```

3. **Create environment file**:
```bash
echo "REACT_APP_API_URL=http://localhost:5002" > .env
```

4. **Start development server**:
```bash
npm start
```

The React dashboard will be available at **http://localhost:3000**

### Running Both Backend and Frontend

Use the convenient development script:

```bash
./run_dev.sh
```

This will start:
- Backend API on http://localhost:5002
- React frontend on http://localhost:3000

### Building for Production

```bash
cd frontend
npm run build
```

The optimized production build will be in the `frontend/build` directory.

### Frontend Technologies

- **React 18**: Latest React with Concurrent Features
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first styling
- **Recharts**: Composable charting library
- **Framer Motion**: Smooth animations
- **Axios**: HTTP client for API calls

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | System health check |
| `/api/stats` | GET | System statistics |
| `/api/articles` | GET | Filtered articles |
| `/api/analyses` | GET | AI analyses |
| `/api/search?q=query` | GET | Search articles |
| `/api/export?format=json` | GET | Export data |

### Filtering Options

- **Category**: conflict, sanctions, trade, diplomacy, economics, energy, technology
- **Sentiment**: positive, neutral, negative
- **Time Range**: 6h, 24h, 3d, 1w
- **Search**: Full-text search

## 🤖 Bot Features

### Intelligent News Processing

1. **Multi-source Aggregation**: Combines news from various APIs
2. **Advanced Categorization**: AI-powered content classification
3. **Sentiment Analysis**: Emotional tone analysis with confidence scores
4. **Deduplication**: Prevents duplicate content
5. **Quality Filtering**: Ensures high-quality analysis

### Investment Analysis

The AI generates specific investment recommendations including:

- **Asset/Instrument**: Specific tradeable assets with tickers
- **Investment Thesis**: Clear reasoning and logic
- **Time Horizon**: Short, medium, or long-term outlook
- **Conviction Level**: 1-5 confidence rating
- **Risk Assessment**: Primary downside scenarios
- **Position Sizing**: Portfolio allocation recommendations

### Scheduling

- **Default**: Runs every 6 hours
- **Customizable**: Modify schedule in `main.py`
- **On-demand**: Manual execution via web interface

## 🛡️ Security

### Security Features

- **🔐 HTTPS Support**: SSL/TLS encryption
- **🛡️ Security Headers**: OWASP-compliant headers
- **⚡ Rate Limiting**: API protection
- **🔍 Input Validation**: Parameter sanitization
- **📝 Audit Logging**: Complete action tracking
- **🔒 Session Security**: Secure cookie configuration

### Best Practices

1. **Use Environment Variables**: Never commit API keys
2. **Enable HTTPS**: In production environments
3. **Regular Updates**: Keep dependencies current
4. **Monitor Logs**: Watch for unusual activity
5. **Backup Data**: Regular database backups

### Security Headers

The application automatically adds security headers:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'; ...
```

## 📊 Monitoring

### System Health

Monitor system health through multiple channels:

1. **Web Dashboard**: Real-time status at `/api/health`
2. **Log Files**: Detailed logging in `bot.log` and `process_manager.log`
3. **Statistics**: JSON metrics in `process_stats.json`
4. **Process Monitor**: Auto-restart and health checks

### Key Metrics

- **Uptime**: System running time
- **Memory Usage**: RAM consumption per process
- **CPU Usage**: Processor utilization
- **Database Health**: Integrity and performance
- **API Response Times**: Performance monitoring
- **Error Rates**: Failure tracking

### Alerts

Configure alerts for:

- Process failures
- High resource usage
- API errors
- Database issues
- Low disk space

## 🔄 API Reference

### REST API

#### Health Check
```http
GET /api/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "database": {
    "health_score": 1.0,
    "size_mb": 15.2
  },
  "response_time_ms": 45.2
}
```

#### Get Articles
```http
GET /api/articles?category=conflict&limit=20&sentiment=negative
```

Response:
```json
{
  "articles": [...],
  "count": 15,
  "filters_applied": {
    "category": "conflict",
    "sentiment": "negative",
    "limit": 20
  }
}
```

#### Search Articles
```http
GET /api/search?q=sanctions&limit=10
```

Response:
```json
{
  "articles": [...],
  "count": 8,
  "query": "sanctions",
  "total_searched": 1250
}
```

### Python API

```python
from database import NewsDatabase

# Initialize database
db = NewsDatabase()

# Get recent articles
articles = db.get_recent_articles(limit=50, category='conflict')

# Get statistics
stats = db.get_enhanced_stats()

# Health check
health = db.get_system_health()
```

## 🧪 Testing

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test categories
pytest tests/test_database.py
pytest tests/test_api.py
pytest tests/test_bot.py
```

### Test Categories

1. **Unit Tests**: Individual component testing
2. **Integration Tests**: Component interaction testing
3. **API Tests**: REST endpoint testing
4. **Database Tests**: Data persistence testing
5. **Process Tests**: System integration testing

### Mock Testing

For development and testing without API calls:

```bash
# Enable test mode
TEST_MODE=true python main.py
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Import Errors
```bash
ModuleNotFoundError: No module named 'flask'
```
**Solution**: Install dependencies
```bash
pip install -r requirements.txt
```

#### 2. API Key Errors
```bash
HTTP 401: Unauthorized
```
**Solution**: Check API keys in `.env` file
```bash
# Verify API keys are correctly set
cat .env | grep API_KEY
```

#### 3. Database Locked
```bash
sqlite3.OperationalError: database is locked
```
**Solution**: Database automatically handles locks with retry logic

#### 4. Port Already in Use
```bash
OSError: [Errno 48] Address already in use
```
**Solution**: Change port or kill existing process
```bash
# Change port
PORT=5001 python web_app.py

# Kill existing process
lsof -ti:5001 | xargs kill -9
```

#### 5. Memory Issues
```bash
Process killed due to high memory usage
```
**Solution**: Adjust memory limits or optimize database
```bash
# Optimize database
python -c "from database import NewsDatabase; db = NewsDatabase(); db.optimize_database()"
```

### Debug Mode

Enable debug mode for detailed error information:

```bash
# Enable debug logging
LOG_LEVEL=DEBUG python run_all.py

# Enable Flask debug mode
FLASK_ENV=development python web_app.py
```

### Log Analysis

Monitor logs for issues:

```bash
# Watch real-time logs
tail -f bot.log | grep ERROR

# Search for specific errors
grep "HTTP" bot.log | tail -20

# Analyze database operations
grep "database" process_manager.log
```

### Health Checks

Verify system health:

```bash
# Check web interface
curl -s http://localhost:5001/api/health | jq

# Test database connection
python -c "from database import NewsDatabase; db = NewsDatabase(); print(db.get_system_health())"

# Verify API keys
python -c "import os; print('NewsAPI:', bool(os.getenv('NEWSAPI_KEY'))); print('OpenAI:', bool(os.getenv('OPENAI_API_KEY')))"
```

### Getting Help

1. **Check Logs**: Review `bot.log` and `process_manager.log`
2. **Health Endpoint**: Visit `/api/health` for system status
3. **Documentation**: Refer to this README
4. **GitHub Issues**: Report bugs and request features
5. **Community**: Join our Discord server

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### Development Setup

```bash
# Fork the repository and clone
git clone https://github.com/your-username/watchfuleye.git
cd watchfuleye

# Create development environment
python -m venv dev-env
source dev-env/bin/activate

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### Code Standards

- **Python**: Follow PEP 8 style guide
- **Documentation**: Document all functions and classes
- **Testing**: Write tests for new features
- **Commits**: Use conventional commit messages

### Contribution Process

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Areas for Contribution

- 🧠 **AI Improvements**: Better analysis algorithms
- 📊 **Visualization**: Enhanced charts and dashboards
- 🔌 **Integrations**: New notification channels
- 🌐 **Internationalization**: Multi-language support
- 📱 **Mobile App**: Native mobile applications
- 🔒 **Security**: Enhanced security features

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### MIT License Summary

- ✅ **Commercial Use**: Use in commercial projects
- ✅ **Modification**: Modify the source code
- ✅ **Distribution**: Distribute copies
- ✅ **Private Use**: Use privately
- ❌ **Liability**: No warranty or liability
- ❌ **Trademark Use**: No trademark rights

---

## 🙏 Acknowledgments

- **NewsAPI**: For providing excellent news data
- **OpenAI**: For powerful AI analysis capabilities
- **Flask**: For the robust web framework
- **Tailwind CSS**: For beautiful, responsive design
- **Chart.js**: For interactive visualizations

---

## 📞 Support

- **Documentation**: You're reading it! 📖
- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/discussions)
- **Email**: support@diatoms.ai

---

<div align="center">

**[⬆ Back to Top](#-watchfuleye-news-intelligence-system)**

Made with ❤️ by the WatchfulEye Team

</div>

# Ollama Integration for Enhanced AI Analysis

WatchfulEye now supports enhanced AI analysis through Ollama, a local AI model serving system.

### Prerequisites

1. Install Ollama from [ollama.ai](https://ollama.ai/)
2. Download the Dolphin 3.0 (Llama 3.1 8B) model:
   ```bash
   ollama pull hf.co/cognitivecomputations/Dolphin3.0-Llama3.1-8B-GGUF:Q4_0
   ```

### Running with Ollama Support

To enable the Ollama-powered AI Analysis feature:

1. Make sure Ollama is installed and running on your system
2. Start both the main web server and the Ollama API server using one of these methods:

#### Option 1: Complete System (Recommended)
```bash
# Start all services including Ollama API
./run_complete.sh
```

This comprehensive script:
- Starts the main backend (web_app.py) on port 5002
- Starts the Ollama API server (run_ollama.py) on port 5003
- Starts the React frontend on port 3000
- Starts the news bot
- Ensures all services can communicate with each other
- Provides detailed error handling and status reporting

#### Option 2: Ollama-only Addition
```bash
# If you only want to add Ollama to the existing system
./run_with_ollama.sh
```

This script will:
- Start the Ollama API server on port 5003
- Start the main web server on port 5002
- Open the appropriate terminal windows (on macOS) or use tmux/screen sessions (on Linux)

### Troubleshooting Ollama Integration

If you see "Unable to connect to Ollama service" in the AI Analysis modal:

1. Verify that Ollama is installed and running:
   ```bash
   curl http://localhost:11434/api/version
   ```

2. Make sure the Ollama API server is running on port 5003:
   ```bash
   lsof -i :5003
   ```

3. If the server isn't running, start it manually:
   ```bash
   source venv/bin/activate
   python run_ollama.py
   ```

4. Test the Ollama API directly:
   ```bash
   curl http://localhost:5003/api/ollama-analysis
   ```

### Manual Testing

You can test the Ollama analysis endpoint directly with:

```bash
python3 -c "
import requests, json
response = requests.post('http://localhost:5003/api/ollama-analysis', 
    json={
        'title': 'Example Article', 
        'description': 'This is a test article for Ollama analysis', 
        'source': 'Test', 
        'category': 'technology', 
        'sentiment_score': -0.2
    }
)
print(json.dumps(response.json(), indent=2))
"
```

## 🚀 Running the System

The system is now designed to run in separate components:

### Running the Web Interface Only (No Bot)
```bash
# Start the backend, Ollama API server, and frontend
./run_complete.sh test
```

### Running the News Bot Separately
To run the news bot with direct terminal output (recommended):
```bash
# Open a new terminal window
./run_bot.sh test
```

This will:
1. Display all bot logs directly in the terminal
2. Show Telegram message delivery status in real-time
3. Verify your configuration settings before running

You can run the news bot in either test or production mode:
- `test`: Runs the bot once and then exits
- `prod`: Runs the bot continuously with scheduled updates

### Complete System (Legacy Mode)
If you prefer to run everything together (not recommended for debugging):
```bash
# Use the older version that starts everything
./run.sh
``` 
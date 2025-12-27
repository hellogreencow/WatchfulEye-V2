#!/bin/bash

# =============================================================================
# DiatomsAI News Intelligence System - Setup Script
# =============================================================================
# Automated setup and configuration script for the DiatomsAI system
# Usage: ./setup.sh [--production] [--docker] [--help]
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="DiatomsAI News Intelligence System"
PYTHON_MIN_VERSION="3.8"
REQUIRED_DISK_SPACE_MB=500
VENV_NAME="diatoms-env"

# Global variables
PRODUCTION_MODE=false
DOCKER_MODE=false
SKIP_DEPS=false
VERBOSE=false

# =============================================================================
# Utility Functions
# =============================================================================

print_header() {
    echo -e "${BLUE}=================================================================${NC}"
    echo -e "${PURPLE}  🌍 $PROJECT_NAME - Setup Script${NC}"
    echo -e "${BLUE}=================================================================${NC}"
    echo ""
}

print_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_separator() {
    echo -e "${BLUE}-----------------------------------------------------------------${NC}"
}

# =============================================================================
# Command Line Argument Parsing
# =============================================================================

show_help() {
    cat << EOF
DiatomsAI News Intelligence System - Setup Script

USAGE:
    ./setup.sh [OPTIONS]

OPTIONS:
    --production        Setup for production environment
    --docker           Setup for Docker deployment
    --skip-deps        Skip dependency installation
    --verbose          Enable verbose output
    --help             Show this help message

EXAMPLES:
    ./setup.sh                    # Standard development setup
    ./setup.sh --production       # Production setup
    ./setup.sh --docker          # Docker setup
    ./setup.sh --skip-deps       # Skip dependency installation

For more information, see README.md

EOF
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --production)
                PRODUCTION_MODE=true
                shift
                ;;
            --docker)
                DOCKER_MODE=true
                shift
                ;;
            --skip-deps)
                SKIP_DEPS=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# =============================================================================
# System Checks
# =============================================================================

check_operating_system() {
    print_step "Checking operating system..."
    
    case "$(uname -s)" in
        Linux*)     OS="Linux";;
        Darwin*)    OS="macOS";;
        CYGWIN*)    OS="Windows";;
        MINGW*)     OS="Windows";;
        *)          OS="Unknown";;
    esac
    
    print_success "Operating System: $OS"
    
    if [[ "$OS" == "Unknown" ]]; then
        print_warning "Unknown operating system. Setup may not work correctly."
    fi
}

check_python_version() {
    print_step "Checking Python installation..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install Python 3.8 or higher."
        print_info "Visit: https://www.python.org/downloads/"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    
    # Version comparison
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
        print_success "Python $PYTHON_VERSION detected (>= $PYTHON_MIN_VERSION required)"
    else
        print_error "Python $PYTHON_VERSION is too old. Please install Python $PYTHON_MIN_VERSION or higher."
        exit 1
    fi
}

check_pip() {
    print_step "Checking pip installation..."
    
    if ! command -v pip3 &> /dev/null; then
        print_error "pip3 is not installed. Please install pip3."
        print_info "Try: python3 -m ensurepip --upgrade"
        exit 1
    fi
    
    PIP_VERSION=$(pip3 --version | cut -d' ' -f2)
    print_success "pip $PIP_VERSION detected"
}

check_disk_space() {
    print_step "Checking available disk space..."
    
    if command -v df &> /dev/null; then
        AVAILABLE_SPACE=$(df . | tail -1 | awk '{print $4}')
        AVAILABLE_MB=$((AVAILABLE_SPACE / 1024))
        
        if [[ $AVAILABLE_MB -lt $REQUIRED_DISK_SPACE_MB ]]; then
            print_warning "Low disk space: ${AVAILABLE_MB}MB available, ${REQUIRED_DISK_SPACE_MB}MB recommended"
        else
            print_success "Sufficient disk space: ${AVAILABLE_MB}MB available"
        fi
    else
        print_warning "Could not check disk space"
    fi
}

check_network_connectivity() {
    print_step "Checking network connectivity..."
    
    if command -v curl &> /dev/null; then
        if curl -s --max-time 10 https://pypi.org > /dev/null; then
            print_success "Network connectivity verified"
        else
            print_warning "Network connectivity issues detected"
            print_info "Some features may not work properly"
        fi
    elif command -v wget &> /dev/null; then
        if wget -q --timeout=10 --tries=1 https://pypi.org -O /dev/null; then
            print_success "Network connectivity verified"
        else
            print_warning "Network connectivity issues detected"
        fi
    else
        print_warning "Could not verify network connectivity (curl/wget not found)"
    fi
}

check_required_files() {
    print_step "Checking required project files..."
    
    REQUIRED_FILES=(
        "main.py"
        "web_app.py"
        "database.py"
        "run_all.py"
        "requirements.txt"
        "config.example"
    )
    
    MISSING_FILES=()
    
    for file in "${REQUIRED_FILES[@]}"; do
        if [[ ! -f "$file" ]]; then
            MISSING_FILES+=("$file")
        fi
    done
    
    if [[ ${#MISSING_FILES[@]} -eq 0 ]]; then
        print_success "All required files present"
    else
        print_error "Missing required files: ${MISSING_FILES[*]}"
        print_info "Please ensure you have all project files"
        exit 1
    fi
}

# =============================================================================
# Environment Setup
# =============================================================================

create_virtual_environment() {
    if [[ "$DOCKER_MODE" == true ]]; then
        print_info "Skipping virtual environment creation for Docker mode"
        return
    fi
    
    print_step "Setting up Python virtual environment..."
    
    if [[ -d "$VENV_NAME" ]]; then
        print_warning "Virtual environment already exists"
        read -p "Do you want to recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$VENV_NAME"
            print_info "Removed existing virtual environment"
        else
            print_info "Using existing virtual environment"
            return
        fi
    fi
    
    python3 -m venv "$VENV_NAME"
    print_success "Virtual environment created: $VENV_NAME"
    
    # Activate virtual environment
    source "$VENV_NAME/bin/activate"
    print_success "Virtual environment activated"
    
    # Upgrade pip
    pip install --upgrade pip
    print_success "pip upgraded to latest version"
}

install_dependencies() {
    if [[ "$SKIP_DEPS" == true ]]; then
        print_info "Skipping dependency installation"
        return
    fi
    
    print_step "Installing Python dependencies..."
    
    if [[ ! -f "requirements.txt" ]]; then
        print_error "requirements.txt not found"
        exit 1
    fi
    
    # Install requirements
    if [[ "$VERBOSE" == true ]]; then
        pip install -r requirements.txt
    else
        pip install -r requirements.txt > /dev/null 2>&1
    fi
    
    print_success "Dependencies installed successfully"
    
    # Verify critical imports
    print_step "Verifying critical dependencies..."
    
    python3 -c "
import sys
import importlib

critical_modules = [
    'requests', 'flask', 'schedule', 'sqlite3', 
    'psutil', 'datetime', 'json', 'logging'
]

failed_imports = []
for module in critical_modules:
    try:
        importlib.import_module(module)
    except ImportError as e:
        failed_imports.append(f'{module}: {e}')

if failed_imports:
    print('Failed to import critical modules:')
    for failure in failed_imports:
        print(f'  - {failure}')
    sys.exit(1)
else:
    print('All critical dependencies verified')
"
    
    print_success "All critical dependencies verified"
}

# =============================================================================
# Configuration Setup
# =============================================================================

setup_configuration() {
    print_step "Setting up configuration..."
    
    if [[ ! -f "config.example" ]]; then
        print_error "config.example not found"
        exit 1
    fi
    
    if [[ -f ".env" ]]; then
        print_warning ".env file already exists"
        read -p "Do you want to overwrite it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Keeping existing .env file"
            return
        fi
    fi
    
    cp config.example .env
    print_success "Configuration template copied to .env"
    
    print_separator
    echo -e "${YELLOW}⚠️  IMPORTANT: You need to configure your API keys in the .env file${NC}"
    echo ""
    echo -e "${CYAN}Required API Keys:${NC}"
    echo "  1. NewsAPI Key (free at https://newsapi.org/)"
    echo "  2. OpenAI API Key (from https://platform.openai.com/)"
    echo ""
    echo -e "${CYAN}Required Notification Setup:${NC}"
    echo "  3. At least one notification method (Email recommended)"
    echo ""
    print_info "Edit .env file with your actual values before running the system"
    print_separator
}

validate_configuration() {
    print_step "Validating configuration..."
    
    if [[ ! -f ".env" ]]; then
        print_warning "No .env file found. Using config.example values."
        return
    fi
    
    # Source the .env file
    set -a
    source .env
    set +a
    
    # Check required variables
    MISSING_CONFIG=()
    
    if [[ -z "$NEWSAPI_KEY" || "$NEWSAPI_KEY" == "your_newsapi_key_here" ]]; then
        MISSING_CONFIG+=("NEWSAPI_KEY")
    fi
    
    if [[ -z "$OPENAI_API_KEY" || "$OPENAI_API_KEY" == "your_openai_api_key_here" ]]; then
        MISSING_CONFIG+=("OPENAI_API_KEY")
    fi
    
    # Check at least one notification method
    NOTIFICATION_CONFIGURED=false
    
    if [[ "$EMAIL_ENABLED" == "true" && "$EMAIL_FROM" != "your_email@gmail.com" ]]; then
        NOTIFICATION_CONFIGURED=true
    fi
    
    if [[ "$TELEGRAM_ENABLED" == "true" && "$TELEGRAM_BOT_TOKEN" != "your_bot_token_here" ]]; then
        NOTIFICATION_CONFIGURED=true
    fi
    
    if [[ "$DISCORD_ENABLED" == "true" && "$DISCORD_WEBHOOK_URL" != "https://discord.com/api/webhooks/your_webhook_url_here" ]]; then
        NOTIFICATION_CONFIGURED=true
    fi
    
    if [[ "$PUSHOVER_ENABLED" == "true" && "$PUSHOVER_TOKEN" != "your_pushover_token_here" ]]; then
        NOTIFICATION_CONFIGURED=true
    fi
    
    if [[ "$NOTIFICATION_CONFIGURED" == false ]]; then
        MISSING_CONFIG+=("NOTIFICATION_METHOD")
    fi
    
    if [[ ${#MISSING_CONFIG[@]} -eq 0 ]]; then
        print_success "Configuration validation passed"
    else
        print_error "Configuration validation failed"
        print_info "Missing or unconfigured: ${MISSING_CONFIG[*]}"
        print_info "Please edit .env file with your actual values"
        return 1
    fi
}

# =============================================================================
# Database Setup
# =============================================================================

setup_database() {
    print_step "Setting up database..."
    
    # Create database directory if needed
    mkdir -p "$(dirname "${DB_PATH:-news_bot.db}")"
    
    # Initialize database
    python3 -c "
from database import NewsDatabase
import sys

try:
    db = NewsDatabase('${DB_PATH:-news_bot.db}')
    print('Database initialized successfully')
    
    # Run health check
    health = db.get_system_health()
    if health.get('health_score', 0) > 0.8:
        print('Database health check passed')
    else:
        print('Database health check warning')
        
except Exception as e:
    print(f'Database setup failed: {e}')
    sys.exit(1)
"
    
    print_success "Database setup completed"
}

# =============================================================================
# Directory Structure
# =============================================================================

create_directories() {
    print_step "Creating directory structure..."
    
    DIRECTORIES=(
        "logs"
        "backups"
        "static"
        "templates"
        "tmp"
    )
    
    for dir in "${DIRECTORIES[@]}"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            if [[ "$VERBOSE" == true ]]; then
                print_info "Created directory: $dir"
            fi
        fi
    done
    
    print_success "Directory structure created"
}

# =============================================================================
# Production Setup
# =============================================================================

setup_production() {
    if [[ "$PRODUCTION_MODE" != true ]]; then
        return
    fi
    
    print_step "Configuring production environment..."
    
    # Update .env for production
    if [[ -f ".env" ]]; then
        sed -i.bak 's/FLASK_ENV=development/FLASK_ENV=production/' .env
        sed -i.bak 's/DEBUG_MODE=true/DEBUG_MODE=false/' .env
        sed -i.bak 's/HTTPS_ENABLED=false/HTTPS_ENABLED=true/' .env
        print_success "Production configuration applied"
    fi
    
    # Set proper file permissions
    chmod 600 .env 2>/dev/null || true
    chmod +x setup.sh run_all.py 2>/dev/null || true
    
    print_success "Production security settings applied"
    
    print_warning "Production mode enabled. Remember to:"
    print_info "  1. Configure HTTPS/SSL certificates"
    print_info "  2. Set up proper firewall rules"
    print_info "  3. Configure log rotation"
    print_info "  4. Set up monitoring and alerts"
}

# =============================================================================
# Docker Setup
# =============================================================================

setup_docker() {
    if [[ "$DOCKER_MODE" != true ]]; then
        return
    fi
    
    print_step "Setting up Docker configuration..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        print_info "Please install Docker first: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    # Create Dockerfile if it doesn't exist
    if [[ ! -f "Dockerfile" ]]; then
        cat > Dockerfile << 'EOF'
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5001

CMD ["python", "run_all.py"]
EOF
        print_success "Dockerfile created"
    fi
    
    # Create docker-compose.yml if it doesn't exist
    if [[ ! -f "docker-compose.yml" ]]; then
        cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  diatoms-ai:
    build: .
    ports:
      - "5001:5001"
    environment:
      - FLASK_ENV=production
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
    env_file:
      - .env
EOF
        print_success "docker-compose.yml created"
    fi
    
    print_success "Docker configuration completed"
}

# =============================================================================
# Testing and Validation
# =============================================================================

run_tests() {
    print_step "Running system tests..."
    
    # Test imports
    python3 -c "
import main
import web_app
import database
import run_all
print('All modules import successfully')
"
    
    # Test database operations
    python3 -c "
from database import NewsDatabase
db = NewsDatabase(':memory:')  # Use in-memory database for testing
print('Database operations test passed')
"
    
    # Test configuration loading
    python3 -c "
from main import Config
config = Config.from_env()
print('Configuration loading test passed')
"
    
    print_success "System tests completed successfully"
}

# =============================================================================
# Final Setup and Instructions
# =============================================================================

show_completion_message() {
    print_separator
    echo -e "${GREEN}🎉 Setup completed successfully!${NC}"
    print_separator
    echo ""
    echo -e "${CYAN}📝 Next Steps:${NC}"
    echo ""
    
    if ! validate_configuration > /dev/null 2>&1; then
        echo -e "${YELLOW}1. Configure your API keys:${NC}"
        echo "   Edit .env file with your actual API keys"
        echo "   - NewsAPI: https://newsapi.org/"
        echo "   - OpenAI: https://platform.openai.com/"
        echo ""
        echo -e "${YELLOW}2. Set up notifications:${NC}"
        echo "   Configure at least one notification method in .env"
        echo ""
    fi
    
    echo -e "${CYAN}3. Start the system:${NC}"
    if [[ "$DOCKER_MODE" == true ]]; then
        echo "   docker-compose up -d"
    elif [[ -d "$VENV_NAME" ]]; then
        echo "   source $VENV_NAME/bin/activate"
        echo "   python run_all.py"
    else
        echo "   python run_all.py"
    fi
    echo ""
    
    echo -e "${CYAN}4. Access the dashboard:${NC}"
    echo "   http://localhost:5001"
    echo ""
    
    echo -e "${CYAN}📚 Documentation:${NC}"
    echo "   README.md - Complete documentation"
    echo "   config.example - All configuration options"
    echo ""
    
    echo -e "${CYAN}🔍 Monitoring:${NC}"
    echo "   Logs: tail -f bot.log"
    echo "   Health: curl http://localhost:5001/api/health"
    echo ""
    
    if [[ "$PRODUCTION_MODE" == true ]]; then
        echo -e "${YELLOW}⚠️  Production Mode Enabled${NC}"
        echo "   Remember to configure HTTPS and security settings"
        echo ""
    fi
    
    print_separator
    echo -e "${PURPLE}Thank you for using DiatomsAI News Intelligence System!${NC}"
    print_separator
}

# =============================================================================
# Error Handling
# =============================================================================

cleanup_on_error() {
    print_error "Setup failed. Cleaning up..."
    
    # Remove partially created virtual environment
    if [[ -d "$VENV_NAME" ]] && [[ ! -f "$VENV_NAME/.setup_complete" ]]; then
        rm -rf "$VENV_NAME"
        print_info "Removed incomplete virtual environment"
    fi
    
    exit 1
}

trap cleanup_on_error ERR

# =============================================================================
# Main Execution
# =============================================================================

main() {
    print_header
    
    # Parse command line arguments
    parse_arguments "$@"
    
    # Show configuration
    if [[ "$VERBOSE" == true ]]; then
        print_info "Setup Configuration:"
        print_info "  Production Mode: $PRODUCTION_MODE"
        print_info "  Docker Mode: $DOCKER_MODE"
        print_info "  Skip Dependencies: $SKIP_DEPS"
        print_info "  Verbose: $VERBOSE"
        print_separator
    fi
    
    # System checks
    check_operating_system
    check_python_version
    check_pip
    check_disk_space
    check_network_connectivity
    check_required_files
    
    # Environment setup
    create_directories
    create_virtual_environment
    install_dependencies
    
    # Configuration
    setup_configuration
    
    # Database setup
    setup_database
    
    # Mode-specific setup
    setup_production
    setup_docker
    
    # Testing
    run_tests
    
    # Mark virtual environment as complete
    if [[ -d "$VENV_NAME" ]]; then
        touch "$VENV_NAME/.setup_complete"
    fi
    
    # Completion
    show_completion_message
}

# =============================================================================
# Script Entry Point
# =============================================================================

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 
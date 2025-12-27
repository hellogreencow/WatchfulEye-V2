# 🚀 WatchfulEye Production Infrastructure - Next Steps

**Goal**: Transform from tmux-based deployment to production-grade infrastructure ready for 700k launch

**Total Time**: ~12-14 hours (spread over 3 days)
**Status**: Pre-execution planning phase
**Last Updated**: October 10, 2025

---

## 📋 PRE-FLIGHT CHECKLIST

Before starting, verify:
- [ ] Current system is accessible via SSH
- [ ] Root access available
- [ ] Git installed (`git --version`)
- [ ] Python 3.8+ installed (`python3 --version`)
- [ ] Node.js installed (`node --version`)
- [ ] Current backups exist (`ls -lh news_bot.db`)
- [ ] .env file configured with all API keys
- [ ] tmux sessions running: `tmux ls`

**Current Architecture:**
```
Session 1: ./run_complete.sh prod (backend + frontend + bot)
Session 2: python3 webapp.py (redundant?)
Bot: PID 1084469 (running since Sept 6)
Database: /opt/watchfuleye2/news_bot.db (87MB, 63,157 articles)
```

---

# PHASE 1: SYSTEMD SERVICES MIGRATION (2-3 hours)

## Step 1.1: Backup Current State (15 min)

### Create backup directory
```bash
cd /opt/watchfuleye2
mkdir -p backups/manual
mkdir -p backups/auto
mkdir -p scripts
```

### Backup database
```bash
timestamp=$(date +%Y%m%d_%H%M%S)
cp news_bot.db backups/manual/news_bot_${timestamp}.db
```

**Verify backup:**
```bash
ls -lh backups/manual/
sqlite3 backups/manual/news_bot_${timestamp}.db "SELECT COUNT(*) FROM articles;"
# Expected: 63157 or similar
```

### Backup current configuration
```bash
cp .env backups/manual/.env_${timestamp}
tar -czf backups/manual/watchfuleye_config_${timestamp}.tar.gz \
    .env \
    *.py \
    *.sh \
    *.md \
    requirements.txt
```

**Checkpoint**: Verify backups exist and are not zero-size

---

## Step 1.2: Document Current Process State (10 min)

### Check what's actually running
```bash
# List all WatchfulEye processes
ps aux | grep -E "watchful|main.py|web_app.py|node.*serve|react" | grep -v grep > process_snapshot.txt
cat process_snapshot.txt
```

### Check tmux sessions
```bash
tmux ls
# Note the session names and when they were created
```

### Check listening ports
```bash
ss -tlnp | grep -E ":3000|:5002|:5003"
# Expected:
# - 3000: Frontend (node/serve)
# - 5002: Backend (Python/Flask)
# - 5003: Optional (Ollama API if running)
```

### Save current environment
```bash
env | grep -E "OPENAI|OPENROUTER|TELEGRAM|NEWSAPI|VOYAGE|PERSPECTIVES" > backups/manual/env_vars_${timestamp}.txt
```

**Checkpoint**: You should see:
- Bot process (PID 1084469 or new)
- Backend process on port 5002
- Frontend process on port 3000

---

## Step 1.3: Create Systemd Service Files (30 min)

### Service 1: WatchfulEye Bot
```bash
cat > /etc/systemd/system/watchfuleye-bot.service << 'EOF'
[Unit]
Description=WatchfulEye News Collection Bot
Documentation=https://github.com/your-repo/watchfuleye
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/watchfuleye2

# Environment
Environment="PATH=/opt/watchfuleye2/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
EnvironmentFile=/opt/watchfuleye2/.env

# Execution
ExecStart=/opt/watchfuleye2/venv/bin/python3 /opt/watchfuleye2/main.py
ExecReload=/bin/kill -HUP $MAINPID

# Restart policy
Restart=always
RestartSec=10
StartLimitIntervalSec=300
StartLimitBurst=5

# Resource limits
MemoryMax=1G
MemoryHigh=800M
CPUQuota=150%

# Logging
StandardOutput=append:/opt/watchfuleye2/logs/bot.log
StandardError=append:/opt/watchfuleye2/logs/bot_error.log
SyslogIdentifier=watchfuleye-bot

# Watchdog (detect hung processes)
WatchdogSec=300

# Hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
```

**Verify file created:**
```bash
cat /etc/systemd/system/watchfuleye-bot.service
ls -lh /etc/systemd/system/watchfuleye-bot.service
```

---

### Service 2: WatchfulEye Backend (Gunicorn)
```bash
cat > /etc/systemd/system/watchfuleye-backend.service << 'EOF'
[Unit]
Description=WatchfulEye Backend API (Gunicorn)
Documentation=https://github.com/your-repo/watchfuleye
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
User=root
Group=root
WorkingDirectory=/opt/watchfuleye2

# Environment
Environment="PATH=/opt/watchfuleye2/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="FLASK_APP=web_app.py"
EnvironmentFile=/opt/watchfuleye2/.env

# Gunicorn execution
ExecStart=/opt/watchfuleye2/venv/bin/gunicorn \
    --bind 0.0.0.0:5002 \
    --workers 4 \
    --threads 2 \
    --worker-class sync \
    --timeout 120 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile /opt/watchfuleye2/logs/backend_access.log \
    --error-logfile /opt/watchfuleye2/logs/backend_error.log \
    --log-level info \
    --preload \
    web_app:app

ExecReload=/bin/kill -HUP $MAINPID

# Restart policy
Restart=always
RestartSec=10
StartLimitIntervalSec=300
StartLimitBurst=5

# Resource limits
MemoryMax=2G
MemoryHigh=1.5G
CPUQuota=200%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=watchfuleye-backend

# Watchdog
WatchdogSec=60

# Hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
```

**Verify:**
```bash
cat /etc/systemd/system/watchfuleye-backend.service
```

---

### Service 3: WatchfulEye Frontend
```bash
cat > /etc/systemd/system/watchfuleye-frontend.service << 'EOF'
[Unit]
Description=WatchfulEye React Frontend
Documentation=https://github.com/your-repo/watchfuleye
After=network-online.target watchfuleye-backend.service
Wants=network-online.target
Requires=watchfuleye-backend.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/watchfuleye2/frontend/build

# Execution - using npx serve
ExecStart=/usr/local/bin/npx serve -s . -l 3000 --no-port-switching

# Restart policy
Restart=always
RestartSec=10
StartLimitIntervalSec=300
StartLimitBurst=5

# Resource limits
MemoryMax=512M
MemoryHigh=400M

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=watchfuleye-frontend

# Hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
```

**Verify:**
```bash
cat /etc/systemd/system/watchfuleye-frontend.service
```

---

### Service 4: Health Monitor
```bash
cat > /opt/watchfuleye2/scripts/health_monitor.py << 'PYEOF'
#!/usr/bin/env python3
"""
WatchfulEye Health Monitor
Checks system health and sends alerts if issues detected
"""
import requests
import os
import sys
import time
import json
from datetime import datetime, timedelta
import logging
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/opt/watchfuleye2/logs/health_monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment
from dotenv import load_dotenv
load_dotenv('/opt/watchfuleye2/.env')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
EMAIL_FROM = os.getenv('EMAIL_FROM')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_TO = os.getenv('EMAIL_TO')

def check_backend_health():
    """Check if backend API is responding"""
    try:
        response = requests.get('http://localhost:5002/api/health', timeout=10)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Backend healthy: {data.get('status', 'unknown')}")
            return True, "Backend API responding normally"
        else:
            return False, f"Backend returned status {response.status_code}"
    except Exception as e:
        return False, f"Backend check failed: {str(e)}"

def check_frontend_health():
    """Check if frontend is serving"""
    try:
        response = requests.get('http://localhost:3000', timeout=10)
        if response.status_code == 200:
            logger.info("Frontend healthy")
            return True, "Frontend responding normally"
        else:
            return False, f"Frontend returned status {response.status_code}"
    except Exception as e:
        return False, f"Frontend check failed: {str(e)}"

def check_bot_activity():
    """Check if bot has updated log recently"""
    try:
        bot_log = Path('/opt/watchfuleye2/logs/bot.log')
        if not bot_log.exists():
            return False, "Bot log file not found"

        mtime = datetime.fromtimestamp(bot_log.stat().st_mtime)
        age = datetime.now() - mtime

        # Bot should update at least every 4.5 hours (4hr cycle + 30min grace)
        if age < timedelta(hours=4.5):
            logger.info(f"Bot active (last update {age.total_seconds()/3600:.1f}h ago)")
            return True, f"Bot last active {age.total_seconds()/60:.0f} minutes ago"
        else:
            return False, f"Bot inactive for {age.total_seconds()/3600:.1f} hours"
    except Exception as e:
        return False, f"Bot check failed: {str(e)}"

def check_database():
    """Check database integrity"""
    try:
        import sqlite3
        conn = sqlite3.connect('/opt/watchfuleye2/news_bot.db')
        cursor = conn.cursor()

        # Integrity check
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        if result != 'ok':
            return False, f"Database integrity check failed: {result}"

        # Check article count
        cursor.execute("SELECT COUNT(*) FROM articles")
        count = cursor.fetchone()[0]
        logger.info(f"Database healthy: {count} articles")

        conn.close()
        return True, f"Database OK ({count} articles)"
    except Exception as e:
        return False, f"Database check failed: {str(e)}"

def send_telegram_alert(message):
    """Send alert via Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured")
        return False

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': f"🚨 WATCHFULEYE ALERT\n\n{message}",
            'parse_mode': 'Markdown'
        }
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Telegram alert failed: {e}")
        return False

def send_email_alert(message):
    """Send alert via email"""
    if not EMAIL_FROM or not EMAIL_PASSWORD or not EMAIL_TO:
        logger.warning("Email not configured")
        return False

    try:
        msg = MIMEText(message)
        msg['Subject'] = '🚨 WatchfulEye System Alert'
        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_TO

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"Email alert failed: {e}")
        return False

def main():
    """Run all health checks"""
    logger.info("=" * 50)
    logger.info("Starting health check cycle")

    issues = []

    # Run all checks
    checks = [
        ("Backend API", check_backend_health),
        ("Frontend", check_frontend_health),
        ("Bot Activity", check_bot_activity),
        ("Database", check_database)
    ]

    for name, check_func in checks:
        healthy, message = check_func()
        if not healthy:
            issues.append(f"❌ {name}: {message}")
            logger.error(f"{name} check FAILED: {message}")
        else:
            logger.info(f"{name} check PASSED: {message}")

    # Send alerts if issues found
    if issues:
        alert_message = "WatchfulEye system issues detected:\n\n" + "\n".join(issues)
        alert_message += f"\n\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        logger.error(f"SENDING ALERTS: {len(issues)} issues")
        send_telegram_alert(alert_message)
        send_email_alert(alert_message)
    else:
        logger.info("All checks passed ✅")

    logger.info("Health check cycle complete")
    logger.info("=" * 50)

if __name__ == '__main__':
    while True:
        try:
            main()
            time.sleep(300)  # Check every 5 minutes
        except KeyboardInterrupt:
            logger.info("Health monitor stopped by user")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Health monitor error: {e}")
            time.sleep(60)
PYEOF

chmod +x /opt/watchfuleye2/scripts/health_monitor.py
```

**Create health monitor service:**
```bash
cat > /etc/systemd/system/watchfuleye-monitor.service << 'EOF'
[Unit]
Description=WatchfulEye Health Monitor
Documentation=https://github.com/your-repo/watchfuleye
After=network-online.target watchfuleye-backend.service watchfuleye-bot.service
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/watchfuleye2

Environment="PATH=/opt/watchfuleye2/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

ExecStart=/opt/watchfuleye2/venv/bin/python3 /opt/watchfuleye2/scripts/health_monitor.py

Restart=always
RestartSec=30

StandardOutput=journal
StandardError=journal
SyslogIdentifier=watchfuleye-monitor

[Install]
WantedBy=multi-user.target
EOF
```

---

### Service 5: Automated Backup (Timer + Service)

**Create backup script:**
```bash
cat > /opt/watchfuleye2/scripts/backup.sh << 'BASHEOF'
#!/bin/bash
set -e

BACKUP_DIR="/opt/watchfuleye2/backups/auto"
DB_PATH="/opt/watchfuleye2/news_bot.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/news_bot_${TIMESTAMP}.db"
LOG_FILE="/opt/watchfuleye2/logs/backup.log"

echo "[$(date)] Starting backup..." | tee -a "$LOG_FILE"

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo "[$(date)] ERROR: Database not found at $DB_PATH" | tee -a "$LOG_FILE"
    exit 1
fi

# Create backup directory if needed
mkdir -p "$BACKUP_DIR"

# Copy database
cp "$DB_PATH" "$BACKUP_FILE"

# Verify backup integrity
sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" > /tmp/backup_check.txt 2>&1
if grep -q "ok" /tmp/backup_check.txt; then
    echo "[$(date)] Backup created successfully: $BACKUP_FILE" | tee -a "$LOG_FILE"

    # Get size
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[$(date)] Backup size: $SIZE" | tee -a "$LOG_FILE"

    # Count articles
    ARTICLES=$(sqlite3 "$BACKUP_FILE" "SELECT COUNT(*) FROM articles;")
    echo "[$(date)] Articles in backup: $ARTICLES" | tee -a "$LOG_FILE"

    # Compress backups older than 24 hours
    find "$BACKUP_DIR" -name "*.db" -type f -mtime +1 -not -name "*.gz" -exec gzip {} \;
    echo "[$(date)] Compressed old backups" | tee -a "$LOG_FILE"

    # Delete backups older than 7 days
    find "$BACKUP_DIR" -name "*.db.gz" -type f -mtime +7 -delete
    echo "[$(date)] Cleaned up old backups (>7 days)" | tee -a "$LOG_FILE"

    echo "[$(date)] Backup completed successfully ✅" | tee -a "$LOG_FILE"
    exit 0
else
    echo "[$(date)] ERROR: Backup integrity check failed!" | tee -a "$LOG_FILE"
    cat /tmp/backup_check.txt | tee -a "$LOG_FILE"
    rm "$BACKUP_FILE"
    exit 1
fi
BASHEOF

chmod +x /opt/watchfuleye2/scripts/backup.sh
```

**Create backup service:**
```bash
cat > /etc/systemd/system/watchfuleye-backup.service << 'EOF'
[Unit]
Description=WatchfulEye Database Backup
Documentation=https://github.com/your-repo/watchfuleye

[Service]
Type=oneshot
User=root
Group=root
WorkingDirectory=/opt/watchfuleye2

ExecStart=/opt/watchfuleye2/scripts/backup.sh

StandardOutput=journal
StandardError=journal
SyslogIdentifier=watchfuleye-backup

[Install]
WantedBy=multi-user.target
EOF
```

**Create backup timer (runs every 6 hours):**
```bash
cat > /etc/systemd/system/watchfuleye-backup.timer << 'EOF'
[Unit]
Description=WatchfulEye Backup Timer (every 6 hours)
Documentation=https://github.com/your-repo/watchfuleye

[Timer]
OnBootSec=10min
OnUnitActiveSec=6h
Persistent=true

[Install]
WantedBy=timers.target
EOF
```

**Verify all service files:**
```bash
ls -lh /etc/systemd/system/watchfuleye-*
```

**Expected output:**
```
-rw-r--r-- 1 root root ... watchfuleye-backend.service
-rw-r--r-- 1 root root ... watchfuleye-backup.service
-rw-r--r-- 1 root root ... watchfuleye-backup.timer
-rw-r--r-- 1 root root ... watchfuleye-bot.service
-rw-r--r-- 1 root root ... watchfuleye-frontend.service
-rw-r--r-- 1 root root ... watchfuleye-monitor.service
```

---

## Step 1.4: Create Log Directory (5 min)

```bash
mkdir -p /opt/watchfuleye2/logs
touch /opt/watchfuleye2/logs/bot.log
touch /opt/watchfuleye2/logs/bot_error.log
touch /opt/watchfuleye2/logs/backend_access.log
touch /opt/watchfuleye2/logs/backend_error.log
touch /opt/watchfuleye2/logs/health_monitor.log
touch /opt/watchfuleye2/logs/backup.log

chmod 644 /opt/watchfuleye2/logs/*.log
```

**Verify:**
```bash
ls -lh /opt/watchfuleye2/logs/
```

---

## Step 1.5: Install Gunicorn (5 min)

```bash
cd /opt/watchfuleye2
source venv/bin/activate
pip install gunicorn
pip freeze | grep gunicorn
```

**Expected output:**
```
gunicorn==21.2.0
```

---

## Step 1.6: Stop Current tmux Processes (10 min)

**IMPORTANT: This is the transition point. After this, you're on systemd.**

### List current tmux sessions
```bash
tmux ls
```

### Attach to first session and document what's running
```bash
tmux attach -t 0  # or whatever session name
# Press Ctrl+B, then D to detach without killing
```

### Stop all tmux sessions gracefully
```bash
# First, note which processes are running
ps aux | grep -E "main.py|web_app.py|node.*serve" | grep -v grep

# Kill the old bot process (PID 1084469 or current)
pkill -f "python3 main.py"

# Kill any other Python web processes
pkill -f "python3 web_app.py"
pkill -f "python web_app.py"

# Kill node/serve processes
pkill -f "serve.*3000"

# Kill all tmux sessions
tmux kill-server
```

**Verify everything stopped:**
```bash
ps aux | grep -E "main.py|web_app.py|serve" | grep -v grep
# Should return nothing

ss -tlnp | grep -E ":3000|:5002"
# Should return nothing
```

**Checkpoint**: Nothing should be running on ports 3000 or 5002

---

## Step 1.7: Enable and Start Systemd Services (15 min)

### Reload systemd
```bash
systemctl daemon-reload
```

### Enable all services (start on boot)
```bash
systemctl enable watchfuleye-bot.service
systemctl enable watchfuleye-backend.service
systemctl enable watchfuleye-frontend.service
systemctl enable watchfuleye-monitor.service
systemctl enable watchfuleye-backup.service
systemctl enable watchfuleye-backup.timer
```

**Verify enabled:**
```bash
systemctl list-unit-files | grep watchfuleye
```

**Expected output:**
```
watchfuleye-backend.service    enabled
watchfuleye-backup.service     enabled
watchfuleye-backup.timer       enabled
watchfuleye-bot.service        enabled
watchfuleye-frontend.service   enabled
watchfuleye-monitor.service    enabled
```

### Start services in order
```bash
# Start backend first (frontend depends on it)
systemctl start watchfuleye-backend.service
sleep 5

# Check backend started
systemctl status watchfuleye-backend.service
# Should show "active (running)"

# Start frontend
systemctl start watchfuleye-frontend.service
sleep 5

# Check frontend started
systemctl status watchfuleye-frontend.service

# Start bot
systemctl start watchfuleye-bot.service
sleep 5

# Check bot started
systemctl status watchfuleye-bot.service

# Start monitor
systemctl start watchfuleye-monitor.service

# Start backup timer
systemctl start watchfuleye-backup.timer
```

### Verify all services running
```bash
systemctl status watchfuleye-*
```

**Alternative: Check all at once:**
```bash
for service in watchfuleye-{backend,frontend,bot,monitor}.service watchfuleye-backup.timer; do
    echo "=== $service ==="
    systemctl is-active $service
done
```

**Expected output:**
```
=== watchfuleye-backend.service ===
active
=== watchfuleye-frontend.service ===
active
=== watchfuleye-bot.service ===
active
=== watchfuleye-monitor.service ===
active
=== watchfuleye-backup.timer ===
active
```

---

## Step 1.8: Verify Services Working (15 min)

### Check if ports are listening
```bash
ss -tlnp | grep -E ":3000|:5002"
```

**Expected output:**
```
LISTEN 0  128  0.0.0.0:3000  0.0.0.0:*  users:(("node",pid=...))
LISTEN 0  128  0.0.0.0:5002  0.0.0.0:*  users:(("gunicorn",pid=...))
```

### Test backend health
```bash
curl -s http://localhost:5002/api/health | jq
```

**Expected output:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-10T...",
  "database": {
    "health_score": 1.0,
    "size_mb": 87.0
  },
  "response_time_ms": 4.5
}
```

### Test frontend
```bash
curl -s http://localhost:3000 | head -20
```

**Should see HTML:**
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>WatchfulEye...</title>
```

### Test external access (if domain configured)
```bash
curl -s https://watchfuleye.us/api/health | jq
```

### Check logs
```bash
# Backend logs
tail -50 /opt/watchfuleye2/logs/backend_access.log

# Bot logs
tail -50 /opt/watchfuleye2/logs/bot.log

# Health monitor logs
tail -50 /opt/watchfuleye2/logs/health_monitor.log

# System journal
journalctl -u watchfuleye-backend -n 50
journalctl -u watchfuleye-bot -n 50
```

---

## Step 1.9: Test Auto-Restart (15 min)

**This is critical - verify services restart automatically when killed.**

### Test backend restart
```bash
# Get PID
systemctl status watchfuleye-backend.service | grep "Main PID"

# Kill process with -9 (simulates crash)
PID=$(systemctl show -p MainPID --value watchfuleye-backend.service)
kill -9 $PID

# Wait 15 seconds
sleep 15

# Check if restarted
systemctl status watchfuleye-backend.service
# Should show "active (running)" with NEW PID

# Verify API still works
curl -s http://localhost:5002/api/health
```

### Test bot restart
```bash
PID=$(systemctl show -p MainPID --value watchfuleye-bot.service)
kill -9 $PID
sleep 15
systemctl status watchfuleye-bot.service
# Should be active again
```

### Test frontend restart
```bash
PID=$(systemctl show -p MainPID --value watchfuleye-frontend.service)
kill -9 $PID
sleep 15
systemctl status watchfuleye-frontend.service
curl -s http://localhost:3000 | head -5
```

**Checkpoint**: All services should auto-restart within 10-15 seconds

---

## Step 1.10: Test Backup System (10 min)

### Trigger backup manually
```bash
systemctl start watchfuleye-backup.service
```

### Check backup status
```bash
systemctl status watchfuleye-backup.service
```

### Verify backup created
```bash
ls -lh /opt/watchfuleye2/backups/auto/
```

**Should see:**
```
-rw-r--r-- 1 root root 87M Oct 10 18:30 news_bot_20251010_183045.db
```

### Check backup log
```bash
cat /opt/watchfuleye2/logs/backup.log
```

**Should show:**
```
[2025-10-10 18:30:45] Starting backup...
[2025-10-10 18:30:47] Backup created successfully: ...
[2025-10-10 18:30:47] Backup size: 87M
[2025-10-10 18:30:48] Articles in backup: 63157
[2025-10-10 18:30:48] Backup completed successfully ✅
```

### Verify backup timer
```bash
systemctl list-timers | grep watchfuleye
```

**Should show next run time:**
```
Fri 2025-10-11 00:30:00 UTC  6h left  ...  watchfuleye-backup.timer
```

---

## PHASE 1 COMPLETION CHECKLIST

- [ ] All 6 service files created in /etc/systemd/system/
- [ ] All services enabled (start on boot)
- [ ] All services currently running
- [ ] Backend responds on port 5002
- [ ] Frontend responds on port 3000
- [ ] API health check returns healthy
- [ ] Services auto-restart when killed
- [ ] Backup system tested and working
- [ ] Logs being written to /opt/watchfuleye2/logs/
- [ ] No tmux sessions running
- [ ] Old bot process (PID 1084469) killed

**Validation command:**
```bash
echo "=== SERVICE STATUS ==="
systemctl is-active watchfuleye-{backend,frontend,bot,monitor}.service watchfuleye-backup.timer

echo -e "\n=== PORTS LISTENING ==="
ss -tlnp | grep -E ":3000|:5002"

echo -e "\n=== API HEALTH ==="
curl -s http://localhost:5002/api/health | jq -r '.status'

echo -e "\n=== LATEST BACKUP ==="
ls -lht /opt/watchfuleye2/backups/auto/ | head -2
```

**If all checks pass, proceed to Phase 2.**

---

# PHASE 2: MONITORING & ALERTING (1-2 hours)

## Step 2.1: Set Up UptimeRobot (30 min)

### Create account
1. Go to https://uptimerobot.com/
2. Sign up for FREE account (50 monitors included)
3. Verify email

### Add monitors
1. Click "Add New Monitor"

**Monitor 1: Frontend**
- Monitor Type: HTTP(s)
- Friendly Name: WatchfulEye Frontend
- URL: https://watchfuleye.us (or http://your-ip:3000)
- Monitoring Interval: 5 minutes
- Monitor Timeout: 30 seconds
- Alert Contacts: Your email

**Monitor 2: Backend API**
- Monitor Type: HTTP(s)
- Friendly Name: WatchfulEye API Health
- URL: https://watchfuleye.us/api/health (or http://your-ip:5002/api/health)
- Monitoring Interval: 5 minutes
- Keyword: "healthy" (alerts if this word not found in response)
- Alert Contacts: Your email + SMS if available

**Monitor 3: Bot Log Activity**
- Monitor Type: Port
- Friendly Name: WatchfulEye Server SSH
- IP/Host: your-server-ip
- Port: 22
- Monitoring Interval: 5 minutes

### Configure alerts
1. Go to My Settings → Alert Contacts
2. Add Email (free)
3. Add SMS (if premium) or Telegram/Discord webhook
4. Set alert preferences:
   - ✅ Email immediately when down
   - ✅ Email when back up
   - ⬜ Email for SSL expiration (7 days before)

### Test monitors
1. Stop backend: `systemctl stop watchfuleye-backend`
2. Wait 5-10 minutes
3. Check if you received alert email
4. Start backend: `systemctl start watchfuleye-backend`
5. Check if you received "back up" email

**Checkpoint**: You should receive alerts when services go down

---

## Step 2.2: Configure Internal Health Monitor (already done in Step 1.4)

The health monitor service is already running. Verify it's working:

```bash
# Check service status
systemctl status watchfuleye-monitor.service

# View recent logs
journalctl -u watchfuleye-monitor -n 100 --no-pager

# Or check log file
tail -100 /opt/watchfuleye2/logs/health_monitor.log
```

**Expected log output:**
```
2025-10-10 18:45:00 - INFO - Starting health check cycle
2025-10-10 18:45:01 - INFO - Backend API check PASSED
2025-10-10 18:45:02 - INFO - Frontend check PASSED
2025-10-10 18:45:03 - INFO - Bot Activity check PASSED
2025-10-10 18:45:04 - INFO - Database check PASSED
2025-10-10 18:45:04 - INFO - All checks passed ✅
```

### Test alert system
```bash
# Stop backend to trigger alert
systemctl stop watchfuleye-backend

# Wait 5 minutes, then check logs
tail -50 /opt/watchfuleye2/logs/health_monitor.log

# Should see alert sent
# 2025-10-10 18:50:00 - ERROR - Backend API check FAILED
# 2025-10-10 18:50:01 - ERROR - SENDING ALERTS: 1 issues

# Check Telegram for alert message
# Check email for alert

# Restart backend
systemctl start watchfuleye-backend
```

---

## Step 2.3: Set Up Discord Webhook (Optional, 15 min)

### Create webhook
1. Open Discord
2. Go to Server Settings → Integrations → Webhooks
3. Click "New Webhook"
4. Name: WatchfulEye Alerts
5. Channel: #watchfuleye-alerts (or create it)
6. Copy webhook URL

### Add to .env
```bash
echo 'DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your-webhook-url' >> /opt/watchfuleye2/.env
```

### Test Discord alerts
Create test script:
```bash
cat > /opt/watchfuleye2/scripts/test_discord_alert.py << 'PYEOF'
import requests
import os
from dotenv import load_dotenv

load_dotenv('/opt/watchfuleye2/.env')

webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
if not webhook_url:
    print("No Discord webhook configured")
    exit(1)

message = {
    "content": "🚨 **TEST ALERT**\n\nWatchfulEye monitoring system test\n\nIf you see this, alerts are working! ✅"
}

response = requests.post(webhook_url, json=message)
if response.status_code == 204:
    print("✅ Discord alert sent successfully")
else:
    print(f"❌ Failed: {response.status_code}")
PYEOF

python3 /opt/watchfuleye2/scripts/test_discord_alert.py
```

---

## Step 2.4: Create Monitoring Dashboard Script (20 min)

```bash
cat > /opt/watchfuleye2/scripts/status_dashboard.sh << 'BASHEOF'
#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "════════════════════════════════════════════════════════"
echo "          WATCHFULEYE STATUS DASHBOARD"
echo "          $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "════════════════════════════════════════════════════════"

# Service Status
echo -e "\n📊 SERVICE STATUS"
echo "─────────────────────────────────────────────────────────"
for service in watchfuleye-{backend,frontend,bot,monitor}.service watchfuleye-backup.timer; do
    if systemctl is-active --quiet $service; then
        echo -e "${GREEN}✓${NC} $service"
    else
        echo -e "${RED}✗${NC} $service"
    fi
done

# Port Status
echo -e "\n🔌 PORT STATUS"
echo "─────────────────────────────────────────────────────────"
if ss -tlnp | grep -q ":5002"; then
    echo -e "${GREEN}✓${NC} Backend API (5002)"
else
    echo -e "${RED}✗${NC} Backend API (5002)"
fi

if ss -tlnp | grep -q ":3000"; then
    echo -e "${GREEN}✓${NC} Frontend (3000)"
else
    echo -e "${RED}✗${NC} Frontend (3000)"
fi

# API Health
echo -e "\n🏥 API HEALTH CHECK"
echo "─────────────────────────────────────────────────────────"
HEALTH=$(curl -s http://localhost:5002/api/health 2>/dev/null)
if echo "$HEALTH" | grep -q "healthy"; then
    echo -e "${GREEN}✓${NC} Backend API responding"
    echo "$HEALTH" | jq -r '.status, .database.health_score' 2>/dev/null | sed 's/^/  /'
else
    echo -e "${RED}✗${NC} Backend API not responding"
fi

# Database Stats
echo -e "\n💾 DATABASE STATUS"
echo "─────────────────────────────────────────────────────────"
if [ -f /opt/watchfuleye2/news_bot.db ]; then
    SIZE=$(du -h /opt/watchfuleye2/news_bot.db | cut -f1)
    ARTICLES=$(sqlite3 /opt/watchfuleye2/news_bot.db "SELECT COUNT(*) FROM articles" 2>/dev/null || echo "ERROR")
    CONVERSATIONS=$(sqlite3 /opt/watchfuleye2/news_bot.db "SELECT COUNT(*) FROM conversations" 2>/dev/null || echo "ERROR")
    echo "  Size: $SIZE"
    echo "  Articles: $ARTICLES"
    echo "  Conversations: $CONVERSATIONS"
else
    echo -e "${RED}✗${NC} Database file not found"
fi

# Recent Backups
echo -e "\n💼 BACKUP STATUS"
echo "─────────────────────────────────────────────────────────"
LATEST_BACKUP=$(ls -t /opt/watchfuleye2/backups/auto/*.db 2>/dev/null | head -1)
if [ -n "$LATEST_BACKUP" ]; then
    echo -e "${GREEN}✓${NC} Latest: $(basename $LATEST_BACKUP)"
    echo "  Size: $(du -h $LATEST_BACKUP | cut -f1)"
    echo "  Age: $(stat -c %y $LATEST_BACKUP | cut -d' ' -f1-2)"
else
    echo -e "${YELLOW}⚠${NC} No backups found"
fi

# System Resources
echo -e "\n⚙️  SYSTEM RESOURCES"
echo "─────────────────────────────────────────────────────────"
CPU=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
MEM=$(free -m | awk 'NR==2{printf "%.1f%%", $3*100/$2 }')
DISK=$(df -h /opt/watchfuleye2 | awk 'NR==2{print $5}')

echo "  CPU Usage: $CPU%"
echo "  Memory Usage: $MEM"
echo "  Disk Usage: $DISK"

# Recent Errors
echo -e "\n🚨 RECENT ERRORS (last hour)"
echo "─────────────────────────────────────────────────────────"
ERROR_COUNT=$(journalctl --since "1 hour ago" -p err --no-pager | grep -c watchfuleye || echo "0")
if [ "$ERROR_COUNT" -gt 0 ]; then
    echo -e "${RED}⚠${NC} $ERROR_COUNT errors in last hour"
    journalctl --since "1 hour ago" -p err --no-pager | grep watchfuleye | tail -5
else
    echo -e "${GREEN}✓${NC} No errors in last hour"
fi

echo "════════════════════════════════════════════════════════"
BASHEOF

chmod +x /opt/watchfuleye2/scripts/status_dashboard.sh
```

**Test dashboard:**
```bash
/opt/watchfuleye2/scripts/status_dashboard.sh
```

---

## PHASE 2 COMPLETION CHECKLIST

- [ ] UptimeRobot account created
- [ ] 2-3 monitors configured (Frontend, Backend, Server)
- [ ] Alert emails configured and tested
- [ ] Internal health monitor service running
- [ ] Health monitor successfully detects and alerts on failures
- [ ] Discord webhook configured (optional)
- [ ] Status dashboard script created
- [ ] All monitoring systems tested by intentionally stopping services

**Validation:**
```bash
# Run status dashboard
/opt/watchfuleye2/scripts/status_dashboard.sh

# All services should show ✓ green checkmarks
```

---

# PHASE 3: CHAT WEB-SEARCH FIX (1 hour)

## Step 3.1: Add Comprehensive Logging (15 min)

**Edit web_app.py to add detailed chat logging:**

```bash
cd /opt/watchfuleye2
cp web_app.py web_app.py.backup_$(date +%Y%m%d_%H%M%S)
```

Now we'll add logging at key points. Find these lines and add logging:

**Around line 3026 (chat stream endpoint):**
```python
# After parsing request data
logger.info(f"[CHAT] New request: query='{user_message[:100]}...', use_rag={use_rag}, use_search={data.get('use_search')}, angle={angle}, horizon={horizon}")
```

**Around line 3130 (semantic search):**
```python
# After semantic search
logger.info(f"[CHAT] Semantic search returned {len(semantic_ids)} article IDs")
```

**Around line 3233 (source filtering):**
```python
# After building sources list
logger.info(f"[CHAT] Retrieved {len(sources)} sources, mode={mode_label}, prompt_cap={prompt_source_cap}")
if sources:
    avg_sim = sum(s.get('similarity', 0.5) for s in sources) / len(sources)
    logger.info(f"[CHAT] Average similarity: {avg_sim:.3f}")
```

**Around line 3375 (model selection):**
```python
# After model selection
logger.info(f"[CHAT] Using model: {model_to_use}, use_search={data.get('use_search')}, sources={len(sources)}")
```

**Around line 3420 (response complete):**
```python
# After response generation
elapsed = time.time() - start_time  # Add start_time = time.time() at beginning of generate()
logger.info(f"[CHAT] Response complete: {len(full_response)} chars in {elapsed:.2f}s, coverage={coverage_ratio_local:.2f}")
```

---

## Step 3.2: Fix Hardcoded Metadata Bug (5 min)

**Find line ~3424 in web_app.py:**

**BEFORE (WRONG):**
```python
'use_rag': True,  # ← HARDCODED!
```

**AFTER (CORRECT):**
```python
'use_rag': use_rag,  # Use actual value from request
```

---

## Step 3.3: Improve RAG Filtering in Web-Search Mode (20 min)

**Find the section around line 3230-3270 where sources are built.**

**Add this filtering logic:**

```python
# Around line 3270, after sources list is built
if data.get('use_search') and sources:
    # In web-search mode, only keep high-confidence semantic results
    # Filter out low-relevance sources that pollute the context

    # Calculate similarity scores if not already present
    for source in sources:
        if 'similarity' not in source:
            source['similarity'] = 0.5  # default mid-range

    # Filter: only keep sources with similarity > 0.6
    sources_before = len(sources)
    sources = [s for s in sources if s.get('similarity', 1.0) > 0.6]

    # Sort by similarity descending
    sources.sort(key=lambda x: x.get('similarity', 0), reverse=True)

    # Cap to 10 best sources (was 24)
    sources = sources[:10]

    logger.info(f"[CHAT] Web-search mode: filtered {sources_before} → {len(sources)} sources (similarity > 0.6)")
```

**This ensures web-search mode only uses the most relevant sources, preventing garbage articles from polluting the AI's context.**

---

## Step 3.4: Verify Perplexity Model Configuration (10 min)

**Check .env file:**
```bash
grep "PERSPECTIVES_MODEL" /opt/watchfuleye2/.env
```

**If empty or not found, add it:**
```bash
echo 'PERSPECTIVES_MODEL=perplexity/sonar-pro' >> /opt/watchfuleye2/.env
```

**Or use a model you know works:**
```bash
# Alternatives:
# PERSPECTIVES_MODEL=perplexity/sonar
# PERSPECTIVES_MODEL=openai/gpt-4o-mini (fallback if Perplexity doesn't work)
```

---

## Step 3.5: Restart Backend and Test (10 min)

```bash
# Restart backend to load changes
systemctl restart watchfuleye-backend.service

# Wait for startup
sleep 10

# Check if started successfully
systemctl status watchfuleye-backend.service

# Test API health
curl -s http://localhost:5002/api/health | jq
```

**Test chat with logging:**

1. Open browser to https://watchfuleye.us
2. Start a chat
3. Toggle "Search Mode" ON
4. Ask: "What's the price of Bitcoin right now?"
5. Watch backend logs in real-time:

```bash
journalctl -u watchfuleye-backend -f | grep "\[CHAT\]"
```

**Expected log output:**
```
[CHAT] New request: query='What's the price of Bitcoin...', use_rag=True, use_search=True, angle=neutral, horizon=medium
[CHAT] Semantic search returned 156 article IDs
[CHAT] Retrieved 24 sources, mode=web, prompt_cap=10
[CHAT] Average similarity: 0.723
[CHAT] Web-search mode: filtered 24 → 8 sources (similarity > 0.6)
[CHAT] Using model: perplexity/sonar-pro, use_search=True, sources=8
[CHAT] Response complete: 847 chars in 3.42s, coverage=0.81
```

**This tells you EXACTLY what's happening:**
- RAG is pulling articles
- Similarity scores are good (>0.6)
- Web-search mode is active (using Perplexity)
- Sources are filtered down from 24 to 8 best matches
- Response is fast (3.42s)

---

## PHASE 3 COMPLETION CHECKLIST

- [ ] web_app.py backed up
- [ ] Comprehensive logging added at 5+ key points
- [ ] Hardcoded metadata bug fixed (line ~3424)
- [ ] Web-search mode source filtering implemented
- [ ] Perplexity model configured in .env
- [ ] Backend restarted successfully
- [ ] Chat tested with both RAG and web-search modes
- [ ] Logs show detailed information about each chat request
- [ ] No more "I don't have information" responses for basic queries

**Validation:**
```bash
# Test chat and check logs
tail -100 /opt/watchfuleye2/logs/backend_access.log | grep CHAT
journalctl -u watchfuleye-backend -n 100 | grep "\[CHAT\]"
```

---

# PHASE 4: PERFORMANCE OPTIMIZATION (1 hour)

## Step 4.1: SQLite Optimizations (15 min)

**Edit web_app.py database connection settings:**

Find where SQLite connections are created (around line 170-200) and add:

```python
# After: conn = sqlite3.connect(db_path)
# Add these PRAGMA statements:

conn.execute('PRAGMA journal_mode=WAL')  # Write-Ahead Logging (2-3x faster)
conn.execute('PRAGMA synchronous=NORMAL')  # Faster writes, still safe
conn.execute('PRAGMA cache_size=-64000')  # 64MB cache
conn.execute('PRAGMA temp_store=MEMORY')  # Temp tables in RAM
conn.execute('PRAGMA mmap_size=268435456')  # 256MB memory-mapped I/O
```

**Why this matters:**
- **WAL mode**: Allows concurrent reads while writing (crucial for high traffic)
- **cache_size**: Keeps frequently accessed data in memory
- **mmap_size**: Memory-mapped I/O is faster than traditional file I/O

---

## Step 4.2: Add Database Indexes (if missing) (15 min)

```bash
sqlite3 /opt/watchfuleye2/news_bot.db << 'SQLEOF'
-- Check existing indexes
.indexes articles

-- Add missing indexes for common queries
CREATE INDEX IF NOT EXISTS idx_articles_created_desc ON articles(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
CREATE INDEX IF NOT EXISTS idx_articles_sentiment ON articles(sentiment_score);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);

-- Conversation indexes
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, last_message_at DESC);

-- Optimize database
ANALYZE;
VACUUM;

-- Show index statistics
.stats on
.exit
SQLEOF
```

**Verify indexes created:**
```bash
sqlite3 /opt/watchfuleye2/news_bot.db ".indexes articles"
```

---

## Step 4.3: Configure Rate Limiting for Launch (10 min)

**Edit web_app.py rate limiting configuration:**

Find the Flask-Limiter configuration (around line 160-180):

**BEFORE:**
```python
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
```

**AFTER (adjusted for launch traffic):**
```python
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["1000 per day", "100 per hour"],
    storage_uri="memory://"
)
```

**Add endpoint-specific limits:**

Find the chat endpoint (around line 2700) and adjust:

```python
@app.route('/api/chat/conversations/<int:conversation_id>/messages/stream', methods=['POST'])
@limiter.limit("30 per hour")  # Chat is expensive, limit more strictly
def chat_stream(conversation_id):
    # ... existing code
```

---

## Step 4.4: Add Load Shedding Protection (15 min)

**Add before_request hook to shed load when server is overloaded:**

Add this near the top of web_app.py (after app initialization):

```python
import psutil

# Load shedding thresholds
CPU_THRESHOLD = 90  # Shed load if CPU > 90%
MEMORY_THRESHOLD = 85  # Shed load if memory > 85%

@app.before_request
def check_server_load():
    """
    Shed load if server is overloaded
    Returns 503 Service Unavailable with Retry-After header
    """
    # Skip health checks
    if request.path == '/api/health':
        return None

    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_percent = psutil.virtual_memory().percent

        if cpu_percent > CPU_THRESHOLD:
            logger.warning(f"Load shedding: CPU at {cpu_percent:.1f}%")
            return jsonify({
                'error': 'Server under high load',
                'message': 'Please retry in 60 seconds',
                'cpu_percent': cpu_percent
            }), 503, {'Retry-After': '60'}

        if memory_percent > MEMORY_THRESHOLD:
            logger.warning(f"Load shedding: Memory at {memory_percent:.1f}%")
            return jsonify({
                'error': 'Server under high load',
                'message': 'Please retry in 60 seconds',
                'memory_percent': memory_percent
            }), 503, {'Retry-After': '60'}

    except Exception as e:
        logger.error(f"Load check error: {e}")

    return None
```

---

## Step 4.5: Restart and Verify Optimizations (5 min)

```bash
# Restart backend
systemctl restart watchfuleye-backend.service

# Wait for startup
sleep 10

# Check status
systemctl status watchfuleye-backend.service

# Test API
curl -s http://localhost:5002/api/health | jq

# Check if Gunicorn is using multiple workers
ps aux | grep gunicorn
# Should see 4 worker processes + 1 master
```

---

## PHASE 4 COMPLETION CHECKLIST

- [ ] SQLite PRAGMA optimizations added to web_app.py
- [ ] Database indexes created and verified
- [ ] Rate limiting adjusted for launch traffic
- [ ] Load shedding protection implemented
- [ ] Backend restarted successfully
- [ ] Multiple Gunicorn workers running (4 expected)
- [ ] API response times improved

**Benchmark response times:**
```bash
# Test API performance
time curl -s http://localhost:5002/api/articles?limit=50 > /dev/null
time curl -s http://localhost:5002/api/stats > /dev/null
time curl -s http://localhost:5002/api/health > /dev/null

# All should complete in <500ms
```

---

# PHASE 5: TESTING & VALIDATION (3 hours)

## Step 5.1: Systemd Crash Recovery Test (30 min)

**Test each service recovers from crashes:**

```bash
cat > /opt/watchfuleye2/scripts/test_crash_recovery.sh << 'BASHEOF'
#!/bin/bash

services=("watchfuleye-backend" "watchfuleye-frontend" "watchfuleye-bot")

for service in "${services[@]}"; do
    echo "=== Testing $service ==="

    # Get current PID
    old_pid=$(systemctl show -p MainPID --value $service.service)
    echo "  Current PID: $old_pid"

    # Kill with -9 (simulate crash)
    kill -9 $old_pid
    echo "  Killed process"

    # Wait for restart
    sleep 15

    # Check if restarted
    if systemctl is-active --quiet $service.service; then
        new_pid=$(systemctl show -p MainPID --value $service.service)
        echo "  ✓ Restarted with PID: $new_pid"
    else
        echo "  ✗ FAILED TO RESTART!"
        exit 1
    fi

    echo ""
done

echo "=== All services passed crash recovery test ✅ ==="
BASHEOF

chmod +x /opt/watchfuleye2/scripts/test_crash_recovery.sh
```

**Run test:**
```bash
/opt/watchfuleye2/scripts/test_crash_recovery.sh
```

**Expected output:**
```
=== Testing watchfuleye-backend ===
  Current PID: 12345
  Killed process
  ✓ Restarted with PID: 12567

=== Testing watchfuleye-frontend ===
  Current PID: 12346
  Killed process
  ✓ Restarted with PID: 12589

=== Testing watchfuleye-bot ===
  Current PID: 12347
  Killed process
  ✓ Restarted with PID: 12601

=== All services passed crash recovery test ✅ ===
```

---

## Step 5.2: Load Testing (1 hour)

### Install Apache Bench
```bash
apt-get update && apt-get install -y apache2-utils
```

### Test 1: Frontend Static Files
```bash
ab -n 1000 -c 50 http://localhost:3000/
```

**Expected output:**
```
Requests per second: 500-1000
Time per request: 20-50ms
Failed requests: 0
```

### Test 2: Backend Articles API
```bash
ab -n 5000 -c 100 -H "Accept: application/json" http://localhost:5002/api/articles?limit=50
```

**Pass criteria:**
- Requests per second: >100
- Mean time per request: <500ms
- Failed requests: 0

### Test 3: Backend Stats API
```bash
ab -n 10000 -c 200 http://localhost:5002/api/stats
```

**Pass criteria:**
- Requests per second: >200
- Mean time per request: <200ms
- Failed requests: 0

### Test 4: Backend Health (most critical)
```bash
ab -n 20000 -c 500 http://localhost:5002/api/health
```

**Pass criteria:**
- Requests per second: >500
- Mean time per request: <100ms
- Failed requests: 0

### Test 5: Chat Endpoint (expensive)
```bash
# Create test payload
cat > /tmp/chat_test.json << 'EOF'
{
  "user_message": "What's trending in tech today?",
  "use_rag": true,
  "use_search": false,
  "angle": "neutral",
  "horizon": "medium"
}
EOF

# Test with lower concurrency (chat is expensive)
ab -n 100 -c 10 -p /tmp/chat_test.json -T 'application/json' http://localhost:5002/api/chat/conversations/1/messages/stream
```

**Pass criteria:**
- Mean time per request: <10s
- Failed requests: 0

---

### Monitor during load tests:
```bash
# In separate terminal, watch resources
watch -n 1 'echo "CPU: $(top -bn1 | grep Cpu | awk '"'"'{print $2}'"'"')"; echo "MEM: $(free -m | awk '"'"'NR==2{printf \"%.1f%%\", $3*100/$2}'"'"')"; echo ""; systemctl status watchfuleye-backend --no-pager | grep "Memory:"'
```

**If load tests fail:**
1. Check Gunicorn worker count (increase to 8 if needed)
2. Verify SQLite WAL mode enabled
3. Check memory usage (may need to increase limits)
4. Review logs for errors: `journalctl -u watchfuleye-backend -n 100`

---

## Step 5.3: Backup/Restore Test (30 min)

```bash
cat > /opt/watchfuleye2/scripts/test_backup_restore.sh << 'BASHEOF'
#!/bin/bash
set -e

echo "=== BACKUP/RESTORE TEST ==="

# 1. Take backup
echo "1. Creating backup..."
systemctl start watchfuleye-backup.service
sleep 5

# Get latest backup
LATEST_BACKUP=$(ls -t /opt/watchfuleye2/backups/auto/*.db | head -1)
echo "   Latest backup: $LATEST_BACKUP"

if [ -z "$LATEST_BACKUP" ]; then
    echo "   ✗ No backup found!"
    exit 1
fi

# 2. Verify backup integrity
echo "2. Verifying backup integrity..."
CHECK=$(sqlite3 "$LATEST_BACKUP" "PRAGMA integrity_check;")
if [ "$CHECK" = "ok" ]; then
    echo "   ✓ Integrity check passed"
else
    echo "   ✗ Integrity check FAILED: $CHECK"
    exit 1
fi

# 3. Count articles in backup
echo "3. Checking backup contents..."
BACKUP_ARTICLES=$(sqlite3 "$LATEST_BACKUP" "SELECT COUNT(*) FROM articles;")
echo "   Articles in backup: $BACKUP_ARTICLES"

# 4. Test restore to temp location
echo "4. Testing restore..."
RESTORE_TEST="/tmp/restore_test_$(date +%s).db"
cp "$LATEST_BACKUP" "$RESTORE_TEST"

# Verify restored database
RESTORE_ARTICLES=$(sqlite3 "$RESTORE_TEST" "SELECT COUNT(*) FROM articles;")
if [ "$RESTORE_ARTICLES" = "$BACKUP_ARTICLES" ]; then
    echo "   ✓ Restore successful: $RESTORE_ARTICLES articles"
else
    echo "   ✗ Restore FAILED: expected $BACKUP_ARTICLES, got $RESTORE_ARTICLES"
    exit 1
fi

# 5. Clean up test
rm "$RESTORE_TEST"

echo ""
echo "=== BACKUP/RESTORE TEST PASSED ✅ ==="
echo "Backup size: $(du -h $LATEST_BACKUP | cut -f1)"
echo "Articles: $BACKUP_ARTICLES"
BASHEOF

chmod +x /opt/watchfuleye2/scripts/test_backup_restore.sh
/opt/watchfuleye2/scripts/test_backup_restore.sh
```

---

## Step 5.4: Deploy/Rollback Test (30 min)

### Create deployment structure
```bash
mkdir -p /opt/watchfuleye2/releases
mkdir -p /opt/watchfuleye2/shared

# Move database to shared
if [ ! -f /opt/watchfuleye2/shared/news_bot.db ]; then
    cp /opt/watchfuleye2/news_bot.db /opt/watchfuleye2/shared/
fi
```

### Create deploy script
```bash
cat > /opt/watchfuleye2/scripts/deploy.sh << 'BASHEOF'
#!/bin/bash
set -e

VERSION=$1
if [ -z "$VERSION" ]; then
    echo "Usage: ./deploy.sh <version>"
    exit 1
fi

RELEASES_DIR="/opt/watchfuleye2/releases"
RELEASE_DIR="$RELEASES_DIR/$VERSION"
CURRENT_LINK="/opt/watchfuleye2/current"

echo "=== DEPLOYING VERSION $VERSION ==="

# 1. Create release directory
echo "1. Creating release directory..."
mkdir -p "$RELEASE_DIR"

# 2. Copy code (excluding shared files)
echo "2. Copying code..."
rsync -av \
    --exclude 'releases/' \
    --exclude 'shared/' \
    --exclude 'current' \
    --exclude 'news_bot.db' \
    --exclude '*.log' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    /opt/watchfuleye2/ "$RELEASE_DIR/"

# 3. Create symlinks to shared resources
echo "3. Linking shared resources..."
ln -sf /opt/watchfuleye2/shared/news_bot.db "$RELEASE_DIR/news_bot.db"
ln -sf /opt/watchfuleye2/shared/.env "$RELEASE_DIR/.env"

# 4. Update systemd service files to use release
echo "4. Updating systemd services..."
# (In production, update ExecStart paths to use $CURRENT_LINK)

# 5. Switch current symlink
echo "5. Switching current symlink..."
if [ -L "$CURRENT_LINK" ]; then
    PREVIOUS=$(readlink "$CURRENT_LINK")
    echo "   Previous: $PREVIOUS"
fi
ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
echo "   Current: $(readlink $CURRENT_LINK)"

# 6. Restart services
echo "6. Restarting services..."
systemctl restart watchfuleye-backend.service
systemctl restart watchfuleye-frontend.service
sleep 10

# 7. Health check
echo "7. Running health check..."
if curl -s http://localhost:5002/api/health | grep -q "healthy"; then
    echo "   ✓ Health check passed"
    echo ""
    echo "=== DEPLOYMENT SUCCESSFUL ✅ ==="
    exit 0
else
    echo "   ✗ Health check FAILED"
    echo "   Rolling back..."
    if [ -n "$PREVIOUS" ]; then
        ln -sfn "$PREVIOUS" "$CURRENT_LINK"
        systemctl restart watchfuleye-backend.service
        systemctl restart watchfuleye-frontend.service
    fi
    echo "=== DEPLOYMENT FAILED ❌ ==="
    exit 1
fi
BASHEOF

chmod +x /opt/watchfuleye2/scripts/deploy.sh
```

### Create rollback script
```bash
cat > /opt/watchfuleye2/scripts/rollback.sh << 'BASHEOF'
#!/bin/bash
set -e

VERSION=$1
if [ -z "$VERSION" ]; then
    echo "Usage: ./rollback.sh <version>"
    exit 1
fi

RELEASES_DIR="/opt/watchfuleye2/releases"
RELEASE_DIR="$RELEASES_DIR/$VERSION"
CURRENT_LINK="/opt/watchfuleye2/current"

echo "=== ROLLING BACK TO $VERSION ==="

# Check if version exists
if [ ! -d "$RELEASE_DIR" ]; then
    echo "✗ Version $VERSION not found in $RELEASES_DIR"
    exit 1
fi

# Switch symlink
echo "1. Switching to $VERSION..."
ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"

# Restart services
echo "2. Restarting services..."
systemctl restart watchfuleye-backend.service
systemctl restart watchfuleye-frontend.service
sleep 10

# Health check
echo "3. Health check..."
if curl -s http://localhost:5002/api/health | grep -q "healthy"; then
    echo "   ✓ Rollback successful"
    echo ""
    echo "=== ROLLBACK COMPLETE ✅ ==="
    exit 0
else
    echo "   ✗ Rollback failed - service not healthy"
    exit 1
fi
BASHEOF

chmod +x /opt/watchfuleye2/scripts/rollback.sh
```

### Test deployment
```bash
# Test deploy
/opt/watchfuleye2/scripts/deploy.sh v1.0.0

# Test rollback
/opt/watchfuleye2/scripts/deploy.sh v1.0.1
/opt/watchfuleye2/scripts/rollback.sh v1.0.0
```

---

## Step 5.5: 24-Hour Burn-In (24 hours)

**Let the system run for 24 hours under systemd before launch:**

```bash
echo "=== 24-HOUR BURN-IN STARTED at $(date) ==="
echo "Check back in 24 hours and run validation"
```

**During burn-in, monitor:**
1. All services stay running (check every 6 hours)
2. No memory leaks (memory usage stable)
3. Backups running successfully every 6 hours
4. Health monitor detecting and reporting any issues
5. Bot completing analysis cycles every 4 hours

**After 24 hours, run validation:**
```bash
cat > /opt/watchfuleye2/scripts/validate_burn_in.sh << 'BASHEOF'
#!/bin/bash

echo "=== 24-HOUR BURN-IN VALIDATION ==="

# 1. Check all services still running
echo "1. Service Status:"
for svc in watchfuleye-{backend,frontend,bot,monitor}.service watchfuleye-backup.timer; do
    if systemctl is-active --quiet $svc; then
        echo "   ✓ $svc"
    else
        echo "   ✗ $svc FAILED"
    fi
done

# 2. Check for crashes/restarts
echo -e "\n2. Service Restarts:"
for svc in watchfuleye-{backend,frontend,bot}.service; do
    restarts=$(systemctl show $svc -p NRestarts --value)
    echo "   $svc: $restarts restarts"
done

# 3. Check memory usage
echo -e "\n3. Memory Usage:"
for svc in watchfuleye-{backend,frontend,bot}.service; do
    mem=$(systemctl show $svc -p MemoryCurrent --value)
    mem_mb=$((mem / 1024 / 1024))
    echo "   $svc: ${mem_mb}MB"
done

# 4. Check backups
echo -e "\n4. Backups:"
backup_count=$(ls /opt/watchfuleye2/backups/auto/*.db 2>/dev/null | wc -l)
echo "   Backups created: $backup_count (expected: 4 for 24hrs)"

# 5. Check bot activity
echo -e "\n5. Bot Activity:"
bot_log_age=$(($(date +%s) - $(stat -c %Y /opt/watchfuleye2/logs/bot.log)))
bot_log_age_hrs=$((bot_log_age / 3600))
echo "   Last bot activity: ${bot_log_age_hrs}h ago (should be <4.5h)"

# 6. Check article growth
echo -e "\n6. Database Growth:"
article_count=$(sqlite3 /opt/watchfuleye2/shared/news_bot.db "SELECT COUNT(*) FROM articles")
echo "   Total articles: $article_count (should have grown by ~400-600)"

echo -e "\n=== BURN-IN VALIDATION COMPLETE ==="
BASHEOF

chmod +x /opt/watchfuleye2/scripts/validate_burn_in.sh
```

---

## PHASE 5 COMPLETION CHECKLIST

- [ ] Crash recovery test passed for all services
- [ ] Load tests passed (Frontend, Backend APIs)
- [ ] Chat endpoint handles concurrent requests
- [ ] Backup/restore test passed
- [ ] Deploy/rollback scripts tested
- [ ] 24-hour burn-in completed successfully
- [ ] No service crashes during burn-in
- [ ] Memory usage stable (no leaks)
- [ ] Automated backups running every 6 hours
- [ ] Bot completing cycles every 4 hours

**Validation command after 24 hours:**
```bash
/opt/watchfuleye2/scripts/validate_burn_in.sh
```

---

# PHASE 6: LAUNCH PREPARATION (2 hours)

## Step 6.1: Create Quick Reference Card (15 min)

```bash
cat > /opt/watchfuleye2/QUICK_REFERENCE.md << 'MDEOF'
# WatchfulEye Quick Reference

## 🚦 Check System Status
```bash
/opt/watchfuleye2/scripts/status_dashboard.sh
```

## 🔧 Service Management
```bash
# Check status
systemctl status watchfuleye-{backend,frontend,bot,monitor}.service

# Restart a service
systemctl restart watchfuleye-backend.service

# View logs
journalctl -u watchfuleye-backend -f
tail -f /opt/watchfuleye2/logs/bot.log
```

## 💾 Manual Backup
```bash
systemctl start watchfuleye-backup.service
ls -lht /opt/watchfuleye2/backups/auto/ | head -5
```

## 🚨 Emergency Procedures

### Service Down
```bash
systemctl restart watchfuleye-backend.service
systemctl status watchfuleye-backend.service
```

### Database Locked
```bash
# Restart backend (will close connections)
systemctl restart watchfuleye-backend.service
```

### Restore from Backup
```bash
LATEST=$(ls -t /opt/watchfuleye2/backups/auto/*.db | head -1)
systemctl stop watchfuleye-backend watchfuleye-bot
cp $LATEST /opt/watchfuleye2/shared/news_bot.db
systemctl start watchfuleye-backend watchfuleye-bot
```

### Server Under Load
```bash
# Check resources
htop
# Or
/opt/watchfuleye2/scripts/status_dashboard.sh

# If needed, temporarily disable bot
systemctl stop watchfuleye-bot
```

## 📊 Monitor During Launch
```bash
# Real-time monitoring
watch -n 5 '/opt/watchfuleye2/scripts/status_dashboard.sh'

# Follow all logs
tail -f /opt/watchfuleye2/logs/*.log

# Watch for errors
journalctl -f -p err
```

## 🔍 Troubleshooting

### Check if services auto-restart
```bash
# Kill a process
PID=$(systemctl show -p MainPID --value watchfuleye-backend.service)
kill -9 $PID
# Wait 15 seconds
systemctl status watchfuleye-backend.service
# Should be active again
```

### View error logs
```bash
journalctl -u watchfuleye-backend -p err --since today
journalctl -u watchfuleye-bot -p err --since today
```

### Check database
```bash
sqlite3 /opt/watchfuleye2/shared/news_bot.db "PRAGMA integrity_check;"
sqlite3 /opt/watchfuleye2/shared/news_bot.db "SELECT COUNT(*) FROM articles;"
```
MDEOF
```

---

## Step 6.2: Create Launch Checklist (15 min)

```bash
cat > /opt/watchfuleye2/LAUNCH_CHECKLIST.md << 'MDEOF'
# 🚀 LAUNCH DAY CHECKLIST

## Pre-Launch (Day Before)
- [ ] All systemd services running for 24+ hours
- [ ] No crashes or restarts in last 24 hours
- [ ] Backup system tested and working
- [ ] Load tests passed
- [ ] Health monitoring active (UptimeRobot + internal)
- [ ] Status dashboard accessible
- [ ] Quick reference card printed/accessible
- [ ] Emergency procedures reviewed
- [ ] Got 8 hours of sleep ✨

## Launch Morning (Before Tweet)
- [ ] Run full status check: `/opt/watchfuleye2/scripts/status_dashboard.sh`
- [ ] All services showing green ✓
- [ ] API health check passes
- [ ] Frontend loads: https://watchfuleye.us
- [ ] Chat works with test query
- [ ] Database has recent articles (check timestamp)
- [ ] Bot completed cycle in last 4 hours
- [ ] Recent backup exists (<6 hours old)
- [ ] Disk space sufficient (>20GB free)
- [ ] Server resources normal (<50% CPU/RAM)

## Tweet Thread (9am ET)
```
1/5: "I spent 3 months building what Bloomberg charges $2,000/month for.

Now it's free. And you can try it right now."

2/5: "WatchfulEye: AI-powered geopolitical intelligence
• 63,000+ analyzed articles
• Real-time AI analysis
• Free Telegram briefs every 4 hours
• Chat with AI analyst

Built for serious people who need edge."

3/5: [Screenshot of dashboard + chat working]

4/5: "Live since Sept 6. 35+ days uptime.
Processing 400-500 articles daily.
Already helping analysts make better decisions."

5/5: "700k of you saw this week's threads.

Now use the intelligence platform behind them.

Try it: https://watchfuleye.us

DMs open. First 100 users get priority access to pro features."
```

## First Hour After Tweet
- [ ] Monitor status dashboard every 15 minutes
- [ ] Watch UptimeRobot for downtime alerts
- [ ] Check journalctl for errors: `journalctl -f -p err`
- [ ] Monitor server load: CPU, memory, disk
- [ ] Check concurrent users (if analytics installed)
- [ ] Respond to DMs within 30 minutes

## First 6 Hours
- [ ] Monitor every 30-60 minutes
- [ ] Gather feedback in spreadsheet
- [ ] Check for common error patterns in logs
- [ ] Note any performance issues
- [ ] Respond to all DMs
- [ ] Tweet engagement (likes/replies/retweets)
- [ ] Fix critical issues immediately if they arise

## First 24 Hours
- [ ] Monitor every 2-3 hours
- [ ] Create feedback summary
- [ ] Identify top 3 issues/requests
- [ ] Tweet progress update
- [ ] Start planning fixes for top issues

## Degraded Mode Triggers
If any of these occur, enable degraded mode:

### CPU > 90% sustained
Action: Enable load shedding (already implemented)

### Database locks
Action: Restart backend: `systemctl restart watchfuleye-backend`

### Chat overload
Action: Temporarily disable chat endpoint

### Bot crashes
Action: `systemctl stop watchfuleye-bot` (dashboard still works)

### Out of disk space
Action: Clean old backups: `find /opt/watchfuleye2/backups/auto -name "*.db.gz" -mtime +3 -delete`

## Success Metrics (Week 1)
- [ ] 5,000+ site visitors
- [ ] 500+ active users
- [ ] 100+ Telegram subscribers
- [ ] <1% error rate
- [ ] <5min total downtime
- [ ] 50+ pieces of feedback collected
MDEOF
```

---

## Step 6.3: Prepare Tweet Thread Assets (30 min)

### Take screenshots
1. Open https://watchfuleye.us in browser
2. Screenshot the dashboard with charts
3. Start a chat, ask "What's the latest on Taiwan tensions?"
4. Screenshot the chat response showing sources
5. Open Telegram, screenshot a recent brief

### Optimize images
```bash
mkdir -p /opt/watchfuleye2/launch_assets
# Copy screenshots to this folder
# Name them: dashboard.png, chat.png, telegram.png
```

### Draft tweet thread in Google Doc/Notes
- Write 5 tweets
- Include screenshots
- Schedule or save as draft
- Have ready to post at 9am ET

---

## Step 6.4: Set Up Analytics (Optional, 30 min)

### Add Simple Analytics
```bash
# Add to frontend/src/index.html (if not already there)
# Google Analytics or Plausible (privacy-friendly)
```

### Create tracking spreadsheet
```
Date | Visitors | New Users | Active Chats | Telegram Signups | Issues | Notes
10/11 | ? | ? | ? | ? | ? | Launch day
```

---

## Step 6.5: Final Pre-Launch Validation (30 min)

**Run complete system check:**

```bash
cat > /opt/watchfuleye2/scripts/pre_launch_validation.sh << 'BASHEOF'
#!/bin/bash

echo "════════════════════════════════════════════════════════"
echo "       WATCHFULEYE PRE-LAUNCH VALIDATION"
echo "       $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "════════════════════════════════════════════════════════"

ISSUES=0

# 1. Services
echo -e "\n✓ CHECKING SERVICES..."
for svc in watchfuleye-{backend,frontend,bot,monitor}.service watchfuleye-backup.timer; do
    if systemctl is-active --quiet $svc; then
        echo "  ✓ $svc"
    else
        echo "  ✗ $svc NOT RUNNING"
        ((ISSUES++))
    fi
done

# 2. Ports
echo -e "\n✓ CHECKING PORTS..."
if ss -tlnp | grep -q ":5002"; then
    echo "  ✓ Backend (5002)"
else
    echo "  ✗ Backend (5002) NOT LISTENING"
    ((ISSUES++))
fi
if ss -tlnp | grep -q ":3000"; then
    echo "  ✓ Frontend (3000)"
else
    echo "  ✗ Frontend (3000) NOT LISTENING"
    ((ISSUES++))
fi

# 3. API Health
echo -e "\n✓ CHECKING API..."
HEALTH=$(curl -s http://localhost:5002/api/health 2>/dev/null)
if echo "$HEALTH" | grep -q "healthy"; then
    echo "  ✓ API responding"
else
    echo "  ✗ API NOT RESPONDING"
    ((ISSUES++))
fi

# 4. Database
echo -e "\n✓ CHECKING DATABASE..."
if [ -f /opt/watchfuleye2/shared/news_bot.db ]; then
    ARTICLES=$(sqlite3 /opt/watchfuleye2/shared/news_bot.db "SELECT COUNT(*) FROM articles" 2>/dev/null)
    if [ -n "$ARTICLES" ]; then
        echo "  ✓ Database OK ($ARTICLES articles)"
    else
        echo "  ✗ Database QUERY FAILED"
        ((ISSUES++))
    fi
else
    echo "  ✗ Database FILE NOT FOUND"
    ((ISSUES++))
fi

# 5. Recent Backup
echo -e "\n✓ CHECKING BACKUPS..."
LATEST_BACKUP=$(ls -t /opt/watchfuleye2/backups/auto/*.db 2>/dev/null | head -1)
if [ -n "$LATEST_BACKUP" ]; then
    BACKUP_AGE=$(($(date +%s) - $(stat -c %Y "$LATEST_BACKUP")))
    BACKUP_AGE_HRS=$((BACKUP_AGE / 3600))
    if [ $BACKUP_AGE_HRS -lt 8 ]; then
        echo "  ✓ Recent backup (${BACKUP_AGE_HRS}h ago)"
    else
        echo "  ⚠ Old backup (${BACKUP_AGE_HRS}h ago)"
    fi
else
    echo "  ✗ NO BACKUPS FOUND"
    ((ISSUES++))
fi

# 6. Bot Activity
echo -e "\n✓ CHECKING BOT..."
BOT_LOG="/opt/watchfuleye2/logs/bot.log"
if [ -f "$BOT_LOG" ]; then
    BOT_AGE=$(($(date +%s) - $(stat -c %Y "$BOT_LOG")))
    BOT_AGE_HRS=$((BOT_AGE / 3600))
    if [ $BOT_AGE_HRS -lt 5 ]; then
        echo "  ✓ Bot active (${BOT_AGE_HRS}h ago)"
    else
        echo "  ⚠ Bot inactive (${BOT_AGE_HRS}h ago)"
    fi
else
    echo "  ✗ Bot log not found"
    ((ISSUES++))
fi

# 7. Disk Space
echo -e "\n✓ CHECKING DISK SPACE..."
DISK_USAGE=$(df -h /opt/watchfuleye2 | awk 'NR==2{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    echo "  ✓ Disk space OK (${DISK_USAGE}% used)"
else
    echo "  ⚠ Disk space high (${DISK_USAGE}% used)"
fi

# 8. System Resources
echo -e "\n✓ CHECKING RESOURCES..."
CPU=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{printf "%.0f", 100 - $1}')
MEM=$(free -m | awk 'NR==2{printf "%.0f", $3*100/$2}')
echo "  CPU: ${CPU}%"
echo "  Memory: ${MEM}%"

# 9. Monitoring
echo -e "\n✓ CHECKING MONITORING..."
if systemctl is-active --quiet watchfuleye-monitor.service; then
    echo "  ✓ Health monitor active"
else
    echo "  ✗ Health monitor NOT RUNNING"
    ((ISSUES++))
fi
echo "  Note: Check UptimeRobot manually at uptimerobot.com"

# Summary
echo ""
echo "════════════════════════════════════════════════════════"
if [ $ISSUES -eq 0 ]; then
    echo "       ✅ ALL CHECKS PASSED - READY TO LAUNCH"
else
    echo "       ⚠️  $ISSUES ISSUES FOUND - REVIEW ABOVE"
fi
echo "════════════════════════════════════════════════════════"

exit $ISSUES
BASHEOF

chmod +x /opt/watchfuleye2/scripts/pre_launch_validation.sh
```

**Run validation:**
```bash
/opt/watchfuleye2/scripts/pre_launch_validation.sh
```

**If all checks pass: READY TO LAUNCH 🚀**

---

## PHASE 6 COMPLETION CHECKLIST

- [ ] Quick reference card created
- [ ] Launch checklist created and reviewed
- [ ] Tweet thread drafted with screenshots
- [ ] Analytics set up (optional)
- [ ] Pre-launch validation script created
- [ ] Pre-launch validation passed (0 issues)
- [ ] Emergency procedures reviewed and understood
- [ ] Contact information ready (DMs, email, Discord)
- [ ] Got sleep and mentally prepared

**Final validation:**
```bash
/opt/watchfuleye2/scripts/pre_launch_validation.sh
```

---

# LAUNCH DAY PROTOCOL

## Hour 0: Launch (9am ET)
1. Run pre-launch validation one final time
2. Tweet thread
3. Pin tweet to profile
4. Enable notifications for DMs

## Hours 0-1: Critical Monitoring
```bash
# Terminal 1: Status dashboard
watch -n 60 '/opt/watchfuleye2/scripts/status_dashboard.sh'

# Terminal 2: Real-time errors
journalctl -f -p err

# Terminal 3: Backend logs
journalctl -u watchfuleye-backend -f | grep -E "ERROR|WARN|\[CHAT\]"
```

**Check every 15 minutes:**
- [ ] Services still running
- [ ] API responding
- [ ] No error spikes
- [ ] CPU/Memory acceptable
- [ ] Respond to DMs

## Hours 1-6: Active Monitoring
- Check every 30-60 minutes
- Gather feedback
- Fix critical issues immediately
- Tweet updates

## Hours 6-24: Sustained Operation
- Check every 2-3 hours
- Compile feedback
- Plan fixes for top 3 issues
- Celebrate if things are going well 🎉

---

# POST-LAUNCH (Week 1)

## Day 1-2: Hot Fixes
- Address critical bugs within 6 hours
- Deploy fixes using `/opt/watchfuleye2/scripts/deploy.sh v1.0.1`
- Test thoroughly before deploying
- Tweet about fixes: "Based on feedback, just shipped X"

## Day 3-7: Feature Iteration
- Implement top 3 requested features
- Build in public: share progress
- Engage with users daily
- Monitor metrics

## Metrics to Track
- Daily active users
- Telegram subscribers
- Chat usage
- Error rates
- Uptime percentage
- User feedback themes

---

# EMERGENCY CONTACTS & PROCEDURES

## If Server Goes Down

### 1. Check service status
```bash
systemctl status watchfuleye-{backend,frontend,bot}
```

### 2. Check logs
```bash
journalctl -u watchfuleye-backend -n 100 --no-pager
```

### 3. Restart services
```bash
systemctl restart watchfuleye-backend watchfuleye-frontend
```

### 4. If still down, restore from backup
```bash
LATEST=$(ls -t /opt/watchfuleye2/backups/auto/*.db | head -1)
systemctl stop watchfuleye-{backend,bot}
cp $LATEST /opt/watchfuleye2/shared/news_bot.db
systemctl start watchfuleye-{backend,bot}
```

### 5. Communicate
Tweet: "Experiencing technical issues. Team is working on it. Updates in 30 minutes."

## If Database Corrupted

### 1. Stop services
```bash
systemctl stop watchfuleye-{backend,bot}
```

### 2. Restore latest backup
```bash
LATEST=$(ls -t /opt/watchfuleye2/backups/auto/*.db | head -1)
cp $LATEST /opt/watchfuleye2/shared/news_bot.db
```

### 3. Verify integrity
```bash
sqlite3 /opt/watchfuleye2/shared/news_bot.db "PRAGMA integrity_check;"
```

### 4. Restart services
```bash
systemctl start watchfuleye-{backend,bot}
```

## If Under Heavy Load

### 1. Check resources
```bash
/opt/watchfuleye2/scripts/status_dashboard.sh
```

### 2. Temporarily disable bot
```bash
systemctl stop watchfuleye-bot
```

### 3. Increase Gunicorn workers (if CPU allows)
Edit `/etc/systemd/system/watchfuleye-backend.service`:
```ini
# Change --workers 4 to --workers 8
```
Then:
```bash
systemctl daemon-reload
systemctl restart watchfuleye-backend
```

---

# ROLLBACK PROCEDURE

If something goes wrong after a deploy:

```bash
# 1. Check current version
readlink /opt/watchfuleye2/current

# 2. List available versions
ls /opt/watchfuleye2/releases/

# 3. Rollback
/opt/watchfuleye2/scripts/rollback.sh v1.0.0

# 4. Verify
curl -s http://localhost:5002/api/health | jq
```

---

# SUCCESS CRITERIA

## Week 1 Goals
- [ ] 5,000-10,000 site visitors
- [ ] 500-1,000 active users
- [ ] 100-200 Telegram subscribers
- [ ] <1% error rate
- [ ] <5 minutes total downtime
- [ ] 95%+ uptime
- [ ] 50+ pieces of feedback
- [ ] Top 3 issues identified and planned

## Month 1 Goals
- [ ] 2,000+ registered users
- [ ] 500+ Telegram subscribers
- [ ] 40%+ retention rate
- [ ] 50+ willing to pay for premium
- [ ] 99.5%+ uptime
- [ ] Feature roadmap based on user feedback

---

# FINAL THOUGHTS

You've built something real. The infrastructure is now solid. The monitoring is in place. You're ready for this.

**Remember:**
- Users are forgiving if you're responsive
- Ship fixes fast (within 6-24 hours)
- Build in public - share metrics, learnings, failures
- Engage with every user in DMs
- This is your moment - execute hard

**You got this. 🚀**

---

# APPENDIX: USEFUL COMMANDS

## View all logs
```bash
tail -f /opt/watchfuleye2/logs/*.log
```

## Check service restarts
```bash
for svc in watchfuleye-{backend,frontend,bot}.service; do
    echo "$svc: $(systemctl show $svc -p NRestarts --value) restarts"
done
```

## Database queries
```bash
sqlite3 /opt/watchfuleye2/shared/news_bot.db << EOF
SELECT COUNT(*) as total_articles FROM articles;
SELECT DATE(created_at) as date, COUNT(*) as count
FROM articles
GROUP BY DATE(created_at)
ORDER BY date DESC
LIMIT 7;
EOF
```

## Monitor resource usage
```bash
watch -n 5 'ps aux | grep -E "gunicorn|python3 main.py|node.*serve" | grep -v grep'
```

## Clear space if needed
```bash
# Compress old logs
find /opt/watchfuleye2/logs -name "*.log" -mtime +7 -exec gzip {} \;

# Delete old backups
find /opt/watchfuleye2/backups/auto -name "*.db.gz" -mtime +7 -delete
```

---

**END OF NEXT_STEPS.md**

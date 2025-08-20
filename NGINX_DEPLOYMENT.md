# WatchfulEye Production Deployment with Nginx

This guide provides step-by-step instructions for deploying the WatchfulEye News Intelligence System on a production server using Nginx as a reverse proxy with SSL support.

## Prerequisites

- Ubuntu 20.04 or newer server
- Domain name pointed to your server
- Root or sudo access to the server
- Nginx installed
- Let's Encrypt SSL certificate
- Node.js 16+ and npm installed
- Python 3.8+ installed
- Ollama installed on the server (if using AI Analysis feature)

## Step 1: Install Required Software

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Nginx if not already installed
sudo apt install -y nginx

# Install Python and pip
sudo apt install -y python3 python3-pip python3-venv

# Install Node.js and npm (if not already installed)
curl -fsSL https://deb.nodesource.com/setup_16.x | sudo -E bash -
sudo apt install -y nodejs

# Install Certbot for SSL certificates
sudo apt install -y certbot python3-certbot-nginx

# Install Ollama (for AI Analysis)
curl -fsSL https://ollama.com/install.sh | sh
```

## Step 2: Clone the Repository

```bash
# Create directory for the application
sudo mkdir -p /var/www/watchfuleye
sudo chown $USER:$USER /var/www/watchfuleye

# Clone the repository
git clone https://github.com/yourusername/watchfuleye.git /var/www/watchfuleye

# Navigate to the project directory
cd /var/www/watchfuleye
```

## Step 3: Set Up Python Environment and Dependencies

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Create configuration file (modify with your API keys and settings)
cp config.example .env
# Edit the .env file with your settings
nano .env
```

## Step 4: Build the React Frontend

```bash
# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Create production build
npm run build

# Return to the main directory
cd ..
```

## Step 5: Configure Nginx

```bash
# Copy the Nginx configuration file
sudo cp nginx.production.conf /etc/nginx/sites-available/watchfuleye.conf

# Edit the configuration file to update domain name and paths
sudo nano /etc/nginx/sites-available/watchfuleye.conf
```

Make sure to update:
- `server_name` with your actual domain
- SSL certificate paths if they differ
- Any other paths specific to your setup

```bash
# Create a symbolic link to enable the site
sudo ln -s /etc/nginx/sites-available/watchfuleye.conf /etc/nginx/sites-enabled/

# Remove the default configuration if needed
sudo rm /etc/nginx/sites-enabled/default

# Test the Nginx configuration
sudo nginx -t

# Reload Nginx if the test is successful
sudo systemctl reload nginx
```

## Step 6: Set Up SSL with Let's Encrypt

```bash
# Obtain SSL certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Generate a strong Diffie-Hellman group
sudo openssl dhparam -out /etc/ssl/certs/dhparam.pem 2048
```

## Step 7: Configure Systemd Services

Create systemd service files to manage the WatchfulEye processes:

### Main Backend Service

```bash
sudo nano /etc/systemd/system/watchfuleye-backend.service
```

Add the following content:

```ini
[Unit]
Description=WatchfulEye Backend API
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/watchfuleye
Environment="PATH=/var/www/watchfuleye/venv/bin"
ExecStart=/var/www/watchfuleye/venv/bin/python3 web_app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Ollama API Service

```bash
sudo nano /etc/systemd/system/watchfuleye-ollama.service
```

Add the following content:

```ini
[Unit]
Description=WatchfulEye Ollama API
After=network.target ollama.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/watchfuleye
Environment="PATH=/var/www/watchfuleye/venv/bin"
ExecStart=/var/www/watchfuleye/venv/bin/python3 run_ollama.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### News Bot Service

```bash
sudo nano /etc/systemd/system/watchfuleye-bot.service
```

Add the following content:

```ini
[Unit]
Description=WatchfulEye News Bot
After=network.target watchfuleye-backend.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/watchfuleye
Environment="PATH=/var/www/watchfuleye/venv/bin"
ExecStart=/var/www/watchfuleye/venv/bin/python3 main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Step 8: Set Correct Permissions

```bash
# Set appropriate ownership
sudo chown -R www-data:www-data /var/www/watchfuleye

# Make sure Python scripts are executable
sudo chmod +x /var/www/watchfuleye/*.py

# Create log directories with correct permissions
sudo mkdir -p /var/log/watchfuleye
sudo chown www-data:www-data /var/log/watchfuleye
```

## Step 9: Pull Required Ollama Models

```bash
# Pull the Dolphin 3.0 model for AI Analysis
ollama pull hf.co/cognitivecomputations/Dolphin3.0-Llama3.1-8B-GGUF:Q4_0
```

## Step 10: Start and Enable Services

```bash
# Reload systemd to recognize new service files
sudo systemctl daemon-reload

# Start and enable the services
sudo systemctl start watchfuleye-backend
sudo systemctl enable watchfuleye-backend

sudo systemctl start watchfuleye-ollama
sudo systemctl enable watchfuleye-ollama

sudo systemctl start watchfuleye-bot
sudo systemctl enable watchfuleye-bot
```

## Step 11: Verify Deployment

Check service status:
```bash
sudo systemctl status watchfuleye-backend
sudo systemctl status watchfuleye-ollama
sudo systemctl status watchfuleye-bot
```

Check the application logs:
```bash
# Backend logs
sudo journalctl -u watchfuleye-backend -f

# Ollama API logs
sudo journalctl -u watchfuleye-ollama -f

# Bot logs
sudo journalctl -u watchfuleye-bot -f
```

Visit your domain in a browser to verify that the frontend is working.

## Troubleshooting

### Nginx Issues
- Check Nginx error logs: `sudo tail -f /var/log/nginx/error.log`
- Test Nginx configuration: `sudo nginx -t`
- Check Nginx status: `sudo systemctl status nginx`

### Application Issues
- Check application logs in journalctl
- Make sure all environment variables are set correctly
- Verify that the correct ports are being used in the Nginx configuration
- Check that the Ollama service is running: `sudo systemctl status ollama`

### SSL Issues
- Renew certificates if needed: `sudo certbot renew`
- Check certificate expiration: `sudo certbot certificates`

## Maintenance

### Regular Updates
```bash
# Navigate to the application directory
cd /var/www/watchfuleye

# Pull the latest changes
git pull

# Activate the virtual environment
source venv/bin/activate

# Update Python dependencies
pip install -r requirements.txt

# Update frontend
cd frontend
npm install
npm run build
cd ..

# Restart services
sudo systemctl restart watchfuleye-backend
sudo systemctl restart watchfuleye-ollama
sudo systemctl restart watchfuleye-bot
```

### Backup Strategy
Regularly backup these components:
- Database file: `/var/www/watchfuleye/watchfuleye.db`
- Configuration files
- SSL certificates
- Output logs and analysis data

## Security Considerations

- Keep your server and software up to date
- Use strong passwords and consider using SSH keys for authentication
- Configure a firewall (e.g., UFW) to restrict access to necessary ports
- Regularly monitor logs for suspicious activity
- Consider setting up fail2ban to prevent brute force attacks

For additional support or questions, please refer to the project documentation or contact the maintainers. 
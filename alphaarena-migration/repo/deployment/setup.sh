#!/bin/bash
# Enhanced VPS Setup Script with Security Checks
# Run as root or with sudo

# Exit on error
set -e

echo "🚀 Starting Investment App VPS Setup..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root or with sudo"
    exit 1
fi

# Validate .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo "   Please copy .env.production.example to .env and fill in your values:"
    echo "   cp .env.production.example .env"
    echo "   nano .env"
    exit 1
fi

# Fix Windows line endings if present (common when uploading via WinSCP)
echo "🔧 Converting line endings for Unix compatibility..."
sed -i 's/\r$//' .env 2>/dev/null || true

# Validate critical environment variables
echo "🔍 Validating environment variables..."
source .env

if [ -z "$API_KEY" ] || [ "$API_KEY" = "your-super-secret-api-key-here-change-this" ]; then
    echo "❌ Error: API_KEY not set in .env"
    echo "   Generate one with: openssl rand -hex 32"
    exit 1
fi

if [ -z "$SOLANA_PRIVATE_KEY" ] || [ "$SOLANA_PRIVATE_KEY" = "your-solana-private-key-base58-format" ]; then
    echo "⚠️  Warning: SOLANA_PRIVATE_KEY not set. Live trading (PM7) will not work."
    echo "   Continue anyway? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ Error: OPENAI_API_KEY not set in .env"
    exit 1
fi

echo "✅ Environment variables validated"

# Update package list
echo "📦 Updating system packages..."
apt-get update

# Install Python3 and venv if not present
echo "🐍 Installing Python dependencies..."
apt-get install -y python3 python3-pip python3-venv

# Install Nginx
echo "🌐 Installing Nginx..."
apt-get install -y nginx

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📁 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies
echo "📚 Installing Python packages..."
pip install --upgrade pip
pip install -r backend/requirements.txt

# Set proper permissions on .env
chmod 600 .env
echo "🔒 Set .env file permissions to 600 (user read/write only)"

# Copy Nginx configuration
echo "⚙️  Setting up Nginx configuration..."
cp deployment/nginx.conf /etc/nginx/sites-available/investment-app

# Create symlink if it doesn't exist
if [ ! -L /etc/nginx/sites-enabled/investment-app ]; then
    ln -s /etc/nginx/sites-available/investment-app /etc/nginx/sites-enabled/
    echo "✅ Created Nginx site symlink"
fi

# Remove default Nginx site
if [ -L /etc/nginx/sites-enabled/default ]; then
    rm /etc/nginx/sites-enabled/default
    echo "✅ Removed default Nginx site"
fi

# Test Nginx configuration
echo "🧪 Testing Nginx configuration..."
nginx -t

# Copy systemd service file
echo "⚙️  Setting up systemd service..."
cp deployment/investment-app.service /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next Steps:"
echo "   1. Run firewall setup: sudo bash deployment/firewall-setup.sh"
echo "   2. Run SSL setup: sudo bash deployment/ssl-setup.sh"
echo "   3. Start the service: sudo systemctl start investment-app"
echo "   4. Enable auto-start: sudo systemctl enable investment-app"
echo "   5. Start Nginx: sudo systemctl start nginx"
echo "   6. Enable Nginx: sudo systemctl enable nginx"
echo ""
echo "📊 Check status:"
echo "   - App status: sudo systemctl status investment-app"
echo "   - Nginx status: sudo systemctl status nginx"
echo "   - View logs: sudo journalctl -u investment-app -f"
echo ""


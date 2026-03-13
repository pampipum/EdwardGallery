#!/bin/bash
# Firewall Setup Script for Ubuntu VPS
# Configures UFW (Uncomplicated Firewall) with secure defaults

set -e

echo "🔒 Setting up UFW Firewall..."

# Install UFW if not present
if ! command -v ufw &> /dev/null; then
    echo "Installing UFW..."
    apt-get update
    apt-get install -y ufw
fi

# Reset UFW to defaults (WARNING: This will remove all existing rules)
echo "Resetting UFW to defaults..."
ufw --force reset

# Default policies: deny incoming, allow outgoing
ufw default deny incoming
ufw default allow outgoing

# Allow SSH (CRITICAL - don't lock yourself out!)
echo "Allowing SSH (port 22)..."
ufw allow 22/tcp comment 'SSH access'

# Allow HTTP (for Let's Encrypt ACME challenge)
echo "Allowing HTTP (port 80)..."
ufw allow 80/tcp comment 'HTTP for SSL verification'

# Allow HTTPS (production traffic)
echo "Allowing HTTPS (port 443)..."
ufw allow 443/tcp comment 'HTTPS production traffic'

# DENY direct access to FastAPI backend
echo "Blocking direct access to port 8000..."
ufw deny 8000/tcp comment 'Block direct backend access'

# Enable UFW
echo "Enabling UFW..."
ufw --force enable

# Show status
echo ""
echo "✅ Firewall configuration complete!"
echo ""
ufw status verbose

echo ""
echo "⚠️  IMPORTANT: Verify SSH still works before closing this session!"
echo "    Open a NEW terminal and test: ssh user@your-vps-ip"
echo "    If you can't connect, you have 30 seconds to disable UFW: sudo ufw disable"

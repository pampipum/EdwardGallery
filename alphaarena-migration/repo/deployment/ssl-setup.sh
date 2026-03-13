#!/bin/bash
# SSL Setup Script for Ubuntu VPS
# Installs Certbot and configures Let's Encrypt SSL certificates

set -e

DOMAIN="app1.attikonlab.uk"
EMAIL="${SSL_EMAIL:-admin@attikonlab.uk}"  # Change this to your email

echo "🔐 Setting up SSL with Let's Encrypt..."

# Install Certbot and Nginx plugin
echo "Installing Certbot..."
apt-get update
apt-get install -y certbot python3-certbot-nginx

# Verify Nginx is installed
if ! command -v nginx &> /dev/null; then
    echo "❌ Error: Nginx is not installed. Please install Nginx first."
    exit 1
fi

# Verify Nginx configuration
echo "Testing Nginx configuration..."
nginx -t

# Stop Nginx temporarily (Certbot standalone mode)
echo "Obtaining SSL certificate for $DOMAIN..."
systemctl stop nginx

# Obtain certificate (standalone mode for initial setup)
certbot certonly --standalone \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    -d "$DOMAIN"

# Start Nginx again
systemctl start nginx

# Set up automatic renewal
echo "Setting up automatic certificate renewal..."
systemctl enable certbot.timer
systemctl start certbot.timer

# Test automatic renewal
echo "Testing certificate renewal process..."
certbot renew --dry-run

echo ""
echo "✅ SSL setup complete!"
echo ""
echo "Certificate locations:"
echo "  - Certificate: /etc/letsencrypt/live/$DOMAIN/fullchain.pem"
echo "  - Private Key: /etc/letsencrypt/live/$DOMAIN/privkey.pem"
echo ""
echo "Certificates will auto-renew via systemd timer."
echo ""
echo "Next steps:"
echo "  1. Update Nginx configuration to use these certificates"
echo "  2. Reload Nginx: sudo systemctl reload nginx"
echo "  3. Test SSL: https://$DOMAIN"

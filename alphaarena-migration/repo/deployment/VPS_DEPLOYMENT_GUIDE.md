# VPS Deployment Guide - Investment Trading App

Complete guide for deploying your Investment Trading App to Ubuntu VPS with full security hardening.

## 📋 Pre-Deployment Checklist

Before starting deployment, ensure you have:

- [ ] Ubuntu VPS with root/sudo access
- [ ] Domain `app1.attikonlab.uk` DNS A record pointing to your VPS IP
- [ ] SSH access to your VPS
- [ ] All API keys ready (OpenAI, Gemini, Solana wallet private key)
- [ ] Generated strong API_KEY for endpoint protection

### DNS Configuration

Verify your domain is configured correctly:

```bash
# On your local machine, test DNS resolution
nslookup app1.attikonlab.uk

# Should return your VPS IP address
```

**If DNS is not configured:** Log into your domain registrar (where you bought attikonlab.uk) and create an A record:
- **Type**: A
- **Name**: app1
- **Value**: Your VPS IP address
- **TTL**: 3600 (or default)

## 🚀 Deployment Steps

### Step 1: Upload Files to VPS

From your local machine, upload the project to your VPS:

```bash
# Option A: Using rsync (recommended)
rsync -avz --exclude 'venv' --exclude 'node_modules' --exclude '.git' \
  c:\Users\andre\Desktop\project\Investment/ \
  root@YOUR_VPS_IP:/opt/investment-app/

# Option B: Using scp
scp -r c:\Users\andre\Desktop\project\Investment \
  root@YOUR_VPS_IP:/opt/investment-app/
```

### Step 2: SSH into Your VPS

```bash
ssh root@YOUR_VPS_IP
cd /opt/investment-app
```

### Step 3: Configure Environment Variables

Create your production `.env` file:

```bash
# Copy the example template
cp .env.production.example .env

# Edit with your actual values
nano .env
```

**Required values to set:**

```bash
# Generate a strong API key
openssl rand -hex 32

# Then in .env, set:
API_KEY=<paste-generated-key-here>
SOLANA_PRIVATE_KEY=<your-solana-wallet-private-key>
OPENAI_API_KEY=<your-openai-api-key>
GEMINI_API_KEY=<your-gemini-api-key>
```

**Save and exit**: Press `Ctrl+X`, then `Y`, then `Enter`

**Secure the .env file:**

```bash
chmod 600 .env
chown root:root .env
```

### Step 4: Run Initial Setup

```bash
# Make scripts executable
chmod +x deployment/*.sh

# Run main setup script
sudo bash deployment/setup.sh
```

This script will:
- ✅ Validate environment variables
- ✅ Install Python, pip, and dependencies
- ✅ Install and configure Nginx
- ✅ Set up systemd service
- ✅ Create virtual environment

### Step 5: Configure Firewall

```bash
sudo bash deployment/firewall-setup.sh
```

This configures UFW to:
- ✅ Allow SSH (port 22)
- ✅ Allow HTTP (port 80) for SSL verification
- ✅ Allow HTTPS (port 443) for production traffic
- ✅ **DENY port 8000** (blocks direct backend access)

**⚠️ CRITICAL**: After running this, **immediately** test SSH in a new terminal:

```bash
# From your local machine, open a NEW terminal
ssh root@YOUR_VPS_IP
```

If you can't connect, you have a few minutes to disable the firewall from your CURRENT session:

```bash
sudo ufw disable
```

### Step 6: Setup SSL Certificates

**Important**: Before running this, ensure your DNS is propagated (Step 1 checklist). Let's Encrypt will verify domain ownership.

```bash
# Edit ssl-setup.sh to set your email (optional)
nano deployment/ssl-setup.sh
# Change: EMAIL="admin@attikonlab.uk" to your email

# Run SSL setup
sudo bash deployment/ssl-setup.sh
```

This will:
- ✅ Install Certbot
- ✅ Obtain SSL certificate for `app1.attikonlab.uk`
- ✅ Set up automatic renewal (certificates auto-renew every 60 days)

### Step 7: Start Services

```bash
# Start the FastAPI application
sudo systemctl start investment-app
sudo systemctl enable investment-app  # Auto-start on boot

# Reload Nginx with SSL configuration
sudo systemctl reload nginx
sudo systemctl enable nginx  # Auto-start on boot

# Check status
sudo systemctl status investment-app
sudo systemctl status nginx
```

### Step 8: Verify Deployment

```bash
# Check if the backend is running locally
curl http://localhost:8000/api/dashboard

# Check if Nginx is proxying correctly (HTTPS)
curl https://app1.attikonlab.uk/api/dashboard

# Check SSL certificate
curl -vI https://app1.attikonlab.uk 2>&1 | grep "subject:"
```

**From your local machine browser:**

Navigate to: `https://app1.attikonlab.uk`

You should see your Investment App frontend with a valid SSL certificate (green padlock 🔒).

## 🔒 Security Verification

### Test 1: Direct Backend Access Blocked

```bash
# This should FAIL (connection refused)
curl http://app1.attikonlab.uk:8000/api/dashboard

# This should work (through Nginx)
curl https://app1.attikonlab.uk/api/dashboard
```

### Test 2: CORS Protection

Open browser console on an unauthorized domain (e.g., `https://google.com`), run:

```javascript
fetch('https://app1.attikonlab.uk/api/dashboard')
  .then(r => r.json())
  .then(console.log)
  .catch(console.error)
```

**Expected**: CORS error in console (blocked by browser due to origin mismatch)

### Test 3: Rate Limiting

```bash
# Rapid-fire 70 requests
for i in {1..70}; do 
  curl -s -o /dev/null -w "Request $i: %{http_code}\n" \
    https://app1.attikonlab.uk/api/dashboard
  sleep 0.5
done
```

**Expected**: After ~60 requests, you should see HTTP 429 (Too Many Requests) responses

### Test 4: API Key Protection

Test a protected endpoint without API key:

```bash
# Should fail with 401 Unauthorized
curl -X POST https://app1.attikonlab.uk/api/portfolio/start/pm1 \
  -H "Content-Type: application/json" \
  -d '{"capital": 1000}'

# Should work with correct API key
curl -X POST https://app1.attikonlab.uk/api/portfolio/start/pm1 \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY_FROM_ENV" \
  -d '{"capital": 1000}'
```

### Test 5: SSL Certificate

Visit https://www.ssllabs.com/ssltest/ and enter `app1.attikonlab.uk`

**Expected**: Grade A or A+ rating

## 📊 Monitoring & Maintenance

### View Application Logs

```bash
# Follow live logs
sudo journalctl -u investment-app -f

# View last 100 lines
sudo journalctl -u investment-app -n 100

# View errors only
sudo journalctl -u investment-app -p err
```

### View Nginx Logs

```bash
# Access logs
sudo tail -f /var/log/nginx/investment-app-access.log

# Error logs
sudo tail -f /var/log/nginx/investment-app-error.log
```

### Restart Services

```bash
# After code changes
sudo systemctl restart investment-app

# After Nginx config changes
sudo systemctl reload nginx
```

### Update Application

```bash
# From local machine, upload new code
rsync -avz --exclude 'venv' --exclude '.git' \
  c:\Users\andre\Desktop\project\Investment/ \
  root@YOUR_VPS_IP:/opt/investment-app/

# On VPS, restart the service
ssh root@YOUR_VPS_IP "cd /opt/investment-app && sudo systemctl restart investment-app"
```

## 🆘 Troubleshooting

### Issue: "Connection Refused" when accessing domain

**Diagnostics:**

```bash
# Check if Nginx is running
sudo systemctl status nginx

# Check if port 443 is open
sudo netstat -tlnp | grep :443

# Check firewall
sudo ufw status
```

**Fix:**

```bash
sudo systemctl start nginx
sudo ufw allow 443/tcp
```

### Issue: "502 Bad Gateway"

This means Nginx can't reach the FastAPI backend.

**Diagnostics:**

```bash
# Check if investment-app is running
sudo systemctl status investment-app

# Check if it's listening on port 8000
sudo netstat -tlnp | grep :8000

# Check application logs
sudo journalctl -u investment-app -n 50
```

**Fix:**

```bash
# Restart the app
sudo systemctl restart investment-app

# If it fails to start, check logs for errors
sudo journalctl -u investment-app -n 100 --no-pager
```

### Issue: SSL Certificate Errors

**Diagnostics:**

```bash
# Check if certificate exists
sudo ls -la /etc/letsencrypt/live/app1.attikonlab.uk/

# Test certificate renewal
sudo certbot renew --dry-run
```

**Fix:**

```bash
# Re-run SSL setup
sudo bash /opt/investment-app/deployment/ssl-setup.sh
```

### Issue: Rate Limiting Not Working

**Diagnostics:**

```bash
# Check if rate_limiting is enabled in config
cat /opt/investment-app/backend/config.json | grep -A 3 rate_limiting

# Check application logs for rate limit warnings
sudo journalctl -u investment-app | grep "Rate limit"
```

**Fix:**

Verify `backend/config.json` has:

```json
"rate_limiting": {
    "enabled": true,
    "requests_per_minute": 60
}
```

## 📝 Security Best Practices

1. **Regular Updates**: Keep your VPS packages updated
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Rotate API Keys**: Change your `API_KEY` periodically
   ```bash
   # Generate new key
   openssl rand -hex 32
   # Update .env
   nano /opt/investment-app/.env
   # Restart service
   sudo systemctl restart investment-app
   ```

3. **Monitor Logs**: Regularly check for suspicious activity
   ```bash
   # Check for failed authentication attempts
   sudo journalctl -u investment-app | grep "401\|403"
   ```

4. **Backup Wallet**: Your Solana private key should be backed up securely OFFLINE

5. **Firewall Monitoring**: Regularly verify firewall rules
   ```bash
   sudo ufw status verbose
   ```

## 🎯 Next Steps

Once deployment is verified:

1. ✅ Update frontend to point to `https://app1.attikonlab.uk` (if separate)
2. ✅ Test all trading functions through the secured API
3. ✅ Set up monitoring/alerting (optional: UptimeRobot, Pingdom)
4. ✅ Configure automated backups of portfolio data
5. ✅ Document your deployment-specific customizations

---

**Need Help?** Check logs first, then review the troubleshooting section above.

# 🚀 Quick Start - VPS Deployment

**Domain**: https://app1.attikonlab.uk  
**VPS OS**: Ubuntu

## Before You Start

1. ✅ DNS A record for `app1.attikonlab.uk` pointing to your VPS IP
2. ✅ SSH access to your VPS
3. ✅ API keys ready (OpenAI, Gemini, Solana private key)

---

## Deployment Commands (Run on VPS)

```bash
# 1. Upload files from your Windows machine
rsync -avz --exclude 'venv' --exclude '.git' \
  c:\Users\andre\Desktop\project\Investment/ \
  root@YOUR_VPS_IP:/opt/investment-app/

# 2. SSH into VPS
ssh root@YOUR_VPS_IP
cd /opt/investment-app

# 3. Create .env file
cp .env.production.example .env
nano .env

# Fill in these values:
# API_KEY=<run: openssl rand -hex 32>
# SOLANA_PRIVATE_KEY=<your-base58-private-key>
# OPENAI_API_KEY=<your-key>
# GEMINI_API_KEY=<your-key>

# Save: Ctrl+X, Y, Enter

# 4. Run setup (installs Python, Nginx, creates venv)
sudo bash deployment/setup.sh

# 5. Setup firewall (blocks port 8000, allows 22/80/443)
sudo bash deployment/firewall-setup.sh

# 6. Setup SSL (Let's Encrypt certificates)
sudo bash deployment/ssl-setup.sh

# 7. Start everything
sudo systemctl start investment-app
sudo systemctl enable investment-app
sudo systemctl start nginx
sudo systemctl enable nginx
```

---

## Verify It Works

```bash
# On VPS - Check status
sudo systemctl status investment-app
sudo systemctl status nginx

# Test locally (should work)
curl http://localhost:8000/api/dashboard

# Test HTTPS (should work)
curl https://app1.attikonlab.uk/api/dashboard

# Test direct access blocked (should FAIL)
curl http://app1.attikonlab.uk:8000/api/dashboard

# View logs
sudo journalctl -u investment-app -f
```

---

## Security Features Enabled

✅ **CORS**: Only `http://localhost:8000` and `https://app1.attikonlab.uk` allowed  
✅ **Rate Limiting**: 60 requests/minute, returns HTTP 429 when exceeded  
✅ **SSL/HTTPS**: Let's Encrypt with auto-renewal  
✅ **Firewall**: UFW blocks direct backend access (port 8000)  
✅ **Nginx Security**: HSTS, X-Frame-Options, X-Content-Type-Options headers  

---

## Common Commands

```bash
# Restart after code changes
sudo systemctl restart investment-app

# View live logs
sudo journalctl -u investment-app -f

# Check firewall status
sudo ufw status

# Test SSL renewal
sudo certbot renew --dry-run
```

---

**Full documentation**: [VPS_DEPLOYMENT_GUIDE.md](file:///c:/Users/andre/Desktop/project/Investment/deployment/VPS_DEPLOYMENT_GUIDE.md)

# VPS Deployment Guide

This guide will help you deploy your Investment Application to a VPS. We will use **WinSCP** for file transfer and **Putty** for running commands.

## Prerequisites
- A VPS (Virtual Private Server) running Ubuntu or Debian.
- Root password or a user with sudo privileges.
- **WinSCP** installed on your local machine.
- **Putty** installed on your local machine.

## Step 1: Prepare Files for Transfer
I have created a `deployment` folder in your project with two helper files:
1. `investment-app.service`: A configuration file to keep your app running in the background.
2. `setup.sh`: A script to install dependencies automatically.

## Step 2: Transfer Files using WinSCP
1. Open **WinSCP**.
2. Connect to your VPS using your IP address, username (usually `root`), and password.
3. In the right panel (Remote), navigate to `/opt`.
4. Right-click and create a new directory named `investment-app`.
5. Open the `investment-app` directory.
6. In the left panel (Local), navigate to your project folder: `c:\Users\andre\Desktop\project\Investment`.
7. Select and drag the following files/folders to the right panel:
   - `backend/` (folder)
   - `frontend/` (folder)
   - `deployment/` (folder)
   - `.env` (file)
   - `portfolio.json` (file)

> **Note**: Ensure `.env` is transferred. It might be hidden. If you don't see it, make sure to enable "Show hidden files" in WinSCP or create it manually on the server.

## Step 3: Install and Setup using Putty
1. Open **Putty**.
2. Connect to your VPS IP address.
3. Log in as `root`.
4. Run the following commands to set up the application:

```bash
# Go to the application directory
cd /opt/investment-app

# Make the setup script executable
chmod +x deployment/setup.sh

# Run the setup script (Installs Python, creates venv, installs requirements)
./deployment/setup.sh
```

## Step 4: Configure the Service
Now we will set up the application to run automatically and restart if it crashes.

```bash
# Copy the service file to the system directory
cp deployment/investment-app.service /etc/systemd/system/

# Reload systemd to recognize the new service
systemctl daemon-reload

# Enable the service to start on boot
systemctl enable investment-app

# Start the service immediately
systemctl start investment-app
```

## Step 5: Verify Deployment and Sync Check
To ensure the application is running and the "sync check" is working timely:

1. **Check Status**:
   ```bash
   systemctl status investment-app
   ```
   You should see `Active: active (running)`.

2. **Check Logs (Verify Sync Check)**:
   The application logs every time it runs a market check. To see these logs in real-time:
   ```bash
   journalctl -u investment-app -f
   ```
   - Look for lines saying: `Starting Market Check...`
   - You should see this immediately after startup.
   - It will repeat every 4 hours (as configured in `trading_loop.py`).

3. **Manual Trigger (Optional)**:
   If you want to force a check immediately to verify it works without waiting:
   ```bash
   # Assuming you are still in /opt/investment-app
   curl -X POST "http://localhost:8000/api/portfolio/tick"
   ```
   Check the logs again, and you should see a new check starting.

## Troubleshooting
- **If the service fails to start**:
  Check logs with `journalctl -u investment-app -n 50`.
  Common issues:
  - Missing `.env` file.
  - Wrong paths in `investment-app.service` (if you didn't use `/opt/investment-app`).
  - Port 8000 already in use.

- **Updating the App**:
  1. Upload new files via WinSCP.
  2. Restart the service: `systemctl restart investment-app`.

## Firewall & VPN Troubleshooting
If you cannot access the app at `http://YOUR_IP:8000`:

1.  **Check Firewall (UFW)**:
    ```bash
    ufw allow 8000
    ufw reload
    ```

2.  **Check NordVPN (If installed)**:
    NordVPN can block incoming ports. You need to whitelist port 8000.
    ```bash
    # Whitelist the port
    nordvpn whitelist add port 8000
    
    # Or temporarily disconnect to test
    nordvpn disconnect
    ```

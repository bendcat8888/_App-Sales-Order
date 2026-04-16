# Deployment Guide: Streamlit App to Ubuntu Server

This guide will walk you through deploying your Streamlit application to an Ubuntu Server from scratch.

## Prerequisites
- Ubuntu Server (20.04 LTS or later recommended)
- SSH access to the server
- Root or sudo access

---

## Step 1: Initial Server Setup

### 1.1 Update System Packages
```bash
sudo apt update
sudo apt upgrade -y
```

### 1.2 Install Essential Tools
```bash
sudo apt install -y python3 python3-pip python3-venv git curl wget
```

### 1.3 Verify Python Installation
```bash
python3 --version
pip3 --version
```

---

## Step 2: Create Application Directory

### 2.1 Create Directory Structure
```bash
# Navigate to your application directory (already created)
cd /home/rgbadmins/Streamlit_Apps/so_solvang

# Ensure you have proper permissions
chmod 755 /home/rgbadmins/Streamlit_Apps/so_solvang
```

**Note:** If you prefer a different location like `/opt/streamlit-app`, you can use:
```bash
sudo mkdir -p /opt/streamlit-app
sudo chown $USER:$USER /opt/streamlit-app
cd /opt/streamlit-app
```

### 2.2 Upload Your Application Files

**Option A: Using SCP (from your local machine)**
```bash
# From your local Windows machine (PowerShell or Command Prompt)
# Replace 'rgbadmins' with your actual username and 'your-server-ip' with your server IP
scp "C:\Users\Benedic Cater\SynologyDrive\Software Development\Python Codes\Sales_Order_Inventory_App.py" rgbadmins@your-server-ip:/home/rgbadmins/Streamlit_Apps/so_solvang/
scp -r "C:\Users\Benedic Cater\SynologyDrive\Software Development\Python Codes\product_images" rgbadmins@your-server-ip:/home/rgbadmins/Streamlit_Apps/so_solvang/
scp "C:\Users\Benedic Cater\SynologyDrive\Software Development\Python Codes\requirements.txt" rgbadmins@your-server-ip:/home/rgbadmins/Streamlit_Apps/so_solvang/
# Upload any other required files (CSV files, etc.)
```

**Option B: Using Git (if you have a repository)**
```bash
cd /home/rgbadmins/Streamlit_Apps/so_solvang
git clone https://your-repository-url.git .
```

**Option C: Using SFTP Client (FileZilla, WinSCP, etc.)**
- Connect to your server via SFTP
- Upload all necessary files to `/home/rgbadmins/Streamlit_Apps/so_solvang/`

---

## Step 3: Create Virtual Environment

### 3.1 Create Virtual Environment
```bash
cd /home/rgbadmins/Streamlit_Apps/so_solvang
python3 -m venv venv
```

### 3.2 Activate Virtual Environment
```bash
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt.

### 3.3 Upgrade pip
```bash
pip install --upgrade pip
```

---

## Step 4: Install Dependencies

### 4.1 Create requirements.txt

First, create a `requirements.txt` file with all your dependencies (or use the one you uploaded):

```bash
cd /home/rgbadmins/Streamlit_Apps/so_solvang
# If you uploaded requirements.txt, skip this step
# Otherwise create it:
nano requirements.txt
```

Add the following content (adjust based on your actual dependencies):
```
streamlit>=1.28.0
pandas>=1.5.0
pyodbc>=4.0.39
sqlalchemy>=2.0.0
openpyxl>=3.1.0
Pillow>=10.0.0
```

Save and exit (Ctrl+X, then Y, then Enter).

### 4.2 Install Dependencies
```bash
# Make sure virtual environment is activated
source venv/bin/activate
pip install -r Requirements.txt
```

### 4.3 Install Additional System Dependencies (for pyodbc)
```bash
# Install ODBC driver for SQL Server
sudo apt install -y unixodbc unixodbc-dev
sudo apt install -y curl apt-transport-https

# Download and install Microsoft ODBC Driver for SQL Server
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list

sudo apt update
sudo ACCEPT_EULA=Y apt install -y msodbcsql18
```

---

## Step 5: Configure Application

### 5.1 Set Up Environment Variables (if needed)
```bash
cd /home/rgbadmins/Streamlit_Apps/so_solvang
nano .env
```

Add any environment variables your app needs (database credentials, etc.):
```
DB_SERVER=your-db-server
DB_NAME=your-db-name
DB_USER=your-db-user
DB_PASSWORD=your-db-password
```

### 5.2 Create Streamlit Config Directory
```bash
mkdir -p ~/.streamlit
nano ~/.streamlit/config.toml
```

Add configuration:
```toml
[server]
port = 8501
address = "0.0.0.0"
enableCORS = false
enableXsrfProtection = true

[browser]
gatherUsageStats = false
```

### 5.3 Set File Permissions
```bash
cd /opt/streamlit-app
chmod +x Sales_Order_Inventory_App.py
```

---

## Step 6: Test the Application

### 6.1 Run Streamlit Manually (for testing)
```bash
cd /home/rgbadmins/Streamlit_Apps/so_solvang
source venv/bin/activate
streamlit run Sales_Order_Inventory_App.py
```

Test by accessing: `http://your-server-ip:8501`

Press `Ctrl+C` to stop the server.

---

## Step 7: Create Systemd Service (Run as Background Service)

### 7.1 Create Service File
```bash
sudo nano /etc/systemd/system/streamlit-app.service
```

Add the following content:
```ini
[Unit]
Description=Streamlit Application - Sales Order Solvang
After=network.target

[Service]
Type=simple
User=rgbadmins
WorkingDirectory=/home/rgbadmins/Streamlit_Apps/so_solvang
Environment="PATH=/home/rgbadmins/Streamlit_Apps/so_solvang/venv/bin"
ExecStart=/home/rgbadmins/Streamlit_Apps/so_solvang/venv/bin/streamlit run Sales_Order_Inventory_App.py --server.port=8501 --server.address=0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Note:** The service is configured for user `rgbadmins` and the directory `/home/rgbadmins/Streamlit_Apps/so_solvang`. Adjust if needed.

### 7.2 Enable and Start Service
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable streamlit-app.service

# Start the service
sudo systemctl start streamlit-app.service

# Check status
sudo systemctl status streamlit-app.service
```

### 7.3 View Logs
```bash
# View logs
sudo journalctl -u streamlit-app.service -f

# View last 100 lines
sudo journalctl -u streamlit-app.service -n 100
```

---

## Step 8: Configure Firewall

### 8.1 Allow Port 8501 (if using UFW)
```bash
sudo ufw allow 8501/tcp
sudo ufw reload
```

### 8.2 Check Firewall Status
```bash
sudo ufw status
```

---

## Step 9: Set Up Nginx Reverse Proxy (Optional but Recommended)

### 9.1 Install Nginx
```bash
sudo apt install -y nginx
```

### 9.2 Create Nginx Configuration
```bash
sudo nano /etc/nginx/sites-available/streamlit-app
```

Add configuration:
```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain or IP

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
```

### 9.3 Enable Site
```bash
sudo ln -s /etc/nginx/sites-available/streamlit-app /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Step 10: Set Up SSL with Let's Encrypt (Optional)

### 10.1 Install Certbot
```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 10.2 Obtain SSL Certificate
```bash
sudo certbot --nginx -d your-domain.com
```

Follow the prompts to complete the setup.

---

## Step 11: Maintenance Commands

### 11.1 Service Management
```bash
# Start service
sudo systemctl start streamlit-app

# Stop service
sudo systemctl stop streamlit-app

# Restart service
sudo systemctl restart streamlit-app

# Check status
sudo systemctl status streamlit-app

# View logs
sudo journalctl -u streamlit-app -f
```

### 11.2 Update Application
```bash
cd /home/rgbadmins/Streamlit_Apps/so_solvang
source venv/bin/activate

# Update code files (via git, scp, etc.)
# Then restart service
sudo systemctl restart streamlit-app
```

### 11.3 Update Dependencies
```bash
cd /home/rgbadmins/Streamlit_Apps/so_solvang
source venv/bin/activate
pip install --upgrade -r requirements.txt
sudo systemctl restart streamlit-app
```

---

## Troubleshooting

### Check if Port is in Use
```bash
sudo netstat -tulpn | grep 8501
```

### Check Application Logs
```bash
sudo journalctl -u streamlit-app.service -n 50
```

### Test Database Connection
```bash
cd /home/rgbadmins/Streamlit_Apps/so_solvang
source venv/bin/activate
python3 -c "import pyodbc; print('pyodbc installed successfully')"
```

### Verify File Permissions
```bash
ls -la /home/rgbadmins/Streamlit_Apps/so_solvang
```

---

## Security Considerations

1. **Firewall**: Only open necessary ports
2. **SSL**: Use HTTPS in production
3. **Authentication**: Implement Streamlit authentication or use a reverse proxy with authentication
4. **File Permissions**: Ensure sensitive files have proper permissions
5. **Environment Variables**: Store sensitive data in environment variables, not in code

---

## Quick Reference Checklist

- [ ] System updated
- [ ] Python and pip installed
- [ ] Application directory created
- [ ] Files uploaded to server
- [ ] Virtual environment created and activated
- [ ] Dependencies installed
- [ ] Application tested manually
- [ ] Systemd service created and enabled
- [ ] Firewall configured
- [ ] Nginx configured (optional)
- [ ] SSL certificate installed (optional)
- [ ] Application running and accessible

---

## Additional Notes

- Replace `your-username`, `your-domain.com`, and `your-server-ip` with your actual values
- Adjust file paths if you use a different directory structure
- For production, consider using a process manager like `supervisor` or `pm2` as alternatives to systemd
- Monitor server resources: `htop` or `top` for CPU/memory usage


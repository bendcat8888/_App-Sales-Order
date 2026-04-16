# Quick Start Guide - Sales Order Solvang App

## Your Directory Structure
```
/home/rgbadmins/Streamlit_Apps/so_solvang/
```

## Step-by-Step Deployment

### 1. Connect to Your Server
```bash
ssh rgbadmins@your-server-ip
```

### 2. Navigate to Your App Directory
```bash
cd /home/rgbadmins/Streamlit_Apps/so_solvang
```

### 3. Upload Your Files (from Windows)

**Using PowerShell or Command Prompt:**
```powershell
# Upload main application file
scp "C:\Users\Benedic Cater\SynologyDrive\Software Development\Python Codes\Sales_Order_Inventory_App.py" rgbadmins@your-server-ip:/home/rgbadmins/Streamlit_Apps/so_solvang/

# Upload requirements.txt
scp "C:\Users\Benedic Cater\SynologyDrive\Software Development\Python Codes\requirements.txt" rgbadmins@your-server-ip:/home/rgbadmins/Streamlit_Apps/so_solvang/

# Upload product_images folder
scp -r "C:\Users\Benedic Cater\SynologyDrive\Software Development\Python Codes\product_images" rgbadmins@your-server-ip:/home/rgbadmins/Streamlit_Apps/so_solvang/

# Upload any CSV files if needed
# scp "path\to\your\file.csv" rgbadmins@your-server-ip:/home/rgbadmins/Streamlit_Apps/so_solvang/
```

**Or use FileZilla/WinSCP:**
- Connect via SFTP to your server
- Navigate to `/home/rgbadmins/Streamlit_Apps/so_solvang/`
- Upload all necessary files

### 4. On Ubuntu Server - Create Virtual Environment
```bash
cd /home/rgbadmins/Streamlit_Apps/so_solvang
python3 -m venv venv
source venv/bin/activate
```

### 5. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 6. Install ODBC Driver (for SQL Server connection)
```bash
sudo apt install -y unixodbc unixodbc-dev
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt update
sudo ACCEPT_EULA=Y apt install -y msodbcsql18
```

### 7. Create Streamlit Config
```bash
mkdir -p ~/.streamlit
cat > ~/.streamlit/config.toml << EOF
[server]
port = 8501
address = "0.0.0.0"
enableCORS = false
enableXsrfProtection = true

[browser]
gatherUsageStats = false
EOF
```

### 8. Test the Application
```bash
cd /home/rgbadmins/Streamlit_Apps/so_solvang
source venv/bin/activate
streamlit run Sales_Order_Inventory_App.py
```

Access at: `http://your-server-ip:8501`

Press `Ctrl+C` to stop.

### 9. Create Systemd Service (Run in Background)

Create service file:
```bash
sudo nano /etc/systemd/system/streamlit-app.service
```

Paste this content:
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

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable streamlit-app.service
sudo systemctl start streamlit-app.service
sudo systemctl status streamlit-app.service
```

### 10. Configure Firewall
```bash
sudo ufw allow 8501/tcp
sudo ufw reload
```

## Useful Commands

### Check Service Status
```bash
sudo systemctl status streamlit-app
```

### View Logs
```bash
sudo journalctl -u streamlit-app -f
```

### Restart Service
```bash
sudo systemctl restart streamlit-app
```

### Stop Service
```bash
sudo systemctl stop streamlit-app
```

### Start Service
```bash
sudo systemctl start streamlit-app
```

## File Structure
```
/home/rgbadmins/Streamlit_Apps/so_solvang/
├── Sales_Order_Inventory_App.py
├── requirements.txt
├── venv/
│   └── (virtual environment files)
├── product_images/
│   └── (your product images)
└── (any CSV files or other data files)
```

## Troubleshooting

### If service fails to start:
```bash
# Check logs
sudo journalctl -u streamlit-app -n 50

# Verify file paths
ls -la /home/rgbadmins/Streamlit_Apps/so_solvang

# Test manually
cd /home/rgbadmins/Streamlit_Apps/so_solvang
source venv/bin/activate
streamlit run Sales_Order_Inventory_App.py
```

### Check if port is in use:
```bash
sudo netstat -tulpn | grep 8501
```

### Verify Python packages:
```bash
cd /home/rgbadmins/Streamlit_Apps/so_solvang
source venv/bin/activate
pip list
```

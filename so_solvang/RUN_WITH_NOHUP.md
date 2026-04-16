# Running Streamlit with nohup

## Quick Command

```bash
cd /home/rgbadmins/Streamlit_Apps/so_solvang
source venv/bin/activate
nohup streamlit run Sales_Order_Inventory_App.py --server.port 8509 --server.maxUploadSize 500 > streamlit.log 2>&1 &
```

## Command Explanation

- **`nohup`** - Runs the command immune to hangups, continues running even after you close the terminal
- **`streamlit run Sales_Order_Inventory_App.py`** - Runs your Streamlit application
- **`--server.port 8509`** - Sets the port to 8509 (change as needed)
- **`--server.maxUploadSize 500`** - Sets maximum upload size to 500MB
- **`> streamlit.log`** - Redirects standard output to log file
- **`2>&1`** - Redirects error output to the same log file
- **`&`** - Runs the process in the background

## Complete Steps

### 1. Navigate to your app directory
```bash
cd /home/rgbadmins/Streamlit_Apps/so_solvang
```

### 2. Activate virtual environment
```bash
source venv/bin/activate
```

### 3. Run with nohup
```bash
nohup streamlit run Sales_Order_Inventory_App.py --server.port 8509 --server.maxUploadSize 500 > streamlit.log 2>&1 &
```

### 4. Verify it's running
```bash
# Check if process is running
ps aux | grep streamlit

# Or check if port is listening
sudo netstat -tulpn | grep 8509
```

### 5. View logs
```bash
# View last 50 lines
tail -n 50 streamlit.log

# Follow logs in real-time
tail -f streamlit.log
```

## Managing the Process

### Check if running
```bash
ps aux | grep streamlit
```

### Stop the process
```bash
# Find the process ID (PID)
ps aux | grep streamlit

# Kill the process (replace <PID> with actual process ID)
kill <PID>

# Or kill all streamlit processes
pkill -f streamlit
```

### Restart the process
```bash
# Stop first
pkill -f streamlit

# Then start again
cd /home/rgbadmins/Streamlit_Apps/so_solvang
source venv/bin/activate
nohup streamlit run Sales_Order_Inventory_App.py --server.port 8509 --server.maxUploadSize 500 > streamlit.log 2>&1 &
```

## Access the Application

Once running, access it at:
```
http://your-server-ip:8509
```

## Port Options

You can change the port as needed:
- Port 8501 (default): `--server.port 8501`
- Port 8509: `--server.port 8509`
- Port 8080: `--server.port 8080`

## Upload Size Options

Adjust max upload size as needed:
- 100MB: `--server.maxUploadSize 100`
- 500MB: `--server.maxUploadSize 500`
- 1000MB (1GB): `--server.maxUploadSize 1000`

## Firewall Configuration

If using a custom port, make sure to allow it in the firewall:

```bash
# For port 8509
sudo ufw allow 8509/tcp
sudo ufw reload
```

## Advantages of nohup

✅ Simple to use  
✅ Quick setup  
✅ Good for testing  
✅ Survives SSH disconnection  
✅ Easy to view logs  

## Disadvantages of nohup

❌ Doesn't auto-restart on failure  
❌ Won't start automatically on server reboot  
❌ Manual process management  
❌ No automatic recovery from crashes  

## When to Use nohup vs Systemd

**Use nohup for:**
- Quick testing
- Development environments
- Temporary deployments
- When you don't need auto-restart

**Use systemd for:**
- Production environments
- When you need auto-restart on failure
- When you need automatic startup on boot
- When you need better process management

## Troubleshooting

### Process not starting
```bash
# Check if port is already in use
sudo netstat -tulpn | grep 8509

# Check logs for errors
cat streamlit.log
```

### Can't access the application
```bash
# Check if process is running
ps aux | grep streamlit

# Check firewall
sudo ufw status

# Check if port is listening
sudo netstat -tulpn | grep 8509
```

### View full error logs
```bash
tail -n 100 streamlit.log
```


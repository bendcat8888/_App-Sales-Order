#!/bin/bash
# start_streamlit.sh
# Script to start the Streamlit app in background with logging

# Exit immediately on error
set -e

# Navigate to app folder
cd /home/rgbadmins/Stremalit_Apps/so_solvang
source venv/bin/activate

# ONE-LINER COMMAND #
###############################################################################################################################################################
cd "/home/rgbadmins/Stremalit_Apps/so_solvang" && source venv/bin/activate

# for PDF HTML
cd "/home/rgbadmins/Stremalit_Apps/PDF_Architect

# NOHUP Commands #
###############################################################################################################################################################
nohup streamlit run Sales_Order_Inventory_App.py --server.port 8509 --server.maxUploadSize 500 > /home/rgbadmins/Stremalit_Apps/so_solvang/streamlit_app_SO.log 2>&1 &

# for PDF HTML
nohup python3 -m http.server 8512

# Restart VM #
###############################################################################################################################################################
sudo shutdown -r
sudo reboot

# for PDF HTML
sudo docker exec -it waf  nginx -s reload

###############################################################################################################################################################

# Cron setup #
###############################################################################################################################################################
crontab -e
0 * * * * cd /home/rgbadmins/Stremalit_Apps/so_solvang && /home/rgbadmins/Stremalit_Apps/so_solvang/venv/bin/python notification_scheduler.py
###############################################################################################################################################################

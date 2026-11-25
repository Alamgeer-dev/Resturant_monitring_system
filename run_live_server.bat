@echo off
cd /d "%~dp0"
echo Starting Restaurant Detection System on 0.0.0.0:8000
echo LAN:   http://localhost:8000
echo Web:   http://YOUR_PUBLIC_IP:8000  (requires router port-forward / firewall rule)
python main.py
pause

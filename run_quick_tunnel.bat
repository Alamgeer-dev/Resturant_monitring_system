@echo off
cd /d "%~dp0"
echo Starting app + temporary Cloudflare tunnel...
echo Open the https://*.trycloudflare.com URL printed in the tunnel window.
start "Restaurant Detection App" cmd /k python main.py
start "Cloudflare Quick Tunnel" cmd /k cloudflared.exe tunnel --url http://localhost:8000

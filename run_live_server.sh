#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "Starting Restaurant Detection System on 0.0.0.0:8000"
echo "LAN: http://localhost:8000"
echo "Web: http://SERVER_PUBLIC_IP:8000 (open TCP 8000 in firewall/security group)"
python3 main.py

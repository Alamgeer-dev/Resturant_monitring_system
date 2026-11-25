# Live Server Deployment (بغیر Cloudflare)

یہ گائیڈ براہِ راست سرور پر چلانے کے لیے ہے: **VPS with public IP** یا **گھر کی PC + router port forwarding**۔

> نوٹ: VS Code کا "Live Server" ایکسٹینشن صرف static files کے لیے ہے۔ اس پروجیکٹ کو چلانے کے لیے `python main.py` (FastAPI) لازمی ہے۔

---

## 1) VPS پر چلانا (تجویز کردہ)

آپ کو ایک VPS چاہیے جس کا **public IP** ہو (Hetzner, DigitalOcean, AWS Lightsail, یا کوئی بھی)۔

### 1.1 ڈومین نہیں ہے — صرف IP پر چلائیں

```bash
git clone <your-repo-url> restaurant
cd restaurant
cp deploy/.env.example .env
```

`.env` میں:
```env
CAMERA_SOURCE=rtsp://user:pass@192.168.1.64:554/stream
AUTH_USERNAME=admin
AUTH_PASSWORD=change-this-strong-password
```
(USB webcam VPS میں کام نہیں کرے گی؛ RTSP/IP camera یا `data/video.mp4` استعمال کریں۔ فوری ٹیسٹ کے لیے `SIMULATE=true` بھی ہو سکتا ہے۔)

چلائیں:
```bash
docker compose up -d --build
docker compose logs -f restaurant
```

پھر کھولیں:
```
http://SERVER_PUBLIC_IP:8000
```

### 1.2 فائر وال / Security Group کھولیں

VPS پر:
```bash
sudo ufw allow 8000/tcp
sudo ufw reload
```
AWS/GCP/Azure میں/hosting panel میں بھی inbound rule `TCP 8000` شامل کریں۔

> `docker-compose.cloudflare.yml` کو بالکل استعمال نہ کریں — وہ صرف ٹنل کے لیے تھا۔

### 1.3 ڈائریکٹ systemd (Docker کے بغیر)

```bash
sudo apt update
sudo apt install python3-venv -y
sudo mkdir -p /opt/restaurant
sudo cp -r . /opt/restaurant
cd /opt/restaurant
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -c "from ultralytics import YOLO; YOLO('yolo11n.pt')"

sudo cp deploy/systemd/restaurant.service /etc/systemd/system/
sudo nano /etc/systemd/system/restaurant.service
sudo systemctl daemon-reload
sudo systemctl enable --now restaurant
sudo systemctl status restaurant
```

سروس فائل میں `SERVER_HOST=127.0.0.1` ہو تو اُسے `0.0.0.0` کر دیں اگر براہِ راست 8000 پر چلانا ہے (یا nginx استعمال کریں)۔

---

## 2) گھر کی PC کو live server بنانا (Port Forwarding)

اگر آپ کا کیمرہ USB webcam ہے تو یہی طریقہ استعمال کریں۔

1. `config.yaml` میں:
   ```yaml
   server:
     host: 0.0.0.0
     port: 8000
   auth:
     username: admin
     password: "مضبوط-پاسورڈ"
   ```
2. ونڈوز فائر وال میں inbound rule بنائیں: `TCP 8000`۔
3. اپنے PC کا LAN IP معلوم کریں:
   ```powershell
   ipconfig
   ```
   مثلاً `192.168.1.50`۔
4. Router admin پینل میں **Port Forwarding**:
   - External port: `8000`
   - Internal IP: `192.168.1.50`
   - Internal port: `8000`
   - Protocol: TCP
5. اپنا public IP معلوم کریں: https://ifconfig.me
6. کہیں سے بھی کھولیں:
   ```
   http://YOUR_PUBLIC_IP:8000
   ```

 اگر آپ کا ISP static IP نہیں دیتا تو مفت Dynamic DNS استعمال کریں (مثلاً `duckdns.org`) تاکہ IP بدلنے پر بھی ایک ہی نام چلے۔ اس کے لیے ڈومین خریدنے کی ضرورت نہیں۔

---

## 3) HTTPS چاہیے تو (ڈومین کے ساتھ، بغیر Cloudflare)

صرف اُس وقت ممکن ہے جب آپ کے پاس ڈومین ہو جو سرور کی طرف اشارہ کرے:

```bash
sudo apt install nginx certbot python3-certbot-nginx -y
sudo cp deploy/nginx.conf /etc/nginx/conf.d/restaurant.conf
sudo nano /etc/nginx/conf.d/restaurant.conf   # server_name بدلیں
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d dashboard.example.com
```

`deploy/nginx.conf` میں پہلے ہی `/ws` WebSocket اور `/video_feed` (buffering off) کے لیے درست settings ہیں۔

 ڈومین کے بغیر صرف `http://IP:8000` ممکن ہے — براؤزر میں "Not secure" دکھے گا مگر system چلے گا۔

---

## 4) چیک کریں

```bash
curl http://SERVER_IP:8000/api/state
curl -u admin:'پاسورڈ' http://SERVER_IP:8000/api/state
curl -I http://SERVER_IP:8000/video_feed
```

لاگ:
```bash
docker compose logs -f restaurant        # Docker
journalctl -u restaurant -f             # systemd
ونڈوز: python main.py والی PowerShell دیکھیں
```

---

## 5) مسائل

| علامت | حل |
|---|---|
| سائٹ نہیں کھلتی | فائر وال/security group میں 8000 کھولیں؛ سروس چل رہی ہے یا نہیں چیک کریں |
| `Connection refused` | `server.host: 0.0.0.0` اور درست port یقینی بنائیں |
| Dashboard آتا ہے مگر video خالی | RTSP URL/کیمرہ چیک کریں؛ logs دیکھیں |
| کوئی detection نہیں | `MODEL_WEIGHTS` اور class names چیک کریں |
| 401 | Basic auth credentials درست ہیں؟ |
| RTSP کام نہیں کرے | VPN/port-forward؛ USB webcam VPS میں نظر نہیں آئے گی |

**سیکیورٹی:** براہِ راست انٹرنیٹ پر Basic auth ہمیشہ آن رکھیں، مضبوط پاسورڈ استعمال کریں، اور صرف ضروری پورٹ کھولیں۔

# Review + Online Deployment Guide

> **Cloudflare نہیں چاہتے؟** براہِ راست VPS/public IP پر چلانے کے لیے `LIVE_SERVER.md` دیکھیں۔ یہ فائل ٹنل/Nginx کے آپشنز پر ہے۔

## 1) Review کا خلاصہ

**اچھیاں باتیں**
- Detection + tracking + table assignment + DB + UI سب ایک ہی pipeline میں جڑے ہیں۔
- Configuration-driven ہے: کیمرہ، کلاسز، ٹیبل polygons، سرور سب `config.yaml` میں۔
- `simulate` موڈ کی وجہ سے بغیر کیمرے بھی پورا system ٹیسٹ ہو سکتا ہے۔
- SQLite میں entry time، sessions، events محفوظ ہیں اور CSV export بھی ہے۔

** Deployment سے پہلے جو باتیں ٹھیک کیں**
| مسئلہ | حل |
|---|---|
| `uvicorn.run` کے بعد `system.stop()` نہیں چلتا تھا | `try/finally` میں شامل کیا |
| Multi-worker سے state ٹوٹ سکتا تھا | `workers=1` لازمی کر دیا |
| کوئی authentication نہیں تھا | optional HTTP Basic auth شامل کیا (`auth.username/password`) |
| Container/VPS میں config ایڈٹ کرنا پڑتا تھا | environment overrides شامل کیے (`CAMERA_SOURCE`, `SERVER_PORT`, ...) |
| DB container کے اندر ضائع ہو سکتا تھا | `./data` کو volume میں دیا |
| RTSP پاسورڈ config میں لکھنا | `.env` / secret میں رکھنے کا طریقہ دیا |

**اہم حقیقت:** اگر آپ کا کیمرہ USB webcam ہے تو وہ صرف اُسی PC پر چلے گا جس سے جڑا ہے۔ کلاؤڈ پر صرف اُس وقت چلے گا جب کیمرہ IP/RTSP ہو یا مقامی PC پر چل کر ٹنل کے ذریعے آن لائن دکھایا جائے۔

---

## 2) طریقہ A — مقامی PC + Cloudflare Tunnel

یہ تجویز کردہ طریقہ ہے۔ کیمرہ آپ کی PC کے پاس رہتا ہے، آپ کو router port open کرنے کی ضرورت نہیں، اور آپ کو مفت HTTPS URL ملتا ہے۔

### قدم 0 — فوری ٹیسٹ (بغیر ڈومین، ابھی کر سکتے ہیں)

1. Cloudflared ڈاؤنلوڈ کریں: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/  
   (Windows: `cloudflared-windows-amd64.exe` کو `cloudflared.exe` کا نام دے کر project فولڈر میں رکھیں)۔
2. ایپ چلائیں:
   ```powershell
   python main.py
   ```
3. دوسری PowerShell میں:
   ```powershell
   .\cloudflared.exe tunnel --url http://localhost:8000
   ```
4. آؤٹ پٹ میں کچھ ایسا آئے گا:
   ```
   https://a1b2c3d4-xxxx.trycloudflare.com
   ```
   اسی URL کو کسی بھی جگہ سے یا فون سے کھول کر dashboard چیک کریں۔

> یہ **عارضی** URL ہے، ہر بار بدلتی ہے اور account/ڈومین کی ضرورت نہیں۔ مستقل URL کے لیے اگلا قدم دیکھیں۔  
> سہولت کے لیے `run_quick_tunnel.bat` بھی بنا دیا گیا ہے — اسے ڈبل کلک کریں (شرط: `cloudflared.exe` project فولڈر میں ہو)۔

### قدم 1 — مستقل URL کے لیے ڈومین حاصل کریں

آپ کے پاس ابھی ڈومین نہیں، اس لیے:
- Cloudflare Dashboard → **Domain Registration → Register a domain** سے نیا ڈومین خریدیں (سالانہ تقریباً $10)، **یا**
- Namecheap جیسے ریجسٹرار سے ڈومین خرید کر اس کے nameservers Cloudflare والے کر دیں۔
- Cloudflare Dashboard → **Add a site** → ڈومین ٹائپ کریں → Free plan → DNS scan → Nameservers بدلیں → statuses `Active` ہونے تک انتظار کریں۔

### قدم 2 — Basic auth آن کریں (expose کرنے سے پہلے)

`config.yaml` کے آخر میں:
```yaml
auth:
  username: admin
  password: "اپنا-مضبوط-پاسورڈ"
```

### قدم 3 — Named tunnel + Public Hostname (آسان ترین طریقہ)

1. https://dash.cloudflare.com → **Zero Trust → Networks → Tunnels → Create a tunnel** → نام `restaurant-detect` → **Save tunnel**۔
2. اگلے اسکرین میں **Windows** ٹیب دکھائیں اور دیا گیا **token** کاپی کریں (یہ لمبا `eyJ...` والا ٹیکسٹ ہوتا ہے)۔
3. Admin PowerShell میں:
   ```powershell
   .\cloudflared.exe service install eyJ...آپ_کا_ٹوکن...
   ```
   اب Cloudflared بطور Windows service چلے گا۔
4. اُسی ٹنل میں **Public Hostname → Add a public hostname**:
   - Subdomain: `restaurant`
   - Domain: `آپکاڈومین.com`
   - Service Type: `HTTP`
   - URL: `localhost:8000`
5. اب مستقل URL کھلے گا:
   ```
   https://restaurant.آپکاڈومین.com
   ```

> متبادل (config فائل والا طریقہ): `%USERPROFILE%\.cloudflared\config.yml` میں `tunnel: <UUID>`، `credentials-file: ...json` اور `ingress` لکھ کر `cloudflared tunnel run restaurant-detect` چلائیں — تفصیل پرانے deployment گائیڈ میں محفوظ ہے۔ اوپر والا token طریقہ آسان ہے۔

> بہتر سیکیورٹی: Cloudflare Access سے ایک ای میل/OTP گیٹ لگا دیں، تب ایپ کا Basic auth بھی رہے گا اور ڈبل حفاظت ہوگی۔

> بہتر سیکیورٹی: Cloudflare Access سے ایک ای میل/OTP گیٹ لگا دیں، تب ایپ کا Basic auth بھی رہے گا اور ڈبل حفاظت ہوگی۔

---

## 3) طریقہ B — VPS + Docker (IP camera کے لیے بہترین)

Hetzner / DigitalOcean / AWS Lightsail جیسی VPS پر یہ طریقہ استعمال کریں۔

### قدم 1 — فائلز تیار کریں
```bash
git clone <آپ کی repo URL> restaurant
cd restaurant
cp deploy/.env.example .env
```

`.env` میں کیمرہ اور پاسورڈ دیں:
```env
CAMERA_SOURCE=rtsp://user:pass@192.168.1.64:554/stream
AUTH_USERNAME=admin
AUTH_PASSWORD=change-this-strong-password
```

### قدم 2 — چلائیں
```bash
docker compose up -d --build
docker compose logs -f restaurant
```
Dashboard: `http://<VPS-IP>:8000`

### قدم 3 — بغیر پورٹ کھولے HTTPS (تجویز)
Cloudflare dashboard میں **Remote-managed tunnel** بنائیں اور ٹوکن کاپی کریں:
```env
CLOUDFLARE_TUNNEL_TOKEN=آپ_کا_ٹوکن
```
پھر:
```bash
docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml up -d --build
```
اب آپ کو VPS پر 8000 کھولنے کی ضرورت نہیں —Cloudflare tunnel سب سنبھال لے گا۔

### قدم 4 — اپ ڈیٹ / ریسٹارٹ
```bash
docker compose pull
docker compose up -d --build
docker compose restart restaurant
```

**نوٹ:** RTSP کیمرہ VPS تک پہنچنے کے لیے یا تو کیمرہ پبلک/پورٹ فارورڈ ہو، یا بہتر یہ کہ کیمرے اور VPS کے درمیان WireGuard VPN بنائیں۔ USB webcam VPS میں کبھی نظر نہیں آئے گی۔

---

## 4) طریقہ C — VPS + Nginx + Let's Encrypt (کلاسیکی)

اگر آپ conventional VM چاہتے ہیں:

```bash
sudo apt update
sudo apt install python3-venv nginx certbot python3-certbot-nginx -y
sudo mkdir -p /opt/restaurant
sudo cp -r . /opt/restaurant
cd /opt/restaurant
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -c "from ultralytics import YOLO; YOLO('yolo11n.pt')"
```

Systemd service:
```bash
sudo cp deploy/systemd/restaurant.service /etc/systemd/system/
sudo nano /etc/systemd/system/restaurant.service   # RTSP URL + پاسورڈ بدلیں
sudo systemctl daemon-reload
sudo systemctl enable --now restaurant
sudo systemctl status restaurant
```

Nginx:
```bash
sudo cp deploy/nginx.conf /etc/nginx/conf.d/restaurant.conf
sudo nano /etc/nginx/conf.d/restaurant.conf        # dashboard.example.com بدلیں
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d dashboard.example.com
```

---

## 5) PaaS (Render / Railway / Fly.io) — کب کام کرے گا؟

صرف اس وقت جب:
- کیمرہ RTSP/public URL ہو (webcam نہیں)، اور
- پلیٹ فارم پر **persistent volume** ہو (SQLite کے لیے)، اور
- سروس سو نہ جائے (ورنہ camera loop رکے گا)۔

ان پلیٹ فارمز پر `CMD` یہ ہوگا: `python main.py`، env vars وہی جو `.env.example` میں ہیں۔ free-tier sleep کی وجہ سے حقیقی time monitoring کے لیے یہ کم موزوں ہے۔

---

## 6) Deployment کے بعد چیک کریں

```bash
curl http://localhost:8000/api/state
curl http://localhost:8000/api/events?limit=10
curl -I http://localhost:8000/video_feed
```
اندازہ ہونا چاہیے:
```json
{"totals":{"people":0,"tables":4,"occupied":0,"free":4,"served":0}, ...}
```

اگر Basic auth آن ہے:
```bash
curl -u admin:'پاسورڈ' http://localhost:8000/api/state
```

---

## 7) عام مسائل

| علامت | وجہ / حل |
|---|---|
| `Cannot open camera source` | غلط `CAMERA_SOURCE`; پہلے `python scripts/check_camera.py` چلائیں |
| Dashboard کھلتا ہے مگر video خالی | کیمرہ loop ٹوٹ گیا؛ logs دیکھیں، `fps_limit` اور `imgsz` کم کریں |
| WebSocket disconnected | Nginx میں `Upgrade` headers ہیں یا نہیں؛ `deploy/nginx.conf` دیکھیں |
| کوئی Detection نہیں | `MODEL_WEIGHTS` غلط یا class names میچ نہیں; `python -c "from ultralytics import YOLO; print(YOLO('yolo11n.pt').names)"` |
| ڈیٹا گائب | `./data` volume mount ہے یا نہیں چیک کریں |
| RTSP پاسورڈ لیک | `.env` میں رکھیں اور `.gitignore` میں `.env` شامل کریں |

**سیکیورٹی یاد رکھیں:** `server.host: 0.0.0.0` صرف مقامی نیٹ ورک کے لیے ہے۔ انٹرنیٹ پر صرف Cloudflare Access/Tunnel یا Nginx+HTTPS کے پیچھے لائیں، اور Basic auth کا پاسورڈ ہمیشہ بدلیں۔

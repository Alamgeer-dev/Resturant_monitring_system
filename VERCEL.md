# Vercel Deployment — کیا ممکن ہے؟

## مختصر جواب

**پورا project Vercel پر کام نہیں کرے گا۔** Vercel serverless/static پلیٹ فارم ہے؛ آپ کا system ایک مسلسل چلنے والا Python process ہے جسے کیمرہ، threads، WebSocket، MJPEG video stream اور SQLite چاہیے۔

| حصہ | Vercel پر |
|---|---|
| Static dashboard (HTML/CSS/JS) | ✅ ہاں |
| `python main.py` camera loop | ❌ نہیں |
| USB webcam | ❌ نہیں |
| RTSP کیمرے کا مسلسل loop | ❌ فنکشن ٹائم آؤٹ کی وجہ سے |
| SQLite کی مقامی فائل | ❌ serverless FS عارضی |
| WebSocket + MJPEG stream | ⚠️ قابلِ اعتماد نہیں |
| Detection / Tracking | ❌ |

`vercel.json` اس لیے شامل کیا گیا ہے کہ **صرف frontend** ڈیپلائے ہو سکے۔

---

## Hybrid طریقہ (یہ کام کرے گا)

- **Backend:** آپ کا live server / VPS / Render / Railway / Fly.io — وہاں `python main.py` یا Docker چلے گا۔
- **Frontend:** Vercel پر صرف `src/static`۔

### قدم 1 — Backend تیار کریں

VPS پر (جیسا کہ `LIVE_SERVER.md` میں ہے):
```bash
docker compose up -d --build
```

Backend کی `config.yaml` میں Vercel domain کو CORS کی اجازت دیں:
```yaml
server:
  cors_origins:
    - "https://آپ-کی-app.vercel.app"
```

اگر backend پر Basic auth آن ہے تو credentials browser میں دینی ہوں گی۔

### قدم 2 — Frontend کو backend کا پتہ بتائیں

`src/static/index.html` میں:
```html
<script>window.RDS_API_BASE = "https://backend.example.com";</script>
```

یہی value `/api/*`, `/video_feed` اور `/ws` کے لیے استعمال ہوگی۔

> Vercel rewrites سے proxy کرنے کی کوشش نہ کریں — MJPEG/WebSocket long-lived streams Vercel کے پروکسی میں بفر/ٹائم آؤٹ ہو سکتی ہیں۔ براہِ راست backend URL بہتر ہے۔

### قدم 3 — GitHub → Vercel

1. پروجیکٹ کو GitHub پر push کریں۔
2. https://vercel.com → **Add New → Project** → repository import کریں۔
3. Vercel خود بخود `vercel.json` پڑھے گا:
   - Output Directory: `src/static`
   - Build Command: خالی
4. **Deploy** دبائیں۔
5. ملنے والا `https://...vercel.app` لنک اصل dashboard دکھائے گا، مگر ڈیٹا آپ کے backend سے آئے گا۔

---

## سیدھا راستہ (زیادہ آسان)

اگر آپ کو صرف ایک کام کرنے والا آن لائن لنک چاہیے تو **Vercel کی بجائے براہِ راست live server** استعمال کریں (`LIVE_SERVER.md`) — وہاں frontend + backend + camera ایک ہی جگہ چلتے ہیں اور لنک فوراً کام کرتا ہے۔

---

## خلاصہ

- Vercel صرف **خوبصورت UI** دے سکتا ہے، وہ بھی تب جب backend کہیں اور چل رہا ہو۔
- کیمرہ والا حقیقی system VPS/live server پر ہی چلے گا۔
- میں آپ کے لیے hybrid (Vercel UI + VPS backend) مکمل config کر سکتا ہوں اگر آپ بتادیں کہ backend کس URL پر چلے گا۔

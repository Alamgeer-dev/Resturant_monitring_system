# Restaurant Detection System (Camera + YOLO + Tracking)

یہ نظام ایک fixed camera سے لوگوں اور ٹیبلز کو detect + track کرتا ہے، ہر شخص کی entry time ریکارڈ کرتا ہے، ہر ٹیبل پر موجود افراد کی تعداد، ٹیبل free/occupied، اور یہ کہ serve ہو چکا ہے یا نہیں — سب کچھ live dashboard میں دکھاتا ہے۔

## کیا کیا کرتا ہے

| Feature | طریقہ |
|---|---|
| ریسٹورنٹ میں کل لوگ | YOLO person detection + ByteTrack IDs |
| ہر فرد کی entry time | جب بھی نیا track ID آئے، اُس وقت کو `people.first_seen` میں محفوظ |
| ٹیبلز کی تعداد | COCO کا `dining table` class یا آپ کا training کیا ہوا `table` model |
| ہر ٹیبل پر کتنے لوگ | شخص کے centre کو ٹیبل کے polygon/nearest table سے میچ |
| Table free / occupied | اُس ٹیبل سے منسلک active tracks کی تعداد |
| Served یا نہیں | `bowl/plate/cup/food` detection (auto) یا dashboard بٹن (manual) |
| History / export | SQLite + CSV + live events |

## فائلوں کی ساخت

```
main.py                 camera loop + web server شروع کرتا ہے
config.yaml            camera, model, classes, table polygons, server设置
src/database.py         SQLite (people, tables, sessions, events)
src/models.py           YOLO detector + ByteTrack (+ simulate mode)
src/table_manager.py    person→table assignment, occupancy, served logic, overlay
src/app.py              FastAPI: /api/state, /ws, /video_feed, serve/clear APIs
src/static/             Live dashboard (HTML/CSS/JS)
scripts/                camera check, frame capture, ROI calibration, dataset split, training
datasets/, models/, runs/   ڈیٹا اور ماڈلز
```

## انسٹالیشن

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

پہلی بار `yolo11n.pt` خود بخود ڈاؤنلوڈ ہو جائے گا (انٹرنیٹ درکار)۔

## چلانا

### 1) بغیر camera/model (UI ٹیسٹ)
`config.yaml` میں `model.simulate: true` کریں، پھر:
```powershell
python main.py
```
 browser میں کھولیں: http://localhost:8000

### 2) اصل webcam
```powershell
python scripts/check_camera.py        # پہلے کیمرا index چیک کریں
python main.py --source 0
```
`config.yaml` میں `camera.source: 0` بھی ہو سکتا ہے۔

### 3) IP camera / RTSP
```powershell
python main.py --source "rtsp://user:password@192.168.1.64:554/stream"
```

### 4) ویڈیو فائل سے ٹیسٹ
```powershell
python main.py --source "data/video.mp4"
```

### 5) صرف camera loop (بغیر web UI)
```powershell
python main.py --no-server
```

ونڈوز کے لیے `run.bat` بھی بنا دیا گیا ہے — ڈبل کلک کریں۔

## ٹیبل پولی گون کیلیبریٹ کرنا (اہم)

fixed camera کے لیے سب سے درست طریقہ یہ ہے کہ آپ ایک frame پر ہر ٹیبل کے چار کونے کلک کریں:

```powershell
python scripts/calibrate_rois.py --source 0
```

- Left click = نقطہ شامل کریں
- `n` = ٹیبل ختم، اگلا ٹیبل شروع
- `u` = پچھلا نقطہ ہٹائیں
- `q` = محفوظ کریں اور باہر نکلیں

اس سے `config.yaml` میں `tables.rois` خود بخود لکھ دی جائیں گی۔ نقاط normalized (`0..1`) ہوتے ہیں۔

اگر آپ کے پاس polygon نہیں بنانے کا وقت ہے تو `tables.mode: auto` کر دیں —_system detected `dining table` boxes کو ٹیبل سمجھے گا (کم درست لیکن فوری)۔

## Dataset اور Model Training — مکمل گائیڈ

### A. لوگ (person)
شروع کے لیے کوئی dataset نہیں چاہیے: `yolo11n.pt` (COCO) میں `person` پہلے سے ہے۔
اگر آپ کے ریسٹورنٹ کی روشنی/زاویے مختلف ہیں تو بہتری کے لیے:
- 300–800 تصاویر اپنے کیمرے سے لیں (`scripts/capture_frames.py`)۔
- صرف `person` class labeling کریں (CVAT / Roboflow / LabelImg)۔
- `table` dataset والی طرح split + train کریں، پھر `model.weights` میں نیا weights دے دیں۔

### B. ٹیبلز (table)
- **تصاویر:** اپنے اصل کیمرے سے 200–500 تصاویر، مختلف اوقات، روشنی، اور مختلف seating حالات کے ساتھ۔
- **Labeling:** ہر میز کے گرد tight bounding box، class name `table` (انڈیکس 0)۔ اگر چاہیں تو `chair` بھی الگ class کر سکتے ہیں۔
- **Tools:** Roboflow (آسان ترین)، CVAT، یا LabelImg۔ YOLO txt فارمٹ:
  ```
  0 0.512 0.438 0.240 0.180
  ```
  مطلب: `class x_center y_center width height` — سب `0..1` میں normalize۔
- **Split:** تقریباً 80% train، 10% val، 10% test۔
  ```powershell
  python scripts/prepare_dataset.py --images dataset/raw/images --labels dataset/raw/labels --out dataset/table --names table --val 0.1 --test 0.1
  ```
- **Train:**
  ```powershell
  python scripts/train.py --data dataset/table/data.yaml --model yolo11n.pt --epochs 100 --name table_model --copy-to models/table.pt
  ```
- **استعمال:** `config.yaml` میں `model.weights: models/table.pt` اور `classes.table: [table]`۔

### C. Served detection (plate / food)
دو طریقے:

1. **Manual (spimple):** dashboard میں ہر ٹیبل کے نیچے **Mark served** بٹن۔ `tables.serve_mode: manual`۔
2. **Auto:** `bowl/cup/fork/knife/spoon/sandwich/pizza/cake` COCO classes پہلے سے موجود ہیں۔ بہتر نتائج کے لیے اپنا `plate`/`food` model ٹرین کریں:
   - 200–400 تصاویر جن میں خالی پلیٹ، کھانا، tray، کپ وغیرہ واضح ہوں۔
   - Classes مثلاً `plate, food, cup`۔
   - ایک ہی model میں `table` بھی شامل کر سکتے ہیں تاکہ ایک ہی weights دونوں کام کرے۔
   ```powershell
   python scripts/prepare_dataset.py --images dataset/raw/serve_images --labels dataset/raw/serve_labels --out dataset/serve --names plate,food,cup --val 0.1 --test 0.1
   python scripts/train.py --data dataset/serve/data.yaml --model yolo11n.pt --epochs 100 --name serve_model --copy-to models/serve.pt
   ```
   پھر `config.yaml`:
   ```yaml
   model:
     weights: models/serve.pt
   classes:
     person: [person]
     table: [table]
     serve: [plate, food, cup, bowl]
   ```
   `serve_delay_sec` بتائیں کہ پلیٹ کم از کم اتنے سیکنڈ ٹیبل کے علاقے میں رہے تو ہی "served" مانا جائے (غلط detection سے بچنے کے لیے)۔

> نوٹ: اگر آپ ایک ہی model میں `person, table, plate, food` سب ٹرین کروں تو بھی یہی system کام کرے گا — بس `classes` میں درست نام لکھ دیں۔

### D. Entry time اور counts
ان کے لیے کسی dataset کی ضرورت نہیں — ByteTrack ہر detection کو مستقل ID دیتا ہے۔ جب نیا ID پہلی بار آئے، اُسی لمحے کو entry time سمجھ کر DB میں لکھا جاتا ہے؛ جب وہ ID `lose_grace_sec` تک غائب رہے تو "left" ہو جاتا ہے۔

## Training کے بعد چیک کریں

```powershell
python -c "from ultralytics import YOLO; m=YOLO('models/table.pt'); print(m.names); m.val(data='dataset/table/data.yaml')"
```
mAP@0.5 تقریباً 0.7+ اچھا شروع ہے۔ اگر پریکٹس میں غلط detect ہو رہا ہے تو زیادہ تصاویر، بہتر labeling، اور `model.conf` تھوڑا بڑھا کر دیکھیں۔

## Dashboard / API

- `http://localhost:8000/` — live UI
- `GET /api/state` — موجودہ حالت JSON
- `GET /api/events?limit=100` — واقعات
- `GET /api/export.csv` — CSV ڈاؤنلوڈ
- `POST /api/tables/T1/serve` — دستی طور پر served mark
- `POST /api/tables/T1/clear` — ٹیبل صاف/free
- `GET /video_feed` — MJPEG video (overlays کے ساتھ)
- `ws://localhost:8000/ws` — live state updates

## تجاویز / مسائل

- کیمرہ ہر وقت ایک ہی جگہ پر رکھیں، ورنہ polygon دوبارہ کیلیبریٹ کریں۔
- ٹیبل polygons میں کرسیاں بھی شامل کریں تاکہ بیٹھا ہوا شخص polygon کے اندر آئے۔
- اگر GPU نہیں ہے تو `model.device: cpu` اور `imgsz: 416` کر کے رفتار بہتر کریں۔
- RTSP میں ویدیو رک جائے تو `camera.fps_limit: 15` اور `imgsz: 416` آزمائیں۔
- لوگ ایک دوسرے کے پیچھے چھپ جائیں تو tracking ٹوٹ سکتی ہے — اضافی کیمرہ یا بہتر model مدد کرتا ہے۔
- ڈیٹا بیس فائل: `data/restaurant.db` — اگر صاف کرنا ہو تو بس یہ فائل ڈیلیٹ کریں، system دوبارہ بنائے گا۔

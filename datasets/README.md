# Dataset folder

یہاں آپ کی تصاویر اور labels رکھیں۔ تجویز کردہ فولڈرز:

```
datasets/
  raw/
    tables/        # ٹیبل ٹریننگ کے لیے خام تصاویر
    serve_images/  # پلیٹ/کھانا/کپ کی تصاویر
    labels/        # YOLO .txt لیبلز (تصویر والی فائل کے ہم نام)
  table/           # prepare_dataset.py سے بنا ہوا (images/train, labels/train, data.yaml)
  serve/           # اسی طرح
```

YOLO label فارمٹ (ایک لائن فی object):
```
<class_id> <x_center> <y_center> <width> <height>
```
تمام قدریں `0..1` میں (image width/height سے تقسیم)۔

شروعات کے لیے:
```powershell
python scripts/capture_frames.py --source 0 --out datasets/raw/tables --count 300 --interval 0.5
python scripts/prepare_dataset.py --images datasets/raw/tables --labels datasets/raw/labels --out datasets/table --names table --val 0.1 --test 0.1
python scripts/train.py --data datasets/table/data.yaml --model yolo11n.pt --epochs 100 --name table_model --copy-to models/table.pt
```

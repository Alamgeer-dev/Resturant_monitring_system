# Models folder

یہاں آپ کے train شدہ `.pt` weights رکھیں۔

- `yolo11n.pt` — COCO pretrained، پہلی بار خود ڈاؤنلوڈ ہوتا ہے۔ اس میں `person`, `dining table`, `bowl`, `cup` وغیرہ موجود ہیں۔
- `models/table.pt` — صرف/زیادہ تر ٹیبلز کے لیے آپ کا model۔
- `models/serve.pt` — پلیٹ/کھانا/کپ کے لیے آپ کا model۔

استعمال کے لیے `config.yaml` میں:
```yaml
model:
  weights: models/table.pt
classes:
  person: [person]
  table: [table]
  serve: [plate, food, cup, bowl]
```

اگر ایک ہی model میں سب classes ہوں تو اُسی weights کا راستہ دیں اور `classes` میں وہی نام رکھیں جو `model.names` میں ہیں۔

"""Train a YOLO model for tables / plates / food.

Usage:
  python scripts/train.py --data dataset/table/data.yaml --model yolo11n.pt --epochs 100 --name table_model
  python scripts/train.py --data dataset/serve/data.yaml --model yolo11n.pt --epochs 100 --name serve_model
"""
import argparse
import os
import shutil

from ultralytics import YOLO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="dataset/table/data.yaml")
    ap.add_argument("--model", default="yolo11n.pt")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default="", help="cpu / 0 / empty=auto")
    ap.add_argument("--name", default="restaurant_model")
    ap.add_argument("--copy-to", default="", help="optional destination for best.pt")
    args = ap.parse_args()

    model = YOLO(args.model)
    kwargs = dict(data=args.data, epochs=args.epochs, imgsz=args.imgsz,
                  batch=args.batch, project="runs/train", name=args.name)
    if args.device:
        kwargs["device"] = args.device
    results = model.train(**kwargs)

    best = os.path.join("runs", "train", args.name, "weights", "best.pt")
    print(f"\n[INFO] Training finished. Best weights: {best}")
    print(results)
    if args.copy_to:
        os.makedirs(os.path.dirname(args.copy_to) or ".", exist_ok=True)
        shutil.copy2(best, args.copy_to)
        print(f"[INFO] Copied to {args.copy_to}")


if __name__ == "__main__":
    main()

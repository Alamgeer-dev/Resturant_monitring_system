"""Split images/labels into train/val/test and write YOLO data.yaml.

Expected layout (YOLO format):
  dataset/raw/images/*.jpg
  dataset/raw/labels/*.txt   (optional at first; add before training)

Usage:
  python scripts/prepare_dataset.py --images dataset/raw/images --labels dataset/raw/labels \
      --out dataset/table --names table --val 0.1 --test 0.1
"""
import argparse
import os
import random
import shutil

import yaml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", default="dataset/raw/images")
    ap.add_argument("--labels", default="dataset/raw/labels")
    ap.add_argument("--out", default="dataset/table")
    ap.add_argument("--names", default="table", help="comma separated class names in label-id order")
    ap.add_argument("--val", type=float, default=0.1)
    ap.add_argument("--test", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)
    images = sorted([f for f in os.listdir(args.images) if f.lower().endswith((".jpg", ".jpeg", ".png"))])
    if not images:
        raise SystemExit(f"No images found in {args.images}")

    random.shuffle(images)
    n = len(images)
    n_val = int(n * args.val)
    n_test = int(n * args.test)
    splits = {
        "train": images[n_val + n_test:],
        "val": images[:n_val],
        "test": images[n_val:n_val + n_test],
    }

    has_labels = os.path.isdir(args.labels)
    for split, files in splits.items():
        img_dir = os.path.join(args.out, "images", split)
        os.makedirs(img_dir, exist_ok=True)
        if has_labels:
            os.makedirs(os.path.join(args.out, "labels", split), exist_ok=True)
        for f in files:
            shutil.copy2(os.path.join(args.images, f), os.path.join(img_dir, f))
            if has_labels:
                stem = os.path.splitext(f)[0] + ".txt"
                src = os.path.join(args.labels, stem)
                dst = os.path.join(args.out, "labels", split, stem)
                if os.path.exists(src):
                    shutil.copy2(src, dst)
                else:
                    open(dst, "w", encoding="utf-8").close()

    names = [x.strip() for x in args.names.split(",") if x.strip()]
    data = {
        "path": os.path.abspath(args.out),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "nc": len(names),
        "names": {i: name for i, name in enumerate(names)},
    }
    data_path = os.path.join(args.out, "data.yaml")
    with open(data_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False)
    print(f"Wrote {data_path} ({len(splits['train'])} train / {len(splits['val'])} val / {len(splits['test'])} test)")
    if not has_labels:
        print("[WARN] No labels folder found. Label the images before training.")


if __name__ == "__main__":
    main()

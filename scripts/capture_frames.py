"""Capture frames from camera/RTSP/video for dataset collection.

Usage:
  python scripts/capture_frames.py --source 0 --out dataset/raw/tables --count 300 --interval 0.5
"""
import argparse
import os
import time

import cv2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="0", help="camera index, RTSP URL, or video path")
    ap.add_argument("--out", default="dataset/raw/tables")
    ap.add_argument("--count", type=int, default=200)
    ap.add_argument("--interval", type=float, default=0.5)
    ap.add_argument("--prefix", default="frame")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    cap = cv2.VideoCapture(args.source)
    if not cap.isOpened():
        raise SystemExit(f"Cannot open source: {args.source}")

    i = 0
    last = 0.0
    print("Capturing... press 'q' in the preview window to stop early.")
    try:
        while i < args.count:
            ok, frame = cap.read()
            if not ok:
                break
            if time.time() - last >= args.interval:
                path = os.path.join(args.out, f"{args.prefix}_{i:05d}.jpg")
                cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
                i += 1
                last = time.time()
                if i % 25 == 0:
                    print(f"saved {i}/{args.count}")
            cv2.imshow("Capture", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
    print(f"Done: {i} images in {args.out}")


if __name__ == "__main__":
    main()

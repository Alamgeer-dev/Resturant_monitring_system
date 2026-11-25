"""Click table polygons on a camera frame and write them into config.yaml.

Controls:
  Left click      add polygon point
  'n'             finish current table and start next
  'u'             undo last point
  'q'             save config and quit

Usage:
  python scripts/calibrate_rois.py --source 0
"""
import argparse
import os

import cv2
import numpy as np
import yaml

STATE = {"points": [], "rois": [], "frame": None}


def draw():
    img = STATE["frame"].copy()
    for idx, roi in enumerate(STATE["rois"], start=1):
        pts = np.asarray([[int(x * img.shape[1]), int(y * img.shape[0])] for x, y in roi["polygon"]], np.int32)
        cv2.polylines(img, [pts], True, (0, 200, 0), 2)
        cv2.putText(img, roi["id"], tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    pts = np.asarray(STATE["points"], np.int32)
    if len(pts):
        cv2.polylines(img, [pts], False, (0, 160, 255), 2)
        for p in pts:
            cv2.circle(img, tuple(p), 4, (0, 160, 255), -1)
    cv2.putText(img, "Left click: point | n: next table | u: undo | q: save & quit",
                (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imshow("Table ROI calibration", img)


def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        STATE["points"].append((x, y))
        draw()
    elif event == cv2.EVENT_MBUTTONDOWN:
        STATE["points"].pop() if STATE["points"] else None
        draw()


def finish_table():
    pts = STATE["points"]
    if len(pts) >= 3:
        h, w = STATE["frame"].shape[:2]
        idx = len(STATE["rois"]) + 1
        STATE["rois"].append({
            "id": f"T{idx}",
            "label": f"Table {idx}",
            "polygon": [[round(x / w, 4), round(y / h, 4)] for x, y in pts],
        })
        STATE["points"] = []
    draw()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="0")
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.source)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise SystemExit(f"Cannot read a frame from: {args.source}")

    STATE["frame"] = frame
    cv2.namedWindow("Table ROI calibration")
    cv2.setMouseCallback("Table ROI calibration", on_mouse)
    draw()

    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord("n"):
            finish_table()
        elif key == ord("u"):
            if STATE["points"]:
                STATE["points"].pop()
            draw()
        elif key == ord("q"):
            finish_table()
            break
    cv2.destroyAllWindows()

    with open(args.config, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    cfg.setdefault("tables", {})["rois"] = STATE["rois"]
    cfg["tables"]["mode"] = "roi"
    with open(args.config, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False, allow_unicode=True)
    print(f"Saved {len(STATE['rois'])} table polygons to {args.config}")


if __name__ == "__main__":
    main()

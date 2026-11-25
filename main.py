from __future__ import annotations

import argparse
import copy
import os
import threading
import time
from typing import Any, Dict

import cv2
import numpy as np
import uvicorn

from src.app import create_app
from src.config import load_config
from src.database import Database
from src.models import Detector
from src.table_manager import TableManager


class VisionSystem:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.lock = threading.RLock()
        self.db = Database(cfg["database"]["path"])
        self.detector = Detector(cfg)
        self.table_manager = TableManager(cfg, self.db)
        self.state: Dict[str, Any] = self.table_manager.last_state
        self.latest_jpeg: bytes | None = None
        self.running = False
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        print(f"[INFO] Vision loop started (simulate={self.cfg['model']['simulate']})")

    def stop(self) -> None:
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        self.db.close()

    def get_state(self) -> Dict[str, Any]:
        with self.lock:
            return copy.deepcopy(self.state)

    def _open_capture(self):
        source = self.cfg["camera"]["source"]
        cap = cv2.VideoCapture(source)
        if int(self.cfg["camera"].get("width", 0)) > 0:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.cfg["camera"]["width"]))
        if int(self.cfg["camera"].get("height", 0)) > 0:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.cfg["camera"]["height"]))
        return cap, source

    def _loop(self) -> None:
        simulate = bool(self.cfg["model"].get("simulate", False))
        cap = None
        source = None
        is_file = False
        if not simulate:
            cap, source = self._open_capture()
            if not cap.isOpened():
                raise RuntimeError(f"Cannot open camera source: {source}")
            src_str = str(source).lower()
            is_file = src_str.endswith((".mp4", ".avi", ".mkv", ".mov", ".webm"))

        fps_limit = float(self.cfg["camera"].get("fps_limit", 0) or 0)
        frame_dir = self.cfg.get("output", {}).get("frame_dir", "data/frames")
        save_frames = bool(self.cfg.get("output", {}).get("save_frames", False))
        if save_frames:
            os.makedirs(frame_dir, exist_ok=True)

        try:
            while self.running:
                t0 = time.time()
                if simulate:
                    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
                    frame[:] = (35, 35, 35)
                else:
                    ok, frame = cap.read()  # type: ignore[union-attr]
                    if not ok:
                        if is_file:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # type: ignore[union-attr]
                            continue
                        time.sleep(0.2)
                        continue

                detections = self.detector.detect(frame)
                state = self.table_manager.update(detections, (frame.shape[1], frame.shape[0]))
                overlay = self.table_manager.draw(frame, detections, state)

                ok_jpg, buf = cv2.imencode(".jpg", overlay, [cv2.IMWRITE_JPEG_QUALITY, 82])
                if ok_jpg:
                    with self.lock:
                        self.latest_jpeg = buf.tobytes()
                        self.state = state

                if save_frames:
                    cv2.imwrite(os.path.join(frame_dir, f"{int(time.time()*1000)}.jpg"), overlay)

                if fps_limit > 0:
                    elapsed = time.time() - t0
                    time.sleep(max(0.0, 1.0 / fps_limit - elapsed))
        finally:
            if cap is not None:
                cap.release()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Restaurant people/table detection system")
    p.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    p.add_argument("--no-server", action="store_true", help="Run camera loop only (no web UI)")
    p.add_argument("--source", default=None, help="Override camera source (0, rtsp://..., video.mp4)")
    p.add_argument("--simulate", action="store_true", help="Use fake detections (no camera/model) to test UI")
    return p


def main() -> None:
    args = build_parser().parse_args()
    cfg = load_config(args.config)
    if args.source is not None:
        cfg["camera"]["source"] = args.source
    if args.simulate:
        cfg["model"]["simulate"] = True

    system = VisionSystem(cfg)
    system.start()

    if args.no_server:
        print("[INFO] Running without web server. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass
        finally:
            system.stop()
        return

    srv = cfg["server"]
    print(f"[INFO] Dashboard: http://localhost:{srv['port']}")
    uvicorn.run(create_app(system), host=srv["host"], port=int(srv["port"]), log_level="info")


if __name__ == "__main__":
    main()

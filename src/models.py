from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class Detection:
    track_id: Optional[int]
    class_id: int
    class_name: str
    conf: float
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def center(self):
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)


class SimulatedDetector:
    """Fake detections so the UI/database can be tested without a camera or weights."""

    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.t0 = time.time()
        self.rois = cfg["tables"].get("rois") or []
        if not self.rois:
            self.rois = [
                {"id": f"T{i+1}", "polygon": [[0.1, 0.2 + 0.25*i], [0.35, 0.2 + 0.25*i],
                                               [0.35, 0.4 + 0.25*i], [0.1, 0.4 + 0.25*i]]}
                for i in range(4)
            ]

    @staticmethod
    def _center(roi):
        pts = np.array(roi["polygon"], dtype=float)
        return float(pts[:, 0].mean()), float(pts[:, 1].mean())

    def detect(self, frame) -> List[Detection]:
        h, w = frame.shape[:2]
        el = time.time() - self.t0
        out: List[Detection] = []
        for i, roi in enumerate(self.rois):
            cx, cy = self._center(roi)
            tw, th = 0.16, 0.12
            out.append(Detection(i + 1, -1, "table", 0.99,
                                 (cx-tw/2)*w, (cy-th/2)*h, (cx+tw/2)*w, (cy+th/2)*h))
            px = cx + 0.03 * np.sin(el / 2.0 + i)
            py = cy + 0.02 * np.cos(el / 2.0 + i)
            out.append(Detection(100 + i, -1, "person", 0.95,
                                 (px-0.03)*w, (py-0.05)*h, (px+0.03)*w, (py+0.05)*h))
            if el > 5.0 + i:
                out.append(Detection(None, -1, "bowl", 0.90,
                                     (cx-0.02)*w, (cy-0.02)*h, (cx+0.02)*w, (cy+0.02)*h))
        return out


class Detector:
    """YOLO detector + ByteTrack multi-object tracker."""

    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.simulate = bool(cfg["model"].get("simulate", False))
        self.names: Dict[int, str] = {}
        self.class_ids: List[int] = []
        self.model = None

        wanted = set()
        for key in ("person", "table", "serve"):
            wanted.update(cfg["classes"].get(key, []))

        if self.simulate:
            self.impl: Optional[SimulatedDetector] = SimulatedDetector(cfg)
            return

        from ultralytics import YOLO  # imported lazily so --help works without install

        weights = cfg["model"]["weights"]
        self.model = YOLO(weights)
        self.names = dict(self.model.names)
        self.class_ids = [idx for idx, name in self.names.items() if name in wanted]

        if not self.class_ids:
            print("[WARN] No configured class names found in model. Falling back to all classes.")
        else:
            unknown = wanted - set(self.names.values())
            if unknown:
                print(f"[WARN] Classes not in model: {sorted(unknown)}")

    def detect(self, frame) -> List[Detection]:
        if self.simulate or self.model is None:
            return self.impl.detect(frame)  # type: ignore[union-attr]

        m = self.cfg["model"]
        results = self.model.track(
            source=frame,
            persist=True,
            tracker=m["tracker"],
            conf=float(m["conf"]),
            iou=float(m["iou"]),
            imgsz=int(m["imgsz"]),
            device=None if m["device"] == "auto" else m["device"],
            classes=self.class_ids if self.class_ids else None,
            verbose=False,
        )
        if not results or results[0].boxes is None:
            return []

        boxes = results[0].boxes
        count = len(boxes)
        ids = boxes.id.cpu().numpy() if boxes.id is not None else [None] * count
        clss = boxes.cls.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        xyxy = boxes.xyxy.cpu().numpy()

        out: List[Detection] = []
        for i in range(count):
            cls_id = int(clss[i])
            out.append(
                Detection(
                    track_id=int(ids[i]) if ids[i] is not None else None,
                    class_id=cls_id,
                    class_name=self.names.get(cls_id, str(cls_id)),
                    conf=float(confs[i]),
                    x1=float(xyxy[i][0]), y1=float(xyxy[i][1]),
                    x2=float(xyxy[i][2]), y2=float(xyxy[i][3]),
                )
            )
        return out

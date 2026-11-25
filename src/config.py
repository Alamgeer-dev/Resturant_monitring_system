from __future__ import annotations

import copy
import os
from typing import Any, Dict

import yaml

DEFAULT_CONFIG: Dict[str, Any] = {
    "camera": {"source": 0, "width": 0, "height": 0, "fps_limit": 0},
    "model": {
        "weights": "yolo11n.pt",
        "device": "auto",
        "imgsz": 640,
        "conf": 0.45,
        "iou": 0.50,
        "tracker": "bytetrack.yaml",
        "simulate": False,
    },
    "classes": {
        "person": ["person"],
        "table": ["dining table", "table"],
        "serve": [
            "bowl", "cup", "fork", "knife", "spoon", "sandwich",
            "pizza", "cake", "bottle", "wine glass", "plate", "food",
        ],
    },
    "tables": {
        "mode": "roi",
        "max_distance": 0.35,
        "lose_grace_sec": 3.0,
        "serve_delay_sec": 2.0,
        "serve_mode": "both",
        "rois": [],
    },
    "server": {"host": "0.0.0.0", "port": 8000, "mjpeg_fps": 12},
    "database": {"path": "data/restaurant.db"},
}


def _merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            user_cfg = yaml.safe_load(fh) or {}
        cfg = _merge(cfg, user_cfg)

    db_dir = os.path.dirname(cfg["database"]["path"])
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    return cfg


def save_config(cfg: Dict[str, Any], path: str = "config.yaml") -> None:
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False, allow_unicode=True)

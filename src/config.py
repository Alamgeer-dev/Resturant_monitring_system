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
        "chair": ["chair"],
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
    "server": {"host": "0.0.0.0", "port": 8000, "mjpeg_fps": 12, "cors_origins": []},
    "database": {"path": "data/restaurant.db"},
    "auth": {"username": "", "password": ""},
}


def _set_path(cfg: Dict[str, Any], path: tuple, value: Any) -> None:
    cur = cfg
    for key in path[:-1]:
        cur = cur.setdefault(key, {})
    cur[path[-1]] = value


def _as_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_source(value: str):
    text = str(value).strip()
    return int(text) if text.lstrip("-").isdigit() else text


def _apply_env(cfg: Dict[str, Any]) -> None:
    """Environment overrides make Docker/VPS deployment possible without editing YAML."""
    overrides = [
        (("camera", "source"), "CAMERA_SOURCE", _as_source),
        (("camera", "width"), "CAMERA_WIDTH", int),
        (("camera", "height"), "CAMERA_HEIGHT", int),
        (("camera", "fps_limit"), "CAMERA_FPS_LIMIT", float),
        (("model", "weights"), "MODEL_WEIGHTS", str),
        (("model", "device"), "MODEL_DEVICE", str),
        (("model", "imgsz"), "MODEL_IMGSZ", int),
        (("model", "conf"), "MODEL_CONF", float),
        (("model", "simulate"), "SIMULATE", _as_bool),
        (("tables", "mode"), "TABLES_MODE", str),
        (("tables", "serve_mode"), "SERVE_MODE", str),
        (("server", "host"), "SERVER_HOST", str),
        (("server", "port"), "SERVER_PORT", int),
        (("server", "mjpeg_fps"), "MJPEG_FPS", int),
        (("database", "path"), "DB_PATH", str),
        (("auth", "username"), "AUTH_USERNAME", str),
        (("auth", "password"), "AUTH_PASSWORD", str),
    ]
    for path, env_name, cast in overrides:
        if env_name in os.environ:
            _set_path(cfg, path, cast(os.environ[env_name]))


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

    _apply_env(cfg)
    db_dir = os.path.dirname(cfg["database"]["path"])
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    return cfg


def save_config(cfg: Dict[str, Any], path: str = "config.yaml") -> None:
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False, allow_unicode=True)

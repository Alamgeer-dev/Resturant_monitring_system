from __future__ import annotations

import math
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from .database import Database
from .models import Detection


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def hhmmss(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M:%S")
    except Exception:
        return "--:--:--"


def _inside(point: Tuple[float, float], polygon: List[List[float]]) -> bool:
    """Ray-casting test. point and polygon are normalized (0..1)."""
    if not polygon or len(polygon) < 3:
        return False
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_int = (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1
            if x < x_int:
                inside = not inside
    return inside


def _center_of(polygon: List[List[float]]) -> Tuple[float, float]:
    pts = np.asarray(polygon, dtype=float)
    if len(pts) == 0:
        return (0.5, 0.5)
    return float(pts[:, 0].mean()), float(pts[:, 1].mean())


class TableManager:
    """Assigns tracked people to tables and maintains occupancy/served state."""

    def __init__(self, cfg: Dict[str, Any], db: Database):
        self.cfg = cfg
        self.db = db
        tc = cfg["tables"]

        self.person_names = set(cfg["classes"].get("person", []))
        self.table_names = set(cfg["classes"].get("table", []))
        self.chair_names = set(cfg["classes"].get("chair", []))
        self.serve_names = set(cfg["classes"].get("serve", []))

        self.mode = tc.get("mode", "roi")
        self.max_distance = float(tc.get("max_distance", 0.35))
        self.lose_grace = float(tc.get("lose_grace_sec", 3.0))
        self.serve_delay = float(tc.get("serve_delay_sec", 2.0))
        self.serve_mode = tc.get("serve_mode", "both")

        self.first_seen: Dict[int, str] = {}
        self.person_last_seen_ts: Dict[int, float] = {}
        self.person_table: Dict[int, Optional[str]] = {}

        self.tables: Dict[str, Dict[str, Any]] = {}
        if self.mode == "roi":
            for roi in tc.get("rois", []):
                self._add_table(
                    table_id=str(roi["id"]),
                    label=str(roi.get("label", roi["id"])),
                    polygon=[[float(x), float(y)] for x, y in roi["polygon"]],
                )

        self.last_state: Dict[str, Any] = self._empty_state()

    # ------------------------------------------------------------------
    def _add_table(self, table_id: str, label: str, polygon: List[List[float]]) -> Dict[str, Any]:
        ts = now_iso()
        if table_id not in self.tables:
            self.tables[table_id] = {
                "id": table_id,
                "label": label,
                "polygon": polygon,
                "center": _center_of(polygon),
                "active_session": None,
                "served_at": None,
                "serve_since": None,
                "last_seen_ts": time.time(),
                "count": 0,
                "persons": [],
            }
            self.db.register_table(table_id, label, polygon, ts)
        return self.tables[table_id]

    def _empty_state(self) -> Dict[str, Any]:
        return {
            "timestamp": now_iso(),
            "totals": {"people": 0, "tables": 0, "chairs": 0, "occupied": 0, "free": 0, "served": 0},
            "tables": [],
            "people": [],
        }

    # ------------------------------------------------------------------
    def _active_tables(self, detections: List[Detection], w: int, h: int) -> List[str]:
        if self.mode == "roi":
            return list(self.tables.keys())

        now_ts = time.time()
        seen: Dict[str, Tuple[List[List[float]], str]] = {}
        for i, det in enumerate(detections):
            if det.class_name not in self.table_names:
                continue
            tid = det.track_id if det.track_id is not None else -(i + 1)
            table_id = f"A{abs(int(tid))}"
            poly = [
                [det.x1 / w, det.y1 / h], [det.x2 / w, det.y1 / h],
                [det.x2 / w, det.y2 / h], [det.x1 / w, det.y2 / h],
            ]
            seen[table_id] = (poly, f"Table {abs(int(tid))}")

        for table_id, (poly, label) in seen.items():
            t = self._add_table(table_id, label, poly)
            t["polygon"] = poly
            t["center"] = _center_of(poly)
            t["last_seen_ts"] = now_ts

        for table_id, t in self.tables.items():
            if table_id in seen:
                t["absent"] = False
            elif now_ts - t.get("last_seen_ts", now_ts) > self.lose_grace:
                t["absent"] = True

        return [tid for tid, t in self.tables.items() if not t.get("absent", False)]

    def _assign(self, det: Detection, active_ids: List[str], w: int, h: int) -> Optional[str]:
        px, py = det.center[0] / w, det.center[1] / h

        if self.mode == "roi":
            for tid in active_ids:
                if _inside((px, py), self.tables[tid]["polygon"]):
                    return tid

        best_id, best_d = None, float("inf")
        for tid in active_ids:
            cx, cy = self.tables[tid]["center"]
            d = math.hypot(px - cx, py - cy)
            if d < best_d:
                best_id, best_d = tid, d
        if best_id is not None and best_d <= self.max_distance:
            return best_id
        return None

    # ------------------------------------------------------------------
    def update(self, detections: List[Detection], frame_size: Tuple[int, int]) -> Dict[str, Any]:
        w, h = max(1, frame_size[0]), max(1, frame_size[1])
        now_ts = time.time()
        iso = now_iso()

        persons = [d for d in detections if d.class_name in self.person_names and d.track_id is not None]
        chairs = [d for d in detections if d.class_name in self.chair_names]
        serve_dets = [d for d in detections if d.class_name in self.serve_names]

        active_ids = self._active_tables(detections, w, h)
        assigned: Dict[int, Optional[str]] = {}

        # --- people bookkeeping ---
        current_ids = set()
        for det in persons:
            tid = int(det.track_id)  # type: ignore[arg-type]
            current_ids.add(tid)
            table_id = self._assign(det, active_ids, w, h)
            assigned[tid] = table_id

            if tid not in self.first_seen:
                self.first_seen[tid] = iso
                self.db.log_event(iso, "person_enter", table_id, tid,
                                  f"Person {tid} entered")
            self.db.upsert_person(tid, self.first_seen[tid], iso, table_id)

            old_table = self.person_table.get(tid)
            if old_table != table_id and old_table is not None:
                self.db.log_event(iso, "person_table_change", table_id, tid,
                                  f"Person {tid}: {old_table} -> {table_id}")
            self.person_table[tid] = table_id
            self.person_last_seen_ts[tid] = now_ts

        for tid in list(self.person_last_seen_ts.keys()):
            if tid in current_ids:
                continue
            if now_ts - self.person_last_seen_ts[tid] > self.lose_grace:
                self.db.mark_person_left(tid, iso)
                self.db.log_event(iso, "person_leave", self.person_table.get(tid), tid,
                                  f"Person {tid} left")
                self.first_seen.pop(tid, None)
                self.person_table.pop(tid, None)
                self.person_last_seen_ts.pop(tid, None)

        # --- table bookkeeping ---
        table_rows: List[Dict[str, Any]] = []
        for tid in active_ids:
            t = self.tables[tid]
            t_persons = [p for p, tbl in assigned.items() if tbl == tid]
            t["persons"] = t_persons
            t["count"] = len(t_persons)

            if t["count"] > 0 and t["active_session"] is None:
                t["active_session"] = self.db.open_session(tid, t_persons, iso)
                t["served_at"] = None
                t["serve_since"] = None
                self.db.log_event(iso, "table_occupied", tid, None,
                                  f"{t['label']} occupied by {t['count']} person(s)")

            if t["count"] == 0 and t["active_session"] is not None:
                was_served = t["served_at"] is not None
                self.db.close_session(t["active_session"], iso, was_served)
                self.db.log_event(iso, "table_free", tid, None,
                                  f"{t['label']} is free again")
                t["active_session"] = None
                t["served_at"] = None
                t["serve_since"] = None

            if (t["count"] > 0 and t["served_at"] is None
                    and self.serve_mode in ("auto", "both")):
                hit = False
                for sd in serve_dets:
                    sx, sy = sd.center[0] / w, sd.center[1] / h
                    if _inside((sx, sy), t["polygon"]):
                        hit = True
                        break
                    cx, cy = t["center"]
                    if math.hypot(sx - cx, sy - cy) < 0.08:
                        hit = True
                        break
                if hit:
                    if t["serve_since"] is None:
                        t["serve_since"] = now_ts
                    elif now_ts - t["serve_since"] >= self.serve_delay:
                        self.mark_served(tid, source="auto")
                else:
                    t["serve_since"] = None

            people_info = []
            for pid in t_persons:
                entry = self.first_seen.get(pid, iso)
                try:
                    duration = int((datetime.now() - datetime.fromisoformat(entry)).total_seconds())
                except Exception:
                    duration = 0
                people_info.append({
                    "track_id": pid,
                    "entry_time": entry,
                    "entry_hhmmss": hhmmss(entry),
                    "duration_sec": duration,
                })

            table_rows.append({
                "id": tid,
                "label": t["label"],
                "count": t["count"],
                "free": t["count"] == 0,
                "served": t["served_at"] is not None,
                "served_at": t["served_at"],
                "session_id": t["active_session"],
                "people": people_info,
                "polygon": t["polygon"],
            })

        people_rows = []
        for det in persons:
            pid = int(det.track_id)  # type: ignore[arg-type]
            entry = self.first_seen.get(pid, iso)
            try:
                duration = int((datetime.now() - datetime.fromisoformat(entry)).total_seconds())
            except Exception:
                duration = 0
            people_rows.append({
                "track_id": pid,
                "entry_time": entry,
                "entry_hhmmss": hhmmss(entry),
                "duration_sec": duration,
                "table_id": assigned.get(pid),
            })

        occupied = sum(1 for r in table_rows if not r["free"])
        served = sum(1 for r in table_rows if r["served"])
        state = {
            "timestamp": iso,
            "totals": {
                "people": len(persons),
                "tables": len(table_rows),
                "chairs": len(chairs),
                "occupied": occupied,
                "free": len(table_rows) - occupied,
                "served": served,
            },
            "tables": table_rows,
            "people": people_rows,
        }
        self.last_state = state
        return state

    # ------------------------------------------------------------------
    def mark_served(self, table_id: str, source: str = "manual") -> bool:
        t = self.tables.get(str(table_id))
        if t is None:
            return False
        iso = now_iso()
        t["served_at"] = iso
        self.db.mark_served(str(table_id), iso)
        self.db.log_event(iso, "served", str(table_id), None,
                          f"{t['label']} marked served ({source})")
        return True

    def clear_table(self, table_id: str, source: str = "manual") -> bool:
        t = self.tables.get(str(table_id))
        if t is None:
            return False
        iso = now_iso()
        if t["active_session"] is not None:
            self.db.close_session(t["active_session"], iso, t["served_at"] is not None)
        self.db.log_event(iso, "table_cleared", str(table_id), None,
                          f"{t['label']} cleared ({source})")
        t["active_session"] = None
        t["served_at"] = None
        t["serve_since"] = None
        t["persons"] = []
        t["count"] = 0
        return True

    # ------------------------------------------------------------------
    def draw(self, frame, detections: List[Detection], state: Dict[str, Any]):
        h, w = frame.shape[:2]
        canvas = frame.copy()

        for row in state.get("tables", []):
            poly = np.asarray([[int(x * w), int(y * h)] for x, y in row["polygon"]], dtype=np.int32)
            if len(poly) >= 3:
                color = (0, 200, 0) if row["free"] else ((0, 180, 255) if not row["served"] else (255, 180, 0))
                cv2.polylines(canvas, [poly], True, color, 2)
                overlay = canvas.copy()
                cv2.fillPoly(overlay, [poly], color)
                canvas = cv2.addWeighted(overlay, 0.10, canvas, 0.90, 0)

            cx, cy = self.tables[row["id"]]["center"]
            count_txt = "FREE" if row["free"] else f"{row['count']} pax"
            served_txt = "SERVED" if row["served"] else "NOT SERVED"
            label = f"{row['label']} | {count_txt} | {served_txt}"
            cv2.putText(canvas, label, (int(cx * w) - 70, int(cy * h) - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        for det in detections:
            x1, y1, x2, y2 = int(det.x1), int(det.y1), int(det.x2), int(det.y2)
            if det.class_name in self.person_names:
                color = (255, 60, 60)
            elif det.class_name in self.table_names:
                color = (60, 160, 255)
            elif det.class_name in self.chair_names:
                color = (200, 80, 255)
            elif det.class_name in self.serve_names:
                color = (60, 255, 160)
            else:
                color = (160, 160, 160)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)

            if det.class_name in self.person_names and det.track_id is not None:
                entry = self.first_seen.get(int(det.track_id), state["timestamp"])
                lab = f"P{det.track_id} in:{hhmmss(entry)}"
                cv2.putText(canvas, lab, (x1, max(14, y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)

        totals = state.get("totals", {})
        head = (f"People: {totals.get('people',0)}  Tables: {totals.get('tables',0)}  "
                f"Occupied: {totals.get('occupied',0)}  Free: {totals.get('free',0)}  "
                f"Served: {totals.get('served',0)}")
        cv2.rectangle(canvas, (0, 0), (w, 30), (20, 20, 20), -1)
        cv2.putText(canvas, head, (10, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (255, 255, 255), 1, cv2.LINE_AA)
        return canvas

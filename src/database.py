from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional


class Database:
    """Small SQLite store for people, tables, sessions and events."""

    def __init__(self, path: str):
        self.path = path
        self.lock = threading.RLock()
        if os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self.lock, self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS people (
                    track_id      INTEGER PRIMARY KEY,
                    first_seen    TEXT NOT NULL,
                    last_seen     TEXT NOT NULL,
                    left_at       TEXT,
                    current_table TEXT
                );

                CREATE TABLE IF NOT EXISTS tables (
                    table_id  TEXT PRIMARY KEY,
                    label     TEXT,
                    polygon   TEXT,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_id    TEXT NOT NULL,
                    person_ids  TEXT NOT NULL,
                    start_time  TEXT NOT NULL,
                    end_time    TEXT,
                    served_at   TEXT,
                    status      TEXT NOT NULL DEFAULT 'active'
                );

                CREATE TABLE IF NOT EXISTS events (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts        TEXT NOT NULL,
                    type      TEXT NOT NULL,
                    table_id  TEXT,
                    person_id INTEGER,
                    message   TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);
                CREATE INDEX IF NOT EXISTS idx_sessions_table ON sessions(table_id);
                """
            )

    # ---------- tables ----------
    def register_table(self, table_id: str, label: str = "", polygon: Any = None, created_at: str = "") -> None:
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO tables(table_id, label, polygon, created_at) VALUES (?,?,?,?)",
                (str(table_id), label, json.dumps(polygon or []), created_at),
            )
            self.conn.execute("UPDATE tables SET label=? WHERE table_id=?", (label, str(table_id)))

    # ---------- people ----------
    def upsert_person(self, track_id: int, first_seen: str, last_seen: str, table_id: Optional[str]) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO people(track_id, first_seen, last_seen, left_at, current_table)
                VALUES (?,?,?,NULL,?)
                ON CONFLICT(track_id) DO UPDATE SET
                    last_seen=excluded.last_seen,
                    current_table=excluded.current_table,
                    left_at=NULL
                """,
                (int(track_id), first_seen, last_seen, table_id),
            )

    def mark_person_left(self, track_id: int, when: str) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                "UPDATE people SET left_at=?, current_table=NULL WHERE track_id=?",
                (when, int(track_id)),
            )

    # ---------- sessions ----------
    def open_session(self, table_id: str, person_ids: List[int], start_time: str) -> int:
        with self.lock, self.conn:
            cur = self.conn.execute(
                "INSERT INTO sessions(table_id, person_ids, start_time, status) VALUES (?,?,?,'active')",
                (str(table_id), json.dumps([int(p) for p in person_ids]), start_time),
            )
            return int(cur.lastrowid)

    def close_session(self, session_id: int, end_time: str, served: bool) -> None:
        status = "served" if served else "left_unserved"
        with self.lock, self.conn:
            self.conn.execute(
                "UPDATE sessions SET end_time=?, status=? WHERE id=? AND end_time IS NULL",
                (end_time, status, int(session_id)),
            )

    def mark_served(self, table_id: str, served_at: str) -> bool:
        with self.lock, self.conn:
            cur = self.conn.execute(
                """
                UPDATE sessions
                   SET served_at=?, status='served'
                 WHERE table_id=? AND end_time IS NULL AND served_at IS NULL
                """,
                (served_at, str(table_id)),
            )
            return cur.rowcount > 0

    # ---------- events ----------
    def log_event(
        self,
        ts: str,
        event_type: str,
        table_id: Optional[str] = None,
        person_id: Optional[int] = None,
        message: str = "",
    ) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO events(ts, type, table_id, person_id, message) VALUES (?,?,?,?,?)",
                (ts, event_type, table_id, person_id, message),
            )

    def get_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (int(limit),)
            ).fetchall()
        return [dict(r) for r in rows]

    def export_csv(self) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "ts", "type", "table_id", "person_id", "message"])
        with self.lock:
            rows = self.conn.execute("SELECT * FROM events ORDER BY id").fetchall()
        for r in rows:
            writer.writerow([r["id"], r["ts"], r["type"], r["table_id"], r["person_id"], r["message"]])
        return buf.getvalue()

    def close(self) -> None:
        with self.lock:
            self.conn.close()

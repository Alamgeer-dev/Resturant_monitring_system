from __future__ import annotations

import asyncio
import base64
import copy
import os
import secrets
import time
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def create_app(system: Any) -> FastAPI:
    app = FastAPI(title="Restaurant Detection System", version="1.0")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    origins = (system.cfg.get("server", {}) or {}).get("cors_origins", []) or []
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    security = HTTPBasic(auto_error=False)
    auth_cfg = system.cfg.get("auth", {}) or {}

    def _credentials_ok(username: str, password: str) -> bool:
        user = auth_cfg.get("username") or ""
        pwd = auth_cfg.get("password") or ""
        if not user or not pwd:
            return True
        return (secrets.compare_digest(username, user)
                and secrets.compare_digest(password, pwd))

    def require_auth(credentials: HTTPBasicCredentials | None = Depends(security)) -> bool:
        # Auth disabled: allow everyone (default for local use).
        if not auth_cfg.get("username") or not auth_cfg.get("password"):
            return True
        if credentials is None or not _credentials_ok(credentials.username, credentials.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Basic"},
            )
        return True

    async def ws_auth(websocket: WebSocket) -> bool:
        header = websocket.headers.get("authorization", "")
        if not header.startswith("Basic "):
            if auth_cfg.get("username") and auth_cfg.get("password"):
                await websocket.close(code=1008)
                return False
            return True
        try:
            decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
            user, pwd = decoded.split(":", 1)
        except Exception:
            await websocket.close(code=1008)
            return False
        if not _credentials_ok(user, pwd):
            await websocket.close(code=1008)
            return False
        return True

    @app.get("/", include_in_schema=False, dependencies=[Depends(require_auth)])
    def index():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    @app.get("/api/state", dependencies=[Depends(require_auth)])
    def api_state() -> Dict[str, Any]:
        with system.lock:
            return copy.deepcopy(system.state)

    @app.get("/api/events", dependencies=[Depends(require_auth)])
    def api_events(limit: int = 100):
        return {"events": system.db.get_events(limit)}

    @app.get("/api/export.csv", dependencies=[Depends(require_auth)])
    def api_export():
        return Response(content=system.db.export_csv(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=events.csv"})

    @app.get("/video_feed", dependencies=[Depends(require_auth)])
    def video_feed():
        fps = max(1, int(system.cfg["server"].get("mjpeg_fps", 12)))

        def gen():
            while True:
                with system.lock:
                    frame = system.latest_jpeg
                if frame is None:
                    time.sleep(0.05)
                    continue
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
                time.sleep(1.0 / fps)

        return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.websocket("/ws")
    async def websocket_state(websocket: WebSocket):
        if not await ws_auth(websocket):
            return
        await websocket.accept()
        try:
            while True:
                with system.lock:
                    state = copy.deepcopy(system.state)
                await websocket.send_json(state)
                await asyncio.sleep(0.5)
        except WebSocketDisconnect:
            pass
        except Exception:
            try:
                await websocket.close()
            except Exception:
                pass

    @app.post("/api/tables/{table_id}/serve", dependencies=[Depends(require_auth)])
    def api_serve(table_id: str):
        ok = system.table_manager.mark_served(str(table_id), source="manual")
        return {"ok": ok, "table_id": str(table_id)}

    @app.post("/api/tables/{table_id}/clear", dependencies=[Depends(require_auth)])
    def api_clear(table_id: str):
        ok = system.table_manager.clear_table(str(table_id), source="manual")
        return {"ok": ok, "table_id": str(table_id)}

    return app

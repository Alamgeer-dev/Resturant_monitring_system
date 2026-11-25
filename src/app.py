from __future__ import annotations

import asyncio
import copy
import os
import time
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def create_app(system: Any) -> FastAPI:
    app = FastAPI(title="Restaurant Detection System", version="1.0")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    @app.get("/api/state")
    def api_state() -> Dict[str, Any]:
        with system.lock:
            return copy.deepcopy(system.state)

    @app.get("/api/events")
    def api_events(limit: int = 100):
        return {"events": system.db.get_events(limit)}

    @app.get("/api/export.csv")
    def api_export():
        return Response(content=system.db.export_csv(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=events.csv"})

    @app.get("/video_feed")
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

    @app.post("/api/tables/{table_id}/serve")
    def api_serve(table_id: str):
        ok = system.table_manager.mark_served(str(table_id), source="manual")
        return {"ok": ok, "table_id": str(table_id)}

    @app.post("/api/tables/{table_id}/clear")
    def api_clear(table_id: str):
        ok = system.table_manager.clear_table(str(table_id), source="manual")
        return {"ok": ok, "table_id": str(table_id)}

    return app

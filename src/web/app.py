import asyncio
import base64
import io
import json
import logging
import os
from typing import Any, Dict, List
import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from ..bridge.device_manager import DeviceManager
from ..engine.scheduler import DailyRoutineScheduler
from ..engine.session_runner import SessionRunner

logger = logging.getLogger(__name__)


def create_app(config_path: str = "config/default_config.yaml") -> FastAPI:
    # Load configuration
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    app = FastAPI(title="TikTok iOS Automation Suite", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Core State
    device_manager = DeviceManager(
        wda_url=config.get("device", {}).get("wda_url", "http://localhost:8100")
    )
    active_websockets: List[WebSocket] = []

    def on_runner_update(stats_dict: Dict[str, Any]):
        # Non-blocking async event broadcast to connected WebSockets
        msg = json.dumps({"type": "stats", "data": stats_dict})
        for ws in list(active_websockets):
            try:
                asyncio.run_coroutine_threadsafe(ws.send_text(msg), loop=app.state.loop)
            except Exception:
                pass

    runner = SessionRunner(
        config=config,
        device_manager=device_manager,
        on_status_update=on_runner_update,
    )
    scheduler = DailyRoutineScheduler(runner=runner, config=config)

    app.state.config = config
    app.state.device_manager = device_manager
    app.state.runner = runner
    app.state.scheduler = scheduler
    app.state.active_websockets = active_websockets

    @app.on_event("startup")
    async def startup_event():
        app.state.loop = asyncio.get_running_loop()
        scheduler.start()

    # REST Endpoints
    @app.post("/api/actions/capture-screen")
    def action_capture_screen():
        """Captures a single screenshot on-demand without continuous background load."""
        img = device_manager.get_screen()
        if img:
            thumb = img.copy()
            thumb.thumbnail((360, 780))
            buf = io.BytesIO()
            thumb.save(buf, format="JPEG", quality=75)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return {"status": "ok", "image": b64}
        return {"status": "error"}
    @app.get("/api/status")
    def get_status():
        conn = device_manager.check_connection()
        stats = runner.get_stats()
        upcoming = scheduler.get_upcoming_sessions()
        return {
            "device": conn,
            "session": stats,
            "scheduler": {
                "enabled": scheduler.enabled,
                "upcoming": upcoming,
            },
        }

    @app.get("/api/config")
    def get_config():
        return app.state.config

    @app.post("/api/config")
    def update_config(payload: Dict[str, Any]):
        app.state.config.update(payload)
        runner.update_config(app.state.config)
        return {"status": "ok", "config": app.state.config}

    @app.post("/api/actions/start")
    def action_start(duration_minutes: int = 15):
        success = runner.start(duration_minutes=duration_minutes)
        if not success:
            raise HTTPException(status_code=400, detail="Session already active")
        return {"status": "started", "duration_minutes": duration_minutes}

    @app.post("/api/actions/pause")
    def action_pause():
        runner.pause()
        return {"status": "paused"}

    @app.post("/api/actions/resume")
    def action_resume():
        runner.resume()
        return {"status": "resumed"}

    @app.post("/api/actions/stop")
    def action_stop():
        runner.stop()
        return {"status": "stopped"}

    @app.post("/api/actions/skip")
    def action_skip():
        runner.skip_video()
        return {"status": "skipping"}

    @app.post("/api/actions/test-swipe")
    def action_test_swipe():
        try:
            w, h = device_manager.client.get_window_size()
            runner.gesture.screen_width = w
            runner.gesture.screen_height = h
        except Exception:
            pass
        success = runner.gesture.swipe_next_video()
        return {"status": "ok" if success else "failed"}

    @app.post("/api/actions/test-like")
    def action_test_like():
        try:
            w, h = device_manager.client.get_window_size()
            runner.gesture.screen_width = w
            runner.gesture.screen_height = h
        except Exception:
            pass
        success = runner.gesture.double_tap_like()
        return {"status": "ok" if success else "failed"}

    @app.get("/api/screen")
    def get_screen_raw():
        img = device_manager.get_screen()
        if not img:
            raise HTTPException(status_code=503, detail="Screen unavailable")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return Response(content=buf.getvalue(), media_type="image/jpeg")

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        active_websockets.append(websocket)
        # Send initial state snapshot immediately
        await websocket.send_text(json.dumps({
            "type": "stats",
            "data": runner.get_stats(),
        }))
        try:
            while True:
                data = await websocket.receive_text()
                # Handle incoming messages from UI if needed
        except WebSocketDisconnect:
            if websocket in active_websockets:
                active_websockets.remove(websocket)
        except Exception:
            if websocket in active_websockets:
                active_websockets.remove(websocket)

    # Mount compiled React frontend if present
    frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/dist"))
    if os.path.exists(frontend_dist):
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app

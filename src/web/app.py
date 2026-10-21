import asyncio
import base64
import csv
import io
import json
import logging
import os
import threading
import time
import traceback
from typing import Any, Dict, List, Optional
import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from ..bridge.device_manager import DeviceManager
from ..engine.scheduler import DailyRoutineScheduler
from ..engine.session_runner import SessionRunner
from ..storage import SessionDatabase, AnalyticsEngine

logger = logging.getLogger(__name__)


def deep_update(base: dict, update: dict) -> dict:
    """Recursively updates nested dictionaries in base with values from update."""
    for k, v in update.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            deep_update(base[k], v)
        else:
            base[k] = v
    return base


def create_app(
    config_path: str = "config/default_config.yaml",
    device_manager: Optional[DeviceManager] = None,
    runner: Optional[SessionRunner] = None,
    config: Optional[dict] = None,
    db: Optional[SessionDatabase] = None,
) -> FastAPI:
    # Load configuration
    abs_config_path = os.path.abspath(config_path)
    if config is None:
        with open(abs_config_path, "r", encoding="utf-8") as f:
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
    if device_manager is None:
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

    if db is None:
        db = getattr(runner, "db", None) if runner else None
    if db is None:
        db = SessionDatabase()
    analytics = AnalyticsEngine(db)

    if runner is None:
        runner = SessionRunner(
            config=config,
            device_manager=device_manager,
            on_status_update=on_runner_update,
            db=db,
        )
    elif getattr(runner, "db", None) is None:
        runner.db = db
    scheduler = DailyRoutineScheduler(runner=runner, config=config)

    app.state.config = config
    app.state.config_path = abs_config_path
    app.state.device_manager = device_manager
    app.state.runner = runner
    app.state.scheduler = scheduler
    app.state.active_websockets = active_websockets
    app.state.db = db
    app.state.analytics = analytics

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
        deep_update(app.state.config, payload)
        runner.update_config(app.state.config)
        scheduler.config = app.state.config.get("scheduler", {})
        scheduler.enabled = scheduler.config.get("enabled", True)

        # Persist updated configuration back to disk atomically
        try:
            cfg_path = app.state.config_path
            dir_name = os.path.dirname(cfg_path)
            os.makedirs(dir_name, exist_ok=True)
            temp_path = f"{cfg_path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(app.state.config, f, default_flow_style=False, sort_keys=False)
            os.replace(temp_path, cfg_path)
            logger.info(f"Persisted updated config to {cfg_path}")
        except Exception as e:
            logger.error(f"Failed to persist config to disk ({app.state.config_path}): {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save config: {e}")

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
        runner.ensure_app_open()
        changed, reason = runner.swipe_next_video_verified()
        return {"status": "ok" if changed else "failed", "changed": changed, "details": reason}

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

    @app.post("/api/actions/test-comment")
    def action_test_comment():
        try:
            w, h = device_manager.client.get_window_size()
            runner.gesture.screen_width = w
            runner.gesture.screen_height = h
        except Exception:
            pass
        runner.ensure_app_open()
        opened = runner.open_comments_verified()
        time.sleep(1.5)
        closed = runner.close_comments_verified()
        return {
            "status": "ok" if (opened and closed) else "failed",
            "opened": opened,
            "closed": closed,
            "message": "Comment drawer opened & closed successfully (OCR verified)" if (opened and closed) else "Could not verify comments via OCR"
        }

    @app.api_route("/api/actions/test-author-profile", methods=["GET", "POST"])
    def action_test_author_profile(auto_return: bool = True):
        try:
            device_manager.check_connection()
            runner.wda = device_manager.client
            runner.gesture.client = device_manager.client
            size = device_manager.client.get_window_size()
            if size and len(size) == 2:
                runner.gesture.screen_width = size[0]
                runner.gesture.screen_height = size[1]
        except Exception as e:
            logger.debug(f"Device update in action_test_author_profile: {e}")
        try:
            return runner.test_author_profile(auto_return=auto_return)
        except Exception as e:
            logger.exception("Error in action_test_author_profile:")
            return {"status": "failed", "message": str(e), "traceback": traceback.format_exc()}

    @app.api_route("/api/actions/test-author-follow", methods=["GET", "POST"])
    def action_test_author_follow():
        try:
            device_manager.check_connection()
            runner.wda = device_manager.client
            runner.gesture.client = device_manager.client
            size = device_manager.client.get_window_size()
            if size and len(size) == 2:
                runner.gesture.screen_width = size[0]
                runner.gesture.screen_height = size[1]
        except Exception as e:
            logger.debug(f"Device update in action_test_author_follow: {e}")
        try:
            return runner.test_author_follow()
        except Exception as e:
            logger.exception("Error in action_test_author_follow:")
            return {"status": "failed", "followed": False, "message": str(e), "traceback": traceback.format_exc()}

    @app.api_route("/api/actions/open-app", methods=["GET", "POST"])
    def action_open_app():
        try:
            device_manager.check_connection()
            runner.wda = device_manager.client
            runner.gesture.client = device_manager.client
            w, h = device_manager.client.get_window_size()
            runner.gesture.screen_width = w
            runner.gesture.screen_height = h
        except Exception:
            pass
        opened = runner.ensure_app_open()
        return {"status": "ok" if opened else "failed", "opened": opened}

    @app.api_route("/api/actions/close-app", methods=["GET", "POST"])
    def action_close_app():
        runner.close_app()
        return {"status": "ok"}

    @app.post("/api/actions/recover-feed")
    def action_recover_feed():
        try:
            w, h = device_manager.client.get_window_size()
            runner.gesture.screen_width = w
            runner.gesture.screen_height = h
        except Exception:
            pass
        recovered, state = runner.recover_to_feed()
        return {"status": "ok" if recovered else "failed", "recovered": recovered, "state": state}

    @app.post("/api/actions/trigger-search")
    def action_trigger_search(term: Optional[str] = None, videos_to_watch: Optional[int] = None):
        """Triggers TikTok search seeding on device to narrow down FYP algorithm to target niche."""
        query = term
        if not query:
            seed_terms = app.state.config.get("niche", {}).get("seed_terms", [])
            query = seed_terms[0] if seed_terms else "technology"

        def _worker():
            try:
                runner.trigger_search_seeding(term=query, videos_to_watch=videos_to_watch)
            except Exception as e:
                logger.error(f"Error during search seeding: {e}")

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return {"status": "started", "term": query, "videos_to_watch": videos_to_watch or "randomized"}

    @app.api_route("/api/actions/test-tags", methods=["GET", "POST"])
    def action_test_tags():
        """Captures the current screen and runs Vision OCR & NicheTrainer against configured target tags."""
        img = device_manager.get_screen()
        if not img:
            raise HTTPException(status_code=503, detail="Unable to capture screen from device")

        caption, full_text = runner.ocr.extract_full_content(img)
        is_ad = runner.detector.is_sponsored(caption) or runner.detector.is_sponsored(full_text)

        score, matched_kws = runner.trainer.evaluate_relevance(caption)
        matched_in = "caption" if matched_kws else ""
        if not matched_kws and full_text:
            score, matched_kws = runner.trainer.evaluate_relevance(full_text)
            if matched_kws:
                matched_in = "video overlay / screen"

        is_niche = len(matched_kws) > 0

        buf = io.BytesIO()
        rgb_img = img.convert("RGB") if img.mode != "RGB" else img
        rgb_img.save(buf, format="JPEG", quality=75)
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        return {
            "status": "ok",
            "is_niche": is_niche,
            "matched_keywords": matched_kws,
            "matched_in": matched_in,
            "score": round(score, 2),
            "is_ad": is_ad,
            "caption": caption,
            "full_text": full_text[:400],
            "image": f"data:image/jpeg;base64,{img_b64}",
        }

    @app.get("/api/screen")
    def get_screen_raw():
        img = device_manager.get_screen()
        if not img:
            raise HTTPException(status_code=503, detail="Screen unavailable")
        buf = io.BytesIO()
        rgb_img = img.convert("RGB") if img.mode != "RGB" else img
        rgb_img.save(buf, format="JPEG", quality=80)
        return Response(content=buf.getvalue(), media_type="image/jpeg")

    # Session History & Analytics Endpoints
    @app.get("/api/sessions")
    def get_sessions(limit: int = 50, offset: int = 0):
        """Returns paginated list of sessions."""
        cur_db = getattr(app.state, "db", db)
        return {"sessions": cur_db.get_sessions(limit=limit, offset=offset)}

    @app.get("/api/sessions/{session_id}")
    def get_session_detail(session_id: str):
        """Returns session details with full itemized video interaction timeline."""
        cur_db = getattr(app.state, "db", db)
        session_data = cur_db.get_session_by_id(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        return session_data

    @app.delete("/api/sessions/{session_id}")
    def delete_session(session_id: str):
        """Deletes a session and its video interactions."""
        cur_db = getattr(app.state, "db", db)
        success = cur_db.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete session")
        return {"status": "ok", "deleted": session_id}

    @app.delete("/api/sessions")
    def clear_all_sessions():
        """Clears all session history."""
        cur_db = getattr(app.state, "db", db)
        success = cur_db.clear_all_sessions()
        if not success:
            raise HTTPException(status_code=500, detail="Failed to clear sessions")
        return {"status": "ok", "message": "All sessions cleared"}

    @app.get("/api/analytics/summary")
    def get_analytics_summary():
        """Returns lifetime KPIs, today's totals, and 4-Factor Account Warming Health Score."""
        cur_analytics = getattr(app.state, "analytics", analytics)
        return cur_analytics.get_summary_metrics()

    @app.get("/api/analytics/trends")
    def get_analytics_trends(limit: int = 20):
        """Returns chronological session metrics progression and top discovered keywords."""
        cur_analytics = getattr(app.state, "analytics", analytics)
        return cur_analytics.get_trends(limit=limit)

    @app.get("/api/sessions/export/download")
    def export_sessions(format: str = "json"):
        """Exports session history and video interactions in JSON or CSV format."""
        cur_db = getattr(app.state, "db", db)
        sessions = cur_db.get_sessions(limit=1000)
        if format.lower() == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "Session ID", "Start Time", "End Time", "Duration (s)", "State",
                "Videos Watched", "Likes", "Favorites", "Comments", "Follows",
                "Ads Skipped", "Niche Matches", "Niche Match Rate", "Exit Reason"
            ])
            for s in sessions:
                writer.writerow([
                    s.get("session_id"),
                    s.get("start_time"),
                    s.get("end_time"),
                    s.get("duration_seconds"),
                    s.get("state"),
                    s.get("videos_watched"),
                    s.get("likes_count"),
                    s.get("favorites_count"),
                    s.get("comments_viewed"),
                    s.get("follows_count"),
                    s.get("ads_skipped"),
                    s.get("niche_matched_count"),
                    s.get("niche_match_rate"),
                    s.get("exit_reason"),
                ])
            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=tiktok_sessions_{int(time.time())}.csv"}
            )
        else:
            detailed_sessions = []
            for s in sessions:
                detail = cur_db.get_session_by_id(s["session_id"])
                if detail:
                    detailed_sessions.append(detail)
            return Response(
                content=json.dumps(detailed_sessions, indent=2),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=tiktok_sessions_{int(time.time())}.json"}
            )

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

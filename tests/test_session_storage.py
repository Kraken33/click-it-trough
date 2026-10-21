import os
import shutil
import tempfile
import unittest
from fastapi.testclient import TestClient

from src.storage.session_db import SessionDatabase
from src.storage.analytics import AnalyticsEngine
from src.web.app import create_app


class TestSessionStorageAndAnalytics(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_sessions.db")
        self.db = SessionDatabase(db_path=self.db_path)
        self.analytics = AnalyticsEngine(self.db)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_database_crud(self):
        # 1. Create session
        sess_id = "sess_20261020_001"
        ok = self.db.create_session(
            session_id=sess_id,
            start_time="2026-10-20T12:00:00",
            target_keywords=["escooter", "kukirin"],
            session_follow_target=3,
        )
        self.assertTrue(ok)

        # 2. Log video interactions
        ok1 = self.db.log_video_interaction(
            session_id=sess_id,
            caption="Testing Kukirin G2 Max escooter!",
            matched_keywords=["kukirin", "escooter"],
            is_niche=True,
            is_ad=False,
            is_live=False,
            dwell_time_seconds=14.5,
            action_liked=True,
            action_favorited=False,
            action_comment_viewed=True,
            action_followed=True,
            action_skipped_early=False,
        )
        self.assertTrue(ok1)

        ok2 = self.db.log_video_interaction(
            session_id=sess_id,
            caption="Generic funny cats video",
            matched_keywords=[],
            is_niche=False,
            is_ad=False,
            is_live=False,
            dwell_time_seconds=6.0,
            action_liked=False,
            action_favorited=False,
            action_comment_viewed=False,
            action_followed=False,
            action_skipped_early=False,
        )
        self.assertTrue(ok2)

        # 3. Update session progress
        self.db.update_session_progress(
            session_id=sess_id,
            duration_seconds=120,
            videos_watched=2,
            likes_count=1,
            favorites_count=0,
            comments_viewed=1,
            follows_count=1,
            ads_skipped=0,
            lives_skipped=0,
            niche_matched_count=1,
            state="RUNNING",
        )

        # 4. Finalize session
        self.db.finalize_session(
            session_id=sess_id,
            duration_seconds=150,
            videos_watched=2,
            likes_count=1,
            favorites_count=0,
            comments_viewed=1,
            follows_count=1,
            ads_skipped=0,
            lives_skipped=0,
            niche_matched_count=1,
            state="COMPLETED",
            exit_reason="Target duration reached",
            end_time="2026-10-20T12:02:30",
        )

        # 5. Retrieve session and verify details
        sessions = self.db.get_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], sess_id)
        self.assertEqual(sessions[0]["state"], "COMPLETED")
        self.assertEqual(sessions[0]["videos_watched"], 2)
        self.assertEqual(sessions[0]["likes_count"], 1)
        self.assertEqual(sessions[0]["niche_matched_count"], 1)

        session_detail = self.db.get_session_by_id(sess_id)
        self.assertIsNotNone(session_detail)
        self.assertEqual(len(session_detail["videos"]), 2)
        self.assertTrue(session_detail["videos"][0]["is_niche"])
        self.assertTrue(session_detail["videos"][0]["action_liked"])
        self.assertTrue(session_detail["videos"][0]["action_followed"])
        self.assertFalse(session_detail["videos"][1]["is_niche"])

    def test_analytics_and_warming_score(self):
        sess_id = "sess_20261020_002"
        self.db.create_session(
            session_id=sess_id,
            start_time="2026-10-20T13:00:00",
            target_keywords=["escooter", "vesc"],
            session_follow_target=2,
        )

        for i in range(10):
            is_niche = i < 7  # 70% niche
            self.db.log_video_interaction(
                session_id=sess_id,
                caption=f"Video #{i} about {'escooter vesc' if is_niche else 'random news'}",
                matched_keywords=["escooter", "vesc"] if is_niche else [],
                is_niche=is_niche,
                is_ad=False,
                is_live=False,
                dwell_time_seconds=15.0 if is_niche else 6.0,
                action_liked=(i == 1),  # 1 like out of 10 = 10% (organic target 8-18%)
                action_favorited=False,
                action_comment_viewed=False,
                action_followed=False,
                action_skipped_early=False,
            )

        self.db.finalize_session(
            session_id=sess_id,
            duration_seconds=300,
            videos_watched=10,
            likes_count=1,
            favorites_count=0,
            comments_viewed=0,
            follows_count=0,
            ads_skipped=0,
            lives_skipped=0,
            niche_matched_count=7,
            state="COMPLETED",
            exit_reason="Target duration reached",
        )

        metrics = self.analytics.get_summary_metrics()
        self.assertEqual(metrics["lifetime"]["total_sessions"], 1)
        self.assertEqual(metrics["lifetime"]["total_videos_watched"], 10)
        self.assertEqual(metrics["lifetime"]["like_rate_percent"], 10.0)
        self.assertEqual(metrics["lifetime"]["niche_match_rate_percent"], 70.0)

        # Verify 4-Factor Account Warming Health Score
        score_data = metrics["warming_health_score"]
        self.assertGreaterEqual(score_data["score"], 70)
        self.assertIn("factors", score_data)
        self.assertIn("niche_alignment", score_data["factors"])
        self.assertIn("engagement_balance", score_data["factors"])
        self.assertIn("dwell_differentiation", score_data["factors"])
        self.assertIn("session_stability", score_data["factors"])

        # Trends
        trends = self.analytics.get_trends()
        self.assertEqual(len(trends["session_progression"]), 1)
        self.assertGreater(len(trends["top_keywords"]), 0)
        kws = [k["keyword"] for k in trends["top_keywords"]]
        self.assertIn("escooter", kws)

    def test_api_endpoints(self):
        class DummyDeviceManager:
            client = None
            def get_screen(self):
                return None
            def check_connection(self):
                return True

        cfg = {
            "device": {"wda_url": "http://localhost:8100"},
            "safety": {"screenshot_dir": "logs/captchas"},
            "niche": {"target_keywords": ["escooter"]},
            "schedule": {"enabled": False},
        }

        app = create_app(
            config=cfg,
            device_manager=DummyDeviceManager(),
        )
        # Inject our test DB
        app.state.db = self.db
        app.state.analytics = self.analytics
        client = TestClient(app)

        # Seed 1 session
        self.db.create_session("sess_api_test", start_time="2026-10-20T14:00:00")
        self.db.log_video_interaction(
            session_id="sess_api_test",
            caption="Kukirin unboxing",
            matched_keywords=["kukirin"],
            is_niche=True,
            dwell_time_seconds=12.0,
        )
        self.db.finalize_session(
            session_id="sess_api_test",
            duration_seconds=120,
            videos_watched=1,
            likes_count=1,
            favorites_count=0,
            comments_viewed=0,
            follows_count=0,
            ads_skipped=0,
            lives_skipped=0,
            niche_matched_count=1,
            state="COMPLETED",
        )

        # Test GET /api/sessions
        res = client.get("/api/sessions")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("sessions", data)
        self.assertGreaterEqual(len(data["sessions"]), 1)

        # Test GET /api/sessions/{session_id}
        res = client.get("/api/sessions/sess_api_test")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["session_id"], "sess_api_test")
        self.assertEqual(len(data["videos"]), 1)

        # Test GET /api/analytics/summary
        res = client.get("/api/analytics/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("lifetime", data)
        self.assertIn("warming_health_score", data)

        # Test GET /api/analytics/trends
        res = client.get("/api/analytics/trends")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("session_progression", data)
        self.assertIn("top_keywords", data)

        # Test GET /api/sessions/export/download (JSON)
        res = client.get("/api/sessions/export/download?format=json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "application/json")

        # Test GET /api/sessions/export/download (CSV)
        res = client.get("/api/sessions/export/download?format=csv")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/csv", res.headers["content-type"])
        self.assertIn("sess_api_test", res.text)

        # Test DELETE /api/sessions/{session_id}
        res = client.delete("/api/sessions/sess_api_test")
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(self.db.get_session_by_id("sess_api_test"))

    def test_session_runner_db_integration(self):
        from unittest.mock import MagicMock, patch
        from src.engine.session_runner import SessionRunner

        config = {
            "device": {"wda_url": "http://localhost:8100"},
            "follow": {"follows_per_session_min": 1, "follows_per_session_max": 2},
            "niche": {"target_keywords": ["escooter", "kukirin"]},
        }
        dev_mgr = MagicMock()
        runner = SessionRunner(config=config, device_manager=dev_mgr, db=self.db)

        with patch("threading.Thread") as mock_thread:
            runner.start()
            # Session should be immediately in self.db
            session_data = self.db.get_session_by_id(runner.stats.session_id)
            self.assertIsNotNone(session_data)
            self.assertEqual(session_data["state"], "RUNNING")
            self.assertIn("kukirin", session_data["target_keywords"])
            runner.stop()


if __name__ == "__main__":
    unittest.main()

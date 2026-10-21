import unittest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from src.web.app import create_app


class TestWebAuthorEndpoints(unittest.TestCase):
    def setUp(self):
        self.device_mgr = MagicMock()
        self.runner = MagicMock()
        self.config = {
            "device": {"wda_url": "http://localhost:8100"},
            "follow": {"enabled": True},
        }
        self.app = create_app(
            runner=self.runner,
            device_manager=self.device_mgr,
            config=self.config,
        )
        self.client = TestClient(self.app)

    def test_author_profile_endpoint(self):
        self.runner.test_author_profile.return_value = {
            "status": "ok",
            "opened": True,
            "is_following": False,
            "is_private": False,
            "has_pink_button": True,
            "follow_coords": [150.0, 250.0],
            "message": "Profile opened",
        }
        # Test POST
        res = self.client.post("/api/actions/test-author-profile")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["opened"])
        self.assertTrue(data["has_pink_button"])
        self.runner.test_author_profile.assert_called_once_with(auto_return=True)

        # Test GET
        res_get = self.client.get("/api/actions/test-author-profile")
        self.assertEqual(res_get.status_code, 200)

    def test_author_follow_endpoint(self):
        self.runner.test_author_follow.return_value = {
            "status": "ok",
            "followed": True,
            "message": "Successfully followed creator & returned to FYP",
        }
        res = self.client.post("/api/actions/test-author-follow")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["followed"])
        self.runner.test_author_follow.assert_called_once()


if __name__ == "__main__":
    unittest.main()

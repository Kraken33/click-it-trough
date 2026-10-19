import unittest
from unittest.mock import MagicMock, patch
from PIL import Image

from src.vision.detector import ScreenDetector
from src.physics.gesture import BiometricGestureEngine
from src.engine.session_runner import SessionRunner, SessionStats, SessionState


class FakeOCR:
    def __init__(self, text: str = "", observations=None):
        self.text = text
        self.observations = observations or []

    def extract_text(self, image, crop_box=None):
        return self.text

    def extract_header_text(self, image):
        return self.text

    def extract_observations(self, image):
        return self.observations


class TestProfileFollowLogic(unittest.TestCase):
    def setUp(self):
        self.dummy_img = Image.new("RGB", (393, 852), color="black")

    def test_detect_already_following_author(self):
        # Already following
        ocr_following = FakeOCR(text="@escooter_pro\n150 Following  20K Followers  100K Likes\nFollowing  Message\nVideos")
        detector = ScreenDetector(ocr_following)
        self.assertTrue(detector.is_already_following_author(self.dummy_img))

        # Friends
        ocr_friends = FakeOCR(text="@scooter_rider\nFriends  Message\nVideos")
        detector_friends = ScreenDetector(ocr_friends)
        self.assertTrue(detector_friends.is_already_following_author(self.dummy_img))

        # Unfollowed profile with Follow button
        ocr_unfollowed = FakeOCR(text="@new_creator\nFollow  Message\nVideos")
        detector_unfollowed = ScreenDetector(ocr_unfollowed)
        self.assertFalse(detector_unfollowed.is_already_following_author(self.dummy_img))

    def test_detect_private_account(self):
        ocr_private = FakeOCR(text="@secret_user\nThis account is private\nFollow to see their photos and videos")
        detector = ScreenDetector(ocr_private)
        self.assertTrue(detector.is_private_account(self.dummy_img))

        ocr_public = FakeOCR(text="@public_user\nFollow\nLatest videos")
        detector_public = ScreenDetector(ocr_public)
        self.assertFalse(detector_public.is_private_account(self.dummy_img))

    def test_find_follow_button_coords(self):
        # Observation format: (text, cx, cy, w, h)
        observations = [
            ("@creator", 0.5, 0.15, 0.3, 0.03),
            ("Follow", 0.48, 0.32, 0.25, 0.05),
            ("Message", 0.75, 0.32, 0.25, 0.05),
        ]
        ocr = FakeOCR(observations=observations)
        detector = ScreenDetector(ocr)
        coords = detector.find_follow_button_coords(self.dummy_img)
        self.assertIsNotNone(coords)
        self.assertAlmostEqual(coords[0], 0.48 * 393, places=1)
        self.assertAlmostEqual(coords[1], 0.32 * 852, places=1)

    def test_gesture_methods_exist_and_execute(self):
        client = MagicMock()
        client.tap.return_value = True
        client.swipe.return_value = True

        gesture = BiometricGestureEngine(client=client, screen_width=393, screen_height=852)
        self.assertTrue(gesture.tap_author_avatar())
        self.assertTrue(gesture.swipe_to_profile())
        self.assertTrue(gesture.tap_first_profile_video())
        self.assertTrue(gesture.tap_follow_button())
        self.assertTrue(gesture.tap_follow_button(x=150.0, y=280.0))
        self.assertTrue(gesture.tap_profile_back())

    def test_session_runner_samples_follow_target(self):
        config = {
            "device": {"wda_url": "http://localhost:8100", "screen_width": 393, "screen_height": 852},
            "follow": {
                "enabled": True,
                "min_matched_tags": 2,
                "follows_per_session_min": 2,
                "follows_per_session_max": 4,
            },
            "safety": {"max_daily_follows": 10},
        }
        dev_mgr = MagicMock()
        runner = SessionRunner(config=config, device_manager=dev_mgr)

        with patch("threading.Thread") as mock_thread:
            runner.start()
            self.assertTrue(2 <= runner.stats.session_follow_target <= 4)
            self.assertEqual(runner.stats.follows_count, 0)
            mock_thread.return_value.start.assert_called_once()
            runner.stop()

    @patch("time.sleep", return_value=None)
    def test_perform_profile_follow_sequence_success(self, mock_sleep):
        config = {
            "device": {"wda_url": "http://localhost:8100", "screen_width": 393, "screen_height": 852},
            "follow": {
                "enabled": True,
                "min_matched_tags": 2,
                "follows_per_session_min": 2,
                "follows_per_session_max": 3,
                "profile_videos_min": 1,
                "profile_videos_max": 1,
                "profile_video_dwell_min_sec": 0.1,
                "profile_video_dwell_max_sec": 0.2,
            },
            "safety": {"max_daily_follows": 10},
        }
        dev_mgr = MagicMock()
        dev_mgr.get_screen.return_value = self.dummy_img

        runner = SessionRunner(config=config, device_manager=dev_mgr)
        runner.stats.session_follow_target = 2

        # Mock detector to simulate author profile page
        runner.detector = MagicMock()
        runner.detector.detect_screen_state.return_value = ("profile", ["author_profile"])
        runner.detector.is_already_following_author.return_value = False
        runner.detector.is_private_account.return_value = False
        runner.detector.find_follow_button_coords.return_value = (196.0, 270.0)

        # Mock gestures
        runner.gesture = MagicMock()
        runner.gesture.swipe_to_profile.return_value = True
        runner.gesture.tap_author_avatar.return_value = True
        runner.gesture.tap_first_profile_video.return_value = True
        runner.gesture.tap_follow_button.return_value = True
        runner.gesture.tap_profile_back.return_value = True

        runner.recover_to_feed = MagicMock(return_value=(True, "feed"))

        success = runner._perform_profile_follow_sequence(["kukirin", "escooter"])
        self.assertTrue(success)
        self.assertEqual(runner.stats.follows_count, 1)

    @patch("time.sleep", return_value=None)
    def test_perform_profile_follow_sequence_skips_if_already_following(self, mock_sleep):
        config = {
            "device": {"wda_url": "http://localhost:8100", "screen_width": 393, "screen_height": 852},
            "follow": {"enabled": True, "min_matched_tags": 2},
            "safety": {"max_daily_follows": 10},
        }
        dev_mgr = MagicMock()
        dev_mgr.get_screen.return_value = self.dummy_img

        runner = SessionRunner(config=config, device_manager=dev_mgr)
        runner.detector = MagicMock()
        runner.detector.detect_screen_state.return_value = ("profile", ["author_profile"])
        runner.detector.is_already_following_author.return_value = True

        runner.gesture = MagicMock()
        runner.recover_to_feed = MagicMock(return_value=(True, "feed"))

        success = runner._perform_profile_follow_sequence(["vesc", "hyperscooter"])
        self.assertFalse(success)
        self.assertEqual(runner.stats.follows_count, 0)


if __name__ == "__main__":
    unittest.main()

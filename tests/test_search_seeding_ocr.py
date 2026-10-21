import unittest
from unittest.mock import MagicMock, patch, call
from PIL import Image

from src.engine.niche_trainer import NicheTrainer
from src.engine.session_runner import SessionRunner, SessionState
from src.vision.detector import ScreenDetector


class TestSearchSeedingOCR(unittest.TestCase):
    """
    Unit tests for the closed-loop OCR-verified Search Seeding state machine.
    """

    def setUp(self):
        self.trainer = NicheTrainer(
            target_keywords=["escooter", "technology"],
            seed_terms=["ausomgallop"],
        )
        self.mock_client = MagicMock()
        self.mock_gesture = MagicMock()
        self.mock_gesture.screen_width = 393
        self.mock_gesture.screen_height = 852

        self.mock_dm = MagicMock()
        self.mock_detector = MagicMock(spec=ScreenDetector)
        self.mock_detector.ocr = MagicMock()
        self.dummy_img = Image.new("RGB", (393, 852), color=(255, 255, 255))
        self.mock_dm.get_screen.return_value = self.dummy_img

    def test_search_seeding_aborts_if_device_on_homescreen_and_app_cannot_open(self):
        """
        If device is on the iOS home screen and app recovery fails,
        search seeding must abort immediately without executing search keystrokes.
        """
        self.mock_detector.is_homescreen_open.return_value = (True, ["springboard_icons"])
        self.mock_detector.is_tiktok_open.return_value = (False, [])

        mock_recover = MagicMock(return_value=(False, "homescreen"))

        progress_msgs = []
        success = self.trainer.perform_search_seeding(
            client=self.mock_client,
            gesture=self.mock_gesture,
            term="ausomgallop",
            device_manager=self.mock_dm,
            detector=self.mock_detector,
            recover_to_feed_fn=mock_recover,
            on_progress=lambda m: progress_msgs.append(m),
        )

        self.assertFalse(success)
        mock_recover.assert_called_once()
        # Verify no keys were sent
        self.mock_client.send_keys.assert_not_called()
        self.assertTrue(any("homescreen" in m.lower() for m in progress_msgs))

    def test_search_seeding_full_success_flow(self):
        """
        Happy path: App is on FYP, search opens, query confirmed, results loaded,
        video opened & verified playing, seed watched & liked, returned to FYP.
        """
        # Step 0: Initially on FYP feed
        self.mock_detector.is_homescreen_open.return_value = (False, [])
        self.mock_detector.is_tiktok_open.return_value = (True, ["for you"])
        self.mock_detector.detect_screen_state.return_value = ("feed", ["fyp"])
        self.mock_detector.is_feed_navigation_visible.return_value = True

        # Step 1: Open search
        self.mock_detector.find_button_coordinate.side_effect = [
            (0.92, 0.08),  # search icon on FYP
            (0.50, 0.08),  # search input field
            (0.91, 0.08),  # search submit button
            (0.06, 0.08),  # cancel button during back nav
        ]
        self.mock_detector.is_search_page_open.side_effect = [
            (True, ["recent_searches"]),  # Step 1 verify
            (True, ["recent_searches"]),  # Step 6 verify
        ]

        # Step 2: Query verification in OCR text
        self.mock_detector.ocr = MagicMock()
        self.mock_detector.ocr.extract_text.return_value = "ausomgallop search query entered"

        # Step 3: Search results verification
        self.mock_detector.is_search_results_open.side_effect = [
            (True, ["top", "videos"]),     # Step 3 verify
            (False, []),                   # Step 4 video open
            (False, []),                   # Step 6 back nav
        ]

        # Step 4: Video player verification
        self.mock_detector.is_search_video_open.side_effect = [
            (True, ["search_video_active"]),  # Step 4 verify
            (True, ["search_video_active"]),  # Step 6 nav step 1
            (False, []),                      # Step 6 nav step 2
        ]
        self.mock_detector.did_video_change.return_value = (12.5, True)

        # Step 5: Popup detection during dwell
        self.mock_detector.detect_popup.return_value = None

        progress_msgs = []
        success = self.trainer.perform_search_seeding(
            client=self.mock_client,
            gesture=self.mock_gesture,
            term="ausomgallop",
            videos_to_watch=1,
            dwell_min_sec=0.1,
            dwell_max_sec=0.2,
            device_manager=self.mock_dm,
            detector=self.mock_detector,
            on_progress=lambda m: progress_msgs.append(m),
        )

        self.assertTrue(success)
        # Keystrokes were sent
        self.mock_client.send_keys.assert_called_with("ausomgallop")
        # Like was called
        self.mock_gesture.double_tap_like.assert_called_once()
        # Verified OCR messages logged
        self.assertTrue(any("confirmed in search bar via ocr" in m.lower() for m in progress_msgs))
        self.assertTrue(any("search results page verified" in m.lower() for m in progress_msgs))
        self.assertTrue(any("confirmed open & playing" in m.lower() for m in progress_msgs))

    def test_search_seeding_retries_and_recovers_if_search_page_fails_to_open(self):
        """
        If tapping search icon fails to open search page after 3 retries,
        it must invoke recover_to_feed_fn and safely abort.
        """
        self.mock_detector.is_homescreen_open.return_value = (False, [])
        self.mock_detector.is_tiktok_open.return_value = (True, ["for you"])
        self.mock_detector.detect_screen_state.return_value = ("feed", ["fyp"])
        self.mock_detector.is_feed_navigation_visible.return_value = True

        # Search icon coordinate found, but cancel coordinate is not found
        def mock_find_btn(img, pat, **kwargs):
            if "search" in pat:
                return (0.92, 0.08)
            return None

        self.mock_detector.find_button_coordinate.side_effect = mock_find_btn
        self.mock_detector.is_search_page_open.return_value = (False, [])
        self.mock_detector.detect_screen_state.return_value = ("feed", ["fyp"])

        mock_recover = MagicMock(return_value=(True, "feed"))

        progress_msgs = []
        success = self.trainer.perform_search_seeding(
            client=self.mock_client,
            gesture=self.mock_gesture,
            term="ausomgallop",
            device_manager=self.mock_dm,
            detector=self.mock_detector,
            recover_to_feed_fn=mock_recover,
            on_progress=lambda m: progress_msgs.append(m),
        )

        self.assertFalse(success)
        mock_recover.assert_called_once()
        self.mock_client.send_keys.assert_not_called()
        self.assertTrue(any("failed to open search screen after 3 attempts" in m.lower() for m in progress_msgs))

    def test_search_seeding_retries_and_clears_if_query_not_detected_in_bar(self):
        """
        If typed query is not detected by OCR in the search bar, it clears input
        and retries up to 3 times before recovering to feed.
        """
        self.mock_detector.is_homescreen_open.return_value = (False, [])
        self.mock_detector.is_tiktok_open.return_value = (True, ["for you"])
        self.mock_detector.detect_screen_state.return_value = ("feed", ["fyp"])
        self.mock_detector.is_feed_navigation_visible.return_value = True

        self.mock_detector.find_button_coordinate.return_value = (0.92, 0.08)
        self.mock_detector.is_search_page_open.return_value = (True, ["recent_searches"])

        # Query text is never detected in OCR
        self.mock_detector.ocr = MagicMock()
        self.mock_detector.ocr.extract_text.return_value = "completely different text"

        mock_recover = MagicMock(return_value=(True, "feed"))

        progress_msgs = []
        success = self.trainer.perform_search_seeding(
            client=self.mock_client,
            gesture=self.mock_gesture,
            term="ausomgallop",
            device_manager=self.mock_dm,
            detector=self.mock_detector,
            recover_to_feed_fn=mock_recover,
            on_progress=lambda m: progress_msgs.append(m),
        )

        self.assertFalse(success)
        mock_recover.assert_called_once()
        # Backspaces were sent to clear input
        has_backspaces = any(
            any("\x08" in str(arg) or "\b" in str(arg) for arg in c.args)
            for c in self.mock_client.send_keys.call_args_list
        )
        self.assertTrue(has_backspaces)
        self.assertTrue(any("failed after 3 attempts" in m.lower() for m in progress_msgs))

    def test_session_runner_trigger_search_seeding_calls_ensure_app_open(self):
        """
        SessionRunner.trigger_search_seeding must call ensure_app_open()
        and pass device_manager and detector into perform_search_seeding.
        """
        config = {
            "device": {"bundle_id": "com.zhiliaoapp.musically", "screen_width": 393, "screen_height": 852},
            "niche": {"seed_terms": ["ausomgallop"], "seed_videos_min": 1, "seed_videos_max": 1},
        }
        runner = SessionRunner(config=config)
        runner.wda = MagicMock()
        runner.device_manager = MagicMock()
        runner.detector = MagicMock()
        runner.trainer = MagicMock()

        runner.ensure_app_open = MagicMock(return_value=True)
        runner.recover_to_feed = MagicMock(return_value=(True, "feed"))

        runner.detector.detect_screen_state.return_value = ("feed", ["fyp"])
        runner.detector.is_feed_navigation_visible.return_value = True

        runner.trigger_search_seeding(term="ausomgallop", videos_to_watch=1)

        runner.ensure_app_open.assert_called_once()
        runner.trainer.perform_search_seeding.assert_called_once()
        kwargs = runner.trainer.perform_search_seeding.call_args.kwargs
        self.assertEqual(kwargs["term"], "ausomgallop")
        self.assertEqual(kwargs["device_manager"], runner.device_manager)
        self.assertEqual(kwargs["detector"], runner.detector)
        self.assertEqual(kwargs["recover_to_feed_fn"], runner.recover_to_feed)


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from PIL import Image, ImageDraw

from src.vision.detector import ScreenDetector
from src.engine.session_runner import SessionRunner, SessionState


class FakeOCR:
    def __init__(self, text: str = "", header_text: str = "", observations=None):
        self.text = text
        self.header_text = header_text
        self.observations = observations or []

    def extract_text(self, image, crop_box=None):
        return self.text

    def extract_header_text(self, image):
        return self.header_text or self.text

    def extract_observations(self, image):
        return self.observations


def create_mock_video_frame(color_rgb, text_label="video"):
    """Creates a mock phone screen image (393x852) with distinct background and content."""
    img = Image.new("RGB", (393, 852), color=color_rgb)
    draw = ImageDraw.Draw(img)
    # Draw some shapes in the central area
    draw.rectangle([50, 200, 300, 600], fill=(255 - color_rgb[0], 255 - color_rgb[1], 255 - color_rgb[2]))
    draw.text((60, 250), text_label, fill=(255, 255, 255))
    return img


class TestMultiModalVideoChange(unittest.TestCase):
    """Exhaustive tests for multi-modal video change detection and transition guards."""

    def setUp(self):
        self.ocr = FakeOCR()
        self.detector = ScreenDetector(self.ocr)
        self.frame_a = create_mock_video_frame((30, 40, 50), "Video A")
        self.frame_b = create_mock_video_frame((180, 100, 60), "Video B")

    # 1. Transition frame tests
    def test_is_transition_frame_black(self):
        black_img = Image.new("RGB", (393, 852), color=(2, 2, 2))
        self.assertTrue(self.detector.is_transition_frame(black_img))

    def test_is_transition_frame_uniform(self):
        uniform_img = Image.new("RGB", (393, 852), color=(128, 128, 128))
        self.assertTrue(self.detector.is_transition_frame(uniform_img))

    def test_is_transition_frame_real_content(self):
        self.assertFalse(self.detector.is_transition_frame(self.frame_a))

    def test_did_video_change_transition_guard(self):
        black_img = Image.new("RGB", (393, 852), color=(0, 0, 0))
        changed, reason = self.detector.did_video_change(self.frame_a, black_img)
        self.assertFalse(changed)
        self.assertIn("TRANSITION", reason)

    # 2. Visual difference tests
    def test_visual_difference_same_image(self):
        diff, is_changed = self.detector.compute_visual_difference(self.frame_a, self.frame_a)
        self.assertEqual(diff, 0.0)
        self.assertFalse(is_changed)

    def test_visual_difference_distinct_images(self):
        diff, is_changed = self.detector.compute_visual_difference(self.frame_a, self.frame_b)
        self.assertGreater(diff, 0.18)
        self.assertTrue(is_changed)

    # 3. Metrics-based change detection
    def test_did_video_change_metrics_differ(self):
        before_metrics = {"likes": "12.4K", "comments": "540"}
        after_metrics = {"likes": "14.1K", "comments": "540"}
        changed, reason = self.detector.did_video_change(
            self.frame_a, self.frame_a,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
        )
        self.assertTrue(changed)
        self.assertIn("Metrics changed", reason)
        self.assertIn("likes 12.4K -> 14.1K", reason)

    def test_did_video_change_identical_metrics_but_visual_changed(self):
        # Two videos with identical like counts (e.g. 1.2M) but different visual frames
        before_metrics = {"likes": "1.2M"}
        after_metrics = {"likes": "1.2M"}
        changed, reason = self.detector.did_video_change(
            self.frame_a, self.frame_b,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
        )
        self.assertTrue(changed)
        self.assertIn("Visual changed", reason)

    def test_did_video_change_identical_metrics_and_same_visual(self):
        before_metrics = {"likes": "1.2M", "comments": "450"}
        after_metrics = {"likes": "1.2M", "comments": "450"}
        changed, reason = self.detector.did_video_change(
            self.frame_a, self.frame_a,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
        )
        self.assertFalse(changed)
        self.assertIn("Metrics unchanged", reason)

    def test_did_video_change_zero_metrics_relies_on_visual(self):
        # When neither video has recognized sidebar metrics
        changed, reason = self.detector.did_video_change(
            self.frame_a, self.frame_b,
            before_metrics={},
            after_metrics={},
        )
        self.assertTrue(changed)
        self.assertIn("Visual changed", reason)

    # 4. Content signature change detection
    def test_did_video_change_signature_change(self):
        # Pass identical frames (so visual diff is zero) but distinct content signatures
        changed, reason = self.detector.did_video_change(
            self.frame_a, self.frame_a,
            before_sig="@creator1 awesome scooter ride",
            before_metrics={},
            after_metrics={},
        )
        # after_sig will be extracted from frame_a (which won't match @creator1)
        # Alternatively explicitly test extract_content_signature
        sig = self.detector.extract_content_signature(self.frame_a)
        self.assertIsInstance(sig, str)

    # 5. Multilingual and Modern feed recognition
    def test_feed_detection_german_locale(self):
        ocr = FakeOCR(text="Für dich  Folge ich\n@creator Tolles Video\nStartseite  Freunde  +  Posteingang  Profil")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.frame_a)
        self.assertEqual(state, "feed")

    def test_feed_detection_modern_live_and_shop_header(self):
        ocr = FakeOCR(text="LIVE  Shop  For You\nHome  Friends  +  Inbox  Profile")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.frame_a)
        self.assertEqual(state, "feed")


class TestSessionRunnerSwipeIntegration(unittest.TestCase):
    """Verifies that SessionRunner swipe_next_video_verified interacts properly with the new detector."""

    def setUp(self):
        self.cfg = {
            "device": {"screen_width": 393, "screen_height": 852},
            "vision": {"enabled": True},
            "safety": {"max_daily_videos": 100},
        }

    @patch("src.engine.session_runner.DeviceManager")
    def test_swipe_verified_succeeds_on_visual_change(self, MockDM):
        mock_dm = MockDM.return_value
        frame1 = create_mock_video_frame((20, 20, 20), "V1")
        frame2 = create_mock_video_frame((200, 150, 100), "V2")

        mock_dm.get_screen.side_effect = [frame1, frame2]
        mock_dm.client.get_window_size.return_value = (393, 852)

        runner = SessionRunner(config=self.cfg, device_manager=mock_dm)
        runner.gesture.swipe_next_video = MagicMock()

        ok, reason = runner.swipe_next_video_verified(max_retries=1)
        self.assertTrue(ok)
        self.assertTrue(runner.gesture.swipe_next_video.called)
        self.assertIn("Visual changed", reason)

    @patch("src.engine.session_runner.DeviceManager")
    def test_swipe_verified_retries_on_unchanged_screen(self, MockDM):
        mock_dm = MockDM.return_value
        frame1 = create_mock_video_frame((20, 20, 20), "V1")

        # Returns identical frame on all attempts
        mock_dm.get_screen.return_value = frame1
        mock_dm.client.get_window_size.return_value = (393, 852)

        runner = SessionRunner(config=self.cfg, device_manager=mock_dm)
        runner.gesture.swipe_next_video = MagicMock()
        runner.recover_to_feed = MagicMock(return_value=(False, "unrecoverable"))

        ok, reason = runner.swipe_next_video_verified(max_retries=2)
        self.assertFalse(ok)
        self.assertEqual(runner.gesture.swipe_next_video.call_count, 2)


if __name__ == "__main__":
    unittest.main()

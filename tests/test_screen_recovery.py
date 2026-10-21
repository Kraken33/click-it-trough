import unittest
from unittest.mock import MagicMock, patch
from PIL import Image

from src.vision.detector import ScreenDetector
from src.engine.session_runner import SessionRunner, SessionState


class FakeOCR:
    """Mock OCR provider returning pre-configured text and bounding box observations."""

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


class TestScreenInterfaceDetection(unittest.TestCase):
    """Exhaustive tests verifying ScreenDetector identifies every TikTok screen state."""

    def setUp(self):
        self.dummy_img = Image.new("RGB", (393, 852), color="black")

    # 1. Clean FYP Feed
    def test_detect_feed(self):
        ocr = FakeOCR(
            text="Following  For You\n@cool_creator Clean FYP video! #viral #fyp\nHome  Friends  +  Inbox  Profile",
            header_text="Following  For You",
        )
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "feed")
        self.assertTrue(detector.is_tiktok_open(self.dummy_img, text=ocr.text)[0])

    # 2. Likes List / "Liked by" Modal Drawer
    def test_detect_likes_list_header_and_users(self):
        ocr = FakeOCR(text="Likes\n@alice  Follow\n@bob  Follow back\n@charlie  Friends")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "likes_list")

    def test_detect_likes_list_liked_by_variant(self):
        ocr = FakeOCR(text="Liked by john_doe and 142 others\nFollow\nFollow back")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "likes_list")

    def test_detect_likes_list_post_activity(self):
        ocr = FakeOCR(text="Post activity\nAccounts who liked this post\nFollow")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "likes_list")

    def test_likes_list_does_not_false_positive_on_profile(self):
        # A profile has Following, Followers, and Likes counts, but is NOT a likes list drawer
        ocr = FakeOCR(text="@famous_creator\n120 Following  4.5M Followers  89M Likes\nEdit profile\nVideos")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "profile")

    def test_likes_list_does_not_false_positive_on_comment_section(self):
        # Comments with reply counts and likes should be classified as comments
        ocr = FakeOCR(text="Comments (430)\nAdd comment...\nReply\nLoved this! 12 likes")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "comments")

    # 3. Comments Drawer
    def test_detect_comments_standard(self):
        ocr = FakeOCR(text="Comments (120)\nAdd comment...\nReply\nView 24 replies\nAwesome video!")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "comments")

    def test_detect_comments_localized(self):
        ocr = FakeOCR(text="Коментарі (85)\nДодати коментар...\nВідповісти\nСупер відео!")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "comments")

    # 4. Comment Input with Active Keyboard
    def test_detect_comment_input_with_keyboard_keys(self):
        ocr = FakeOCR(text="Add comment\nspace  123  return  send")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "comment_input")

    def test_detect_comment_input_with_replying_to(self):
        ocr = FakeOCR(text="Replying to @cool_creator\nspace  123  done")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "comment_input")

    def test_detect_comment_input_cyrillic_keyboard(self):
        ocr = FakeOCR(text="Додати коментар\nпробел  123  отправить")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "comment_input")

    def test_comment_input_does_not_false_positive_on_send_to_or_send_gift(self):
        # "Send to" is in share sheet, and "Send gift" is in live room
        ocr_share = FakeOCR(text="Share to\nSend to\nCopy link\nRepost")
        detector = ScreenDetector(ocr_share)
        self.assertFalse(detector.is_comment_input_open(self.dummy_img, text=ocr_share.text)[0])

        ocr_live = FakeOCR(text="LIVE\nTap to join\nSend gift\nRose")
        self.assertFalse(detector.is_comment_input_open(self.dummy_img, text=ocr_live.text)[0])

    # 5. Share Sheet
    def test_detect_share_sheet(self):
        ocr = FakeOCR(text="Share to\nSend to\nCopy link\nRepost\nWhatsApp\nMessenger\nSnapchat")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "share")

    def test_detect_share_sheet_localized(self):
        ocr = FakeOCR(text="Поділитися\nПоделиться\nСкопировать ссылку\nRepost")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "share")

    # 6. TikTok Shop / Product Drawer
    def test_detect_shop_drawer(self):
        ocr = FakeOCR(text="TikTok Shop\nProduct details\nAdd to cart\nBuy now\nFree shipping\n1.2k sold")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "shop")

    def test_detect_shop_product_anchor(self):
        ocr = FakeOCR(text="View product\nOrder now\nCoupons available\nFree shipping")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "shop")

    # 7. Sound / Audio Page
    def test_detect_sound_page(self):
        ocr = FakeOCR(text="Use this sound\nAdd to Favorites\nOriginal sound - artist name\n12.4K videos")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "sound")

    def test_detect_sound_page_metadata_variant(self):
        ocr = FakeOCR(text="Contains: Mozart Lacrimosa\nOriginal sound by: jojo.aitools\nSave  Template\n1.4M posts")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "sound")

    def test_sound_page_not_detected_on_feed_with_original_sound(self):
        # A video playing on FYP displays "original sound - artist" in the music ticker
        ocr = FakeOCR(
            text="Following  For You\n@cool_creator Check this out! #fyp #viral\noriginal sound - popular artist\nHome  Friends  +  Inbox  Profile",
            header_text="Following  For You",
        )
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "feed")
        self.assertFalse(detector.is_sound_page_open(self.dummy_img, text=ocr.text)[0])

    def test_sound_page_not_detected_on_feed_with_add_to_favorites_or_story(self):
        ocr = FakeOCR(
            text="For You\nAdd to favorites\nPost to story\nHome  Friends  +  Inbox  Profile",
            header_text="For You",
        )
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "feed")
        self.assertFalse(detector.is_sound_page_open(self.dummy_img, text=ocr.text)[0])

    # 8. Camera / Creation Mode ('+' tab)
    def test_detect_camera_screen(self):
        ocr = FakeOCR(text="Upload  Effects  Templates\n15s  60s  10m  Photo\nFlip  Filters  Timer")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "camera")

    # 9. Active LIVE Room
    def test_detect_live_room(self):
        ocr = FakeOCR(text="LIVE\nTap to join\nMulti-guest\nSend gift\nRose\nHost\nShare live")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "live")

    # 10. Story Player
    def test_detect_story_viewer(self):
        ocr = FakeOCR(text="Message...\n3h ago\nGreat day today!")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "story")

    # 11. Profile Pages (Author Profile & Own Profile Tab)
    def test_detect_author_profile(self):
        ocr = FakeOCR(text="@famous_creator\n120 Following  4.5M Followers  89M Likes\nFollow\nVideos")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "profile")
        self.assertNotIn("profile_tab", markers)

    def test_detect_own_profile_tab(self):
        ocr = FakeOCR(text="@my_handle\n50 Following  1.2K Followers  10K Likes\nEdit profile\nHome  Inbox  Profile")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "profile")
        self.assertIn("profile_tab", markers)

    # 12. Search / Discover Page
    def test_detect_search_page(self):
        ocr = FakeOCR(text="Search\nRecent searches\nTrending searches\nYou may like\nCancel")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "search")

    # 13. Feed Wrong Header Tab (Following / Friends / STEM without For You)
    def test_detect_feed_wrong_tab_following(self):
        ocr = FakeOCR(text="Following  Friends\nVideo content...", header_text="Following  Friends")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "feed_wrong_tab")

    def test_detect_feed_wrong_tab_stem(self):
        ocr = FakeOCR(text="STEM  Shop\nScience video...", header_text="STEM  Shop")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "feed_wrong_tab")

    # 14. Popups & Modal Alerts & Captchas
    def test_detect_popup_notifications(self):
        ocr = FakeOCR(text="Turn on notifications\nDon't miss updates from creators\nNot Now  Enable")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "popup")
        self.assertIn("notifications", markers)

    def test_detect_popup_tracking(self):
        ocr = FakeOCR(text="Allow TikTok to track your activity across apps?\nAsk App not to Track\nAllow")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "popup")
        self.assertIn("tracking", markers)

    def test_detect_popup_rating(self):
        ocr = FakeOCR(text="Enjoying TikTok?\nRate us on the App Store\nNot Now  Rate")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "popup")
        self.assertIn("rating", markers)

    def test_detect_popup_update(self):
        ocr = FakeOCR(text="New version available\nUpdate TikTok to continue\nDismiss  Update")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "popup")
        self.assertIn("update", markers)

    def test_detect_captcha_challenge(self):
        ocr = FakeOCR(text="Security Verification\nVerify to continue\nDrag the slider to complete the puzzle")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "popup")
        self.assertIn("captcha_or_verification", markers)

    # 15. iOS Homescreen / SpringBoard
    def test_detect_homescreen(self):
        ocr = FakeOCR(text="App Library\nSuggestions\nRecently Added\nSocial  Utilities")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "homescreen")

    # 16. Other Tab (Inbox Tab Header)
    def test_detect_inbox_tab(self):
        ocr = FakeOCR(text="Inbox\nDirect messages\nNew message\nHome  Inbox  Profile", header_text="Inbox  Direct messages")
        detector = ScreenDetector(ocr)
        state, markers = detector.detect_screen_state(self.dummy_img)
        self.assertEqual(state, "other_tab")

    # 17. Button Coordinate Finder
    def test_find_button_coordinate(self):
        obs = [
            ("Cancel", 0.90, 0.07, 0.10, 0.03),
            ("Search", 0.50, 0.07, 0.60, 0.04),
        ]
        ocr = FakeOCR(observations=obs)
        detector = ScreenDetector(ocr)
        coord = detector.find_button_coordinate(self.dummy_img, r"cancel")
        self.assertIsNotNone(coord)
        self.assertEqual(coord, (0.90, 0.07))
        coord_px = detector.find_button_coordinate(self.dummy_img, r"cancel", normalized=False)
        self.assertEqual(coord_px, (int(0.90 * 393), int(0.07 * 852)))


class TestSessionRunnerRecoveryExecution(unittest.TestCase):
    """Exhaustive tests verifying SessionRunner executes targeted exits for every screen state."""

    def setUp(self):
        self.dummy_img = Image.new("RGB", (393, 852), color="black")
        self.cfg = {"device": {"wda_url": "http://localhost:8100", "screen_width": 393, "screen_height": 852}}

    def _create_mock_runner(self, initial_state: str, markers=None):
        mock_dm = MagicMock()
        mock_wda = MagicMock()
        mock_dm.client = mock_wda
        mock_dm.get_screen.return_value = self.dummy_img

        runner = SessionRunner(config=self.cfg, device_manager=mock_dm)
        # 1st call: initial state; 2nd call: recovered feed
        runner.detector.detect_screen_state = MagicMock(side_effect=[
            (initial_state, markers or [initial_state]),
            ("feed", ["for you"]),
        ])
        return runner, mock_wda

    def test_recovery_aborts_immediately_if_already_on_feed(self):
        runner, mock_wda = self._create_mock_runner("feed")
        runner.detector.detect_screen_state = MagicMock(return_value=("feed", ["for you"]))
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "feed")
        mock_wda.tap.assert_not_called()
        mock_wda.dismiss_keyboard.assert_not_called()

    def test_recovery_from_search_uses_ocr_cancel_button(self):
        runner, mock_wda = self._create_mock_runner("search")
        runner.detector.find_button_coordinate = MagicMock(return_value=(0.91, 0.07))
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "search")
        # Should tap the OCR-detected Cancel button at (0.91 * 393, 0.07 * 852)
        mock_wda.tap.assert_called_with(0.91 * 393, 0.07 * 852)

    def test_recovery_from_profile_uses_ocr_home_tab(self):
        runner, mock_wda = self._create_mock_runner("profile", markers=["author_profile"])
        runner.detector.find_button_coordinate = MagicMock(return_value=(0.10, 0.95))
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "profile")
        # Should tap the OCR-detected Home tab at (0.10 * 393, 0.95 * 852)
        mock_wda.tap.assert_called_with(0.10 * 393, 0.95 * 852)

    def test_recovery_from_likes_list(self):
        runner, mock_wda = self._create_mock_runner("likes_list")
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "likes_list")
        self.assertTrue(mock_wda.tap.called)

    def test_recovery_from_comments(self):
        runner, mock_wda = self._create_mock_runner("comments")
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "comments")
        self.assertTrue(mock_wda.dismiss_keyboard.called)

    def test_recovery_from_comment_input(self):
        runner, mock_wda = self._create_mock_runner("comment_input")
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "comment_input")
        self.assertTrue(mock_wda.dismiss_keyboard.called)

    def test_recovery_from_share_sheet(self):
        runner, mock_wda = self._create_mock_runner("share")
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "share")
        self.assertTrue(mock_wda.tap.called)

    def test_recovery_from_shop(self):
        runner, mock_wda = self._create_mock_runner("shop")
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "shop")
        self.assertTrue(mock_wda.tap.called)

    def test_recovery_from_sound(self):
        runner, mock_wda = self._create_mock_runner("sound")
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "sound")
        self.assertTrue(mock_wda.tap.called)

    def test_recovery_from_camera(self):
        runner, mock_wda = self._create_mock_runner("camera")
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "camera")
        self.assertTrue(mock_wda.tap.called)

    def test_recovery_from_live(self):
        runner, mock_wda = self._create_mock_runner("live")
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "live")
        self.assertTrue(mock_wda.tap.called)

    def test_recovery_from_story(self):
        runner, mock_wda = self._create_mock_runner("story")
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "story")
        self.assertTrue(mock_wda.tap.called)

    def test_recovery_from_author_profile(self):
        runner, mock_wda = self._create_mock_runner("profile", markers=["author_profile"])
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "profile")
        self.assertTrue(mock_wda.tap.called)

    def test_recovery_from_own_profile_tab(self):
        runner, mock_wda = self._create_mock_runner("profile", markers=["profile_tab"])
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "profile")
        # Should tap bottom Home tab
        self.assertTrue(mock_wda.tap.called)

    def test_recovery_from_search(self):
        runner, mock_wda = self._create_mock_runner("search")
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "search")
        self.assertTrue(mock_wda.tap.called)

    def test_recovery_from_scan(self):
        runner, mock_wda = self._create_mock_runner("scan")
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "scan")
        self.assertTrue(mock_wda.tap.called)

    def test_recovery_from_feed_wrong_tab(self):
        runner, mock_wda = self._create_mock_runner("feed_wrong_tab", markers=["following"])
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "feed_wrong_tab")
        # Taps top For You tab
        self.assertTrue(mock_wda.tap.called)

    def test_recovery_from_popup(self):
        runner, mock_wda = self._create_mock_runner("popup", markers=["notifications"])
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "popup")
        self.assertTrue(mock_wda.tap.called)

    def test_recovery_from_homescreen(self):
        runner, mock_wda = self._create_mock_runner("homescreen")
        runner.ensure_app_open = MagicMock(return_value=True)
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "homescreen")
        self.assertTrue(runner.ensure_app_open.called)

    def test_recovery_from_other_tab(self):
        runner, mock_wda = self._create_mock_runner("other_tab")
        ok, state = runner.recover_to_feed(max_attempts=1)
        self.assertTrue(ok)
        self.assertEqual(state, "other_tab")
        self.assertTrue(mock_wda.tap.called)

    # Multi-Stage Escalation Ladder
    def test_stage2_universal_escalation_ladder(self):
        mock_dm = MagicMock()
        mock_wda = MagicMock()
        mock_dm.client = mock_wda
        mock_dm.get_screen.return_value = self.dummy_img

        runner = SessionRunner(config=self.cfg, device_manager=mock_dm)

        # Step 1 fails to exit, Step 2 succeeds to feed
        runner.detector.detect_screen_state = MagicMock(side_effect=[
            ("likes_list", ["likes_drawer_with_users"]),
            ("likes_list", ["likes_drawer_with_users"]),
            ("likes_list", ["likes_drawer_with_users"]),
            ("feed", ["for you"]),
        ])

        ok, final_state = runner.recover_to_feed(max_attempts=2)
        self.assertTrue(ok)
        self.assertEqual(final_state, "likes_list")
        self.assertTrue(mock_wda.tap.called)

    def test_stage3_app_relaunch_fallback(self):
        mock_dm = MagicMock()
        mock_wda = MagicMock()
        mock_dm.client = mock_wda
        mock_dm.get_screen.return_value = self.dummy_img

        runner = SessionRunner(config=self.cfg, device_manager=mock_dm)
        runner.restart_app = MagicMock(return_value=True)

        # Steps 1 and 2 fail, then restart cleanly recovers to feed
        runner.detector.detect_screen_state = MagicMock(side_effect=[
            ("shop", ["shop"]), # step 1 initial
            ("shop", ["shop"]), # step 1 post-action
            ("shop", ["shop"]), # step 2 initial
            ("shop", ["shop"]), # step 2 post-action
            ("feed", ["for you"]), # post-restart check
        ])

        ok, final_state = runner.recover_to_feed(max_attempts=2)
        self.assertTrue(ok)
        self.assertEqual(final_state, "feed")
        self.assertTrue(runner.restart_app.called)

    def test_stage3_sentinel_alert_when_unrecoverable(self):
        mock_dm = MagicMock()
        mock_wda = MagicMock()
        mock_dm.client = mock_wda
        mock_dm.get_screen.return_value = self.dummy_img

        runner = SessionRunner(config=self.cfg, device_manager=mock_dm)
        runner.restart_app = MagicMock(return_value=False)
        runner.safety.trigger_alert = MagicMock()

        runner.detector.detect_screen_state = MagicMock(return_value=("unknown", []))

        ok, final_state = runner.recover_to_feed(max_attempts=1)
        self.assertFalse(ok)
        self.assertEqual(final_state, "unknown")
        self.assertEqual(runner.stats.state, SessionState.CAPTCHA_HALTED)
        self.assertTrue(runner.safety.trigger_alert.called)


if __name__ == "__main__":
    unittest.main()

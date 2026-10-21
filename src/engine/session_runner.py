import logging
import os
import random
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image

from ..bridge.device_manager import DeviceManager
from ..physics.gesture import BiometricGestureEngine
from ..safety.alert import SafetySentinel
from ..vision.detector import ScreenDetector
from ..vision.ocr import VisionOCR
from .niche_trainer import NicheTrainer
from ..storage.session_db import SessionDatabase

logger = logging.getLogger(__name__)


class SessionState(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    CAPTCHA_HALTED = "CAPTCHA_HALTED"
    STOPPED = "STOPPED"


@dataclass
class SessionStats:
    session_id: str = ""
    start_time: str = ""
    duration_seconds: int = 0
    videos_watched: int = 0
    likes_count: int = 0
    favorites_count: int = 0
    comments_viewed: int = 0
    ads_skipped: int = 0
    lives_skipped: int = 0
    niche_matched_count: int = 0
    follows_count: int = 0
    session_follow_target: int = 0
    current_action: str = "Ready"
    current_dwell_remaining: float = 0.0
    current_caption: str = ""
    current_matched_keywords: List[str] = field(default_factory=list)
    state: SessionState = SessionState.IDLE


class SessionRunner:
    """
    Executes the TikTok FYP loop with biometric gestures, OCR niche weighting,
    real-time safety checks, and WebSocket status broadcast.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        device_manager: Optional[DeviceManager] = None,
        on_status_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        db: Optional[Any] = None,
    ):
        self.config = config
        self.device_manager = device_manager or DeviceManager(
            wda_url=config.get("device", {}).get("wda_url", "http://localhost:8100")
        )
        self.wda = self.device_manager.client
        self.on_status_update = on_status_update

        # Session Persistence
        if db is False:
            self.db = None
        elif db is not None:
            self.db = db
        else:
            try:
                self.db = SessionDatabase()
            except Exception as e:
                logger.warning(f"Could not initialize SessionDatabase: {e}")
                self.db = None

        # Vision & Safety Components
        self.ocr = VisionOCR()
        self.detector = ScreenDetector(self.ocr)
        self.safety = SafetySentinel(
            screenshot_dir=config.get("safety", {}).get("screenshot_dir", "logs/captchas"),
            play_sound=config.get("safety", {}).get("play_sound_on_alert", True),
            macos_notification=config.get("safety", {}).get("macos_notification", True),
        )

        # Niche Trainer
        niche_cfg = config.get("niche", {})
        self.trainer = NicheTrainer(
            target_keywords=niche_cfg.get("target_keywords", []),
            seed_terms=niche_cfg.get("seed_terms", []),
        )

        # Gesture Engine (initialized lazily or with defaults)
        phys_cfg = config.get("physics", {})
        self.gesture = BiometricGestureEngine(
            client=self.wda,
            screen_width=config.get("device", {}).get("screen_width", 393),
            screen_height=config.get("device", {}).get("screen_height", 852),
            handedness=phys_cfg.get("handedness", "right"),
            curve_deviation_px=phys_cfg.get("curve_deviation_px", 24.0),
            jitter_intensity_px=phys_cfg.get("jitter_intensity_px", 2.0),
        )

        # Threading & Control Flags
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._skip_flag = threading.Event()
        self.stats = SessionStats()

    def update_config(self, new_config: Dict[str, Any]):
        """Dynamically updates running configuration parameters from Web UI."""
        self.config.update(new_config)
        niche_cfg = self.config.get("niche", {})
        self.trainer.target_keywords = [k.lower().strip() for k in niche_cfg.get("target_keywords", [])]
        self.trainer.seed_terms = niche_cfg.get("seed_terms", [])

    def get_stats(self) -> Dict[str, Any]:
        """Returns snapshot of current session metrics."""
        return asdict(self.stats)

    def _broadcast_status(self, action: str, **kwargs):
        self.stats.current_action = action
        for k, v in kwargs.items():
            if hasattr(self.stats, k):
                setattr(self.stats, k, v)
        if self.on_status_update:
            try:
                self.on_status_update(self.get_stats())
            except Exception as e:
                logger.debug(f"Broadcast error: {e}")

    def start(self, duration_minutes: Optional[int] = None) -> bool:
        """Starts the warming session in a background worker thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Session is already running.")
            return False

        self._stop_event.clear()
        self._pause_event.clear()
        self._skip_flag.clear()

        follow_cfg = self.config.get("follow", {})
        f_min = int(follow_cfg.get("follows_per_session_min", 1))
        f_max = int(follow_cfg.get("follows_per_session_max", 3))
        follow_target = random.randint(min(f_min, f_max), max(f_min, f_max))

        self.stats = SessionStats(
            session_id=datetime.now().strftime("sess_%Y%m%d_%H%M%S"),
            start_time=datetime.now().isoformat(),
            session_follow_target=follow_target,
            state=SessionState.RUNNING,
            current_action="Starting session...",
        )

        if self.db:
            try:
                self.db.create_session(
                    session_id=self.stats.session_id,
                    start_time=self.stats.start_time,
                    target_keywords=self.trainer.target_keywords,
                    session_follow_target=follow_target,
                )
            except Exception as e:
                logger.error(f"Failed to record session start in DB: {e}")

        self._thread = threading.Thread(
            target=self._run_loop,
            args=(duration_minutes,),
            daemon=True,
        )
        self._thread.start()
        return True

    def pause(self):
        """Pauses the active session."""
        self._pause_event.set()
        self.stats.state = SessionState.PAUSED
        self._broadcast_status("Session paused by user")

    def resume(self):
        """Resumes a paused or captcha-halted session."""
        self._pause_event.clear()
        self.stats.state = SessionState.RUNNING
        self._broadcast_status("Resuming session...")

    def ensure_app_open(self, max_retries: int = 4) -> bool:
        """
        Launches TikTok and uses OCR to verify that TikTok-specific UI text
        (e.g. 'For You', 'Following', 'LIVE', navigation bar) is present on screen.
        Retries launch if not verified.
        """
        # Fast path: check if app is already open and verified on screen
        screen = self.device_manager.get_screen()
        if screen:
            is_open, markers = self.detector.is_tiktok_open(screen)
            if is_open:
                return True

        bundle_id = self.config.get("device", {}).get("bundle_id", "com.zhiliaoapp.musically")
        for attempt in range(1, max_retries + 1):
            if self._stop_event.is_set():
                return False
            self._broadcast_status(f"Opening TikTok (attempt {attempt}/{max_retries})...")
            try:
                self.wda.launch_app(bundle_id)
            except Exception as e:
                logger.debug(f"Error launching app: {e}")
            time.sleep(2.0)

            # OCR verification
            screen = self.device_manager.get_screen()
            if screen:
                is_open, markers = self.detector.is_tiktok_open(screen)
                if is_open:
                    self._broadcast_status(f"TikTok verified open via OCR [{', '.join(markers[:3])}]")
                    logger.info(f"TikTok launch verified via OCR: {markers}")
                    return True
                else:
                    logger.warning(f"TikTok not detected on screen via OCR on attempt {attempt}")
            time.sleep(1.0)

        self._broadcast_status("TikTok launch could not be confirmed via OCR.")
        return False

    def close_app(self, max_retries: int = 3) -> bool:
        """
        Terminates TikTok and uses OCR to verify that the device is on the iOS home screen
        (e.g. 'App Library', 'Suggestions', folder titles) and TikTok is no longer visible.
        """
        if not self.config.get("device", {}).get("close_app_on_finish", True):
            return True

        bundle_id = self.config.get("device", {}).get("bundle_id", "com.zhiliaoapp.musically")
        for attempt in range(1, max_retries + 1):
            self._broadcast_status(f"Closing TikTok & returning home (attempt {attempt}/{max_retries})...")
            try:
                self.wda.terminate_app(bundle_id)
            except Exception as e:
                logger.debug(f"Error terminating app {bundle_id}: {e}")
            try:
                self.wda.homescreen()
            except Exception as e:
                logger.debug(f"Error navigating to homescreen: {e}")
            time.sleep(1.2)

            # OCR verification
            screen = self.device_manager.get_screen()
            if screen:
                is_home, home_markers = self.detector.is_homescreen_open(screen)
                is_tiktok, _ = self.detector.is_tiktok_open(screen)
                if is_home or not is_tiktok:
                    label = ', '.join(home_markers[:3]) if home_markers else 'TikTok closed'
                    self._broadcast_status(f"Home screen verified via OCR [{label}]")
                    logger.info(f"App termination verified via OCR. Homescreen markers: {home_markers}")
                    return True
                else:
                    logger.warning(f"TikTok still detected on screen via OCR on attempt {attempt}")
            time.sleep(0.8)

        self._broadcast_status("App close attempted.")
        return False

    def restart_app(self) -> bool:
        """Cleanly terminates and re-launches TikTok app."""
        bundle_id = self.config.get("device", {}).get("bundle_id", "com.zhiliaoapp.musically")
        self._broadcast_status("Restarting TikTok cleanly...")
        logger.info(f"Restarting TikTok app ({bundle_id})...")
        try:
            self.wda.terminate_app(bundle_id)
        except Exception as e:
            logger.debug(f"Error terminating app during restart: {e}")
        time.sleep(1.2)
        return self.ensure_app_open(max_retries=3)

    def open_comments_verified(self, max_retries: int = 3) -> bool:
        """
        Taps comment icon and uses OCR to verify that the comment drawer/sheet
        is actually open on screen (e.g. 'comments', 'Add comment', 'Reply').
        If not verified, retries the tap.
        """
        for attempt in range(1, max_retries + 1):
            if self._stop_event.is_set():
                return False
            self._broadcast_status(f"Opening comment section 💬 (attempt {attempt}/{max_retries})...")
            self.gesture.tap_comments_icon()
            time.sleep(1.8)

            screen = self.device_manager.get_screen()
            if screen:
                is_open, markers = self.detector.is_comment_section_open(screen)
                if is_open:
                    self._broadcast_status(f"Comment drawer verified open via OCR [{', '.join(markers[:2])}]")
                    logger.info(f"Comment section opened successfully, OCR verified: {markers}")
                    return True
                else:
                    logger.warning(f"Comment drawer not detected on screen via OCR on attempt {attempt}")
            time.sleep(0.5)

        self._broadcast_status("Could not verify comment drawer via OCR.")
        return False

    def close_comments_verified(self, max_retries: int = 3) -> bool:
        """
        Closes the comment drawer and uses OCR to verify that the comment drawer/sheet
        is no longer present on screen and the video feed is active.
        """
        for attempt in range(1, max_retries + 1):
            self._broadcast_status(f"Closing comment section (attempt {attempt}/{max_retries})...")
            # Dismiss keyboard first in case comment input field is focused
            self.wda.dismiss_keyboard()
            self.gesture.close_comments_drawer()
            time.sleep(1.2)

            screen = self.device_manager.get_screen()
            if screen:
                is_open, markers = self.detector.is_comment_section_open(screen)
                is_kb, _ = self.detector.is_comment_input_open(screen)
                if not is_open and not is_kb:
                    self._broadcast_status("Comment drawer verified closed via OCR.")
                    logger.info("Comment section closed successfully, verified via OCR.")
                    return True
                else:
                    logger.warning(f"Comment drawer/input still detected on screen via OCR [{', '.join(markers)}], retrying close...")
                    # Fallback dismissal tap
                    w, h = self.gesture.screen_width, self.gesture.screen_height
                    if attempt % 2 == 1:
                        self.wda.tap(w * 0.5, h * 0.15)
                    else:
                        self.wda.tap(w * 0.935, h * 0.38)
            time.sleep(0.5)

        self._broadcast_status("Comment drawer close attempted.")
        return False

    def _tap_for_you_tab(self, screen: Optional[Image.Image] = None):
        """Taps the For You tab in the top header."""
        w, h = self.gesture.screen_width, self.gesture.screen_height
        # In modern multi-tab layout ('LIVE Community Following Shop For You [Search]'),
        # 'For You' is centered at cx ~ 0.80, cy ~ 0.074.
        self.wda.tap(w * 0.80, h * 0.074)

    def recover_to_feed(self, max_attempts: int = 5) -> Tuple[bool, str]:
        """
        Closed-Loop Hierarchical UI State Machine:
        At each step, captures screen, classifies screen state using OCR observations,
        queries the page-specific layout model to resolve exact target coordinates,
        performs one targeted action, and immediately re-evaluates the screen until
        clean FYP video feed is reached.
        If an 'unknown' screen is encountered, immediately triggers strict assertion
        failure and persists screenshot to logs/unrecognized_screens/.
        """
        w, h = self.gesture.screen_width, self.gesture.screen_height

        for step in range(1, max_attempts + 1):
            screen = self.device_manager.get_screen()
            if not screen:
                time.sleep(1.0)
                continue

            state, markers = self.detector.detect_screen_state(screen)
            marker_str = f"[{', '.join(markers[:2])}]" if markers else ""

            if state == "transition":
                time.sleep(0.4)
                continue

            if state == "feed" or (self.detector.is_feed_navigation_visible(screen) and state not in ("comment_input", "keyboard", "comments", "share", "likes_list", "tako", "popup", "unknown")):
                self._broadcast_status("Confirmed on video feed ✅")
                logger.info(f"[Step {step}] Confirmed on video feed ✅")
                return True, "feed"

            if state == "unknown":
                # Double-check: wait 0.5s and re-evaluate to eliminate transient rendering glitches
                time.sleep(0.5)
                retry_screen = self.device_manager.get_screen()
                if retry_screen:
                    r_state, r_markers = self.detector.detect_screen_state(retry_screen)
                    if r_state == "feed" or (self.detector.is_feed_navigation_visible(retry_screen) and r_state not in ("comment_input", "keyboard", "comments", "share", "likes_list", "tako", "popup", "unknown")):
                        self._broadcast_status("Confirmed on video feed ✅")
                        logger.info(f"[Step {step}] Confirmed on video feed after re-check ✅")
                        return True, "feed"
                    if r_state != "unknown":
                        screen = retry_screen
                        state = r_state
                        markers = r_markers

            if state == "unknown":
                # Strict Assertion Failure on Persistent Unknown Screens
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                os.makedirs("logs/unrecognized_screens", exist_ok=True)
                save_path = f"logs/unrecognized_screens/unrecognized_{timestamp}.png"
                screen.save(save_path)
                logger.error(
                    f"[Step {step}] [CRITICAL] Unrecognized screen state detected. "
                    f"Aborting blind navigation. Saved screenshot to {save_path}"
                )
                self.safety.trigger_alert("Unrecognized screen state detected.", screen_image=screen)
                self.stats.state = SessionState.CAPTCHA_HALTED
                self._broadcast_status(f"CRITICAL: Unrecognized screen state. Saved to {save_path}")
                return False, "unknown"

            # Closed-Loop Page Layout Decision
            action_desc = ""

            if state in ("comment_input", "keyboard"):
                action_desc = "Dismissing keyboard and tapping upper dimmed backdrop"
                self.wda.dismiss_keyboard()
                self.wda.tap(w * 0.50, h * 0.25)
                time.sleep(0.4)
                self.gesture.close_comments_drawer()

            elif state == "likes_list":
                action_desc = "Dismissing likes list modal via upper backdrop tap"
                self.wda.tap(w * 0.50, h * 0.18)
                time.sleep(0.4)
                self.gesture.close_comments_drawer()

            elif state == "comments":
                action_desc = "Closing comment sheet drawer"
                self.wda.dismiss_keyboard()
                self.gesture.close_comments_drawer()
                self.wda.tap(w * 0.50, h * 0.18)

            elif state == "share":
                action_desc = "Dismissing share sheet via upper backdrop tap"
                self.wda.tap(w * 0.50, h * 0.25)
                time.sleep(0.4)
                self.gesture.close_comments_drawer()

            elif state == "tako":
                action_desc = "TikTok Tako drawer: Dismissing keyboard and tapping upper backdrop at (0.50, 0.15)"
                self.wda.dismiss_keyboard()
                self.wda.tap(w * 0.50, h * 0.15)
                time.sleep(0.4)
                self.gesture.close_comments_drawer()

            elif state == "shop":
                for_you_coord = self.detector.find_button_coordinate(
                    screen, r"for you|foryou|для вас|für dich", region=(0.60, 0.03, 0.95, 0.15)
                )
                home_coord = self.detector.find_button_coordinate(
                    screen, r"home|startseite|головна|главная", region=(0.0, 0.88, 0.35, 1.0)
                )
                if for_you_coord:
                    action_desc = f"Shop active: Tapping OCR-detected 'For You' tab at ({for_you_coord[0]*w:.1f}, {for_you_coord[1]*h:.1f})"
                    self.wda.tap(for_you_coord[0] * w, for_you_coord[1] * h)
                elif home_coord:
                    action_desc = f"Shop active: Tapping OCR-detected Home tab at ({home_coord[0]*w:.1f}, {home_coord[1]*h:.1f})"
                    self.wda.tap(home_coord[0] * w, home_coord[1] * h)
                else:
                    action_desc = "Shop active: Tapping 'For You' tab at (0.80, 0.074)"
                    self._tap_for_you_tab()

            elif state == "sound":
                home_coord = self.detector.find_button_coordinate(
                    screen, r"home|startseite|головна|главная", region=(0.0, 0.88, 0.35, 1.0)
                )
                if home_coord:
                    action_desc = f"Sound page with nav: Tapping OCR-detected Home tab at ({home_coord[0]*w:.1f}, {home_coord[1]*h:.1f})"
                    self.wda.tap(home_coord[0] * w, home_coord[1] * h)
                else:
                    action_desc = "Sound detail page: Tapping top-left back chevron at (0.06, 0.073)"
                    self.wda.tap(w * 0.06, h * 0.073)

            elif state == "scan":
                action_desc = "QR scanner: Tapping top-left back chevron"
                self.wda.tap(w * 0.08, h * 0.073)

            elif state == "camera":
                action_desc = "Camera screen: Tapping top-left close 'X' at (0.075, 0.105)"
                self.wda.dismiss_keyboard()
                self.wda.tap(w * 0.075, h * 0.105)

            elif state == "live":
                action_desc = "LIVE broadcast: Tapping top-right close 'X'"
                self.wda.tap(w * 0.95, h * 0.07)

            elif state == "story":
                action_desc = "Story player: Tapping top-right close 'X'"
                self.wda.tap(w * 0.93, h * 0.09)

            elif state == "profile":
                self.wda.dismiss_keyboard()
                home_coord = self.detector.find_button_coordinate(
                    screen, r"home|startseite|головна|главная", region=(0.0, 0.88, 0.35, 1.0)
                )
                if home_coord:
                    action_desc = f"Profile: Tapping OCR-detected Home tab at ({home_coord[0]*w:.1f}, {home_coord[1]*h:.1f})"
                    self.wda.tap(home_coord[0] * w, home_coord[1] * h)
                elif markers and "profile_tab" in markers:
                    action_desc = f"Own profile tab: Tapping Home tab at ({w * 0.10:.1f}, {h * 0.955:.1f})"
                    self.wda.tap(w * 0.10, h * 0.955)
                else:
                    action_desc = "Author profile: Tapping top-left back chevron at (0.06, 0.073)"
                    self.wda.tap(w * 0.06, h * 0.073)

            elif state == "search":
                self.wda.dismiss_keyboard()
                cancel_coord = self.detector.find_button_coordinate(
                    screen, r"cancel|abbrechen|отмена|відміна", region=(0.60, 0.02, 1.0, 0.14)
                )
                if cancel_coord:
                    action_desc = f"Search page: Tapping OCR-detected 'Cancel' at ({cancel_coord[0]*w:.1f}, {cancel_coord[1]*h:.1f})"
                    self.wda.tap(cancel_coord[0] * w, cancel_coord[1] * h)
                elif markers and "discover_sheet" in markers:
                    action_desc = "Discover sheet / overlay: Tapping top-right close 'X' at (0.93, 0.073)"
                    self.wda.tap(w * 0.93, h * 0.073)
                else:
                    action_desc = "Search page: Dismissing keyboard and tapping top-left back chevron at (0.06, 0.073)"
                    self.wda.tap(w * 0.06, h * 0.073)

            elif state == "feed_wrong_tab":
                for_you_coord = self.detector.find_button_coordinate(
                    screen, r"for you|foryou|для вас|für dich", region=(0.60, 0.03, 0.95, 0.15)
                )
                if for_you_coord:
                    action_desc = f"Wrong feed tab: Tapping OCR-detected 'For You' tab at ({for_you_coord[0]*w:.1f}, {for_you_coord[1]*h:.1f})"
                    self.wda.tap(for_you_coord[0] * w, for_you_coord[1] * h)
                else:
                    action_desc = "Wrong feed tab: Tapping 'For You' tab at (0.80, 0.074)"
                    self._tap_for_you_tab()

            elif state == "popup":
                btn_coord = self.detector.find_button_coordinate(
                    screen, r"not now|cancel|dismiss|later|не зараз|отмена|позже"
                )
                if btn_coord:
                    action_desc = f"Modal popup: Tapping OCR-detected dismiss button at ({btn_coord[0]*w:.1f}, {btn_coord[1]*h:.1f})"
                    self.wda.tap(btn_coord[0] * w, btn_coord[1] * h)
                else:
                    popup_type = markers[0] if markers else "generic_modal"
                    dismiss_x, dismiss_y = self.detector.get_dismiss_coordinate(popup_type, w, h)
                    action_desc = f"Modal popup: Tapping dismiss coordinate ({dismiss_x:.1f}, {dismiss_y:.1f})"
                    self.wda.tap(dismiss_x, dismiss_y)

            elif state == "homescreen":
                action_desc = "Device on homescreen: Relaunching TikTok"
                self.ensure_app_open()

            else:
                action_desc = f"Alternative tab '{state}': Tapping Home tab at (0.10, 0.955)"
                self.wda.dismiss_keyboard()
                self.wda.tap(w * 0.10, h * 0.955)

            logger.info(f"[Step {step}/{max_attempts}] Screen: '{state}' {marker_str} -> Action: {action_desc}")
            self._broadcast_status(f"[Step {step}] '{state}': {action_desc}")
            time.sleep(0.8)

            # Closed-Loop Verification: Immediately re-capture screen and verify state transition
            post_screen = self.device_manager.get_screen()
            if post_screen:
                post_state, post_markers = self.detector.detect_screen_state(post_screen)
                if post_state == "feed" or (self.detector.is_feed_navigation_visible(post_screen) and post_state not in ("comment_input", "keyboard", "comments", "share", "likes_list", "tako", "popup", "unknown")):
                    self._broadcast_status(f"Successfully recovered from '{state}' to video feed ✅")
                    logger.info(f"[Step {step}] Verified recovery from '{state}' to 'feed' ✅")
                    return True, state
                else:
                    logger.info(f"[Step {step}] Post-action OCR evaluated screen state as '{post_state}' [{', '.join(post_markers[:2]) if post_markers else ''}]")

        # Emergency Fallback after max closed-loop steps on known states
        logger.warning(f"Failed to recover to feed after {max_attempts} closed-loop steps. Executing clean app restart...")
        self._broadcast_status("Recovery failed: clean restarting TikTok app...")
        restarted = self.restart_app()
        if restarted:
            time.sleep(2.0)
            self.wda.tap(w * 0.10, h * 0.955)
            time.sleep(1.0)
            self._tap_for_you_tab()
            time.sleep(1.2)
            final_screen = self.device_manager.get_screen()
            if final_screen:
                final_state, _ = self.detector.detect_screen_state(final_screen)
                if final_state == "feed":
                    self._broadcast_status("App restart recovered screen to video feed ✅")
                    return True, "feed"

        logger.error("Screen could not be recovered to FYP even after app restart. Triggering sentinel alert.")
        curr_screen = self.device_manager.get_screen()
        self.safety.trigger_alert("Unrecoverable screen state: cannot return to FYP.", screen_image=curr_screen)
        self.stats.state = SessionState.CAPTCHA_HALTED
        self._broadcast_status("Screen recovery failed: paused for safety 🛡️")
        return False, "unrecoverable"

    def swipe_next_video_verified(self, max_retries: int = 3) -> Tuple[bool, str]:
        """
        Executes swipe to next video and verifies that the video changed
        using multi-modal verification (sidebar metrics, visual scene diff, content signature).
        If the video did not change, it retries the swipe with adaptive fling velocity.
        If max retries fail, detects current screen state and recovers back to the video feed.
        Returns (has_changed, reason_description).
        """
        before_img = self.device_manager.get_screen()
        if before_img and self.detector.is_transition_frame(before_img):
            time.sleep(0.4)
            before_img = self.device_manager.get_screen()

        before_metrics = self.detector.extract_sidebar_metrics(before_img) if before_img else {}
        before_likes = before_metrics.get("likes")
        before_sig = self.detector.extract_content_signature(before_img) if before_img else ""

        # Pre-swipe guard: ONLY recover if an actual blocking overlay / non-feed modal is detected
        if before_img:
            state, markers = self.detector.detect_screen_state(before_img)
            blocking_states = (
                "comment_input", "keyboard", "comments", "share", "profile",
                "likes_list", "popup", "homescreen", "other_tab", "feed_wrong_tab",
                "tako", "shop", "camera", "sound", "live", "scan"
            )
            if state in blocking_states:
                logger.warning(
                    f"Blocking overlay/state '{state}' detected prior to swipe. Recovering to video feed..."
                )
                self._broadcast_status(f"Screen on '{state}', recovering to video feed...")
                self.recover_to_feed()
                time.sleep(0.8)
                before_img = self.device_manager.get_screen()
                before_metrics = self.detector.extract_sidebar_metrics(before_img) if before_img else {}
                before_likes = before_metrics.get("likes")
                before_sig = self.detector.extract_content_signature(before_img) if before_img else ""

        last_reason = "No transition detected"
        for attempt in range(1, max_retries + 1):
            if self._stop_event.is_set():
                return False, "Stopped"

            self._broadcast_status(f"Swiping to next video 👆 (attempt {attempt}/{max_retries})...")
            fling_v = 3000.0 if attempt == 1 else (3300.0 + (attempt - 2) * 200.0)
            self.gesture.swipe_next_video(velocity=fling_v)

            # Wait natural video & UI element render time so frame and metrics stabilize
            time.sleep(1.0)

            after_img = self.device_manager.get_screen()
            # If after_img is in mid-transition / buffering, wait 0.4s to stabilize
            if after_img and self.detector.is_transition_frame(after_img):
                time.sleep(0.4)
                after_img = self.device_manager.get_screen()

            if after_img and before_img:
                changed, reason = self.detector.did_video_change(
                    before_img,
                    after_img,
                    before_metrics=before_metrics,
                    before_likes=before_likes,
                    before_sig=before_sig,
                )
                last_reason = reason
                if changed:
                    self._broadcast_status(f"Video changed [{reason}]")
                    logger.info(f"Swipe verified: {reason}")
                    return True, reason
                else:
                    logger.warning(
                        f"Swipe unconfirmed [{reason}], retrying ({attempt}/{max_retries})..."
                    )
                    self._broadcast_status(f"Swipe unconfirmed: {reason}, retrying...")
                    # Advance baseline to current screen so subsequent retry checks against the current video
                    before_img = after_img
                    before_metrics = self.detector.extract_sidebar_metrics(after_img)
                    before_likes = before_metrics.get("likes")
                    before_sig = self.detector.extract_content_signature(after_img)
                    time.sleep(0.5)

        # 3 swipe attempts failed: detect screen state and initiate recovery back to video feed
        logger.warning(
            f"All {max_retries} swipe attempts failed. Detecting screen state and initiating recovery to video feed..."
        )
        self._broadcast_status("3 swipe attempts failed. Detecting screen state to return to video feed...")
        recovered, current_state = self.recover_to_feed()
        if recovered:
            self._broadcast_status(f"Recovered from '{current_state}' back to video feed. Retrying swipe...")
            logger.info(f"Successfully recovered from '{current_state}' back to feed. Executing verified swipe...")
            time.sleep(1.0)
            feed_img = self.device_manager.get_screen()
            if feed_img and self.detector.is_transition_frame(feed_img):
                time.sleep(0.4)
                feed_img = self.device_manager.get_screen()

            feed_metrics = self.detector.extract_sidebar_metrics(feed_img) if feed_img else {}
            feed_likes = feed_metrics.get("likes")
            feed_sig = self.detector.extract_content_signature(feed_img) if feed_img else ""

            self.gesture.swipe_next_video(velocity=3300.0)
            time.sleep(1.0)
            post_swipe_img = self.device_manager.get_screen()
            if post_swipe_img and self.detector.is_transition_frame(post_swipe_img):
                time.sleep(0.4)
                post_swipe_img = self.device_manager.get_screen()

            if post_swipe_img and feed_img:
                changed, reason = self.detector.did_video_change(
                    feed_img,
                    post_swipe_img,
                    before_metrics=feed_metrics,
                    before_likes=feed_likes,
                    before_sig=feed_sig,
                )
                if changed:
                    self._broadcast_status(f"Video changed after recovery [{reason}]")
                    return True, f"Recovered from {current_state} & changed [{reason}]"
                return False, f"Recovered from {current_state} but swipe unconfirmed [{reason}]"
            return True, f"Recovered from {current_state}"

        return False, f"Failed to recover to feed from '{current_state}'"

    def stop(self):
        """Signals the session to terminate gracefully."""
        self._stop_event.set()
        self._pause_event.clear()
        self.stats.state = SessionState.STOPPED
        self._broadcast_status("Session stopped by user")
        if not self._thread or not self._thread.is_alive():
            self.close_app()

    def skip_video(self):
        """Interrupts current video dwell and triggers immediate swipe up."""
        self._skip_flag.set()
        self._broadcast_status("Skipping current video...")

    def _get_screen_scale(self, screen_img: Optional[Image.Image]) -> Tuple[float, float]:
        """Calculates retina scale factor (e.g. 2.0 or 3.0) from image pixels to points."""
        if not screen_img:
            return 1.0, 1.0
        gw = getattr(self.gesture, "screen_width", 0)
        gh = getattr(self.gesture, "screen_height", 0)
        sx = (screen_img.width / gw) if isinstance(gw, (int, float)) and gw > 0 else 1.0
        sy = (screen_img.height / gh) if isinstance(gh, (int, float)) and gh > 0 else 1.0
        return sx, sy

    def _navigate_to_author_profile(self) -> Tuple[bool, Optional[Image.Image]]:
        """
        Navigates from FYP video to author profile with closed-loop verification:
        1. Primary: Horizontal swipe left across the video area.
        2. Verification: Checks if screen transitioned to 'profile'.
        3. Fallback for Carousels/Intercepted: If screen remained on 'feed' (carousel/photo mode detected),
           waits 1.4s animation dwell and taps the author avatar icon once.
        4. Final Verification: Returns (opened, final_screen).
        """
        init_screen = self.device_manager.get_screen()
        if not init_screen:
            return False, None

        # Quick check: already on profile?
        st, _ = self.detector.detect_screen_state(init_screen)
        if st == "profile":
            return True, init_screen

        # Primary Action: Horizontal swipe left across video area
        self._broadcast_status("Swiping left to open author profile...")
        self.gesture.swipe_to_profile()
        time.sleep(random.uniform(1.2, 1.4))

        screen1 = self.device_manager.get_screen()
        if screen1:
            st1, _ = self.detector.detect_screen_state(screen1)
            if st1 == "profile":
                return True, screen1

        # Fallback: Screen remained on feed (carousel / photo mode or swipe intercepted)
        self._broadcast_status(
            "Swipe remained on feed (carousel/photo mode detected). Tapping author avatar fallback..."
        )
        logger.info("Swipe did not open profile (screen remained on feed). Tapping author avatar icon fallback...")
        time.sleep(1.4)  # 1.4s animation dwell for carousel slide transition to settle

        curr_screen = screen1 or init_screen
        avatar_coords = self.detector.find_author_avatar_coords(curr_screen) if curr_screen else None
        if avatar_coords and curr_screen:
            scale_x, scale_y = self._get_screen_scale(curr_screen)
            self.gesture.tap_author_avatar(x=avatar_coords[0] / scale_x, y=avatar_coords[1] / scale_y)
        else:
            self.gesture.tap_author_avatar()
        time.sleep(1.4)

        screen2 = self.device_manager.get_screen()
        if screen2:
            st2, _ = self.detector.detect_screen_state(screen2)
            if st2 == "profile":
                return True, screen2

        return False, screen2

    def _perform_profile_follow_sequence(self, matched_kws: List[str]) -> bool:
        """
        Executes organic author profile visit, watches profile videos, and follows:
        1. Opens creator profile from FYP via swipe / avatar tap.
        2. Verifies author profile screen is open.
        3. Checks if profile is already followed or private.
        4. Taps the first video thumbnail in creator's profile grid.
        5. Watches 1-3 videos with natural human dwell.
        6. Returns to author profile and taps Follow button.
        7. Verifies button change and returns smoothly to FYP feed.
        """
        follow_cfg = self.config.get("follow", {})
        self._broadcast_status(f"🎯 Matched tags [{', '.join(matched_kws)}]: Visiting author profile...")
        logger.info(f"Initiating profile visit & follow sequence for matched tags: {matched_kws}")

        # Navigate to author profile with multi-modal fallback
        opened, screen_img = self._navigate_to_author_profile()

        if not opened or not screen_img:
            logger.warning("Could not navigate to author profile. Recovering feed and advancing to next video...")
            self._broadcast_status("Could not open profile: advancing to next FYP video 👆...")
            self.recover_to_feed()
            time.sleep(random.uniform(0.6, 1.0))
            self.swipe_next_video_verified()
            return False

        # Check if already followed
        if self.detector.is_already_following_author(screen_img):
            logger.info("Author is already followed. Skipping follow sequence.")
            self._broadcast_status("Already following this creator. Returning to FYP...")
            self.gesture.tap_profile_back()
            time.sleep(random.uniform(0.8, 1.4))
            self.recover_to_feed()
            return False

        # Check if private account
        if self.detector.is_private_account(screen_img):
            logger.info("Author profile is private. Skipping follow sequence.")
            self._broadcast_status("Creator profile is private. Returning to FYP...")
            self.gesture.tap_profile_back()
            time.sleep(random.uniform(0.8, 1.4))
            self.recover_to_feed()
            return False

        # Step 4: Watch creator profile videos before following (if configured)
        watch_videos = follow_cfg.get("watch_profile_videos", True)
        if watch_videos:
            vid_min = int(follow_cfg.get("profile_videos_min", 1))
            vid_max = int(follow_cfg.get("profile_videos_max", 2))
            videos_to_watch = random.randint(min(vid_min, vid_max), max(vid_min, vid_max))
            dwell_min = float(follow_cfg.get("profile_video_dwell_min_sec", 4.0))
            dwell_max = float(follow_cfg.get("profile_video_dwell_max_sec", 8.0))

            self._broadcast_status(f"Opening creator video grid (watching {videos_to_watch} video{'s' if videos_to_watch > 1 else ''})...")
            self.gesture.tap_first_profile_video()
            time.sleep(random.uniform(1.2, 1.8))

            post_grid_screen = self.device_manager.get_screen()
            grid_st, _ = self.detector.detect_screen_state(post_grid_screen) if post_grid_screen else ("unknown", [])
            # Only run video dwell if the screen actually navigated away from profile to a video player
            if grid_st != "profile":
                for v_idx in range(videos_to_watch):
                    if self._stop_event.is_set():
                        break
                    v_dwell = random.uniform(min(dwell_min, dwell_max), max(dwell_min, dwell_max))
                    v_start = time.time()
                    while time.time() - v_start < v_dwell:
                        if self._stop_event.is_set() or self._skip_flag.is_set():
                            self._skip_flag.clear()
                            break
                        rem = max(0.0, v_dwell - (time.time() - v_start))
                        self._broadcast_status(f"Watching creator video {v_idx + 1}/{videos_to_watch} ({rem:.1f}s remaining)")
                        time.sleep(0.3)

                    if v_idx < videos_to_watch - 1 and not self._stop_event.is_set():
                        self.gesture.swipe_next_video()
                        time.sleep(random.uniform(1.0, 1.6))

                # Return from video player back to profile page
                self.gesture.tap_profile_back()
                time.sleep(random.uniform(1.0, 1.5))

        # Re-capture profile screen to locate follow button
        profile_screen = self.device_manager.get_screen() or screen_img

        # Step 5: Follow creator on profile page
        coords = self.detector.find_follow_button_coords(profile_screen)
        self._broadcast_status("Tapping Follow button on creator profile...")
        scale_x, scale_y = self._get_screen_scale(profile_screen)
        if coords:
            pt_x = coords[0] / scale_x
            pt_y = coords[1] / scale_y
            self.gesture.tap_follow_button(x=pt_x, y=pt_y)
        else:
            self.gesture.tap_follow_button()

        time.sleep(random.uniform(1.2, 1.8))

        # Closed-loop verification of follow state
        post_screen = self.device_manager.get_screen()
        is_now_followed = self.detector.is_already_following_author(post_screen) if post_screen else False
        has_pink_still, _ = self.detector.has_pink_follow_button(post_screen) if post_screen else (False, None)

        if not is_now_followed and has_pink_still:
            logger.info("Follow state unchanged after first tap, retrying with standard action-row coordinates...")
            self._broadcast_status("Retrying Follow button tap...")
            self.gesture.tap_follow_button()
            time.sleep(random.uniform(1.0, 1.5))
            post_screen = self.device_manager.get_screen()
            is_now_followed = self.detector.is_already_following_author(post_screen) if post_screen else False
            has_pink_still, _ = self.detector.has_pink_follow_button(post_screen) if post_screen else (False, None)

        followed_success = is_now_followed or not has_pink_still
        if followed_success:
            self.stats.follows_count += 1
            self._broadcast_status(
                f"✅ Followed creator! (Session follows: {self.stats.follows_count}/{self.stats.session_follow_target})"
            )
            logger.info(f"Followed creator. Session follows: {self.stats.follows_count}/{self.stats.session_follow_target}")
        else:
            logger.warning("Follow button tap could not be confirmed.")
            self._broadcast_status("Follow button tap not confirmed.")

        pause_min = float(self.config.get("probabilities", {}).get("post_action_pause_min_sec", 0.6))
        pause_max = float(self.config.get("probabilities", {}).get("post_action_pause_max_sec", 1.4))
        time.sleep(random.uniform(min(pause_min, pause_max), max(pause_min, pause_max)))

        # Step 6: Return to FYP feed
        self.gesture.tap_profile_back()
        time.sleep(random.uniform(0.8, 1.4))
        self.recover_to_feed()
        return followed_success

    def test_author_profile(self, auto_return: bool = True) -> Dict[str, Any]:
        """
        Navigates to author profile from FYP, inspects profile state via detector,
        and optionally recovers back to the FYP feed.
        """
        self.ensure_app_open()
        self._broadcast_status("Testing profile visit: navigating to creator profile...")
        opened, screen_img = self._navigate_to_author_profile()

        if not opened or not screen_img:
            self.recover_to_feed()
            return {
                "status": "failed",
                "opened": False,
                "message": "Failed to open author profile via swipe and avatar tap fallback",
            }

        is_following = self.detector.is_already_following_author(screen_img)
        is_private = self.detector.is_private_account(screen_img)
        has_pink_button, _ = self.detector.has_pink_follow_button(screen_img)
        coords = self.detector.find_follow_button_coords(screen_img)
        scale_x, scale_y = self._get_screen_scale(screen_img)
        follow_coords_pt = [round(coords[0] / scale_x, 1), round(coords[1] / scale_y, 1)] if coords else None

        result: Dict[str, Any] = {
            "status": "ok",
            "opened": True,
            "is_following": is_following,
            "is_private": is_private,
            "has_pink_button": has_pink_button,
            "follow_coords": follow_coords_pt,
            "message": f"Profile opened (Following: {is_following}, Private: {is_private}, Pink button: {has_pink_button})",
        }

        if auto_return:
            self._broadcast_status("Returning from profile back to FYP...")
            self.gesture.tap_profile_back()
            time.sleep(random.uniform(0.8, 1.2))
            recovered, _ = self.recover_to_feed()
            result["recovered"] = recovered

        return result

    def test_author_follow(self) -> Dict[str, Any]:
        """
        Executes author follow test sequence on current video.
        """
        if self.stats.state != SessionState.RUNNING:
            self._stop_event.clear()
        self.ensure_app_open()
        self._broadcast_status("Testing author follow pipeline...")
        followed = self._perform_profile_follow_sequence(matched_kws=["manual_test"])
        return {
            "status": "ok" if followed else "failed",
            "followed": followed,
            "message": "Successfully followed creator & returned to FYP" if followed else "Author follow sequence finished without follow (already followed, private, or could not open)",
        }

    def trigger_search_seeding(self, term: Optional[str] = None, videos_to_watch: Optional[int] = None) -> bool:
        """Manually triggers search seeding for a given query or from configured seed terms."""
        query = term
        if not query:
            if self.trainer.seed_terms:
                query = random.choice(self.trainer.seed_terms)
            else:
                query = "technology"

        niche_cfg = self.config.get("niche", {})
        if videos_to_watch is None:
            seed_min = int(niche_cfg.get("seed_videos_min", 2))
            seed_max = int(niche_cfg.get("seed_videos_max", niche_cfg.get("seed_videos_per_term", 4)))
            actual_count = random.randint(min(seed_min, seed_max), max(seed_min, seed_max))
        else:
            actual_count = videos_to_watch

        dwell_min = float(niche_cfg.get("seed_video_dwell_min_sec", 7.0))
        dwell_max = float(niche_cfg.get("seed_video_dwell_max_sec", 15.0))

        # If not already running a main session, reset stop event so manual seeding can run
        if self.stats.state != SessionState.RUNNING:
            self._stop_event.clear()

        # Step 0: Ensure TikTok is running in the foreground and verified via OCR
        self.ensure_app_open()
        screen = self.device_manager.get_screen()
        if screen:
            st, _ = self.detector.detect_screen_state(screen)
            if st != "feed" and not self.detector.is_feed_navigation_visible(screen):
                self._broadcast_status(f"Pre-seeding guard: Recovering from '{st}' to FYP feed...")
                self.recover_to_feed()

        try:
            w, h = self.wda.get_window_size()
            self.gesture.screen_width = w
            self.gesture.screen_height = h
        except Exception:
            pass

        self._broadcast_status(f"Triggering niche search: '{query}'")
        success = self.trainer.perform_search_seeding(
            client=self.wda,
            gesture=self.gesture,
            term=query,
            videos_to_watch=actual_count,
            dwell_min_sec=dwell_min,
            dwell_max_sec=dwell_max,
            on_progress=lambda msg: self._broadcast_status(msg),
            stop_checker=lambda: self._stop_event.is_set(),
            device_manager=self.device_manager,
            detector=self.detector,
            recover_to_feed_fn=self.recover_to_feed,
        )
        if success:
            self.stats.videos_watched += actual_count
            self.stats.likes_count += 1
            self.stats.niche_matched_count += actual_count
            self._broadcast_status(f"Search seeding for '{query}' complete!")
        elif self._stop_event.is_set():
            self._broadcast_status(f"Search seeding for '{query}' stopped by user.")
        return success

    def _sample_dwell_time(self, is_niche_match: bool, is_ad: bool) -> float:
        dwell_cfg = self.config.get("dwell_time", {})
        if is_ad:
            ad_min = float(dwell_cfg.get("ad_skip_min_seconds", dwell_cfg.get("ad_skip_seconds", 0.8)))
            ad_max = float(dwell_cfg.get("ad_skip_max_seconds", dwell_cfg.get("ad_skip_seconds", 1.8)))
            return float(round(random.uniform(min(ad_min, ad_max), max(ad_min, ad_max)), 1))

        min_sec = float(dwell_cfg.get("min_seconds", 4.0))
        max_sec = float(dwell_cfg.get("max_seconds", 22.0))
        if min_sec > max_sec:
            min_sec, max_sec = max_sec, min_sec

        # True continuous randomization across the configured range [min_sec, max_sec]
        base_sample = random.uniform(min_sec, max_sec)

        if is_niche_match:
            mult_min = float(dwell_cfg.get("niche_match_multiplier_min", dwell_cfg.get("niche_match_multiplier", 1.8)))
            mult_max = float(dwell_cfg.get("niche_match_multiplier_max", dwell_cfg.get("niche_match_multiplier", 2.8)))
            mult = random.uniform(min(mult_min, mult_max), max(mult_min, mult_max))
            # Niche videos watch longer without being crushed down to normal video max_seconds
            max_niche_sec = float(dwell_cfg.get("niche_max_seconds", max(max_sec * 2.5, 55.0)))
            sample = min(base_sample * mult, max_niche_sec)
        else:
            sample = base_sample

        return float(round(sample, 1))

    def _run_loop(self, duration_minutes: Optional[int]):
        logger.info("Initializing TikTok session loop...")
        self._broadcast_status("Connecting to iPhone & Launching TikTok...")

        # 1. Ensure WDA connection, anti-freeze settings, and fetch screen dimensions
        try:
            if not self.wda.is_alive():
                self.device_manager.check_connection()
                self.wda = self.device_manager.client
                self.gesture.client = self.wda

            self.wda.ensure_session()
            self.wda._apply_session_settings()
            w, h = self.wda.get_window_size()
            self.gesture.screen_width = w
            self.gesture.screen_height = h
        except Exception as e:
            # Fallback auto-discovery attempt
            try:
                self.device_manager.check_connection()
                self.wda = self.device_manager.client
                self.gesture.client = self.wda
                self.wda.ensure_session()
                self.wda._apply_session_settings()
                w, h = self.wda.get_window_size()
                self.gesture.screen_width = w
                self.gesture.screen_height = h
            except Exception as e2:
                logger.error(f"Cannot initialize WDA session: {e2}")
                self.stats.state = SessionState.STOPPED
                self._broadcast_status(f"Error connecting to iPhone: {e2}")
                return

        # 2. Launch / ensure TikTok is active with OCR verification
        self.ensure_app_open()

        start_ts = time.time()
        max_duration_sec = (duration_minutes * 60) if duration_minutes else None
        probs = self.config.get("probabilities", {})
        safety_cfg = self.config.get("safety", {})

        try:
            # 3. Optional Search Seeding if enabled in config
            niche_cfg = self.config.get("niche", {})
            if niche_cfg.get("seed_search_enabled", False) and self.trainer.seed_terms and not self._stop_event.is_set():
                seed_term = random.choice(self.trainer.seed_terms)
                seed_min = int(niche_cfg.get("seed_videos_min", 2))
                seed_max = int(niche_cfg.get("seed_videos_max", niche_cfg.get("seed_videos_per_term", 4)))
                seed_count = random.randint(min(seed_min, seed_max), max(seed_min, seed_max))
                self.trigger_search_seeding(term=seed_term, videos_to_watch=seed_count)

            # Main Browsing Loop
            while not self._stop_event.is_set():
                # Check pause state
                while self._pause_event.is_set():
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.5)

                # Check duration limit
                elapsed = int(time.time() - start_ts)
                self.stats.duration_seconds = elapsed
                if max_duration_sec and elapsed >= max_duration_sec:
                    self._broadcast_status("Session reached target duration.")
                    break

                # Check daily safety caps
                if self.stats.videos_watched >= safety_cfg.get("max_daily_videos", 150):
                    self._broadcast_status("Daily video safety limit reached.")
                    break

                # Vision & Niche Detection (enabled by default)
                enable_ocr = self.config.get("vision", {}).get("enabled", True)
                is_niche = False
                is_ad = False
                matched_kws = []
                if enable_ocr:
                    try:
                        # Allow video frame & caption to render after swipe
                        time.sleep(0.5)
                        screen_img = self.device_manager.get_screen()
                        if screen_img:
                            # Pre-dwell guard: ensure we are on clean FYP before dwelling
                            st, markers = self.detector.detect_screen_state(screen_img)
                            if st not in ("feed", "unknown"):
                                logger.warning(f"Screen state '{st}' detected before dwell. Recovering to FYP feed...")
                                self._broadcast_status(f"Pre-dwell guard: returning from '{st}' to FYP...")
                                self.recover_to_feed()
                                screen_img = self.device_manager.get_screen()

                        if screen_img:
                            caption, full_text = self.ocr.extract_full_content(screen_img)
                            is_ad = self.detector.is_sponsored(caption) or self.detector.is_sponsored(full_text)
                            
                            # Evaluate relevance: check caption first, then full screen text (titles/stickers)
                            _, matched_kws = self.trainer.evaluate_relevance(caption)
                            if not matched_kws and full_text:
                                _, matched_kws = self.trainer.evaluate_relevance(full_text)

                            is_niche = len(matched_kws) > 0
                            self.stats.current_caption = caption[:100] if caption else full_text[:100]
                            self.stats.current_matched_keywords = matched_kws

                            if is_niche:
                                logger.info(f"Niche matched: {matched_kws}")
                                self._broadcast_status(f"🎯 Niche match: [{', '.join(matched_kws)}]")
                    except Exception as e:
                        logger.debug(f"OCR error during loop: {e}")

                # Track actions taken on this video
                did_like = False
                did_favorite = False
                did_comment = False
                did_follow = False
                did_skip = False

                # Calculate Dwell Time (natural human curve: e.g. 6 to 18 seconds)
                dwell = self._sample_dwell_time(is_niche, is_ad)
                dwell_start = time.time()

                action_desc = f"Watching Niche Video [{', '.join(matched_kws)}]" if is_niche else "Watching FYP Video"
                while time.time() - dwell_start < dwell:
                    if self._stop_event.is_set():
                        break
                    if self._skip_flag.is_set():
                        self._skip_flag.clear()
                        did_skip = True
                        break
                    remaining = max(0.0, dwell - (time.time() - dwell_start))
                    self.stats.current_dwell_remaining = round(remaining, 1)
                    self._broadcast_status(f"{action_desc} ({remaining:.1f}s remaining)")
                    time.sleep(0.3)

                actual_dwell = round(time.time() - dwell_start, 2)
                self.stats.videos_watched += 1
                if is_niche:
                    self.stats.niche_matched_count += 1
                if is_ad:
                    self.stats.ads_skipped += 1

                # Step 7: Natural Interactions (Likes, Comments, Bookmarks) if not an Ad
                if not is_ad and not self._stop_event.is_set():
                    # Like probability sampled from configured range
                    if is_niche:
                        like_min = float(probs.get("like_niche_min", probs.get("like_niche", 0.35)))
                        like_max = float(probs.get("like_niche_max", probs.get("like_niche", 0.55)))
                    else:
                        like_min = float(probs.get("like_base_min", probs.get("like_base", 0.05)))
                        like_max = float(probs.get("like_base_max", probs.get("like_base", 0.15)))
                    like_threshold = random.uniform(min(like_min, like_max), max(like_min, like_max))

                    if random.random() < like_threshold and self.stats.likes_count < safety_cfg.get("max_daily_likes", 35):
                        # Randomized double-tap vs icon ratio
                        dt_min = float(probs.get("double_tap_ratio_min", probs.get("double_tap_ratio", 0.70)))
                        dt_max = float(probs.get("double_tap_ratio_max", probs.get("double_tap_ratio", 0.85)))
                        dt_threshold = random.uniform(min(dt_min, dt_max), max(dt_min, dt_max))

                        if random.random() < dt_threshold:
                            self._broadcast_status("Double-tapping video (Like ❤️)")
                            self.gesture.double_tap_like()
                        else:
                            self._broadcast_status("Tapping heart icon (Like ❤️)")
                            self.gesture.tap_heart_icon()
                        self.stats.likes_count += 1
                        did_like = True

                        pause_min = float(probs.get("post_action_pause_min_sec", 0.6))
                        pause_max = float(probs.get("post_action_pause_max_sec", 1.4))
                        time.sleep(random.uniform(min(pause_min, pause_max), max(pause_min, pause_max)))

                    # Bookmark / Favorite probability sampled from configured range
                    if is_niche:
                        fav_min = float(probs.get("favorite_niche_min", probs.get("favorite_niche", 0.12)))
                        fav_max = float(probs.get("favorite_niche_max", probs.get("favorite_niche", 0.22)))
                    else:
                        fav_min = float(probs.get("favorite_base_min", probs.get("favorite_base", 0.01)))
                        fav_max = float(probs.get("favorite_base_max", probs.get("favorite_base", 0.04)))
                    fav_threshold = random.uniform(min(fav_min, fav_max), max(fav_min, fav_max))

                    if random.random() < fav_threshold and self.stats.favorites_count < safety_cfg.get("max_daily_favorites", 15):
                        self._broadcast_status("Bookmarking video (Favorite ⭐)")
                        self.gesture.tap_bookmark_icon()
                        self.stats.favorites_count += 1
                        did_favorite = True
                        pause_min = float(probs.get("post_action_pause_min_sec", 0.6))
                        pause_max = float(probs.get("post_action_pause_max_sec", 1.4))
                        time.sleep(random.uniform(min(pause_min, pause_max), max(pause_min, pause_max)))

                    # View Comment Drawer probability sampled from configured range
                    if is_niche:
                        comm_min = float(probs.get("comment_drawer_niche_min", probs.get("comment_drawer_view_niche", 0.06)))
                        comm_max = float(probs.get("comment_drawer_niche_max", probs.get("comment_drawer_view_niche", 0.15)))
                    else:
                        comm_min = float(probs.get("comment_drawer_base_min", probs.get("comment_drawer_view_base", 0.01)))
                        comm_max = float(probs.get("comment_drawer_base_max", probs.get("comment_drawer_view_base", 0.03)))
                    comm_threshold = random.uniform(min(comm_min, comm_max), max(comm_min, comm_max))

                    if random.random() < comm_threshold:
                        opened = self.open_comments_verified()
                        if opened:
                            self.stats.comments_viewed += 1
                            did_comment = True
                            # Read comments with configured duration range
                            comm_read_min = float(probs.get("comment_read_min_seconds", 3.0))
                            comm_read_max = float(probs.get("comment_read_max_seconds", 6.5))
                            read_time = random.uniform(min(comm_read_min, comm_read_max), max(comm_read_min, comm_read_max))
                            comm_start = time.time()
                            while time.time() - comm_start < read_time:
                                if self._stop_event.is_set():
                                    break
                                time.sleep(0.2)
                            self.close_comments_verified()
                            # Post-interaction guard: ensure comment sheet or keyboard is not lingering
                            post_comm_screen = self.device_manager.get_screen()
                            if post_comm_screen:
                                post_st, _ = self.detector.detect_screen_state(post_comm_screen)
                                if post_st not in ("feed", "unknown"):
                                    logger.warning(f"Lingering state '{post_st}' after comment view. Recovering...")
                                    self.recover_to_feed()
                            pause_min = float(probs.get("post_action_pause_min_sec", 0.6))
                            pause_max = float(probs.get("post_action_pause_max_sec", 1.4))
                            time.sleep(random.uniform(min(pause_min, pause_max), max(pause_min, pause_max)))
                        else:
                            logger.info("Comment drawer could not be verified open via OCR, continuing loop.")

                    # Author profile visit & follow sequence (if 2+ tags matched and under session quota)
                    follow_cfg = self.config.get("follow", {})
                    if follow_cfg.get("enabled", True) and not self._stop_event.is_set():
                        min_tags = int(follow_cfg.get("min_matched_tags", 2))
                        max_daily_follows = int(safety_cfg.get("max_daily_follows", 15))
                        if (
                            len(matched_kws) >= min_tags
                            and self.stats.follows_count < self.stats.session_follow_target
                            and self.stats.follows_count < max_daily_follows
                        ):
                            prob_min = float(follow_cfg.get("follow_probability_min", 0.50))
                            prob_max = float(follow_cfg.get("follow_probability_max", 0.70))
                            follow_threshold = random.uniform(min(prob_min, prob_max), max(prob_min, prob_max))
                            if random.random() < follow_threshold:
                                follow_ok = self._perform_profile_follow_sequence(matched_kws)
                                if follow_ok:
                                    did_follow = True

                # Persist video interaction & progress to SQLite in real-time
                if self.db:
                    try:
                        self.db.log_video_interaction(
                            session_id=self.stats.session_id,
                            caption=self.stats.current_caption,
                            matched_keywords=matched_kws,
                            is_niche=is_niche,
                            is_ad=is_ad,
                            is_live=False,
                            dwell_time_seconds=actual_dwell,
                            action_liked=did_like,
                            action_favorited=did_favorite,
                            action_comment_viewed=did_comment,
                            action_followed=did_follow,
                            action_skipped_early=did_skip,
                        )
                        self.db.update_session_progress(
                            session_id=self.stats.session_id,
                            duration_seconds=self.stats.duration_seconds,
                            videos_watched=self.stats.videos_watched,
                            likes_count=self.stats.likes_count,
                            favorites_count=self.stats.favorites_count,
                            comments_viewed=self.stats.comments_viewed,
                            follows_count=self.stats.follows_count,
                            ads_skipped=self.stats.ads_skipped,
                            lives_skipped=self.stats.lives_skipped,
                            niche_matched_count=self.stats.niche_matched_count,
                            state=self.stats.state.value if hasattr(self.stats.state, "value") else str(self.stats.state),
                        )
                    except Exception as e:
                        logger.error(f"Error persisting video interaction: {e}")

                # Step 8: Biometric Gesture to Next Video
                # Occasional re-watch swipe back with range sampling
                rewatch_min = float(probs.get("rewatch_swipe_back_min", probs.get("rewatch_swipe_back", 0.02)))
                rewatch_max = float(probs.get("rewatch_swipe_back_max", probs.get("rewatch_swipe_back", 0.06)))
                rewatch_prob = random.uniform(min(rewatch_min, rewatch_max), max(rewatch_min, rewatch_max))
                if random.random() < rewatch_prob:
                    self._broadcast_status("Rewatching previous video (Swipe back ↩️)")
                    self.gesture.swipe_previous_video()
                    time.sleep(random.uniform(3.0, 7.0))

                # Occasional micro-flick with range sampling
                flick_min = float(probs.get("micro_flick_min", probs.get("micro_flick", 0.01)))
                flick_max = float(probs.get("micro_flick_max", probs.get("micro_flick", 0.05)))
                flick_prob = random.uniform(min(flick_min, flick_max), max(flick_min, flick_max))
                if random.random() < flick_prob:
                    self.gesture.micro_flick()
                    time.sleep(random.uniform(0.4, 0.8))

                # Verified Biometric Swipe to Next Video (OCR checked via likes amount)
                self.swipe_next_video_verified()
                # Post-swipe natural stabilization pause with range sampling
                post_swipe_min = float(probs.get("post_swipe_pause_min_sec", 0.8))
                post_swipe_max = float(probs.get("post_swipe_pause_max_sec", 1.8))
                time.sleep(random.uniform(min(post_swipe_min, post_swipe_max), max(post_swipe_min, post_swipe_max)))
        finally:
            prev_state = self.stats.state
            exit_reason = "Completed"
            if self._stop_event.is_set():
                exit_reason = "Stopped by user"
            elif prev_state == SessionState.CAPTCHA_HALTED:
                exit_reason = "Halted by Safety Sentinel (CAPTCHA)"
            elif max_duration_sec and elapsed >= max_duration_sec:
                exit_reason = "Target duration reached"
            elif self.stats.videos_watched >= safety_cfg.get("max_daily_videos", 150):
                exit_reason = "Daily safety limit reached"

            final_state_str = "CAPTCHA_HALTED" if prev_state == SessionState.CAPTCHA_HALTED else "STOPPED"
            self.stats.state = SessionState.STOPPED
            self._broadcast_status("Session finished. Closing app...")
            self.close_app()
            self._broadcast_status("Session finished.")
            if self.db:
                try:
                    self.db.finalize_session(
                        session_id=self.stats.session_id,
                        duration_seconds=self.stats.duration_seconds,
                        videos_watched=self.stats.videos_watched,
                        likes_count=self.stats.likes_count,
                        favorites_count=self.stats.favorites_count,
                        comments_viewed=self.stats.comments_viewed,
                        follows_count=self.stats.follows_count,
                        ads_skipped=self.stats.ads_skipped,
                        lives_skipped=self.stats.lives_skipped,
                        niche_matched_count=self.stats.niche_matched_count,
                        state=final_state_str,
                        exit_reason=exit_reason,
                    )
                except Exception as e:
                    logger.error(f"Error finalizing session in DB: {e}")
            logger.info("TikTok session loop terminated.")

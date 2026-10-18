import logging
import random
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import numpy as np

from ..bridge.device_manager import DeviceManager
from ..physics.gesture import BiometricGestureEngine
from ..safety.alert import SafetySentinel
from ..vision.detector import ScreenDetector
from ..vision.ocr import VisionOCR
from .niche_trainer import NicheTrainer

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
    ):
        self.config = config
        self.device_manager = device_manager or DeviceManager(
            wda_url=config.get("device", {}).get("wda_url", "http://localhost:8100")
        )
        self.wda = self.device_manager.client
        self.on_status_update = on_status_update

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

        self.stats = SessionStats(
            session_id=datetime.now().strftime("sess_%Y%m%d_%H%M%S"),
            start_time=datetime.now().isoformat(),
            state=SessionState.RUNNING,
            current_action="Starting session...",
        )

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

    def stop(self):
        """Signals the session to terminate gracefully."""
        self._stop_event.set()
        self._pause_event.clear()
        self.stats.state = SessionState.STOPPED
        self._broadcast_status("Session stopped by user")

    def skip_video(self):
        """Interrupts current video dwell and triggers immediate swipe up."""
        self._skip_flag.set()
        self._broadcast_status("Skipping current video...")

    def _sample_dwell_time(self, is_niche_match: bool, is_ad: bool) -> float:
        dwell_cfg = self.config.get("dwell_time", {})
        if is_ad:
            return float(dwell_cfg.get("ad_skip_seconds", 1.2))

        min_sec = float(dwell_cfg.get("min_seconds", 3.5))
        max_sec = float(dwell_cfg.get("max_seconds", 40.0))
        mean_sec = float(dwell_cfg.get("mean_seconds", 11.0))

        # Log-normal distribution to mimic realistic human attention spans
        sample = np.random.lognormal(mean=np.log(mean_sec), sigma=0.45)
        sample = max(min_sec, min(sample, max_sec))

        if is_niche_match:
            mult = float(dwell_cfg.get("niche_match_multiplier", 2.2))
            sample = min(sample * mult, max_sec)

        return float(sample)

    def _run_loop(self, duration_minutes: Optional[int]):
        logger.info("Initializing TikTok session loop...")
        self._broadcast_status("Connecting to iPhone & Launching TikTok...")

        # 1. Ensure WDA connection and fetch screen dimensions
        try:
            w, h = self.wda.get_window_size()
            self.gesture.screen_width = w
            self.gesture.screen_height = h
        except Exception as e:
            logger.error(f"Cannot initialize WDA session: {e}")
            self.stats.state = SessionState.STOPPED
            self._broadcast_status(f"Error connecting to iPhone: {e}")
            return

        # 2. Launch TikTok App
        bundle_id = self.config.get("device", {}).get("bundle_id", "com.zhiliaoapp.musically")
        self.wda.launch_app(bundle_id)
        time.sleep(random.uniform(2.5, 4.0))

        # 3. Optional Search Seeding
        niche_cfg = self.config.get("niche", {})
        if niche_cfg.get("seed_search_enabled") and niche_cfg.get("seed_terms"):
            seed_term = random.choice(niche_cfg["seed_terms"])
            self._broadcast_status(f"Seeding algorithm with: '{seed_term}'")
            self.trainer.perform_search_seeding(
                self.wda,
                self.gesture,
                seed_term,
                videos_to_watch=niche_cfg.get("seed_videos_per_term", 3),
            )

        start_ts = time.time()
        max_duration_sec = (duration_minutes * 60) if duration_minutes else None
        probs = self.config.get("probabilities", {})
        safety_cfg = self.config.get("safety", {})

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

            # Step 1: Capture screenshot
            self._broadcast_status("Analyzing video content...")
            screen_img = self.device_manager.get_screen()
            if not screen_img:
                time.sleep(1.0)
                continue

            # Step 2: Security & Captcha Check
            if self.detector.check_for_captcha(screen_img):
                alert_path = self.safety.trigger_captcha_alert(screen_img)
                self.stats.state = SessionState.CAPTCHA_HALTED
                self._broadcast_status(f"Captcha challenge detected! Saved {alert_path}")
                self._pause_event.set()
                continue

            # Step 3: Check for modal popups
            popup_type = self.detector.detect_popup(screen_img)
            if popup_type:
                self._broadcast_status(f"Dismissing popup: {popup_type}")
                dx, dy = self.detector.get_dismiss_coordinate(popup_type, w, h)
                self.wda.tap(dx, dy)
                self.wda.dismiss_alert()
                time.sleep(1.2)
                continue

            # Step 4: Extract Caption & Tags via OCR
            caption = self.ocr.extract_caption_and_tags(screen_img)
            is_ad = self.detector.is_sponsored(caption)
            relevance, matched_kws = self.trainer.evaluate_relevance(caption)
            is_niche = len(matched_kws) > 0

            if is_niche:
                self.stats.niche_matched_count += 1

            self.stats.current_caption = caption[:120] if caption else "(No caption detected)"
            self.stats.current_matched_keywords = matched_kws

            # Step 5: Calculate Dwell Time
            dwell = self._sample_dwell_time(is_niche, is_ad)
            dwell_start = time.time()

            # Step 6: Watch Video with Countdown & Skip Support
            action_desc = "Fast-skipping Ad" if is_ad else (f"Watching Niche Video ({', '.join(matched_kws)})" if is_niche else "Watching FYP Video")
            while time.time() - dwell_start < dwell:
                if self._stop_event.is_set():
                    break
                if self._skip_flag.is_set():
                    self._skip_flag.clear()
                    break
                remaining = max(0.0, dwell - (time.time() - dwell_start))
                self.stats.current_dwell_remaining = round(remaining, 1)
                self._broadcast_status(f"{action_desc} ({remaining:.1f}s remaining)")
                time.sleep(0.2)

            self.stats.videos_watched += 1
            if is_ad:
                self.stats.ads_skipped += 1

            # Step 7: Natural Interactions (Likes, Comments, Bookmarks) if not an Ad
            if not is_ad and not self._stop_event.is_set():
                # Like probability
                like_threshold = probs.get("like_niche", 0.40) if is_niche else probs.get("like_base", 0.10)
                if random.random() < like_threshold and self.stats.likes_count < safety_cfg.get("max_daily_likes", 35):
                    # 75% double-tap, 25% tap heart icon
                    if random.random() < probs.get("double_tap_ratio", 0.75):
                        self._broadcast_status("Double-tapping video (Like ❤️)")
                        self.gesture.double_tap_like()
                    else:
                        self._broadcast_status("Tapping heart icon (Like ❤️)")
                        self.gesture.tap_heart_icon()
                    self.stats.likes_count += 1
                    time.sleep(random.uniform(0.6, 1.2))

                # Bookmark / Favorite probability
                fav_threshold = probs.get("favorite_niche", 0.16) if is_niche else probs.get("favorite_base", 0.03)
                if random.random() < fav_threshold and self.stats.favorites_count < safety_cfg.get("max_daily_favorites", 15):
                    self._broadcast_status("Bookmarking video (Favorite ⭐)")
                    self.gesture.tap_bookmark_icon()
                    self.stats.favorites_count += 1
                    time.sleep(random.uniform(0.8, 1.4))

                # View Comment Drawer probability
                comm_threshold = probs.get("comment_drawer_view_niche", 0.22) if is_niche else probs.get("comment_drawer_view_base", 0.06)
                if random.random() < comm_threshold:
                    self._broadcast_status("Opening comment section 💬")
                    self.gesture.tap_comments_icon()
                    self.stats.comments_viewed += 1
                    # Read comments for 3-6 seconds
                    read_time = random.uniform(3.0, 6.0)
                    time.sleep(read_time)
                    self._broadcast_status("Closing comment section")
                    self.gesture.close_comments_drawer()
                    time.sleep(random.uniform(0.6, 1.0))

            # Step 8: Biometric Gesture to Next Video
            # Occasional re-watch swipe back (~4%)
            if random.random() < probs.get("rewatch_swipe_back", 0.04):
                self._broadcast_status("Rewatching previous video (Swipe back ↩️)")
                self.gesture.swipe_previous_video()
                time.sleep(random.uniform(3.0, 7.0))

            # Occasional micro-flick (~3%)
            if random.random() < probs.get("micro_flick", 0.03):
                self.gesture.micro_flick()
                time.sleep(random.uniform(0.4, 0.8))

            # Standard Biometric Swipe to Next Video
            self._broadcast_status("Swiping to next video 👆")
            self.gesture.swipe_next_video()
            # Post-swipe natural stabilization pause
            time.sleep(random.uniform(0.8, 1.6))

        self.stats.state = SessionState.STOPPED
        self._broadcast_status("Session finished.")
        logger.info("TikTok session loop terminated.")

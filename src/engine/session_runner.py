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

        # 2. Check if TikTok is open (do not force launch to avoid XCTest process hooking)
        time.sleep(0.5)

        start_ts = time.time()
        max_duration_sec = (duration_minutes * 60) if duration_minutes else None
        probs = self.config.get("probabilities", {})
        safety_cfg = self.config.get("safety", {})

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

            # Calculate Dwell Time (natural human curve: e.g. 6 to 18 seconds)
            dwell = self._sample_dwell_time(is_niche, is_ad)
            dwell_start = time.time()

            action_desc = f"Watching Niche Video [{', '.join(matched_kws)}]" if is_niche else "Watching FYP Video"
            while time.time() - dwell_start < dwell:
                if self._stop_event.is_set():
                    break
                if self._skip_flag.is_set():
                    self._skip_flag.clear()
                    break
                remaining = max(0.0, dwell - (time.time() - dwell_start))
                self.stats.current_dwell_remaining = round(remaining, 1)
                self._broadcast_status(f"{action_desc} ({remaining:.1f}s remaining)")
                time.sleep(0.3)

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
                    self._broadcast_status("Opening comment section 💬")
                    self.gesture.tap_comments_icon()
                    self.stats.comments_viewed += 1
                    # Read comments with configured duration range
                    comm_read_min = float(probs.get("comment_read_min_seconds", 3.0))
                    comm_read_max = float(probs.get("comment_read_max_seconds", 6.5))
                    read_time = random.uniform(min(comm_read_min, comm_read_max), max(comm_read_min, comm_read_max))
                    time.sleep(read_time)
                    self._broadcast_status("Closing comment section")
                    self.gesture.close_comments_drawer()
                    pause_min = float(probs.get("post_action_pause_min_sec", 0.6))
                    pause_max = float(probs.get("post_action_pause_max_sec", 1.4))
                    time.sleep(random.uniform(min(pause_min, pause_max), max(pause_min, pause_max)))

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

            # Standard Biometric Swipe to Next Video
            self._broadcast_status("Swiping to next video 👆")
            self.gesture.swipe_next_video()
            # Post-swipe natural stabilization pause with range sampling
            post_swipe_min = float(probs.get("post_swipe_pause_min_sec", 0.8))
            post_swipe_max = float(probs.get("post_swipe_pause_max_sec", 1.8))
            time.sleep(random.uniform(min(post_swipe_min, post_swipe_max), max(post_swipe_min, post_swipe_max)))

        self.stats.state = SessionState.STOPPED
        self._broadcast_status("Session finished.")
        logger.info("TikTok session loop terminated.")

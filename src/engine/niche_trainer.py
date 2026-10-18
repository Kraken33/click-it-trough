import logging
import random
import time
from typing import Callable, List, Optional, Tuple
from ..bridge.wda_client import WDAClient
from ..physics.gesture import BiometricGestureEngine

logger = logging.getLogger(__name__)


class NicheTrainer:
    """
    Evaluates video relevance to the target niche and performs search seeding
    to train TikTok's recommendation algorithm vectors.
    """

    def __init__(self, target_keywords: List[str], seed_terms: List[str]):
        self.target_keywords = [k.lower().strip() for k in target_keywords]
        self.seed_terms = seed_terms

    def evaluate_relevance(self, text: str) -> Tuple[float, List[str]]:
        """
        Calculates a relevance score (0.0 to 1.0) and identifies matching niche keywords.
        Checks both raw text and normalized alphanumeric text (handling dashes, hashtags, spaces).
        """
        if not text:
            return 0.0, []

        import re
        lowered = text.lower()
        normalized = re.sub(r"[^a-z0-9]", "", lowered)

        matched = []
        for kw in self.target_keywords:
            clean_kw = re.sub(r"[^a-z0-9]", "", kw)
            if kw in lowered or (clean_kw and clean_kw in normalized):
                if kw not in matched:
                    matched.append(kw)

        if not matched:
            return 0.0, []

        # Score increases with more keyword hits, up to 1.0
        score = min(1.0, 0.4 + (len(matched) * 0.2))
        return score, matched

    def perform_search_seeding(
        self,
        client: WDAClient,
        gesture: BiometricGestureEngine,
        term: str,
        videos_to_watch: int = 3,
        dwell_min_sec: float = 7.0,
        dwell_max_sec: float = 15.0,
        on_progress: Optional[Callable[[str], None]] = None,
        stop_checker: Optional[Callable[[], bool]] = None,
    ) -> bool:
        """
        Executes a niche search on TikTok to prime the recommendation algorithm.
        1. Taps the search icon (top right).
        2. Enters search query and taps Search.
        3. Taps first video tile in search results.
        4. Browses 2-3 search result videos with human-like dwell and organic like.
        5. Returns back to the main FYP.
        """
        w, h = gesture.screen_width, gesture.screen_height

        def notify(msg: str):
            logger.info(msg)
            if on_progress:
                try:
                    on_progress(msg)
                except Exception:
                    pass

        def should_stop() -> bool:
            return bool(stop_checker and stop_checker())

        try:
            if should_stop():
                notify("Search seeding cancelled.")
                return False

            notify(f"Opening TikTok Search for '{term}'...")
            # 1. Tap search icon (top right: ~93% width, ~7.7% height)
            search_icon_x = w * random.uniform(0.92, 0.94)
            search_icon_y = h * random.uniform(0.073, 0.081)
            client.tap(search_icon_x, search_icon_y)
            time.sleep(random.uniform(1.5, 2.0))

            if should_stop():
                notify("Search seeding stopped.")
                return False

            # 2. Type search text
            notify(f"Typing query: '{term}'...")
            client.send_keys(term)
            time.sleep(random.uniform(0.8, 1.2))

            if should_stop():
                notify("Search seeding stopped.")
                return False

            # Tap red 'Search' button in header (~91.5% width, ~8.2% height)
            notify(f"Executing search for '{term}'...")
            search_btn_x = w * random.uniform(0.90, 0.93)
            search_btn_y = h * random.uniform(0.078, 0.086)
            client.tap(search_btn_x, search_btn_y)
            time.sleep(random.uniform(2.5, 3.5))

            if should_stop():
                notify("Search seeding stopped.")
                return False

            # 3. Tap first video in search results (top-left tile ~25% width, ~30% height)
            notify(f"Opening top video for '{term}'...")
            client.tap(w * random.uniform(0.22, 0.30), h * random.uniform(0.28, 0.35))
            time.sleep(random.uniform(2.0, 2.8))

            # 4. Watch a few search result videos with human attention and likes
            for i in range(videos_to_watch):
                if should_stop():
                    notify("Search seeding stopped.")
                    return False

                d_min = min(dwell_min_sec, dwell_max_sec)
                d_max = max(dwell_min_sec, dwell_max_sec)
                dwell = random.uniform(d_min, d_max)
                notify(f"Watching seed video {i+1}/{videos_to_watch} for {dwell:.1f}s...")
                t_start = time.time()
                while time.time() - t_start < dwell:
                    if should_stop():
                        notify("Search seeding stopped by user.")
                        return False
                    time.sleep(0.3)

                # Like the first or second seed video to signal strong interest
                if i == 0 or (videos_to_watch > 1 and i == 1):
                    notify(f"Liking niche video ({term}) to train FYP algorithm...")
                    gesture.double_tap_like()
                    time.sleep(random.uniform(1.0, 1.5))

                if i < videos_to_watch - 1:
                    if should_stop():
                        notify("Search seeding stopped.")
                        return False
                    notify("Swiping to next video in search feed...")
                    gesture.swipe_next_video()
                    time.sleep(random.uniform(1.2, 2.0))

            # 5. Return to FYP: Tap back arrow (top left: ~6.5% width, ~8.2% height) 3 times
            notify("Returning to main For You Page...")
            back_x = w * random.uniform(0.055, 0.075)
            back_y = h * random.uniform(0.075, 0.088)
            for _ in range(3):
                client.tap(back_x, back_y)
                time.sleep(random.uniform(1.0, 1.4))

            # Optional fallback tap on Home tab icon (bottom left ~10% width, ~95% height)
            client.tap(w * 0.10, h * 0.95)
            time.sleep(1.0)

            notify(f"Search seeding for '{term}' completed! Recommendation vector primed.")
            return True
        except Exception as e:
            logger.warning(f"Search seeding encountered an issue: {e}")
            notify(f"Search seeding error: {e}")
            return False

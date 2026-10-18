import logging
import random
import time
from typing import List, Tuple
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

    def evaluate_relevance(self, caption_and_tags: str) -> Tuple[float, List[str]]:
        """
        Calculates a relevance score (0.0 to 1.0) and identifies matching niche keywords.
        """
        if not caption_and_tags:
            return 0.0, []

        lowered = caption_and_tags.lower()
        matched = []
        for kw in self.target_keywords:
            if kw in lowered:
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
    ) -> bool:
        """
        Executes a niche search on TikTok to prime the recommendation algorithm.
        1. Taps the search icon (top right).
        2. Enters search query.
        3. Taps search button.
        4. Browses 2-3 search result videos with human-like dwell.
        5. Returns back to the main FYP.
        """
        w, h = gesture.screen_width, gesture.screen_height
        logger.info(f"Seeding niche with search term: '{term}'")

        try:
            # 1. Tap search icon (typically around 90% width, 7.5% height in FYP header)
            search_icon_x = w * random.uniform(0.88, 0.93)
            search_icon_y = h * random.uniform(0.065, 0.085)
            client.tap(search_icon_x, search_icon_y)
            time.sleep(random.uniform(1.2, 1.8))

            # 2. Type search text
            # Note: WDA provides keyboard typing via active element or session
            session_id = client.ensure_session()
            client._url(f"/session/{session_id}/wda/keys")
            import requests
            requests.post(
                client._url(f"/session/{session_id}/wda/keys"),
                json={"value": list(term) + ["\n"]},
                timeout=5.0,
            )
            time.sleep(random.uniform(2.5, 3.5))

            # 3. Tap first video in search results (usually top grid item around 35% height)
            client.tap(w * random.uniform(0.25, 0.45), h * random.uniform(0.32, 0.42))
            time.sleep(random.uniform(1.5, 2.2))

            # 4. Watch a few search result videos
            for i in range(videos_to_watch):
                dwell = random.uniform(8.0, 16.0)
                logger.info(f"Watching seed video {i+1}/{videos_to_watch} for {dwell:.1f}s")
                time.sleep(dwell)

                # Like one of the seed videos organically
                if i == 1:
                    gesture.double_tap_like()
                    time.sleep(1.0)

                gesture.swipe_next_video()
                time.sleep(random.uniform(1.0, 1.8))

            # 5. Return to FYP: Tap back arrow (top left, ~7% width, ~7.5% height) twice
            back_x = w * random.uniform(0.05, 0.09)
            back_y = h * random.uniform(0.065, 0.085)
            client.tap(back_x, back_y)
            time.sleep(random.uniform(1.0, 1.5))
            client.tap(back_x, back_y)
            time.sleep(random.uniform(1.0, 1.5))

            logger.info("Search seeding completed successfully. Returned to FYP.")
            return True
        except Exception as e:
            logger.warning(f"Search seeding encountered an issue: {e}")
            return False

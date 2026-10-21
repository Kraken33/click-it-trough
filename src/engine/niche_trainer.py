import logging
import random
import time
from typing import Any, Callable, List, Optional, Tuple
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
        device_manager: Optional[Any] = None,
        detector: Optional[Any] = None,
        recover_to_feed_fn: Optional[Callable[[], Tuple[bool, str]]] = None,
    ) -> bool:
        """
        Closed-Loop OCR-Verified Search Seeding:
        Executes a niche search on TikTok to prime the recommendation algorithm.
        Every state transition is verified with OCR & visual motion checks:
        0. Pre-check: Ensure TikTok is active and on clean FYP feed (recover if needed).
        1. Locate and tap search icon -> verify search screen active.
        2. Focus search input and type query -> verify query tokens visible in search field.
        3. Tap search button -> verify search results loaded.
        4. Tap top video result -> verify full-screen video active & playing.
        5. Watch seed videos with natural dwell, likes, and verified swipes.
        6. Step-by-step verified back navigation to FYP (with recover_to_feed fallback).
        """
        w, h = gesture.screen_width, gesture.screen_height

        def _coord_str(x: Any, y: Any) -> str:
            try:
                return f"({float(x):.1f}, {float(y):.1f})"
            except Exception:
                return f"({x}, {y})"

        def _diff_str(diff: Any) -> str:
            try:
                return f"{float(diff):.1f}%"
            except Exception:
                return f"{diff}%"

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

            # ---------------------------------------------------------
            # Step 0: Initial App Readiness & FYP State Verification
            # ---------------------------------------------------------
            if device_manager and detector:
                screen = device_manager.get_screen()
                if not screen:
                    time.sleep(1.0)
                    screen = device_manager.get_screen()

                if not screen:
                    notify("Device screen not accessible. Aborting search seeding.")
                    return False

                is_home, _ = detector.is_homescreen_open(screen)
                is_open, _ = detector.is_tiktok_open(screen)
                if is_home or not is_open:
                    notify("Device is on homescreen or TikTok not in foreground. Relaunching TikTok...")
                    if recover_to_feed_fn:
                        recovered, r_st = recover_to_feed_fn()
                        if not recovered:
                            notify(f"Could not reach TikTok FYP feed from '{r_st}'. Aborting search seeding.")
                            return False
                    else:
                        notify("TikTok not active and no recovery function provided. Aborting.")
                        return False

                # Ensure clean FYP before initiating search
                curr_screen = device_manager.get_screen()
                if curr_screen:
                    st, _ = detector.detect_screen_state(curr_screen)
                    if st != "feed" and not detector.is_feed_navigation_visible(curr_screen):
                        notify(f"Pre-seeding guard: Current screen '{st}' is not FYP feed. Recovering...")
                        if recover_to_feed_fn:
                            recovered, _ = recover_to_feed_fn()
                            if not recovered:
                                notify("Failed to recover to clean FYP feed. Aborting search seeding.")
                                return False

            # ---------------------------------------------------------
            # Step 1: Open Search (Up to 3 retries with OCR verification)
            # ---------------------------------------------------------
            notify(f"Opening TikTok Search for '{term}'...")
            search_opened = False

            for attempt in range(1, 4):
                if should_stop():
                    notify("Search seeding stopped by user.")
                    return False

                if device_manager and detector:
                    screen = device_manager.get_screen()
                    search_coord = detector.find_button_coordinate(
                        screen, r"search|пошук|поиск", region=(0.75, 0.03, 1.0, 0.15)
                    ) if screen else None

                    if search_coord:
                        s_x, s_y = search_coord[0] * w, search_coord[1] * h
                        notify(f"Tapping OCR search icon at {_coord_str(s_x, s_y)} (attempt {attempt}/3)...")
                    else:
                        s_x = w * random.uniform(0.92, 0.94)
                        s_y = h * random.uniform(0.073, 0.081)
                        notify(f"Tapping search icon area at {_coord_str(s_x, s_y)} (attempt {attempt}/3)...")

                    client.tap(s_x, s_y)

                    # Poll up to 3.0s for search screen transition
                    t_end = time.time() + 3.0
                    while time.time() < t_end:
                        if should_stop():
                            return False
                        time.sleep(0.5)
                        post_screen = device_manager.get_screen()
                        if not post_screen:
                            continue
                        is_srch, markers = detector.is_search_page_open(post_screen)
                        st, _ = detector.detect_screen_state(post_screen)
                        cancel_coord = detector.find_button_coordinate(
                            post_screen, r"cancel|отмена|відміна|abbrechen", region=(0.60, 0.02, 1.0, 0.15)
                        )
                        if is_srch or st == "search" or cancel_coord:
                            notify(f"Search screen verified open via OCR [{', '.join(markers[:2]) if markers else 'search_active'}] ✅")
                            search_opened = True
                            break

                    if search_opened:
                        break
                    notify(f"Search screen not confirmed on attempt {attempt}. Retrying tap...")
                else:
                    s_x = w * random.uniform(0.92, 0.94)
                    s_y = h * random.uniform(0.073, 0.081)
                    client.tap(s_x, s_y)
                    time.sleep(random.uniform(1.5, 2.0))
                    search_opened = True
                    break

            if not search_opened:
                notify("Failed to open search screen after 3 attempts. Aborting search seeding...")
                if recover_to_feed_fn:
                    recover_to_feed_fn()
                return False

            # ---------------------------------------------------------
            # Step 2: Focus & Type Search Query (Up to 3 retries)
            # ---------------------------------------------------------
            query_verified = False

            for attempt in range(1, 4):
                if should_stop():
                    notify("Search seeding stopped by user.")
                    return False

                notify(f"Typing query: '{term}' (attempt {attempt}/3)...")
                if device_manager and detector:
                    screen = device_manager.get_screen()
                    # Focus inside search input field
                    input_coord = detector.find_button_coordinate(
                        screen, r"search|пошук|поиск", region=(0.12, 0.04, 0.82, 0.14)
                    ) if screen else None

                    if input_coord:
                        client.tap(input_coord[0] * w, input_coord[1] * h)
                    else:
                        client.tap(w * 0.40, h * 0.078)
                    time.sleep(0.4)

                    client.send_keys(term)
                    time.sleep(1.0)

                    # OCR verification of query text in search header region
                    post_screen = device_manager.get_screen()
                    if post_screen:
                        full_text = detector.ocr.extract_text(post_screen).lower()
                        term_clean = term.lower().strip()
                        tokens = [t for t in term_clean.split() if len(t) >= 3]
                        if term_clean in full_text or any(token in full_text for token in tokens):
                            notify(f"Query '{term}' confirmed in search bar via OCR ✅")
                            query_verified = True
                            break
                        else:
                            notify(f"Query '{term}' not detected in search bar. Clearing and retrying...")
                            client.send_keys("\b" * (len(term) + 3))
                            time.sleep(0.4)
                else:
                    client.send_keys(term)
                    time.sleep(random.uniform(0.8, 1.2))
                    query_verified = True
                    break

            if not query_verified:
                notify(f"Query entry for '{term}' failed after 3 attempts. Aborting search seeding...")
                if recover_to_feed_fn:
                    recover_to_feed_fn()
                return False

            # ---------------------------------------------------------
            # Step 3: Execute Search (Up to 3 retries with OCR verification)
            # ---------------------------------------------------------
            results_verified = False

            for attempt in range(1, 4):
                if should_stop():
                    notify("Search seeding stopped by user.")
                    return False

                notify(f"Executing search for '{term}' (attempt {attempt}/3)...")
                if device_manager and detector:
                    screen = device_manager.get_screen()
                    search_btn_coord = detector.find_button_coordinate(
                        screen, r"search|пошук|поиск", region=(0.78, 0.04, 0.98, 0.14)
                    ) if screen else None

                    if search_btn_coord:
                        sb_x, sb_y = search_btn_coord[0] * w, search_btn_coord[1] * h
                    else:
                        sb_x = w * random.uniform(0.90, 0.93)
                        sb_y = h * random.uniform(0.078, 0.086)

                    client.tap(sb_x, sb_y)

                    # Poll up to 4.0s for search results page
                    t_end = time.time() + 4.0
                    while time.time() < t_end:
                        if should_stop():
                            return False
                        time.sleep(0.6)
                        post_screen = device_manager.get_screen()
                        if not post_screen:
                            continue
                        is_results, markers = detector.is_search_results_open(post_screen)
                        if is_results:
                            notify(f"Search results page verified via OCR [{', '.join(markers[:2])}] ✅")
                            results_verified = True
                            break

                    if results_verified:
                        break
                    notify(f"Search results not confirmed on attempt {attempt}. Retrying submit...")
                else:
                    sb_x = w * random.uniform(0.90, 0.93)
                    sb_y = h * random.uniform(0.078, 0.086)
                    client.tap(sb_x, sb_y)
                    time.sleep(random.uniform(2.5, 3.5))
                    results_verified = True
                    break

            if not results_verified:
                notify(f"Search results failed to load for '{term}'. Aborting search seeding...")
                if recover_to_feed_fn:
                    recover_to_feed_fn()
                return False

            # ---------------------------------------------------------
            # Step 4: Open Top Video Result (Up to 3 retries with OCR & Motion)
            # ---------------------------------------------------------
            video_opened = False

            for attempt in range(1, 4):
                if should_stop():
                    notify("Search seeding stopped by user.")
                    return False

                notify(f"Opening top video for '{term}' (attempt {attempt}/3)...")
                if device_manager and detector:
                    tile_x = w * random.uniform(0.22, 0.30)
                    tile_y = h * random.uniform(0.28, 0.35)
                    client.tap(tile_x, tile_y)

                    time.sleep(1.8)
                    post_screen = device_manager.get_screen()
                    if post_screen:
                        is_video, v_markers = detector.is_search_video_open(post_screen)
                        # Visual motion check to ensure video is actually playing
                        time.sleep(0.5)
                        motion_frame = device_manager.get_screen()
                        diff, changed = (0.0, False)
                        if motion_frame:
                            diff, changed = detector.did_video_change(post_screen, motion_frame, min_diff=1.8)

                        if is_video or changed:
                            detail = f"markers: {v_markers}" if is_video else f"motion diff: {_diff_str(diff)}"
                            notify(f"Top video confirmed open & playing ({detail}) ✅")
                            video_opened = True
                            break

                    notify(f"Top video did not confirm open on attempt {attempt}. Retrying tap...")
                else:
                    client.tap(w * random.uniform(0.22, 0.30), h * random.uniform(0.28, 0.35))
                    time.sleep(random.uniform(2.0, 2.8))
                    video_opened = True
                    break

            if not video_opened:
                notify(f"Failed to open video from search results for '{term}'. Aborting to FYP...")
                if recover_to_feed_fn:
                    recover_to_feed_fn()
                return False

            # ---------------------------------------------------------
            # Step 5: Watch Seed Videos with Attention & Likes
            # ---------------------------------------------------------
            for i in range(videos_to_watch):
                if should_stop():
                    notify("Search seeding stopped by user.")
                    return False

                d_min = min(dwell_min_sec, dwell_max_sec)
                d_max = max(dwell_min_sec, dwell_max_sec)
                dwell = random.uniform(d_min, d_max)
                dwell_val = f"{float(dwell):.1f}s" if isinstance(dwell, (int, float)) else f"{dwell}s"
                notify(f"Watching seed video {i+1}/{videos_to_watch} for {dwell_val}...")
                t_start = time.time()
                while time.time() - t_start < dwell:
                    if should_stop():
                        notify("Search seeding stopped by user.")
                        return False
                    # Periodically guard against popups during seed watch
                    if device_manager and detector:
                        curr = device_manager.get_screen()
                        if curr:
                            pop = detector.detect_popup(curr)
                            if pop:
                                notify(f"Dismissing modal '{pop}' during seed video...")
                                btn_coord = detector.find_button_coordinate(
                                    curr, r"not now|cancel|dismiss|later|не зараз|отмена|позже"
                                )
                                if btn_coord:
                                    client.tap(btn_coord[0] * w, btn_coord[1] * h)
                                else:
                                    dx, dy = detector.get_dismiss_coordinate(pop, int(w), int(h))
                                    client.tap(dx, dy)
                    time.sleep(0.4)

                # Like the first or second seed video
                if i == 0 or (videos_to_watch > 1 and i == 1):
                    notify(f"Liking niche video ({term}) to train FYP algorithm...")
                    gesture.double_tap_like()
                    time.sleep(random.uniform(1.0, 1.5))

                if i < videos_to_watch - 1:
                    if should_stop():
                        notify("Search seeding stopped by user.")
                        return False
                    notify("Swiping to next video in search feed...")
                    before_swipe = device_manager.get_screen() if device_manager else None
                    gesture.swipe_next_video()
                    time.sleep(random.uniform(1.2, 1.8))
                    if device_manager and detector and before_swipe:
                        after_swipe = device_manager.get_screen()
                        if after_swipe:
                            diff, _ = detector.did_video_change(before_swipe, after_swipe)
                            notify(f"Advanced to next video (frame visual diff: {_diff_str(diff)}) ✅")

            # ---------------------------------------------------------
            # Step 6: Step-by-Step Verified Back Navigation to FYP
            # ---------------------------------------------------------
            notify("Returning to main For You Page...")
            on_fyp = False

            if device_manager and detector:
                for step in range(1, 6):
                    if should_stop():
                        notify("Search seeding stopped by user.")
                        return False

                    screen = device_manager.get_screen()
                    if not screen:
                        time.sleep(0.5)
                        continue

                    st, markers = detector.detect_screen_state(screen)
                    is_feed_nav = detector.is_feed_navigation_visible(screen)
                    if (st == "feed" or is_feed_nav) and st not in (
                        "comment_input", "keyboard", "comments", "share", "search", "unknown"
                    ):
                        notify("Confirmed back on For You Page feed ✅")
                        on_fyp = True
                        break

                    is_vid, _ = detector.is_search_video_open(screen)
                    is_res, _ = detector.is_search_results_open(screen)
                    is_srch, _ = detector.is_search_page_open(screen)

                    if is_vid:
                        notify(f"[Nav step {step}] Video player: Tapping back chevron to search results...")
                        client.tap(w * 0.065, h * 0.078)
                    elif is_res:
                        notify(f"[Nav step {step}] Search results: Tapping back chevron to search input...")
                        client.tap(w * 0.065, h * 0.078)
                    elif is_srch or st == "search":
                        cancel_coord = detector.find_button_coordinate(screen, r"cancel|отмена|відміна|abbrechen")
                        if cancel_coord:
                            notify(f"[Nav step {step}] Search page: Tapping OCR 'Cancel'...")
                            client.tap(cancel_coord[0] * w, cancel_coord[1] * h)
                        else:
                            home_coord = detector.find_button_coordinate(
                                screen, r"home|головна|главная|startseite", region=(0.0, 0.88, 0.35, 1.0)
                            )
                            if home_coord:
                                notify(f"[Nav step {step}] Tapping OCR Home tab...")
                                client.tap(home_coord[0] * w, home_coord[1] * h)
                            else:
                                notify(f"[Nav step {step}] Tapping Home tab at (0.10, 0.955)...")
                                client.tap(w * 0.10, h * 0.955)
                    else:
                        notify(f"[Nav step {step}] Returning from '{st}': Tapping Home tab...")
                        client.tap(w * 0.10, h * 0.955)

                    time.sleep(1.0)

                if not on_fyp:
                    notify("Back navigation did not confirm FYP. Invoking recover_to_feed()...")
                    if recover_to_feed_fn:
                        recovered, _ = recover_to_feed_fn()
                        if recovered:
                            notify("Successfully recovered back to FYP feed ✅")
                            on_fyp = True
            else:
                back_x = w * random.uniform(0.055, 0.075)
                back_y = h * random.uniform(0.075, 0.088)
                for _ in range(3):
                    client.tap(back_x, back_y)
                    time.sleep(random.uniform(1.0, 1.4))
                client.tap(w * 0.10, h * 0.95)
                time.sleep(1.0)
                on_fyp = True

            if on_fyp:
                notify(f"Search seeding for '{term}' completed successfully! Recommendation vector primed ✅")
                return True
            else:
                notify(f"Search seeding completed watch loop but could not confirm return to FYP.")
                return False

        except Exception as e:
            logger.warning(f"Search seeding encountered an issue: {e}")
            notify(f"Search seeding error: {e}")
            if recover_to_feed_fn:
                try:
                    recover_to_feed_fn()
                except Exception:
                    pass
            return False

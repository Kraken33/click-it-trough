import math
import random
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from ..bridge.wda_client import WDAClient


class BiometricGestureEngine:
    """
    Simulates authentic human touch biomechanics on mobile touchscreens.
    Generates cubic Bézier curved trajectories, non-linear velocity profiles,
    and micro-tremor coordinate jitter to defeat anti-bot telemetry.
    """

    def __init__(
        self,
        client: WDAClient,
        screen_width: int = 393,
        screen_height: int = 852,
        handedness: str = "right",
        curve_deviation_px: float = 24.0,
        jitter_intensity_px: float = 2.0,
    ):
        self.client = client
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.handedness = handedness.lower()
        self.curve_deviation_px = curve_deviation_px
        self.jitter_intensity_px = jitter_intensity_px

    def _generate_bezier_curve(
        self,
        p0: Tuple[float, float],
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        p3: Tuple[float, float],
        steps: int = 25,
    ) -> List[Tuple[float, float]]:
        """
        Computes 2D points along a cubic Bézier curve:
        B(t) = (1-t)³P₀ + 3(1-t)²tP₁ + 3(1-t)t²P₂ + t³P₃
        """
        t = np.linspace(0.0, 1.0, steps)
        # Compute coordinates
        x = (
            (1 - t) ** 3 * p0[0]
            + 3 * (1 - t) ** 2 * t * p1[0]
            + 3 * (1 - t) * t ** 2 * p2[0]
            + t ** 3 * p3[0]
        )
        y = (
            (1 - t) ** 3 * p0[1]
            + 3 * (1 - t) ** 2 * t * p1[1]
            + 3 * (1 - t) * t ** 2 * p2[1]
            + t ** 3 * p3[1]
        )

        # Inject subtle human micro-tremor jitter (except endpoints)
        noise_x = np.random.normal(0, self.jitter_intensity_px, steps)
        noise_y = np.random.normal(0, self.jitter_intensity_px, steps)
        noise_x[0] = noise_x[-1] = 0.0
        noise_y[0] = noise_y[-1] = 0.0

        x_jittered = x + noise_x
        y_jittered = y + noise_y

        points = [(float(px), float(py)) for px, py in zip(x_jittered, y_jittered)]
        return points

    def _compute_velocity_durations(self, steps: int, total_duration_ms: int) -> List[int]:
        """
        Calculates non-linear time step durations using ease-in-out curve.
        Human touch accelerates quickly, reaches max speed in the middle, and decelerates gently.
        """
        # Generate ease-out / bell curve distribution of speeds
        t = np.linspace(0, np.pi, steps - 1)
        # Weights higher in the middle means faster movement -> smaller duration per step
        weights = 1.0 / (np.sin(t) + 0.4)
        normalized_weights = weights / np.sum(weights)
        durations = [max(4, int(w * total_duration_ms)) for w in normalized_weights]

        # Ensure sum matches total_duration_ms
        diff = total_duration_ms - sum(durations)
        durations[len(durations) // 2] += diff
        return durations

    def swipe_next_video(
        self,
        duration_ms: Optional[int] = None,
        handedness: Optional[str] = None,
        velocity: Optional[float] = None,
    ) -> bool:
        """
        Performs an organic upward swipe to transition to the next TikTok video.
        Uses native pressAndDragWithVelocity with zero touch-down pause and high flick
        velocity (2800-3500 pt/s) to ensure 100% stable pagination on TikTok's feed.
        """
        hand = (handedness or self.handedness).lower()
        w, h = self.screen_width, self.screen_height

        # Safe horizontal corridor:
        # Avoids center carousel dots (35%-65% width) and sidebar icons (86%-100% width)
        if hand == "left":
            start_x = w * random.uniform(0.24, 0.32)
            end_x = start_x + random.uniform(6, 14)
        else:
            # Right-hand safe corridor: 68% to 76% width
            start_x = w * random.uniform(0.68, 0.76)
            end_x = start_x - random.uniform(6, 14)

        # Start position: Lower area (68% - 76%)
        start_y = h * random.uniform(0.68, 0.76)
        # End position: Upper screen (14% - 20%) - authoritatively crosses 50% snap threshold
        end_y = h * random.uniform(0.14, 0.20)

        fling_velocity = velocity or random.uniform(2800.0, 3500.0)

        # Execute native press & drag with fling velocity and ZERO hold duration
        success = self.client.press_and_drag_with_velocity(
            start_x,
            start_y,
            end_x,
            end_y,
            velocity=fling_velocity,
            press_duration=0.0,
            hold_duration=0.0,
        )
        if not success:
            return self.client.swipe(direction="up", x=start_x, y=start_y, velocity=fling_velocity)
        return True

    def swipe_previous_video(self, velocity: Optional[float] = None) -> bool:
        """Performs an organic downward swipe to return to the previous video."""
        w, h = self.screen_width, self.screen_height
        hand = self.handedness.lower()
        if hand == "left":
            start_x = w * random.uniform(0.24, 0.32)
            end_x = start_x - random.uniform(6, 14)
        else:
            start_x = w * random.uniform(0.68, 0.76)
            end_x = start_x + random.uniform(6, 14)

        start_y = h * random.uniform(0.16, 0.22)
        end_y = h * random.uniform(0.70, 0.76)
        fling_velocity = velocity or random.uniform(2800.0, 3500.0)

        success = self.client.press_and_drag_with_velocity(
            start_x,
            start_y,
            end_x,
            end_y,
            velocity=fling_velocity,
            press_duration=0.0,
            hold_duration=0.0,
        )
        if not success:
            return self.client.swipe(direction="down", x=start_x, y=start_y, velocity=fling_velocity)
        return True

    def micro_flick(self) -> bool:
        """Simulates an accidental small thumb twitch or partial scroll."""
        w, h = self.screen_width, self.screen_height
        hand = self.handedness.lower()
        base_x = w * 0.74 if hand != "left" else w * 0.28
        start_x = base_x + random.uniform(-15, 15)
        start_y = h * 0.58 + random.uniform(-20, 20)
        end_x = start_x + random.uniform(-8, 8)
        end_y = start_y - random.uniform(40, 75)

        return self.client.perform_w3c_actions([
            {
                "type": "pointer",
                "id": "finger1",
                "parameters": {"pointerType": "touch"},
                "actions": [
                    {"type": "pointerMove", "duration": 0, "x": int(start_x), "y": int(start_y)},
                    {"type": "pointerDown", "button": 0},
                    {"type": "pointerMove", "duration": 110, "x": int(end_x), "y": int(end_y)},
                    {"type": "pointerUp", "button": 0},
                ],
            }
        ])

    def double_tap_like(self) -> bool:
        """Double taps center-right of the video screen to send a like."""
        w, h = self.screen_width, self.screen_height
        # Target middle area of the video
        target_x = w * random.uniform(0.42, 0.58)
        target_y = h * random.uniform(0.42, 0.54)
        gap = random.randint(100, 150)
        return self.client.double_tap(target_x, target_y, gap_ms=gap)

    def tap_heart_icon(self) -> bool:
        """Taps the TikTok right-hand sidebar heart icon directly."""
        w, h = self.screen_width, self.screen_height
        # Right action sidebar heart icon is centered around ~92.5% width, ~56.4% height
        heart_x = w * random.uniform(0.905, 0.945)
        heart_y = h * random.uniform(0.552, 0.575)
        return self.client.tap(heart_x, heart_y, dwell_ms=random.randint(45, 75))

    def tap_bookmark_icon(self) -> bool:
        """Taps the TikTok right-hand sidebar bookmark / favorite icon."""
        w, h = self.screen_width, self.screen_height
        # Bookmark icon is below comments, centered around ~92.5% width, ~71.6% height
        bm_x = w * random.uniform(0.905, 0.945)
        bm_y = h * random.uniform(0.705, 0.725)
        return self.client.tap(bm_x, bm_y, dwell_ms=random.randint(45, 75))

    def tap_comments_icon(self) -> bool:
        """Taps the TikTok comment icon to open comment drawer."""
        w, h = self.screen_width, self.screen_height
        # Comment icon is below heart, centered around ~92.5% width, ~63.9% height
        comm_x = w * random.uniform(0.905, 0.945)
        comm_y = h * random.uniform(0.628, 0.648)
        return self.client.tap(comm_x, comm_y, dwell_ms=random.randint(45, 75))

    def close_comments_drawer(self) -> bool:
        """Closes the comment drawer by tapping top dimmed video backdrop or top-right X button."""
        w, h = self.screen_width, self.screen_height
        if random.random() < 0.75:
            # Tap top dimmed video area (0.40-0.60 w, 0.16-0.22 h) which universally dismisses
            # the bottom sheet without touching any comments or keyboard inputs
            tap_x = w * random.uniform(0.40, 0.60)
            tap_y = h * random.uniform(0.16, 0.22)
            return self.client.tap(tap_x, tap_y, dwell_ms=random.randint(45, 75))
        else:
            # Tap top-right 'X' button of comment drawer header (~92-95% width, ~33.8-35.0% height)
            tap_x = w * random.uniform(0.925, 0.945)
            tap_y = h * random.uniform(0.338, 0.350)
            return self.client.tap(tap_x, tap_y, dwell_ms=random.randint(45, 75))

    def tap_author_avatar(self) -> bool:

        """Taps the creator's avatar on the right sidebar of the FYP feed to open their profile."""
        w, h = self.screen_width, self.screen_height
        # Avatar is on the right-hand bar directly above the heart icon (~92.5% w, ~47.5-49.5% h)
        avatar_x = w * random.uniform(0.905, 0.945)
        avatar_y = h * random.uniform(0.472, 0.495)
        return self.client.tap(avatar_x, avatar_y, dwell_ms=random.randint(45, 75))

    def swipe_to_profile(self) -> bool:
        """Swipes horizontally from right to left across the video to open the author profile."""
        w, h = self.screen_width, self.screen_height
        start_x = w * random.uniform(0.78, 0.88)
        end_x = w * random.uniform(0.14, 0.24)
        y = h * random.uniform(0.48, 0.54)
        duration_ms = random.randint(200, 280)
        return self.client.swipe(
            direction="left",
            x=start_x,
            y=y,
            velocity=random.uniform(1500, 2200),
        )

    def tap_first_profile_video(self) -> bool:
        """Taps the first video thumbnail in the author profile's 3-column video grid."""
        w, h = self.screen_width, self.screen_height
        # First video tile is at top-left of the profile grid (~16-22% w, ~68-74% h)
        tile_x = w * random.uniform(0.14, 0.22)
        tile_y = h * random.uniform(0.68, 0.74)
        return self.client.tap(tile_x, tile_y, dwell_ms=random.randint(50, 80))

    def tap_follow_button(self, x: Optional[float] = None, y: Optional[float] = None) -> bool:
        """
        Taps the Follow button on the author's profile page.
        Accepts optional OCR-located pixel coordinates with micro-jitter.
        """
        w, h = self.screen_width, self.screen_height
        if x is not None and y is not None:
            target_x = x + random.uniform(-4, 4)
            target_y = y + random.uniform(-3, 3)
        else:
            # Standard author profile follow button location (~40-60% w, ~30-34% h)
            target_x = w * random.uniform(0.42, 0.58)
            target_y = h * random.uniform(0.305, 0.335)
        return self.client.tap(target_x, target_y, dwell_ms=random.randint(50, 85))

    def tap_profile_back(self) -> bool:
        """Taps the top-left back chevron button on profile or video player to return to previous screen."""
        w, h = self.screen_width, self.screen_height
        back_x = w * random.uniform(0.045, 0.075)
        back_y = h * random.uniform(0.065, 0.082)
        return self.client.tap(back_x, back_y, dwell_ms=random.randint(45, 75))



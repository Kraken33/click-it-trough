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
    ) -> bool:
        """
        Performs an organic upward swipe to transition to the next TikTok video.
        Follows a natural thumb arc pivoted from the lower screen corner.
        """
        hand = (handedness or self.handedness).lower()
        dur = duration_ms or random.randint(140, 210)

        # Screen dimensions
        w, h = self.screen_width, self.screen_height

        # Start position: Safe center area (58% to 63% height is completely clear of all captions, hashtags, and sound tags)
        start_x = w * random.uniform(0.48, 0.52)
        start_y = h * random.uniform(0.58, 0.63)

        # High-velocity native flick (Apple XCTest coordinate swipeUp)
        speed = random.uniform(2700.0, 3300.0)
        success = self.client.swipe(direction="up", x=start_x, y=start_y, velocity=speed)
        if not success:
            # Fallback: high-momentum fling across 45% screen distance
            end_x = start_x + (random.uniform(-14, -4) if hand == "right" else random.uniform(4, 14))
            end_y = h * random.uniform(0.14, 0.18)
            success = self.client.press_and_drag_with_velocity(
                start_x, start_y, end_x, end_y, velocity=speed, press_duration=0.01, hold_duration=0.0
            )
        return success

    def swipe_previous_video(self) -> bool:
        """Performs an organic downward swipe to return to the previous video."""
        w, h = self.screen_width, self.screen_height

        start_x = w * random.uniform(0.48, 0.52)
        start_y = h * random.uniform(0.20, 0.25)

        # Native downward flick
        speed = random.uniform(2500.0, 3000.0)
        success = self.client.swipe(direction="down", x=start_x, y=start_y, velocity=speed)
        if not success:
            end_x = start_x + random.uniform(-12, 12)
            end_y = h * random.uniform(0.70, 0.75)
            success = self.client.press_and_drag_with_velocity(
                start_x, start_y, end_x, end_y, velocity=speed, press_duration=0.01, hold_duration=0.0
            )
        return success

    def micro_flick(self) -> bool:
        """Simulates an accidental small thumb twitch or partial scroll."""
        w, h = self.screen_width, self.screen_height
        start_x = w * 0.5 + random.uniform(-30, 30)
        start_y = h * 0.6 + random.uniform(-20, 20)
        end_x = start_x + random.uniform(-10, 10)
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
        # Right action sidebar heart icon is typically at ~92% width, ~48-52% height
        heart_x = w * random.uniform(0.89, 0.94)
        heart_y = h * random.uniform(0.48, 0.53)
        return self.client.tap(heart_x, heart_y, dwell_ms=random.randint(45, 75))

    def tap_bookmark_icon(self) -> bool:
        """Taps the TikTok right-hand sidebar bookmark / favorite icon."""
        w, h = self.screen_width, self.screen_height
        # Bookmark icon is typically below comments, around ~64-68% height
        bm_x = w * random.uniform(0.89, 0.94)
        bm_y = h * random.uniform(0.63, 0.68)
        return self.client.tap(bm_x, bm_y, dwell_ms=random.randint(45, 75))

    def tap_comments_icon(self) -> bool:
        """Taps the TikTok comment icon to open comment drawer."""
        w, h = self.screen_width, self.screen_height
        # Comment icon is below heart, around ~55-59% height
        comm_x = w * random.uniform(0.89, 0.94)
        comm_y = h * random.uniform(0.55, 0.60)
        return self.client.tap(comm_x, comm_y, dwell_ms=random.randint(45, 75))

    def close_comments_drawer(self) -> bool:
        """Closes the comment drawer by tapping top-right X or tapping top dimmed background."""
        w, h = self.screen_width, self.screen_height
        # Tap the top dimmed portion of the screen (around 15-22% height)
        tap_x = w * random.uniform(0.45, 0.55)
        tap_y = h * random.uniform(0.15, 0.22)
        return self.client.tap(tap_x, tap_y, dwell_ms=random.randint(50, 80))

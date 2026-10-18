import logging
import os
import subprocess
import time
from datetime import datetime
from PIL import Image

logger = logging.getLogger(__name__)


class SafetySentinel:
    """
    Monitors security anomalies, issues alerts via native macOS audio/dialogues,
    and preserves screenshots for review.
    """

    def __init__(
        self,
        screenshot_dir: str = "logs/captchas",
        play_sound: bool = True,
        macos_notification: bool = True,
    ):
        self.screenshot_dir = screenshot_dir
        self.play_sound = play_sound
        self.macos_notification = macos_notification
        os.makedirs(screenshot_dir, exist_ok=True)

    def trigger_captcha_alert(self, screen_image: Image.Image) -> str:
        """
        Executes immediate alert sequence when an interactive captcha or verification challenge is detected.
        Saves screenshot and alerts via audio and macOS notification.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"captcha_alert_{timestamp}.png"
        filepath = os.path.join(self.screenshot_dir, filename)

        try:
            screen_image.save(filepath)
            logger.warning(f"Saved captcha screenshot to: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save captcha screenshot: {e}")

        # Native macOS notification via AppleScript
        if self.macos_notification:
            try:
                apple_script = (
                    'display notification "TikTok triggered a verification challenge. Automation has paused." '
                    'with title "TikTok Bot Alert" sound name "Sosumi"'
                )
                subprocess.run(["osascript", "-e", apple_script], check=False)
            except Exception as e:
                logger.debug(f"Failed to trigger macOS notification: {e}")

        # Play system sound
        if self.play_sound:
            try:
                subprocess.Popen(["afplay", "/System/Library/Sounds/Sosumi.aiff"])
            except Exception as e:
                logger.debug(f"Failed to play system sound: {e}")

        return filepath

import re
from typing import Optional, Tuple
from PIL import Image

from .ocr import VisionOCR


class ScreenDetector:
    """
    Analyzes screen images and extracted text to identify video types (organic vs ad vs live)
    and screen interruptions (popups, security challenges, captchas).
    """

    # Indicators for sponsored / promotional content in TikTok
    AD_PATTERNS = [
        r"\bsponsored\b",
        r"\bpaid partnership\b",
        r"\bpromoted\b",
        r"\bshop now\b",
        r"\binstall now\b",
        r"\bdownload\b",
        r"\blearn more\b",
        r"\border now\b",
        r"\bclaim discount\b",
    ]

    # Indicators for interactive security verification / captchas
    CAPTCHA_PATTERNS = [
        r"verify to continue",
        r"drag the slider",
        r"verification code",
        r"security verification",
        r"select 2 objects",
        r"select the objects",
        r"slide to complete",
        r"puzzle piece",
        r"suspicious activity",
        r"unusual traffic",
    ]

    # Common modal popups
    POPUP_PATTERNS = {
        "notifications": [r"turn on notifications", r"don't miss notifications", r"enable notifications"],
        "tracking": [r"ask app not to track", r"allow tracking"],
        "rating": [r"enjoying tiktok\?", r"rate tiktok", r"rate us"],
        "update": [r"update tiktok", r"new version available"],
        "generic_modal": [r"not now", r"maybe later", r"dismiss"],
    }

    def __init__(self, ocr: Optional[VisionOCR] = None):
        self.ocr = ocr or VisionOCR()

    def check_for_captcha(self, screen_image: Image.Image) -> bool:
        """
        Inspects full screen to detect bot verification / slider challenges.
        """
        text = self.ocr.extract_text(screen_image).lower()
        for pattern in self.CAPTCHA_PATTERNS:
            if re.search(pattern, text):
                return True
        return False

    def is_sponsored(self, caption_text: str) -> bool:
        """
        Returns True if the caption or overlay indicates an advertisement.
        """
        lowered = caption_text.lower()
        for pattern in self.AD_PATTERNS:
            if re.search(pattern, lowered):
                return True
        return False

    def is_live_stream(self, header_text: str, full_text: str) -> bool:
        """
        Returns True if the screen is currently locked into a LIVE broadcast.
        """
        h_lowered = header_text.lower()
        f_lowered = full_text.lower()
        if "live" in h_lowered and ("watch live" in f_lowered or "tap to join" in f_lowered or "host" in f_lowered):
            return True
        if "swipe up to explore more lives" in f_lowered:
            return True
        return False

    def detect_popup(self, screen_image: Image.Image) -> Optional[str]:
        """
        Returns the popup category if an interrupting dialogue is present, else None.
        """
        text = self.ocr.extract_text(screen_image).lower()
        for category, patterns in self.POPUP_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, text):
                    return category
        return None

    def get_dismiss_coordinate(self, popup_type: str, width: int, height: int) -> Tuple[int, int]:
        """
        Returns best approximate coordinates to dismiss known modal dialogues.
        """
        if popup_type in ("notifications", "generic_modal", "rating"):
            # "Not Now" / "Cancel" is almost always in the lower half of the modal
            return (int(width * 0.5), int(height * 0.62))
        elif popup_type == "tracking":
            # "Ask App not to Track" is the bottom option
            return (int(width * 0.5), int(height * 0.58))
        return (int(width * 0.5), int(height * 0.65))

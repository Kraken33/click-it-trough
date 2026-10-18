import re
from typing import List, Optional, Tuple
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

    # Indicators that TikTok app feed/UI is active
    TIKTOK_PATTERNS = [
        r"\bfor you\b",
        r"\bfollowing\b",
        r"\bfriends\b",
        r"\bcommunity\b",
        r"\blive\b",
        r"для вас",
        r"підписки",
        r"подписки",
        r"\btiktok\b",
        r"\badd comment\b",
        r"\bshare to\b",
        r"\bhome\b",
        r"\binbox\b",
        r"\bprofile\b",
    ]

    # Indicators that iOS SpringBoard / Homescreen is active
    HOMESCREEN_PATTERNS = [
        r"app library",
        r"suggestions",
        r"recently added",
        r"productivity",
        r"utilities",
        r"бібліотека програм",
        r"библиотека приложений",
        r"соцсети",
        r"соціальні",
        r"недавно добавленные",
        r"нещодавно додані",
    ]

    # Indicators that TikTok comments drawer is open
    COMMENT_PATTERNS = [
        r"\bcomments?\b",
        r"add comment",
        r"\breply\b",
        r"replies",
        r"коментар",
        r"комментар",
        r"відповісти",
        r"ответить",
        r"додати коментар",
        r"оставьте комментарий",
    ]

    # Indicators that TikTok share drawer / send to sheet is open
    SHARE_PATTERNS = [
        r"\bshare to\b",
        r"\bsend to\b",
        r"\brepost\b",
        r"\bcopy link\b",
        r"\binvite friends\b",
        r"\bwhatsapp\b",
        r"\bsnapchat\b",
        r"\bmessenger\b",
        r"\badd to story\b",
        r"\bduet\b",
        r"\bstitch\b",
        r"поділитися",
        r"поделиться",
        r"скопировать ссылку",
    ]

    # Indicators that an author or user profile page is open
    PROFILE_PATTERNS = [
        r"\bfollowers\b",
        r"\bfollowing\b",
        r"\bedit profile\b",
        r"\bfollow\b",
        r"підписники",
        r"читачі",
        r"підписатися",
        r"подписчики",
        r"подписаться",
    ]

    # Indicators that search / explore is open
    SEARCH_PATTERNS = [
        r"recent searches",
        r"you may like",
        r"trending searches",
        r"search accounts",
        r"пошук",
        r"поиск",
    ]

    # Indicators that story viewer is open
    STORY_PATTERNS = [
        r"\bmessage\.\.\.\b",
        r"\d+h ago\b",
        r"\d+d ago\b",
        r"\d+m ago\b",
    ]

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

    def is_tiktok_open(self, screen_image: Image.Image) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether TikTok UI is currently active on screen.
        Returns (is_open, list_of_matched_indicators).
        """
        text = self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.TIKTOK_PATTERNS if re.search(p, text)]
        if not matched:
            is_comm, comm_m = self.is_comment_section_open(screen_image)
            if is_comm:
                return True, comm_m
        return len(matched) > 0, matched

    def is_homescreen_open(self, screen_image: Image.Image) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether iOS SpringBoard / Homescreen is currently active.
        Returns (is_homescreen, list_of_matched_indicators).
        """
        text = self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.HOMESCREEN_PATTERNS if re.search(p, text)]
        return len(matched) > 0, matched

    def is_comment_section_open(self, screen_image: Image.Image) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether the TikTok comment drawer/sheet is open.
        Returns (is_open, list_of_matched_indicators).
        """
        text = self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.COMMENT_PATTERNS if re.search(p, text)]
        return len(matched) > 0, matched

    def is_share_sheet_open(self, screen_image: Image.Image) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether the TikTok Share / Send to drawer is open.
        Returns (is_open, list_of_matched_indicators).
        """
        text = self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.SHARE_PATTERNS if re.search(p, text)]
        return len(matched) >= 2, matched

    def is_story_open(self, screen_image: Image.Image) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether a TikTok Story is being viewed.
        Returns (is_story, list_of_matched_indicators).
        """
        text = self.ocr.extract_text(screen_image).lower()
        is_feed = ("for you" in text or "following" in text) and ("home" in text or "inbox" in text)
        matched = [p for p in self.STORY_PATTERNS if re.search(p, text)]
        return (not is_feed and len(matched) > 0), matched

    def is_profile_page_open(self, screen_image: Image.Image) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether an author/user profile page is open.
        Returns (is_profile, list_of_matched_indicators).
        """
        text = self.ocr.extract_text(screen_image).lower()
        is_feed = ("for you" in text or "following" in text) and ("home" in text or "inbox" in text)
        matched = [p for p in self.PROFILE_PATTERNS if re.search(p, text)]
        return (not is_feed and len(matched) >= 2), matched

    def is_search_page_open(self, screen_image: Image.Image) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether the TikTok search / explore page is open.
        Returns (is_search, list_of_matched_indicators).
        """
        text = self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.SEARCH_PATTERNS if re.search(p, text)]
        return len(matched) > 0, matched

    def detect_screen_state(self, screen_image: Image.Image) -> Tuple[str, List[str]]:
        """
        Identifies the current screen state:
        - 'feed': Clean FYP video feed.
        - 'comments': Comments sheet drawer is open.
        - 'share': Share sheet / Send to drawer is open.
        - 'story': Story player is open.
        - 'profile': Author profile page is open.
        - 'search': Search / Discover page is open.
        - 'popup': Modal alert or captcha.
        - 'homescreen': iOS SpringBoard / App Library.
        - 'other_tab': On an alternative tab (e.g. Inbox / Friends).
        - 'unknown': Ambiguous state.
        """
        # 1. Homescreen check
        is_home, h_markers = self.is_homescreen_open(screen_image)
        if is_home:
            return "homescreen", h_markers

        # 2. Captcha / security verification check
        if self.check_for_captcha(screen_image):
            return "popup", ["captcha_or_verification"]

        # 3. Interrupting modal popup check
        popup = self.detect_popup(screen_image)
        if popup:
            return "popup", [popup]

        # 4. Comments drawer check
        is_comm, c_markers = self.is_comment_section_open(screen_image)
        if is_comm:
            return "comments", c_markers

        # 5. Share sheet check
        is_share, s_markers = self.is_share_sheet_open(screen_image)
        if is_share:
            return "share", s_markers

        # 6. Story player check
        is_story, st_markers = self.is_story_open(screen_image)
        if is_story:
            return "story", st_markers

        # 7. Profile page check
        is_prof, p_markers = self.is_profile_page_open(screen_image)
        if is_prof:
            return "profile", p_markers

        # 8. Search page check
        is_srch, sr_markers = self.is_search_page_open(screen_image)
        if is_srch:
            return "search", sr_markers

        # 9. Clean video feed check
        is_tt, tt_markers = self.is_tiktok_open(screen_image)
        if is_tt:
            text = self.ocr.extract_text(screen_image).lower()
            if "for you" in text or "для вас" in text:
                return "feed", tt_markers
            else:
                return "other_tab", tt_markers

        return "unknown", []

    def extract_likes_and_signature(self, screen_image: Image.Image) -> Tuple[Optional[str], str]:
        """
        Extracts the likes count (below the heart icon in the right action sidebar)
        and content signature (body text/captions) from a TikTok video screen.
        Returns (likes_count_str, content_signature_str).
        """
        obs = self.ocr.extract_observations(screen_image)
        if not obs:
            return None, ""

        like_candidates = []
        for text, cx, cy, w, h in obs:
            if cx > 0.82 and 0.52 <= cy <= 0.65:
                cleaned = text.replace(" ", "").upper()
                if re.match(r"^\d+([.,]\d+)?[KMB]?$", cleaned):
                    like_candidates.append((cy, cleaned))

        like_count = None
        if like_candidates:
            like_candidates.sort(key=lambda item: abs(item[0] - 0.595))
            like_count = like_candidates[0][1]

        body_texts = [
            text for text, cx, cy, w, h in obs
            if 0.12 <= cy <= 0.90 and cx < 0.85 and len(text) > 2
        ]
        content_sig = " ".join(body_texts[:5]).strip()
        return like_count, content_sig

    def did_video_change(
        self,
        before_image: Image.Image,
        after_image: Image.Image,
        before_likes: Optional[str] = None,
        before_sig: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Verifies whether the video on screen changed after a swipe gesture.
        Uses the likes amount as the primary verification:
        - If likes changed -> Video changed.
        - If likes are identical -> Same video.
        - If likes could not be extracted on one or both -> Falls back to content signature comparison.
        Returns (has_changed, reason_description).
        """
        if before_likes is None or before_sig is None:
            b_likes, b_sig = self.extract_likes_and_signature(before_image)
            before_likes = before_likes or b_likes
            before_sig = before_sig or b_sig

        after_likes, after_sig = self.extract_likes_and_signature(after_image)

        # 1. Primary check: Likes amount
        if before_likes is not None and after_likes is not None:
            if before_likes != after_likes:
                return True, f"Likes changed: {before_likes} -> {after_likes}"
            else:
                if before_sig and after_sig and before_sig == after_sig:
                    return False, f"Likes unchanged ({before_likes}) and identical content"
                elif not before_sig and not after_sig:
                    return False, f"Likes unchanged ({before_likes})"
                if before_sig and after_sig:
                    from difflib import SequenceMatcher
                    ratio = SequenceMatcher(None, before_sig.lower(), after_sig.lower()).ratio()
                    if ratio > 0.60:
                        return False, f"Likes unchanged ({before_likes}) and content match {ratio:.0%}"
                    else:
                        return True, f"Content changed despite same like count ({before_likes})"

        # 2. Fallback check: Content signature if likes count was obscured
        if before_sig and after_sig:
            from difflib import SequenceMatcher
            ratio = SequenceMatcher(None, before_sig.lower(), after_sig.lower()).ratio()
            if ratio < 0.45:
                return True, f"Content changed ({ratio:.0%} match)"
            else:
                return False, f"Content unchanged ({ratio:.0%} match)"

        if (before_likes is None) != (after_likes is None):
            return True, f"Likes indicator changed ({before_likes} vs {after_likes})"

        return False, "Could not detect distinct video markers"


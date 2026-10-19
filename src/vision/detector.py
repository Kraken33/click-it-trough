import re
from typing import Dict, List, Optional, Tuple
from PIL import Image, ImageOps, ImageStat

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

    # Indicators that iOS virtual keyboard / "Add comment" input field is active
    KEYBOARD_PATTERNS = [
        r"\bspace\b",
        r"\bпробел\b",
        r"\bпробіл\b",
        r"\bnpo6e\b",
        r"\b123\b",
        r"\bотправить\b",
        r"\botnpab\b",
        r"\bнадіслати\b",
        r"\breturn\b",
        r"\bdone\b",
        r"\bsend\b",
        r"add comment",
        r"додати коментар",
        r"оставьте комментарий",
        r"replying to",
        r"відповісти користувачу",
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

    def check_for_captcha(self, screen_image: Image.Image, text: Optional[str] = None) -> bool:
        """
        Inspects full screen to detect bot verification / slider challenges.
        """
        raw_text = text if text is not None else self.ocr.extract_text(screen_image).lower()
        for pattern in self.CAPTCHA_PATTERNS:
            if re.search(pattern, raw_text):
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

    def detect_popup(self, screen_image: Image.Image, text: Optional[str] = None) -> Optional[str]:
        """
        Returns the popup category if an interrupting dialogue is present, else None.
        """
        raw_text = text if text is not None else self.ocr.extract_text(screen_image).lower()
        for category, patterns in self.POPUP_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, raw_text):
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

    def is_tiktok_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether TikTok UI is currently active on screen.
        Returns (is_open, list_of_matched_indicators).
        """
        raw_text = text if text is not None else self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.TIKTOK_PATTERNS if re.search(p, raw_text)]
        if not matched:
            if "foryou" in raw_text or "shop" in raw_text:
                matched.append(r"\bfor you\b")
            else:
                is_comm, comm_m = self.is_comment_section_open(screen_image, text=raw_text)
                if is_comm:
                    return True, comm_m
        return len(matched) > 0, matched

    def is_homescreen_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether iOS SpringBoard / Homescreen is currently active.
        Returns (is_homescreen, list_of_matched_indicators).
        """
        raw_text = text if text is not None else self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.HOMESCREEN_PATTERNS if re.search(p, raw_text)]
        return len(matched) > 0, matched

    def is_comment_input_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether the 'Add comment' input section / iOS virtual keyboard is open.
        Returns (is_open, list_of_matched_indicators).
        """
        raw_text = text if text is not None else self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.KEYBOARD_PATTERNS if re.search(p, raw_text)]
        kb_keys = [
            m for m in matched
            if any(k in m for k in ["space", "пробел", "пробіл", "npo6e", "123", "отправить", "otnpab", "надіслати", "return", "done", "send"])
        ]
        if kb_keys:
            return True, matched
        if any(term in raw_text for term in ["add comment", "додати коментар", "оставьте комментарий", "replying to", "cld t.omment"]):
            if any(term in raw_text for term in ["comments", "коментар", "комментар", "reply"]):
                if len(matched) >= 1:
                    return True, matched
        return False, []

    def is_comment_section_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether the TikTok comment drawer/sheet is open.
        Returns (is_open, list_of_matched_indicators).
        """
        raw_text = text if text is not None else self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.COMMENT_PATTERNS if re.search(p, raw_text)]
        return len(matched) > 0, matched

    def is_share_sheet_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether the TikTok Share / Send to drawer is open.
        Returns (is_open, list_of_matched_indicators).
        """
        raw_text = text if text is not None else self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.SHARE_PATTERNS if re.search(p, raw_text)]
        return len(matched) >= 2, matched

    def is_story_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether a TikTok Story is being viewed.
        Returns (is_story, list_of_matched_indicators).
        """
        raw_text = text if text is not None else self.ocr.extract_text(screen_image).lower()
        is_feed = ("home" in raw_text and ("inbox" in raw_text or "profile" in raw_text)) or any(
            t in raw_text for t in ["for you", "foryou", "following", "для вас", "підписки", "подписки"]
        )
        matched = [p for p in self.STORY_PATTERNS if re.search(p, raw_text)]
        return (not is_feed and len(matched) > 0), matched

    def is_profile_page_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether an author/user profile page is open.
        Requires:
        - "following" (or localized equivalent)
        - "followers" (or localized equivalent)
        - "likes" (or localized equivalent)
        Returns (is_profile, list_of_matched_indicators).
        """
        raw_text = text if text is not None else self.ocr.extract_text(screen_image).lower()
        has_following = any(re.search(r"\b" + re.escape(w) + r"\b", raw_text) for w in ["following", "підписки", "подписки"])
        has_followers = any(re.search(r"\b" + re.escape(w) + r"\b", raw_text) for w in ["followers", "підписники", "подписчики", "читачі"])
        has_likes = any(re.search(r"\b" + re.escape(w) + r"\b", raw_text) for w in ["likes", "вподобайки", "лайки"])

        if has_following and has_followers and has_likes:
            has_bottom_bar = "home" in raw_text and ("profile" in raw_text or "профіль" in raw_text or "профиль" in raw_text)
            if has_bottom_bar:
                return True, ["profile_tab", "following_followers_likes"]
            return True, ["author_profile", "following_followers_likes"]
        return False, []

    def is_inbox_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR on the top header region (Y < 0.18) to detect whether the Inbox tab is open.
        Ignores 'inbox' in the bottom navigation bar.
        Returns (is_inbox, list_of_matched_indicators).
        """
        header_text = self.ocr.extract_header_text(screen_image).lower()
        inbox_terms = [
            r"\binbox\b",
            r"\bactivity\b",
            r"\bdirect messages\b",
            r"\bвхідні\b",
            r"\bвходящие\b",
            r"\bповідомлення\b",
            r"\bchats\b",
            r"\bчати\b",
            r"\bчаты\b",
        ]
        matched = [p for p in inbox_terms if re.search(p, header_text)]
        return len(matched) > 0, matched

    def is_search_page_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether the TikTok search / explore page is open.
        Returns (is_search, list_of_matched_indicators).
        """
        raw_text = text if text is not None else self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.SEARCH_PATTERNS if re.search(p, raw_text)]
        return len(matched) > 0, matched

    def detect_screen_state(self, screen_image: Image.Image) -> Tuple[str, List[str]]:
        """
        Identifies the current screen state:
        - 'feed': Clean FYP video feed.
        - 'comment_input': "Add comment" field / iOS virtual keyboard is open.
        - 'comments': Comments sheet drawer is open.
        - 'share': Share sheet / Send to drawer is open.
        - 'story': Story player is open.
        - 'profile': Author profile page or own profile tab is open.
        - 'search': Search / Discover page is open.
        - 'popup': Modal alert or captcha.
        - 'homescreen': iOS SpringBoard / App Library.
        - 'other_tab': On an alternative tab (e.g. Inbox).
        - 'unknown': Ambiguous state.
        """
        # Extract screen text once to evaluate all state detectors efficiently (0.3-0.5s total)
        text = self.ocr.extract_text(screen_image).lower()

        # 1. Homescreen check
        is_home, h_markers = self.is_homescreen_open(screen_image, text=text)
        if is_home:
            return "homescreen", h_markers

        # 2. Captcha / security verification check
        if self.check_for_captcha(screen_image, text=text):
            return "popup", ["captcha_or_verification"]

        # 3. Interrupting modal popup check
        popup = self.detect_popup(screen_image, text=text)
        if popup:
            return "popup", [popup]

        # 4. "Add comment" section / virtual keyboard check (prioritized before comment sheet)
        is_kb, kb_markers = self.is_comment_input_open(screen_image, text=text)
        if is_kb:
            return "comment_input", kb_markers

        # 5. Comments drawer check
        is_comm, c_markers = self.is_comment_section_open(screen_image, text=text)
        if is_comm:
            return "comments", c_markers

        # 6. Share sheet check
        is_share, s_markers = self.is_share_sheet_open(screen_image, text=text)
        if is_share:
            return "share", s_markers

        # 7. Story player check
        is_story, st_markers = self.is_story_open(screen_image, text=text)
        if is_story:
            return "story", st_markers

        # 8. Profile page check (following + followers + likes)
        is_prof, p_markers = self.is_profile_page_open(screen_image, text=text)
        if is_prof:
            return "profile", p_markers

        # 9. Search page check
        is_srch, sr_markers = self.is_search_page_open(screen_image, text=text)
        if is_srch:
            return "search", sr_markers

        # 10. Inbox tab check (header zone only, ignoring bottom navigation bar)
        is_inbox, in_markers = self.is_inbox_open(screen_image, text=text)
        if is_inbox:
            return "other_tab", in_markers

        # 11. Clean video feed check
        is_tt, tt_markers = self.is_tiktok_open(screen_image, text=text)
        if is_tt:
            return "feed", tt_markers

        return "unknown", []

    # Vertical normalized Y-zones for TikTok right-hand sidebar action counters
    # (ordered top-to-bottom: likes -> comments -> saves -> shares)
    METRIC_SLOTS = {
        "likes": (0.45, 0.585, 0.53),        # (min_cy, max_cy, expected_center_cy)
        "comments": (0.585, 0.685, 0.635),
        "saves": (0.685, 0.785, 0.735),
        "shares": (0.785, 0.94, 0.85),
    }

    def extract_sidebar_metrics(self, screen_image: Image.Image) -> Dict[str, str]:
        """
        Extracts all numeric counts available on the right-hand action column:
        likes, comments, saves/bookmarks, and shares.
        Maps detected text to specific metric slots based on vertical coordinate bands.
        If few or no metrics are recognized (e.g. bright/white background),
        applies contrast enhancement and inversion on the sidebar crop.
        Returns a dict mapping slot name to cleaned count string, e.g.:
        {'likes': '12.4K', 'comments': '543', 'saves': '2,100', 'shares': '150'}
        """
        obs = self.ocr.extract_observations(screen_image)
        metrics: Dict[str, Tuple[float, str]] = {}  # slot: (distance_to_center, value)

        def _process_observations(observations, is_cropped: bool = False):
            for item in observations:
                text = item[0]
                cx, cy, w, h = item[1], item[2], item[3], item[4]
                if is_cropped:
                    # Crop covers x: [0.75, 1.0], y: [0.44, 0.94]
                    cx = 0.75 + cx * 0.25
                    cy = 0.44 + cy * 0.50

                if cx < 0.76 or w > 0.24:
                    continue

                cleaned = text.replace(" ", "").replace("·", "").replace("•", "").upper()
                if not re.match(r"^\d[0-9.,]*[KMB]?$", cleaned):
                    continue

                for slot, (min_cy, max_cy, center_cy) in self.METRIC_SLOTS.items():
                    if min_cy <= cy < max_cy:
                        dist = abs(cy - center_cy)
                        if slot not in metrics or dist < metrics[slot][0]:
                            metrics[slot] = (dist, cleaned)
                        break

        if obs:
            _process_observations(obs, is_cropped=False)

        # If 0 or only 1 metric detected, attempt enhanced OCR on right sidebar crop
        if len(metrics) < 2 and screen_image:
            try:
                w, h = screen_image.size
                box = (int(w * 0.75), int(h * 0.44), w, int(h * 0.94))
                crop = screen_image.crop(box)
                gray = crop.convert("L")
                enhanced = ImageOps.autocontrast(gray, cutoff=2)
                stat = ImageStat.Stat(enhanced)
                if stat.mean[0] > 150:
                    enhanced = ImageOps.invert(enhanced)
                crop_obs = self.ocr.extract_observations(enhanced)
                if crop_obs:
                    _process_observations(crop_obs, is_cropped=True)
            except Exception:
                pass

        return {k: v[1] for k, v in metrics.items()}

    def extract_likes_amount(self, screen_image: Image.Image) -> Optional[str]:
        """
        Extracts the likes count from the dedicated zone on the right action sidebar.
        Returns the parsed like count string (e.g. '1,454', '43.2K', '1.2M') or None if not present.
        """
        metrics = self.extract_sidebar_metrics(screen_image)
        return metrics.get("likes")

    def extract_likes_and_signature(self, screen_image: Image.Image) -> Tuple[Optional[str], str]:
        """
        Extracts the likes count from the dedicated zone and content signature (body text).
        Returns (likes_count_str, content_signature_str).
        """
        like_count = self.extract_likes_amount(screen_image)
        obs = self.ocr.extract_observations(screen_image)
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
        before_metrics: Optional[Dict[str, str]] = None,
        after_metrics: Optional[Dict[str, str]] = None,
        before_likes: Optional[str] = None,
        before_sig: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Verifies whether the video on screen changed after a swipe gesture
        by checking all available right-sidebar counters (likes, comments, saves, shares).

        Verification logic:
        1. If both before and after have 0 metrics detected: returns (False, "NO_METRICS:...").
        2. If either before or after has 0 metrics: returns (False, "NO_METRICS:...").
        3. If common metrics exist:
           - If ANY common metric changed: returns (True, "Metrics changed:...").
           - If ALL common metrics match identically: returns (False, "Metrics unchanged:...").
        4. If no common metrics exist between before and after (e.g. due to white background
           covering likes/comments on one screen and saves/shares on the other):
           treats as changed since different metrics became visible.
        """
        if before_metrics is None:
            if before_likes is not None:
                before_metrics = {"likes": before_likes}
            else:
                before_metrics = self.extract_sidebar_metrics(before_image)

        if after_metrics is None:
            after_metrics = self.extract_sidebar_metrics(after_image)

        # Check if zero metrics were detected
        if not before_metrics and not after_metrics:
            return False, "NO_METRICS: No sidebar metrics detected before or after swipe"

        if not before_metrics:
            return False, f"NO_METRICS: No sidebar metrics detected before swipe (after={after_metrics})"

        if not after_metrics:
            return False, f"NO_METRICS: No sidebar metrics detected after swipe (before={before_metrics})"

        # Check overlapping metrics
        common_keys = set(before_metrics.keys()) & set(after_metrics.keys())
        if common_keys:
            changed_keys = [k for k in common_keys if before_metrics[k] != after_metrics[k]]
            if changed_keys:
                changes = ", ".join(f"{k} {before_metrics[k]} -> {after_metrics[k]}" for k in sorted(changed_keys))
                return True, f"Metrics changed: {changes}"
            else:
                same = ", ".join(f"{k}={before_metrics[k]}" for k in sorted(common_keys))
                return False, f"Metrics unchanged ({same}) - still on the same video"
        else:
            # Partial overlap with no common keys: different metrics visible
            return True, f"Different metrics visible (before: {before_metrics}, after: {after_metrics}) - video changed"


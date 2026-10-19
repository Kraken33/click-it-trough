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
        r"для вас",
        r"підписки",
        r"подписки",
        r"\badd comment\b",
        r"\bshare to\b",
        r"\bhome\b",
        r"\binbox\b",
        r"\bprofile\b",
        r"\bprof ile\b",
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
        r"\bwebdriveragent\b",
        r"\btestflight\b",
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
        r"\bsend(?!\s+(to|gift))\b",
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
        r"\btrending\b",
        r"search accounts",
        r"\bask ai\b",
        r"\bclear all\b",
        r"пошук",
        r"поиск",
    ]

    # Indicators that QR scan screen is open
    SCAN_PATTERNS = [
        r"scan your friend's qr code",
        r"my qr code",
        r"tap to turn light on",
    ]

    # Indicators that story viewer is open
    STORY_PATTERNS = [
        r"\bmessage\.\.\.\b",
        r"\d+h ago\b",
        r"\d+d ago\b",
        r"\d+m ago\b",
    ]

    # Indicators that TikTok "Likes" / "Liked by" drawer is open
    LIKES_LIST_PATTERNS = [
        r"\bliked by\b",
        r"\bfollow back\b",
        r"\bwho liked\b",
        r"\bpost activity\b",
    ]

    # Indicators that TikTok Shop or Product drawer/showcase is open
    SHOP_PATTERNS = [
        r"\btiktok shop\b",
        r"\bproduct details\b",
        r"\badd to cart\b",
        r"\bbuy now\b",
        r"\bview product\b",
        r"\bfree shipping\b",
        r"\bcoupons?\b",
        r"\bitems? sold\b",
        r"\b\d+k?\s+sold\b",
        r"\bshipped from\b",
        r"\bmach dein shopping\b",
        r"\borders\b.*\bfavorites\b",
    ]

    # Indicators that Sound / Audio page is open
    SOUND_PATTERNS = [
        r"\buse\s+(this\s+)?sound\b",
        r"\buse sound\b",
        r"\boriginal sound\b",
        r"\blike this sound\b",
        r"\badd to favorites\b",
        r"\bfavorites to find\b",
        r"\badd to music app\b",
        r"\badd to (apple\s+)?music\b",
        r"\bpost to story\b",
    ]

    # Indicators that Camera / Creation screen ('+' tab) is open
    CAMERA_PATTERNS = [
        r"\bupload\b",
        r"\beffects\b",
        r"\btemplates\b",
        r"\b15s\b",
        r"\b60s\b",
        r"\b10m\b",
        r"\bflip\b",
        r"\bfilters\b",
    ]

    # Indicators that an active LIVE stream room is being watched
    LIVE_ROOM_PATTERNS = [
        r"\btap to join\b",
        r"\bmulti-guest\b",
        r"\bsend gift\b",
        r"\brose\b",
        r"\bshare(d)?\s+(the\s+)?live\b",
        r"\bjoined(\s+the\s+live)?\b",
        r"\bsend a rose\b",
        r"\bpopular live\b",
        r"\bdaily ranking\b",
        r"\bhost\b",
        r"\bexplore more lives\b",
        r"\bwatch live\b",
    ]

    def __init__(self, ocr: Optional[VisionOCR] = None):
        self.ocr = ocr or VisionOCR()

    def check_for_captcha(self, screen_image: Image.Image, text: Optional[str] = None) -> bool:
        """
        Inspects full screen to detect bot verification / slider challenges.
        """
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
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
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
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
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
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
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.HOMESCREEN_PATTERNS if re.search(p, raw_text)]
        return len(matched) > 0, matched

    def is_comment_input_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether the 'Add comment' input section / iOS virtual keyboard is open.
        Returns (is_open, list_of_matched_indicators).
        """
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.KEYBOARD_PATTERNS if re.search(p, raw_text)]
        # Primary anchor keys that uniquely identify the iOS virtual keyboard
        primary_kb_keys = [
            m for m in matched
            if any(k in m for k in ["space", "пробел", "пробіл", "123", "return", "replying to", "відповісти"])
        ]
        if primary_kb_keys:
            return True, matched
        if len(matched) >= 2:
            return True, matched
        return False, []

    def is_comment_section_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether the TikTok comment drawer/sheet is open.
        Returns (is_open, list_of_matched_indicators).
        """
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.COMMENT_PATTERNS if re.search(p, raw_text)]
        return len(matched) > 0, matched

    def is_share_sheet_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether the TikTok Share / Send to drawer is open.
        Returns (is_open, list_of_matched_indicators).
        """
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
        has_primary = any(
            re.search(p, raw_text)
            for p in [r"\bshare to\b", r"\bsend to\b", r"\brepost\b", r"\bcopy link\b", r"\badd to story\b", r"\bduet\b", r"\bstitch\b", r"поділитися", r"поделиться", r"скопировать ссылку"]
        )
        matched = [p for p in self.SHARE_PATTERNS if re.search(p, raw_text)]
        return (has_primary and len(matched) >= 2), matched

    def is_tako_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether the TikTok Tako AI assistant drawer/modal is open.
        """
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
        if any(w in raw_text for w in ["tiktok tako", "ask anything"]):
            return True, ["tako_ai_assistant"]
        return False, []

    def is_story_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether a TikTok Story is being viewed.
        Returns (is_story, list_of_matched_indicators).
        """
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
        is_feed = ("home" in raw_text and ("inbox" in raw_text or "profile" in raw_text)) or any(
            t in raw_text for t in ["for you", "foryou", "following", "для вас", "підписки", "подписки"]
        )
        matched = [p for p in self.STORY_PATTERNS if re.search(p, raw_text)]
        return (not is_feed and len(matched) > 0), matched

    def is_profile_page_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether an author/user profile page or own profile tab is open.
        """
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
        has_following = any(re.search(r"\b" + re.escape(w) + r"\b", raw_text) for w in ["following", "підписки", "подписки"])
        has_followers = any(re.search(r"\b" + re.escape(w) + r"\b", raw_text) for w in ["followers", "підписники", "подписчики", "читачі"])
        has_likes = any(re.search(r"\b" + re.escape(w) + r"\b", raw_text) for w in ["likes", "вподобайки", "лайки"])
        has_bottom_bar = any(h in raw_text for h in ["home", "головна", "главная"]) and any(
            p in raw_text for p in ["profile", "prof ile", "профіль", "профиль", "inbox", "discover"]
        )

        # Own profile tab indicators (e.g. Edit profile button + bottom navigation bar)
        has_edit_profile = any(w in raw_text for w in ["edit profile", "редагувати профіль", "изменить профиль", "add bio", "share your daily routine"])
        if (has_edit_profile or (has_following and has_followers)) and has_bottom_bar:
            return True, ["profile_tab", "edit_or_stats"]

        if has_following and has_followers and has_likes:
            if has_bottom_bar:
                return True, ["profile_tab", "following_followers_likes"]
            return True, ["author_profile", "following_followers_likes"]

        if (has_following and has_followers) or (has_following and has_bottom_bar and (has_likes or "bio" in raw_text or "add friends" in raw_text)):
            if has_bottom_bar:
                return True, ["profile_tab", "following_followers"]
            return True, ["author_profile", "following_followers"]

        # Author profile without bottom bar:
        # Detectable by:
        # 1. Follow button + Message / bio / suggested / link.bio
        # 2. Direct Message button without bottom bar (only author profiles have "Message" without bottom bar)
        # 3. Stats row (\d+ \d+ \d+) with "just watched" / "suggested accounts" / "link.bio"
        has_follow_btn = any(re.search(r"\b" + re.escape(w) + r"\b", raw_text) for w in ["follow", "following", "підписатися", "подписаться"])
        has_msg_btn = any(re.search(r"\b" + re.escape(w) + r"\b", raw_text) for w in ["message", "повідомлення", "сообщение"])
        has_stats_row = bool(re.search(r"\b\d+[,.\d]*\s+\d+[,.\d]*\s+\d+[,.\d]*\b", raw_text))
        has_profile_extra = any(w in raw_text for w in ["just watched", "suggested accounts", "link.bio"])

        if not has_bottom_bar:
            if (has_follow_btn and has_msg_btn) or (has_msg_btn and (has_stats_row or has_profile_extra or "video" in raw_text)) or (has_follow_btn and (has_stats_row or has_profile_extra)):
                return True, ["author_profile", "follow_or_message"]
            if has_msg_btn and len(raw_text) > 10:
                return True, ["author_profile", "message_btn"]

        return False, []

    def is_already_following_author(self, screen_image: Image.Image, text: Optional[str] = None) -> bool:
        """
        Detects if the currently viewed author profile is already followed.
        Checks for indicators like 'following', 'friends', 'requested', or a standalone 'message' button.
        """
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()

        # Check if 'follow' button (unfollowed state) is present
        has_unfollowed_btn = any(re.search(r"\b" + re.escape(w) + r"\b", raw_text) for w in ["follow", "підписатися", "подписаться"])

        # Explicit followed / requested terms
        already_following_terms = [
            r"\bfollowing\b",
            r"\bfriends\b",
            r"\brequested\b",
            r"\bпідписки\b",
            r"\bчитаєте\b",
            r"\bви стежите\b",
            r"\bдрузі\b",
            r"\bдрузья\b",
            r"\bзапит надіслано\b",
            r"\bзапрос отправлен\b",
        ]
        has_following_marker = any(re.search(p, raw_text) for p in already_following_terms)

        if has_following_marker and not has_unfollowed_btn:
            return True

        # If Message button is present without an unfollowed 'Follow' button
        has_message_btn = any(re.search(r"\b" + re.escape(w) + r"\b", raw_text) for w in ["message", "повідомлення", "сообщение"])
        if has_message_btn and not has_unfollowed_btn:
            return True

        return False

    def is_private_account(self, screen_image: Image.Image, text: Optional[str] = None) -> bool:
        """Detects if the currently viewed account is private."""
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
        private_terms = [
            "this account is private",
            "private account",
            "це приватний акаунт",
            "это приватный аккаунт",
        ]
        return any(term in raw_text for term in private_terms)

    def find_follow_button_coords(self, screen_image: Image.Image) -> Optional[Tuple[float, float]]:
        """
        Locates the Follow button on the author's profile page using Vision OCR observations.
        Returns (center_x_px, center_y_px) or None if not found.
        """
        observations = self.ocr.extract_observations(screen_image)
        w, h = screen_image.size

        for text, cx, cy, bw, bh in observations:
            clean = text.strip().lower()
            if clean in ["follow", "підписатися", "подписаться"]:
                # Profile follow button is in upper-mid section (typically Y between 0.18 and 0.48)
                if 0.18 <= cy <= 0.48:
                    return cx * w, cy * h

        return None


    def is_inbox_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR on the top header region (Y < 0.18) to detect whether the Inbox tab is open.
        Ignores 'inbox' in the bottom navigation bar.
        Returns (is_inbox, list_of_matched_indicators).
        """
        header_text = self.ocr.extract_header_text(screen_image).lower()
        # If top feed tabs are visible, this is the FYP feed, NOT the inbox tab!
        if any(t in header_text for t in ["for you", "foryou", "following", "shop", "для вас", "підписки"]):
            return False, []

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
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
        has_bottom_bar = any(h in raw_text for h in ["home", "головна", "главная"]) and any(
            p in raw_text for p in ["profile", "prof ile", "inbox", "discover"]
        )
        # Dedicated search page patterns that indicate search even if bottom bar appears
        explicit_search = [p for p in [r"recent searches", r"you may like", r"trending searches", r"search accounts", r"clear all"] if re.search(p, raw_text)]
        if explicit_search:
            return True, explicit_search

        # Check for Discover overlay/drawer (multi-guest / live matching / discover header)
        header_text = self.ocr.extract_header_text(screen_image).lower()
        if "discover" in header_text and not has_bottom_bar:
            return True, ["discover_sheet"]

        if not has_bottom_bar:
            matched = [p for p in self.SEARCH_PATTERNS if re.search(p, raw_text)]
            if matched:
                return True, matched
            has_search_term = any(w in raw_text for w in ["search", "пошук", "поиск"])
            if has_search_term:
                if any(w in raw_text for w in ["cancel", "see more", "ask ai", "refresh"]) or any(
                    k in raw_text for k in ["123", "return", "space", "пробел"]
                ):
                    return True, ["search_page_active"]
        return False, []

    def is_scan_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether the QR code scanner screen is open.
        Returns (is_scan, list_of_matched_indicators).
        """
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.SCAN_PATTERNS if re.search(p, raw_text)]
        return len(matched) >= 1, matched

    def is_likes_list_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether the TikTok "Likes" / "Liked by" drawer/sheet is open.
        Returns (is_likes_list, list_of_matched_indicators).
        """
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.LIKES_LIST_PATTERNS if re.search(p, raw_text)]
        if matched:
            return True, matched

        # Check for "likes" with user interaction buttons (Follow / Follow back / Friends)
        # while excluding profile pages and comment drawers
        has_likes_kw = bool(re.search(r"\blikes\b", raw_text))
        has_follow_btn = any(w in raw_text for w in ["follow", "follow back", "friends"])
        has_comm = any(w in raw_text for w in ["add comment", "reply", "replies", "comments"])
        is_prof, _ = self.is_profile_page_open(screen_image, text=raw_text)
        if has_likes_kw and has_follow_btn and not has_comm and not is_prof:
            return True, ["likes_drawer_with_users"]
        return False, []

    def is_shop_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether a TikTok Shop drawer or product showcase is open.
        Returns (is_shop, list_of_matched_indicators).
        """
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.SHOP_PATTERNS if re.search(p, raw_text)]
        return len(matched) >= 1, matched

    def is_sound_page_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether the audio / sound detail page is open.
        Returns (is_sound, list_of_matched_indicators).
        """
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
        matched = [p for p in self.SOUND_PATTERNS if re.search(p, raw_text)]
        if not matched and "apple music" in raw_text and ("save" in raw_text or "post to story" in raw_text):
            matched = ["apple_music_sound_page"]
        return len(matched) >= 1, matched

    def is_camera_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether the camera / creation screen ('+' icon) is open.
        Returns (is_camera, list_of_matched_indicators).
        """
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
        has_bottom_bar = any(h in raw_text for h in ["home", "головна", "главная"]) and any(
            p in raw_text for p in ["profile", "prof ile", "inbox", "discover"]
        )
        if has_bottom_bar:
            return False, []

        matched = [p for p in self.CAMERA_PATTERNS if re.search(p, raw_text)]
        if len(matched) >= 2 or ("upload" in raw_text and ("effects" in raw_text or "15s" in raw_text or "photo" in raw_text)):
            return True, matched
        return False, []

    def is_live_room_open(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Uses OCR to detect whether the user is inside an active LIVE broadcast stream room.
        Returns (is_live_room, list_of_matched_indicators).
        """
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
        has_bottom_bar = any(h in raw_text for h in ["home", "головна", "главная"]) and any(
            p in raw_text for p in ["profile", "prof ile", "inbox", "discover"]
        )
        matched = [p for p in self.LIVE_ROOM_PATTERNS if re.search(p, raw_text)]
        if len(matched) >= 2 and not has_bottom_bar:
            return True, matched
        if any(g in raw_text for g in ["send gift", "rose", "tap to join", "multi-guest", "share live", "shared the live", "host", "joined", "popular live", "daily ranking", "sag hallo", "herzgeste", "commission paid"]):
            if not has_bottom_bar:
                return True, matched or ["live_room"]
        return False, []

    def is_wrong_feed_tab(self, screen_image: Image.Image, text: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Checks if Following, Friends, Shop, or STEM tab is active without clean FYP For You.
        Returns (is_wrong_tab, list_of_matched_indicators).
        """
        raw_text = text.lower() if text is not None else self.ocr.extract_text(screen_image).lower()
        header_text = self.ocr.extract_header_text(screen_image).lower()

        # Check for empty following feed placeholder
        if "trending creators" in raw_text or "follow an account to see their latest videos" in raw_text:
            return True, ["following_empty_feed"]

        has_foryou = any(t in header_text or t in raw_text for t in ["for you", "foryou", "для вас"])
        has_following = any(t in header_text for t in ["following", "підписки", "подписки"])
        has_friends = any(t in header_text for t in ["friends", "друзі", "друзья"])
        has_shop = "shop" in header_text
        has_stem = "stem" in header_text

        if (has_following or has_friends or has_shop or has_stem) and not has_foryou:
            markers = [t for t in ["following", "friends", "shop", "stem"] if t in header_text]
            return True, markers

        # Or if Shop page indicators are active on the feed
        if any(w in raw_text for w in ["orders", "mach dein shopping", "super brand day", "shipped from"]):
            return True, ["shop_tab_active"]

        return False, []

    def find_button_coordinate(
        self,
        screen_image: Image.Image,
        target_pattern: str,
        region: Optional[Tuple[float, float, float, float]] = None,
        normalized: bool = True,
    ) -> Optional[Tuple[float, float]]:
        """
        Finds the center coordinates (x, y) of text matching target_pattern.
        If normalized=True (default), returns (cx, cy) as floats in [0.0, 1.0].
        If normalized=False, returns pixel coordinates (int(cx * w), int(cy * h)).
        """
        obs = self.ocr.extract_observations(screen_image)
        w, h = screen_image.size
        for text, cx, cy, bw, bh in obs:
            if region:
                rx0, ry0, rx1, ry1 = region
                if not (rx0 <= cx <= rx1 and ry0 <= cy <= ry1):
                    continue
            m = re.search(target_pattern, text.lower())
            if m:
                # If matched text is a substring of a wider multi-word observation (e.g. 'wing Shop For\'You'),
                # calculate the relative horizontal center of the matched substring to avoid tapping adjacent words.
                if len(text) > 0 and bw > 0:
                    sub_rel_x = (m.start() + m.end()) / (2.0 * len(text))
                    matched_cx = (cx - bw / 2.0) + bw * sub_rel_x
                else:
                    matched_cx = cx

                if normalized:
                    return (float(matched_cx), float(cy))
                return (int(matched_cx * w), int(cy * h))
        return None

    def detect_screen_state(self, screen_image: Image.Image) -> Tuple[str, List[str]]:
        """
        Identifies the current screen state:
        - 'feed': Clean FYP video feed.
        - 'search': Search / Discover page is open.
        - 'scan': QR code scanner is open.
        - 'comment_input': "Add comment" field / iOS virtual keyboard is open.
        - 'likes_list': "Liked by" / Likes modal drawer is open.
        - 'comments': Comments sheet drawer is open.
        - 'share': Share sheet / Send to drawer is open.
        - 'shop': TikTok Shop or product showcase drawer is open.
        - 'camera': Camera / Creation mode ('+' tab) is open.
        - 'sound': Sound / Audio detail page is open.
        - 'live': Active LIVE broadcast stream room is open.
        - 'story': Story player is open.
        - 'profile': Author profile page or own profile tab is open.
        - 'feed_wrong_tab': On Following/Friends/Shop tab instead of For You.
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

        # 4. Search page check (CHECK BEFORE generic comment_input so search with keyboard is detected as search)
        is_srch, sr_markers = self.is_search_page_open(screen_image, text=text)
        if is_srch:
            return "search", sr_markers

        # 5. Scan / QR code screen check
        is_scn, scn_markers = self.is_scan_open(screen_image, text=text)
        if is_scn:
            return "scan", scn_markers

        # 6. "Add comment" section / virtual keyboard check (prioritized before comment sheet)
        is_kb, kb_markers = self.is_comment_input_open(screen_image, text=text)
        if is_kb:
            return "comment_input", kb_markers

        # 7. Likes list / "Liked by" drawer check
        is_likes, lk_markers = self.is_likes_list_open(screen_image, text=text)
        if is_likes:
            return "likes_list", lk_markers

        # 8. Comments drawer check
        is_comm, c_markers = self.is_comment_section_open(screen_image, text=text)
        if is_comm:
            return "comments", c_markers

        # 9. Share sheet check
        is_share, s_markers = self.is_share_sheet_open(screen_image, text=text)
        if is_share:
            return "share", s_markers

        # 9b. TikTok Tako AI assistant drawer check
        is_tako, tako_markers = self.is_tako_open(screen_image, text=text)
        if is_tako:
            return "tako", tako_markers

        # 10. TikTok Shop / Product sheet check
        is_shp, shp_markers = self.is_shop_open(screen_image, text=text)
        if is_shp:
            return "shop", shp_markers

        # 11. Camera / creation screen check
        is_cam, cam_markers = self.is_camera_open(screen_image, text=text)
        if is_cam:
            return "camera", cam_markers

        # 12. Sound / Audio page check
        is_snd, snd_markers = self.is_sound_page_open(screen_image, text=text)
        if is_snd:
            return "sound", snd_markers

        # 13. LIVE room check
        is_lv, lv_markers = self.is_live_room_open(screen_image, text=text)
        if is_lv:
            return "live", lv_markers

        # 14. Story player check
        is_story, st_markers = self.is_story_open(screen_image, text=text)
        if is_story:
            return "story", st_markers

        # 15. Profile page check (author profile or own profile tab)
        is_prof, p_markers = self.is_profile_page_open(screen_image, text=text)
        if is_prof:
            return "profile", p_markers

        # 16. Wrong feed tab check (e.g. on Following / Friends / STEM / Shop header tab)
        is_wrong_tab, wt_markers = self.is_wrong_feed_tab(screen_image)
        if is_wrong_tab:
            return "feed_wrong_tab", wt_markers

        # 17. Inbox tab check (header zone only, ignoring bottom navigation bar)
        is_inbox, in_markers = self.is_inbox_open(screen_image, text=text)
        if is_inbox:
            return "other_tab", in_markers

        # 17. Clean video feed check
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


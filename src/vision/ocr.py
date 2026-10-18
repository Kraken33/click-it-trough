import io
import logging
from typing import List, Optional, Tuple
from PIL import Image

logger = logging.getLogger(__name__)


class VisionOCR:
    """
    Hardware-accelerated text recognition powered by Apple's native Vision framework.
    Operates locally on macOS with high accuracy and low latency.
    """

    def __init__(self, recognition_level: str = "accurate"):
        self.recognition_level = recognition_level
        self._has_vision = False
        try:
            import Vision
            import Quartz
            self._vision = Vision
            self._quartz = Quartz
            self._has_vision = True
        except ImportError:
            logger.warning("Apple Vision framework not available. OCR will run in fallback mode.")

    def extract_text(self, image: Image.Image, crop_box: Optional[Tuple[int, int, int, int]] = None) -> str:
        """
        Extracts all recognized text from image or specified crop_box (left, top, right, bottom).
        """
        if crop_box:
            target_img = image.crop(crop_box)
        else:
            target_img = image

        if not self._has_vision:
            return ""

        try:
            # Convert PIL image to PNG buffer
            buf = io.BytesIO()
            target_img.save(buf, format="PNG")
            img_data = buf.getvalue()

            # Create CGImageSource and CGImage via Quartz
            data_provider = self._quartz.CGDataProviderCreateWithData(None, img_data, len(img_data), None)
            cg_image = self._quartz.CGImageCreateWithPNGDataProvider(data_provider, None, False, self._quartz.kCGRenderingIntentDefault)

            if not cg_image:
                return ""

            # Prepare Vision Request
            request = self._vision.VNRecognizeTextRequest.alloc().init()
            if self.recognition_level == "fast":
                request.setRecognitionLevel_(self._vision.VNRequestTextRecognitionLevelFast)
            else:
                request.setRecognitionLevel_(self._vision.VNRequestTextRecognitionLevelAccurate)

            request.setUsesLanguageCorrection_(True)

            # Execute Request Handler
            handler = self._vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, None)
            success, error = handler.performRequests_error_([request], None)

            if not success:
                logger.debug(f"Vision OCR request failed: {error}")
                return ""

            results = request.results()
            if not results:
                return ""

            lines: List[str] = []
            for observation in results:
                top_candidate = observation.topCandidates_(1)
                if top_candidate and len(top_candidate) > 0:
                    lines.append(top_candidate[0].string())

            return " ".join(lines)
        except Exception as e:
            logger.debug(f"Error during Vision OCR extraction: {e}")
            return ""

    def extract_observations(self, image: Image.Image) -> List[Tuple[str, float, float, float, float]]:
        """
        Extracts recognized text elements with normalized bounding boxes:
        Returns list of (text, center_x, center_y, width, height) with origin (0, 0) at top-left.
        """
        if not self._has_vision:
            return []

        try:
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            img_data = buf.getvalue()

            data_provider = self._quartz.CGDataProviderCreateWithData(None, img_data, len(img_data), None)
            cg_image = self._quartz.CGImageCreateWithPNGDataProvider(
                data_provider, None, False, self._quartz.kCGRenderingIntentDefault
            )
            if not cg_image:
                return []

            request = self._vision.VNRecognizeTextRequest.alloc().init()
            request.setRecognitionLevel_(self._vision.VNRequestTextRecognitionLevelAccurate)
            request.setUsesLanguageCorrection_(True)

            handler = self._vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, None)
            success, error = handler.performRequests_error_([request], None)
            if not success or not request.results():
                return []

            observations: List[Tuple[str, float, float, float, float]] = []
            for obs in request.results():
                top = obs.topCandidates_(1)
                if top and len(top) > 0:
                    text = top[0].string().strip()
                    bb = obs.boundingBox()
                    top_y = 1.0 - (bb.origin.y + bb.size.height)
                    cx = float(bb.origin.x + bb.size.width / 2.0)
                    cy = float(top_y + bb.size.height / 2.0)
                    observations.append((text, cx, cy, float(bb.size.width), float(bb.size.height)))

            return observations
        except Exception as e:
            logger.debug(f"Error during Vision OCR extract_observations: {e}")
            return []

    def extract_caption_and_tags(self, image: Image.Image) -> str:
        """
        Extracts the lower region of the TikTok screen where username,
        captions, photo titles, and hashtags are displayed.
        """
        w, h = image.size
        # TikTok caption box: cover left margin to avoid clipped letters, and 55% to 94% height
        box = (0, int(h * 0.55), int(w * 0.90), int(h * 0.94))
        return self.extract_text(image, crop_box=box)

    def extract_full_content(self, image: Image.Image) -> Tuple[str, str]:
        """
        Extracts both caption area text and overall on-screen text (including video stickers,
        titles, subtitles, and search pills).
        Returns (caption_text, full_screen_text).
        """
        caption_text = self.extract_caption_and_tags(image)
        full_text = self.extract_text(image)
        return caption_text, full_text

    def extract_header_text(self, image: Image.Image) -> str:
        """
        Extracts the top header region of the TikTok screen (Tabs: Following, Friends, For You).
        """
        w, h = image.size
        box = (0, 0, w, int(h * 0.16))
        return self.extract_text(image, crop_box=box)

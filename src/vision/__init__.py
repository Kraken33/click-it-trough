"""
Screen Vision and Detection Module.
Provides native Apple Vision OCR, Ad detection, LIVE detection, and Captcha recognition.
"""
from .ocr import VisionOCR
from .detector import ScreenDetector

__all__ = ["VisionOCR", "ScreenDetector"]

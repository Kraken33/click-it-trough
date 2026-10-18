import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image

from .wda_client import WDAClient, WDAClientError

logger = logging.getLogger(__name__)


class DeviceManager:
    """
    Manages physical iPhone connection state, USB detection, and WDA health.
    """

    def __init__(self, wda_url: str = "http://localhost:8100"):
        self.wda_url = wda_url
        self.client = WDAClient(base_url=wda_url)
        self._device_info: Dict[str, Any] = {}
        self._last_screenshot: Optional[Image.Image] = None
        self._last_screenshot_ts: float = 0.0

    def list_usb_devices(self) -> List[Dict[str, Any]]:
        """Scans for connected iOS devices via pymobiledevice3."""
        devices = []
        try:
            import inspect
            from pymobiledevice3.usbmux import list_devices
            
            res = list_devices()
            if inspect.iscoroutine(res):
                import asyncio
                try:
                    mux_devices = asyncio.run(res)
                except RuntimeError:
                    # If already in an event loop
                    loop = asyncio.get_event_loop()
                    mux_devices = loop.run_until_complete(res)
            else:
                mux_devices = res

            for dev in mux_devices:
                devices.append({
                    "serial": dev.serial,
                    "connection_type": getattr(dev, "connection_type", "usb"),
                    "udid": dev.serial,
                })
        except Exception as e:
            logger.debug(f"USB discovery via pymobiledevice3 failed: {e}")
        return devices

    def check_connection(self) -> Dict[str, Any]:
        """
        Tests connection to WDA and fetches device information.
        Returns connection status dictionary.
        """
        usb_devices = self.list_usb_devices()
        is_wda_alive = self.client.is_alive()

        status_info: Dict[str, Any] = {
            "connected": is_wda_alive,
            "wda_alive": is_wda_alive,
            "usb_devices_count": len(usb_devices),
            "usb_devices": usb_devices,
            "wda_url": self.wda_url,
            "details": {},
            "screen_size": None,
        }

        if is_wda_alive:
            try:
                status = self.client.get_status()
                status_info["details"] = status
                width, height = self.client.get_window_size()
                status_info["screen_size"] = {"width": width, "height": height}
                self._device_info = status_info
            except Exception as e:
                logger.warning(f"Error fetching WDA status details: {e}")

        return status_info

    def get_screen(self, max_width: int = 400) -> Optional[Image.Image]:
        """
        Captures latest screen frame, with optional thumbnail scaling for the web dashboard.
        Caches frames briefly to prevent WDA saturation.
        """
        now = time.time()
        # Cap capture rate to max 8 fps to avoid overloading USB bandwidth
        if self._last_screenshot and (now - self._last_screenshot_ts) < 0.12:
            return self._last_screenshot

        try:
            img = self.client.screenshot()
            self._last_screenshot = img
            self._last_screenshot_ts = now
            return img
        except Exception as e:
            logger.debug(f"Screenshot capture failed: {e}")
            return self._last_screenshot

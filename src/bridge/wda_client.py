import base64
import io
import time
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image
import requests


class WDAClientError(Exception):
    """Exception raised for WebDriverAgent communication errors."""
    pass


class WDAClient:
    """
    Lightweight, direct HTTP client communicating with Apple's WebDriverAgent (WDA).
    Connects to http://localhost:8100 over USB port forwarding.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8100", timeout: float = 10.0):
        # Force 127.0.0.1 to avoid IPv6 ::1 resolution failures on macOS
        cleaned = base_url.rstrip("/")
        if "localhost" in cleaned:
            cleaned = cleaned.replace("localhost", "127.0.0.1")
        self.base_url = cleaned
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self._window_size: Optional[Tuple[int, int]] = None
        
        # Persistent HTTP connection pool to avoid opening/closing sockets constantly through usbmux
        self.http = requests.Session()
        from urllib3.util import Retry
        from requests.adapters import HTTPAdapter
        retries = Retry(total=3, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
        self.http.mount("http://", HTTPAdapter(max_retries=retries, pool_connections=5, pool_maxsize=10))

    def _url(self, endpoint: str) -> str:
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def is_alive(self) -> bool:
        """Checks if WDA server is responding on the given endpoint."""
        try:
            resp = self.http.get(self._url("/status"), timeout=2.5)
            return resp.status_code == 200
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        """Returns WDA server status, device UDID, iOS version, and capabilities."""
        resp = self.http.get(self._url("/status"), timeout=self.timeout)
        if resp.status_code != 200:
            raise WDAClientError(f"Failed to fetch status: {resp.status_code} {resp.text}")
        data = resp.json()
        return data.get("value", data)

    def ensure_session(self, force_new: bool = False) -> str:
        """Retrieves existing active session or creates a new one."""
        if not force_new and self.session_id:
            try:
                resp = self.http.get(self._url(f"/session/{self.session_id}"), timeout=3.0)
                if resp.status_code == 200:
                    val = resp.json().get("value", {})
                    if not isinstance(val, dict) or "error" not in val:
                        return self.session_id
            except Exception:
                pass

        # Try active session from status ONLY if it actually validates
        if not force_new:
            try:
                status = self.get_status()
                active_id = status.get("sessionId")
                if active_id:
                    resp = self.http.get(self._url(f"/session/{active_id}"), timeout=3.0)
                    if resp.status_code == 200:
                        val = resp.json().get("value", {})
                        if not isinstance(val, dict) or "error" not in val:
                            self.session_id = active_id
                            return self.session_id
            except Exception:
                pass

        # Create fresh session
        payload = {
            "capabilities": {
                "alwaysMatch": {
                    "shouldWaitForQuiescence": False,
                    "useNewWDA": False,
                }
            }
        }
        resp = self.http.post(self._url("/session"), json=payload, timeout=self.timeout)
        if resp.status_code not in (200, 201):
            raise WDAClientError(f"Failed to create WDA session: {resp.status_code} {resp.text}")
        data = resp.json()
        self.session_id = data.get("sessionId") or data.get("value", {}).get("sessionId")

        # Disable XCTest quiescence waiting to prevent UI freezing in video apps
        self._apply_session_settings()
        return self.session_id

    def _apply_session_settings(self):
        """Disables quiescence and idle waiting in XCTest so video animations don't block input."""
        if not self.session_id:
            return
        try:
            settings_payload = {
                "settings": {
                    "waitForQuiescence": False,
                    "waitForIdleTimeout": 0,
                    "animationCoolOffTimeout": 0,
                    "shouldUseTestManagerForVisibilityDetection": False,
                    "snapshotTimeout": 1.0,
                }
            }
            self.http.post(self._url(f"/session/{self.session_id}/appium/settings"), json=settings_payload, timeout=2.0)
        except Exception:
            pass

    def drag_from_to(self, from_x: float, from_y: float, to_x: float, to_y: float, duration_sec: float = 0.35) -> bool:
        """Executes native XCTest drag from (from_x, from_y) to (to_x, to_y). Fast, smooth, and non-blocking."""
        session_id = self.ensure_session()
        payload = {
            "fromX": int(from_x),
            "fromY": int(from_y),
            "toX": int(to_x),
            "toY": int(to_y),
            "duration": float(duration_sec),
        }
        resp = self.http.post(
            self._url(f"/session/{session_id}/wda/dragfromtoforduration"),
            json=payload,
            timeout=self.timeout,
        )
        if resp.status_code != 200 or "invalid session id" in resp.text:
            # Recreate session and retry once
            session_id = self.ensure_session(force_new=True)
            resp = self.http.post(
                self._url(f"/session/{session_id}/wda/dragfromtoforduration"),
                json=payload,
                timeout=self.timeout,
            )
        return resp.status_code == 200

    def tap(self, x: float, y: float, dwell_ms: int = 60) -> bool:
        """Executes native WDA tap at coordinates (x, y)."""
        session_id = self.ensure_session()
        payload = {"x": int(x), "y": int(y)}
        resp = self.http.post(
            self._url(f"/session/{session_id}/wda/tap"),
            json=payload,
            timeout=self.timeout,
        )
        if resp.status_code != 200 or "invalid session id" in resp.text:
            session_id = self.ensure_session(force_new=True)
            resp = self.http.post(
                self._url(f"/session/{session_id}/wda/tap"),
                json=payload,
                timeout=self.timeout,
            )
        return resp.status_code == 200

    def double_tap(self, x: float, y: float, gap_ms: int = 120) -> bool:
        """Executes native WDA double-tap (like heart gesture in TikTok)."""
        session_id = self.ensure_session()
        payload = {"x": int(x), "y": int(y)}
        resp = self.http.post(
            self._url(f"/session/{session_id}/wda/doubleTap"),
            json=payload,
            timeout=self.timeout,
        )
        if resp.status_code != 200 or "invalid session id" in resp.text:
            session_id = self.ensure_session(force_new=True)
            resp = self.http.post(
                self._url(f"/session/{session_id}/wda/doubleTap"),
                json=payload,
                timeout=self.timeout,
            )
        return resp.status_code == 200

    def get_window_size(self) -> Tuple[int, int]:
        """Returns (width, height) of the device screen in UI points."""
        if self._window_size:
            return self._window_size
        session_id = self.ensure_session()
        resp = self.http.get(self._url(f"/session/{session_id}/window/size"), timeout=self.timeout)
        if resp.status_code != 200 or "invalid session id" in resp.text:
            session_id = self.ensure_session(force_new=True)
            resp = self.http.get(self._url(f"/session/{session_id}/window/size"), timeout=self.timeout)
        if resp.status_code != 200:
            raise WDAClientError(f"Failed to get window size: {resp.status_code} {resp.text}")
        val = resp.json().get("value", {})
        width = int(val.get("width", 393))
        height = int(val.get("height", 852))
        self._window_size = (width, height)
        return self._window_size

    def screenshot(self) -> Image.Image:
        """Captures a screenshot of the iPhone screen and returns a PIL Image."""
        resp = self.http.get(self._url("/screenshot"), timeout=self.timeout)
        if resp.status_code != 200:
            raise WDAClientError(f"Failed to capture screenshot: {resp.status_code} {resp.text}")
        data = resp.json()
        b64_str = data.get("value")
        if not b64_str:
            raise WDAClientError("WDA returned empty screenshot value")
        img_bytes = base64.b64decode(b64_str)
        return Image.open(io.BytesIO(img_bytes))

    def launch_app(self, bundle_id: str) -> bool:
        """Launches target app by bundle id (e.g. com.zhiliaoapp.musically)."""
        session_id = self.ensure_session()
        payload = {"bundleId": bundle_id}
        resp = self.http.post(
            self._url(f"/session/{session_id}/wda/apps/launch"),
            json=payload,
            timeout=self.timeout,
        )
        return resp.status_code == 200

    def terminate_app(self, bundle_id: str) -> bool:
        """Terminates target app by bundle id."""
        session_id = self.ensure_session()
        payload = {"bundleId": bundle_id}
        resp = self.http.post(
            self._url(f"/session/{session_id}/wda/apps/terminate"),
            json=payload,
            timeout=self.timeout,
        )
        return resp.status_code == 200

    def perform_w3c_actions(self, actions: List[Dict[str, Any]]) -> bool:
        """
        Executes raw W3C Actions API actions on the active session.
        Enables microsecond-precise synthetic touch sequences.
        """
        session_id = self.ensure_session()
        payload = {"actions": actions}
        resp = self.http.post(
            self._url(f"/session/{session_id}/actions"),
            json=payload,
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise WDAClientError(f"Action execution failed: {resp.status_code} {resp.text}")
        return True



    def dismiss_alert(self) -> bool:
        """Dismisses any active iOS system modal alert."""
        try:
            session_id = self.ensure_session()
            resp = requests.post(self._url(f"/session/{session_id}/alert/dismiss"), timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False

    def accept_alert(self) -> bool:
        """Accepts any active iOS system modal alert."""
        try:
            session_id = self.ensure_session()
            resp = requests.post(self._url(f"/session/{session_id}/alert/accept"), timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False

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

    def __init__(self, base_url: str = "http://localhost:8100", timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self._window_size: Optional[Tuple[int, int]] = None

    def _url(self, endpoint: str) -> str:
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def is_alive(self) -> bool:
        """Checks if WDA server is responding on the given endpoint."""
        try:
            resp = requests.get(self._url("/status"), timeout=2.5)
            return resp.status_code == 200
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        """Returns WDA server status, device UDID, iOS version, and capabilities."""
        resp = requests.get(self._url("/status"), timeout=self.timeout)
        if resp.status_code != 200:
            raise WDAClientError(f"Failed to fetch status: {resp.status_code} {resp.text}")
        data = resp.json()
        return data.get("value", data)

    def ensure_session(self) -> str:
        """Retrieves existing active session or creates a new one."""
        if self.session_id:
            try:
                resp = requests.get(self._url(f"/session/{self.session_id}"), timeout=3.0)
                if resp.status_code == 200:
                    return self.session_id
            except Exception:
                pass

        # Try to attach to active session from status or create new
        status = self.get_status()
        active_id = status.get("sessionId")
        if active_id:
            self.session_id = active_id
            return self.session_id

        # Create new session
        payload = {
            "capabilities": {
                "alwaysMatch": {
                    "shouldWaitForQuiescence": False,
                    "useNewWDA": False,
                }
            }
        }
        resp = requests.post(self._url("/session"), json=payload, timeout=self.timeout)
        if resp.status_code not in (200, 201):
            raise WDAClientError(f"Failed to create WDA session: {resp.status_code} {resp.text}")
        data = resp.json()
        self.session_id = data.get("sessionId") or data.get("value", {}).get("sessionId")
        return self.session_id

    def get_window_size(self) -> Tuple[int, int]:
        """Returns (width, height) of the device screen in UI points."""
        if self._window_size:
            return self._window_size
        session_id = self.ensure_session()
        resp = requests.get(self._url(f"/session/{session_id}/window/size"), timeout=self.timeout)
        if resp.status_code != 200:
            raise WDAClientError(f"Failed to get window size: {resp.status_code} {resp.text}")
        val = resp.json().get("value", {})
        width = int(val.get("width", 393))
        height = int(val.get("height", 852))
        self._window_size = (width, height)
        return self._window_size

    def screenshot(self) -> Image.Image:
        """Captures a screenshot of the iPhone screen and returns a PIL Image."""
        resp = requests.get(self._url("/screenshot"), timeout=self.timeout)
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
        resp = requests.post(
            self._url(f"/session/{session_id}/wda/apps/launch"),
            json=payload,
            timeout=self.timeout,
        )
        return resp.status_code == 200

    def terminate_app(self, bundle_id: str) -> bool:
        """Terminates target app by bundle id."""
        session_id = self.ensure_session()
        payload = {"bundleId": bundle_id}
        resp = requests.post(
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
        resp = requests.post(
            self._url(f"/session/{session_id}/actions"),
            json=payload,
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise WDAClientError(f"Action execution failed: {resp.status_code} {resp.text}")
        return True

    def tap(self, x: float, y: float, dwell_ms: int = 60) -> bool:
        """Executes a single human-like tap at coordinates (x, y)."""
        actions = [
            {
                "type": "pointer",
                "id": "finger1",
                "parameters": {"pointerType": "touch"},
                "actions": [
                    {"type": "pointerMove", "duration": 0, "x": int(x), "y": int(y)},
                    {"type": "pointerDown", "button": 0},
                    {"type": "pause", "duration": dwell_ms},
                    {"type": "pointerUp", "button": 0},
                ],
            }
        ]
        return self.perform_w3c_actions(actions)

    def double_tap(self, x: float, y: float, gap_ms: int = 120) -> bool:
        """Executes an authentic double-tap (like heart gesture in TikTok)."""
        # Slight jitter between first and second tap (humans never tap the exact same pixel twice)
        x2 = x + 1
        y2 = y - 1
        actions = [
            {
                "type": "pointer",
                "id": "finger1",
                "parameters": {"pointerType": "touch"},
                "actions": [
                    {"type": "pointerMove", "duration": 0, "x": int(x), "y": int(y)},
                    {"type": "pointerDown", "button": 0},
                    {"type": "pause", "duration": 45},
                    {"type": "pointerUp", "button": 0},
                    {"type": "pause", "duration": gap_ms},
                    {"type": "pointerMove", "duration": 0, "x": int(x2), "y": int(y2)},
                    {"type": "pointerDown", "button": 0},
                    {"type": "pause", "duration": 45},
                    {"type": "pointerUp", "button": 0},
                ],
            }
        ]
        return self.perform_w3c_actions(actions)

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

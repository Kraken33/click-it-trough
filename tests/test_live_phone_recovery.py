"""
Live Physical iPhone Test Suite: Multi-Interface Opening & FYP Auto-Recovery Verification.
Directly exercises TikTok on a connected device over USB/WDA.
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import yaml

from src.bridge.device_manager import DeviceManager
from src.engine.session_runner import SessionRunner
from src.vision.detector import ScreenDetector
from src.vision.ocr import VisionOCR

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class LivePhoneRecoveryTester:
    def __init__(self, config_path: str = "config/default_config.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.device_mgr = DeviceManager(
            wda_url=self.config.get("device", {}).get("wda_url", "http://localhost:8100")
        )
        self.wda = self.device_mgr.client
        self.ocr = VisionOCR()
        self.detector = ScreenDetector(self.ocr)
        self.runner = SessionRunner(config=self.config, device_manager=self.device_mgr)

    def check_prerequisites(self) -> bool:
        if not self.wda.is_alive():
            console.print("[bold red]❌ WebDriverAgent is offline on localhost:8100.[/bold red]")
            console.print("Ensure iPhone is connected via USB and ./scripts/start_tunnel.sh is running.")
            return False

        w, h = self.wda.get_window_size()
        console.print(f"[cyan]📱 Connected iPhone screen dimensions: {w}x{h} pt[/cyan]")
        return True

    def run_all_interface_tests(self) -> List[Dict[str, Any]]:
        w, h = self.wda.get_window_size()

        # Step 0: Ensure starting from clean FYP feed
        console.print("[yellow]Syncing to initial TikTok FYP video feed...[/yellow]")
        self.runner.ensure_app_open()
        time.sleep(1.0)
        self.runner.recover_to_feed(max_attempts=3)

        test_cases: List[Dict[str, Any]] = [
            {
                "name": "Comments Drawer",
                "target_states": ["comments"],
                "open_action": lambda: self.wda.tap(w * 0.925, h * 0.638),
                "open_desc": "Tap comments icon on right sidebar",
            },
            {
                "name": "Comment Input & Keyboard",
                "target_states": ["comment_input"],
                "open_action": lambda: (
                    self.wda.tap(w * 0.925, h * 0.638),
                    time.sleep(1.2),
                    self.wda.tap(w * 0.35, h * 0.96),
                ),
                "open_desc": "Open comment drawer and focus 'Add comment' input field",
            },
            {
                "name": "Share Sheet / Send To",
                "target_states": ["share"],
                "open_action": lambda: self.wda.tap(w * 0.925, h * 0.790),
                "open_desc": "Tap share icon on right sidebar",
            },
            {
                "name": "Creator Profile Page",
                "target_states": ["profile"],
                "open_action": lambda: self.wda.press_and_drag_with_velocity(
                    w * 0.90, h * 0.50, w * 0.15, h * 0.50, velocity=2600.0
                ),
                "open_desc": "Swipe left from right edge across video to open author profile",
            },
            {
                "name": "Search / Discover Page",
                "target_states": ["search"],
                "open_action": lambda: self.wda.tap(w * 0.93, h * 0.074),
                "open_desc": "Tap search magnifying glass icon in header",
            },
            {
                "name": "Camera / Creation Screen",
                "target_states": ["camera"],
                "open_action": lambda: self.wda.tap(w * 0.50, h * 0.95),
                "open_desc": "Tap '+' button in bottom center navigation bar",
            },
            {
                "name": "Alternative Tab (Inbox)",
                "target_states": ["other_tab"],
                "open_action": lambda: self.wda.tap(w * 0.70, h * 0.95),
                "open_desc": "Tap 'Inbox' tab in bottom navigation bar",
            },
            {
                "name": "Alternative Tab (Own Profile)",
                "target_states": ["profile"],
                "open_action": lambda: self.wda.tap(w * 0.90, h * 0.95),
                "open_desc": "Tap 'Profile' tab in bottom navigation bar",
            },
            {
                "name": "Sound / Audio Page",
                "target_states": ["sound"],
                "open_action": lambda: self.wda.tap(w * 0.925, h * 0.830),
                "open_desc": "Tap rotating music vinyl at bottom-right",
            },
            {
                "name": "TikTok Shop Page",
                "target_states": ["shop"],
                "open_action": lambda: self.wda.tap(w * 0.66, h * 0.074),
                "open_desc": "Tap 'Shop' tab in top header bar",
            },
            {
                "name": "Wrong Header Feed Tab (Following)",
                "target_states": ["feed_wrong_tab", "feed"],
                "open_action": lambda: self.wda.tap(w * 0.46, h * 0.074),
                "open_desc": "Tap 'Following' tab in top header bar",
            },
        ]

        results = []
        table = Table(title="Live Device Interface Recovery Test Results")
        table.add_column("Interface Case", style="cyan")
        table.add_column("Opening Action", style="dim")
        table.add_column("Detected State", style="yellow")
        table.add_column("Recovery Result", style="bold")
        table.add_column("Latency", style="magenta")

        for tc in test_cases:
            name = tc["name"]
            desc = tc["open_desc"]
            console.print(f"\n[bold blue]━━━ Testing: {name} ━━━[/bold blue]")
            console.print(f"[dim]Action: {desc}[/dim]")

            # Ensure starting from clean feed before each test case
            init_s = self.device_mgr.get_screen()
            if init_s:
                st, _ = self.detector.detect_screen_state(init_s)
                if st != "feed":
                    console.print(f"[dim]Pre-test sync: Currently on '{st}', resetting to FYP...[/dim]")
                    self.runner.recover_to_feed(max_attempts=2)
                    time.sleep(1.0)

            # 1. Trigger interface opening
            start_t = time.time()
            tc["open_action"]()
            time.sleep(2.0)

            # 2. Detect opened screen state
            screen = self.device_mgr.get_screen()
            detected_state = "unknown"
            markers: List[str] = []
            if screen:
                detected_state, markers = self.detector.detect_screen_state(screen)

            marker_info = f" ({', '.join(markers[:2])})" if markers else ""
            console.print(f"Screen detected: [yellow]'{detected_state}'[/yellow]{marker_info}")

            # 3. Execute recovery back to FYP
            rec_start = time.time()
            ok, final_state = self.runner.recover_to_feed(max_attempts=3)
            rec_duration = time.time() - rec_start

            # 4. Settle & verify post-recovery screen state
            time.sleep(0.5)
            post_screen = self.device_mgr.get_screen()
            post_state = "unknown"
            if post_screen:
                post_state, _ = self.detector.detect_screen_state(post_screen)

            passed = ok and post_state == "feed"
            status_str = "[bold green]PASS ✅ (to FYP)[/bold green]" if passed else f"[bold red]FAIL ❌ (ended on '{post_state}')[/bold red]"

            results.append({
                "name": name,
                "detected_state": detected_state,
                "post_state": post_state,
                "passed": passed,
                "duration_s": round(rec_duration, 2),
            })

            table.add_row(
                name,
                desc,
                f"{detected_state}{marker_info}",
                status_str,
                f"{rec_duration:.1f}s",
            )
            time.sleep(1.0)

        console.print("\n")
        console.print(table)
        return results


def main():
    tester = LivePhoneRecoveryTester()
    if not tester.check_prerequisites():
        return
    tester.run_all_interface_tests()


if __name__ == "__main__":
    main()

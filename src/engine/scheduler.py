import logging
import random
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from .session_runner import SessionRunner

logger = logging.getLogger(__name__)


class DailyRoutineScheduler:
    """
    Schedules 2-4 realistic human browsing sessions per day within natural time windows,
    injecting randomized start jitter and duration variations.
    """

    def __init__(self, runner: SessionRunner, config: Dict[str, Any]):
        self.runner = runner
        self.config = config.get("scheduler", {})
        self.enabled = self.config.get("enabled", True)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._daily_schedule: List[Dict[str, Any]] = []
        self._last_schedule_date: Optional[str] = None

    def start(self):
        """Starts the autonomous daily scheduler in background."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()
        logger.info("Autonomous daily routine scheduler started.")

    def stop(self):
        """Stops the scheduler."""
        self._stop_event.set()

    def _generate_today_plan(self):
        """Generates randomized schedule times for today."""
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        if self._last_schedule_date == today_str:
            return

        self._daily_schedule = []
        windows = self.config.get("windows", {})
        jitter_mins = self.config.get("start_jitter_minutes", 20)
        dur_min = self.config.get("session_duration_min", 12)
        dur_max = self.config.get("session_duration_max", 24)

        for win_name, (start_str, end_str) in windows.items():
            start_h, start_m = map(int, start_str.split(":"))
            base_time = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
            jitter_sec = random.randint(-jitter_mins * 60, jitter_mins * 60)
            scheduled_start = base_time + timedelta(seconds=jitter_sec)
            duration_minutes = random.randint(dur_min, dur_max)

            self._daily_schedule.append({
                "window": win_name,
                "start_time": scheduled_start,
                "duration_minutes": duration_minutes,
                "executed": False,
            })

        self._last_schedule_date = today_str
        logger.info(f"Generated daily plan for {today_str}: {len(self._daily_schedule)} sessions.")

    def get_upcoming_sessions(self) -> List[Dict[str, Any]]:
        """Returns the current day's planned sessions for UI display."""
        self._generate_today_plan()
        result = []
        for s in self._daily_schedule:
            result.append({
                "window": s["window"],
                "start_time": s["start_time"].strftime("%H:%M"),
                "duration_minutes": s["duration_minutes"],
                "executed": s["executed"],
            })
        return result

    def _scheduler_loop(self):
        while not self._stop_event.is_set():
            if not self.enabled:
                time.sleep(10)
                continue

            self._generate_today_plan()
            now = datetime.now()

            for item in self._daily_schedule:
                if not item["executed"] and now >= item["start_time"]:
                    # Check if window hasn't expired (within 45 mins of scheduled start)
                    if (now - item["start_time"]).total_seconds() < 2700:
                        logger.info(f"Triggering scheduled {item['window']} session ({item['duration_minutes']}m)...")
                        item["executed"] = True
                        self.runner.start(duration_minutes=item["duration_minutes"])
                        # Wait for session to finish
                        while self.runner._thread and self.runner._thread.is_alive():
                            if self._stop_event.is_set():
                                break
                            time.sleep(5)
                    else:
                        item["executed"] = True  # Missed window

            time.sleep(30)

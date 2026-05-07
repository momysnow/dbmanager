"""Background uptime monitor — pings each DB periodically and records up/down events."""

import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from config import ConfigManager
from core.notifications import NotificationManager


class UptimeMonitor:
    def __init__(
        self,
        config_manager: ConfigManager,
        notification_manager: NotificationManager,
        get_provider_fn: Callable[[int], Any],
    ) -> None:
        self._config = config_manager
        self._notif = notification_manager
        self._get_provider = get_provider_fn
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="uptime-monitor")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._ping_all()
            except Exception as e:
                print(f"[uptime-monitor] error: {e}")
            settings = self._config.get_ping_settings()
            interval = int(settings.get("interval_minutes", 5)) * 60
            self._stop_event.wait(timeout=interval)

    def _ping_all(self) -> None:
        settings = self._config.get_ping_settings()
        if not settings.get("enabled", True):
            return
        for db in self._config.get_databases():
            db_id = db.get("id")
            if db_id is None:
                continue
            new_status = self._ping_db(int(db_id))
            self._record_and_notify(db, new_status)

    def _ping_db(self, db_id: int) -> str:
        try:
            provider = self._get_provider(db_id)
            ok = provider.check_connection()
            return "up" if ok else "down"
        except Exception:
            return "down"

    def _record_and_notify(self, db: Dict[str, Any], new_status: str) -> None:
        db_id = int(db["id"])
        history = self._config.get_uptime_history(db_id)
        prev_status = history[-1]["status"] if history else None
        ts = datetime.now(timezone.utc).isoformat()
        self._config.append_uptime_event(db_id, new_status, ts)
        if prev_status is not None and prev_status != new_status:
            name = str(db.get("name", db_id))
            if new_status == "down":
                self._notif.send_db_down(name)
            else:
                self._notif.send_db_up(name)

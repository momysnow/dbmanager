"""Progress tracking for backup and restore operations."""

from enum import Enum
from typing import Callable, Optional
from datetime import datetime
import threading


class ProgressStatus(Enum):
    """Status of a backup/restore operation"""

    IDLE = "idle"
    PREPARING = "preparing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BackupProgress:
    """
    Tracks progress of backup/restore operations.

    Thread-safe progress tracker that can be used by providers to report
    progress, and by CLI/API to display progress to users.
    """

    def __init__(
        self, callback: Optional[Callable[["BackupProgress"], None]] = None
    ) -> None:
        """
        Initialize progress tracker.

        Args:
            callback: Optional function to call on progress updates.
                     Signature: callback(progress: BackupProgress)
        """
        self._lock = threading.Lock()
        self._status: ProgressStatus = ProgressStatus.IDLE
        self._percentage: int = 0
        self._message: str = ""
        self._current_step: str = ""
        self._total_steps: int = 0
        self._completed_steps: int = 0
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._error: Optional[str] = None
        self._callback: Optional[Callable[["BackupProgress"], None]] = callback

    @property
    def status(self) -> ProgressStatus:
        """Current operation status"""
        with self._lock:
            return self._status

    @property
    def percentage(self) -> int:
        """Completion percentage (0-100)"""
        with self._lock:
            return self._percentage

    @property
    def message(self) -> str:
        """Current progress message"""
        with self._lock:
            return self._message

    @property
    def current_step(self) -> str:
        """Current operation step"""
        with self._lock:
            return self._current_step

    @property
    def error(self) -> Optional[str]:
        """Error message if failed"""
        with self._lock:
            return self._error

    @property
    def elapsed_time(self) -> Optional[float]:
        """Elapsed time in seconds"""
        with self._lock:
            if self._start_time is None:
                return None
            end = self._end_time or datetime.now()
            return (end - self._start_time).total_seconds()

    def start(self, message: str = "Starting operation...") -> None:
        """Mark operation as started"""
        with self._lock:
            self._status = ProgressStatus.PREPARING
            self._message = message
            self._percentage = 0
            self._start_time = datetime.now()
            self._end_time = None
            self._error = None

        self._notify()

    def update(
        self,
        percentage: Optional[int] = None,
        message: Optional[str] = None,
        step: Optional[str] = None,
    ) -> None:
        """
        Update progress.

        Args:
            percentage: Completion percentage (0-100)
            message: Progress message
            step: Current step description
        """
        with self._lock:
            if self._status == ProgressStatus.IDLE:
                self._status = ProgressStatus.RUNNING

            if percentage is not None:
                self._percentage = max(0, min(100, percentage))

            if message is not None:
                self._message = message

            if step is not None:
                self._current_step = step

        self._notify()

    def set_steps(self, total: int) -> None:
        """
        Set total number of steps for the operation.

        Args:
            total: Total number of steps
        """
        with self._lock:
            self._total_steps = total
            self._completed_steps = 0

    def step_completed(self, step_name: str = "") -> None:
        """
        Mark a step as completed and auto-calculate percentage.

        Args:
            step_name: Name of completed step
        """
        with self._lock:
            self._completed_steps += 1
            if self._total_steps > 0:
                self._percentage = int(
                    (self._completed_steps / self._total_steps) * 100
                )
            self._current_step = step_name

        self._notify()

    def complete(self, message: str = "Operation completed") -> None:
        """Mark operation as completed successfully"""
        with self._lock:
            self._status = ProgressStatus.COMPLETED
            self._percentage = 100
            self._message = message
            self._end_time = datetime.now()

        self._notify()

    def fail(self, error: str) -> None:
        """Mark operation as failed"""
        with self._lock:
            self._status = ProgressStatus.FAILED
            self._error = error
            self._message = f"Failed: {error}"
            self._end_time = datetime.now()

        self._notify()

    def _notify(self) -> None:
        """Call callback if provided (without holding lock)"""
        if self._callback:
            try:
                self._callback(self)
            except Exception:
                # Don't let callback errors break progress tracking
                pass

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        with self._lock:
            return {
                "status": self._status.value,
                "percentage": self._percentage,
                "message": self._message,
                "current_step": self._current_step,
                "total_steps": self._total_steps,
                "completed_steps": self._completed_steps,
                "elapsed_time": self.elapsed_time,
                "error": self._error,
            }

    def __repr__(self) -> str:
        return (
            f"BackupProgress(status={self.status.value}, "
            f"percentage={self.percentage}%, "
            f"message='{self.message}')"
        )

"""Structured logging configuration for DBManager"""

import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Log directory
LOG_DIR = Path.home() / ".dbmanager" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Log file paths
MAIN_LOG = LOG_DIR / "dbmanager.log"
ERROR_LOG = LOG_DIR / "error.log"
API_LOG = LOG_DIR / "api.log"


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """Colored console formatter"""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logger(
    name: str,
    level: str = "INFO",
    log_file: Optional[Path] = None,
    use_json: bool = False,
    console: bool = True,
) -> logging.Logger:
    """
    Setup a logger with file and console handlers

    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (default: main log)
        use_json: Use JSON formatter for file logs
        console: Enable console output
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    logger.handlers = []  # Clear existing handlers

    # File handler with rotation
    if log_file is None:
        log_file = MAIN_LOG

    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"  # 10MB
    )
    file_handler.setLevel(logging.DEBUG)

    if use_json:
        file_handler.setFormatter(JSONFormatter())
    else:
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    logger.addHandler(file_handler)

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ColoredFormatter("%(levelname)s - %(message)s"))
        logger.addHandler(console_handler)

    # Error file handler
    error_handler = RotatingFileHandler(
        ERROR_LOG, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s\n"
            "%(pathname)s:%(lineno)d\n",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(error_handler)

    return logger


# Create default loggers
main_logger = setup_logger("dbmanager", level="INFO")
api_logger = setup_logger(
    "dbmanager.api", level="INFO", log_file=API_LOG, console=False
)
backup_logger = setup_logger("dbmanager.backup", level="INFO")
restore_logger = setup_logger("dbmanager.restore", level="INFO")


def get_logger(name: str = "dbmanager") -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)


def log_backup_start(db_name: str, db_id: int) -> None:
    """Log backup start"""
    backup_logger.info(f"Starting backup for database: {db_name} (ID: {db_id})")


def log_backup_success(
    db_name: str,
    backup_file: str,
    size_mb: float,
    duration: Optional[float] = None,
) -> None:
    """Log backup success"""
    msg = f"Backup completed: {db_name} -> {backup_file} ({size_mb:.2f} MB)"
    if duration:
        msg += f" in {duration:.2f}s"
    backup_logger.info(msg)


def log_backup_failure(db_name: str, error: str) -> None:
    """Log backup failure"""
    backup_logger.error(f"Backup failed for {db_name}: {error}")


def log_restore_start(db_name: str, backup_file: str) -> None:
    """Log restore start"""
    restore_logger.info(f"Starting restore for {db_name} from {backup_file}")


def log_restore_success(
    db_name: str, backup_file: str, duration: Optional[float] = None
) -> None:
    """Log restore success"""
    msg = f"Restore completed: {db_name} from {backup_file}"
    if duration:
        msg += f" in {duration:.2f}s"
    restore_logger.info(msg)


def log_restore_failure(db_name: str, backup_file: str, error: str) -> None:
    """Log restore failure"""
    restore_logger.error(f"Restore failed for {db_name} from {backup_file}: {error}")

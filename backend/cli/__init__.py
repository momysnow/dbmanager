"""CLI shared state and utilities"""

from rich.console import Console
from core.manager import DBManager
from core.cron import CronManager

# Shared instances
console = Console()
manager = DBManager()
cron_manager = CronManager()

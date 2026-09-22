from .backups import backups
from .database import db
from .lifecycle import logs, restart, start, status, stop, update
from .local import setup

# Re-exported: the command groups `arcsecond.cli` mounts.
__all__ = [
    "backups",
    "db",
    "setup",
    "start",
    "stop",
    "restart",
    "status",
    "logs",
    "update",
]

from .backups import backups

# check_cmd, not check: `check` is also this package's module of that name,
# and re-exporting the command under it would shadow the module for tests.
from .check import check_cmd
from .database import db
from .lifecycle import logs, restart, start, status, stop, update
from .local import setup

# Re-exported: the command groups `arcsecond.cli` mounts.
__all__ = [
    "backups",
    "check_cmd",
    "db",
    "setup",
    "start",
    "stop",
    "restart",
    "status",
    "logs",
    "update",
]

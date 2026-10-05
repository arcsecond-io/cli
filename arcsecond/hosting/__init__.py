from .backups import backups
from .database import db

# doctor_cmd, not doctor: `doctor` is also this package's module of that name,
# and re-exporting the command under it would shadow the module for tests.
from .doctor import doctor_cmd
from .lifecycle import logs, restart, start, status, stop, update
from .local import setup
from .token import token_group

# Re-exported: the command groups `arcsecond.cli` mounts.
__all__ = [
    "backups",
    "doctor_cmd",
    "db",
    "setup",
    "token_group",
    "start",
    "stop",
    "restart",
    "status",
    "logs",
    "update",
]

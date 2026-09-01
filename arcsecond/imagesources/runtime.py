"""
Where the running proxy is.

There is only ever one live-image proxy on a machine, but it does not always
listen on the default port, and the commands that need to talk to it —
``add``, ``forget``, ``proxy status`` — are typed long after it was started,
often in another terminal. Asking the operator to remember and retype
``--port`` for those is asking them to carry the proxy's bookkeeping for it.

So the proxy writes down where it is when it starts, in
``~/.config/arcsecond/live-image-proxy.json``::

    {"host": "0.0.0.0", "port": 8765, "pid": 4711}

and removes the file when it stops. A detached proxy has no terminal to write
to, so its output goes to a log file next to that note — see :func:`log_path`. A proxy can also be killed outright, in
which case the note outlives it, so the note is never trusted on its own: the
caller health-checks the port before believing it, and clears a note that
nothing answers on. That check is the reason a hard kill needs no cleanup — a
stale note reads as "no proxy running" rather than sending later commands into
the void.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from arcsecond.api.config import ArcsecondConfig

logger = logging.getLogger(__name__)

FILENAME = "live-image-proxy.json"
LOG_FILENAME = "live-image-proxy.log"


def runtime_path() -> Path:
    return ArcsecondConfig.dir_path() / FILENAME


def log_path() -> Path:
    """Where a detached proxy writes what it would have printed.

    A proxy running in the background still has things to say — a camera that
    will not open, a viewer that connected — and with no terminal to say them
    in, they go here.
    """
    return ArcsecondConfig.dir_path() / LOG_FILENAME


def write(host: str, port: int, path: Optional[Path] = None) -> None:
    path = path or runtime_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"host": host, "port": port, "pid": os.getpid()}, indent=2)
            + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        # Not fatal: the proxy serves images perfectly well without it. Only
        # the convenience of finding it without --port is lost.
        logger.warning("Could not record where the proxy is listening: %s", e)


def clear(path: Optional[Path] = None) -> None:
    path = path or runtime_path()
    try:
        path.unlink(missing_ok=True)
    except OSError as e:
        logger.warning("Could not clear %s: %s", path, e)


def read(path: Optional[Path] = None) -> Optional[dict]:
    """What the last proxy to start wrote, without checking it is still there."""
    path = path or runtime_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("port"), int):
        return None
    return data

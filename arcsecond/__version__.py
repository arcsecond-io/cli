"""
Version is defined in pyproject.toml (project.version).
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("arcsecond")
except PackageNotFoundError:
    # Fallback for running from a source checkout without installing.
    __version__ = "0.0.0"

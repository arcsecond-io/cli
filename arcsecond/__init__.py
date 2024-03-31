from .api import ArcsecondAPI, ArcsecondConfig, ArcsecondAPIEndpoint
from .errors import ArcsecondError

name = 'arcsecond'

__all__ = ["ArcsecondAPI",
           "ArcsecondError",
           "ArcsecondConfig",
           "ArcsecondAPIEndpoint"]

__version__ = '3.0.2'

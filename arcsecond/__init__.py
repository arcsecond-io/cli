from .api import ArcsecondAPI, ArcsecondError, ArcsecondConnectionError, ArcsecondInvalidEndpointError

name = 'arcsecond'

__all__ = ["ArcsecondAPI",
           "ArcsecondError",
           "ArcsecondConnectionError",
           "ArcsecondInvalidEndpointError"]

__version__ = '0.6.1'

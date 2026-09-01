from .auth import api, login, me
from .resources import datasets, telescopes
from .uploader import (
    DatasetFileUploader,
    DatasetUploadContext,
)
from .uploader.constants import Status, Substatus
from .uploads import (
    upload_data,
)

# Re-exported: this is the package's public surface.
__all__ = [
    "api",
    "login",
    "me",
    "datasets",
    "telescopes",
    "DatasetFileUploader",
    "DatasetUploadContext",
    "Status",
    "Substatus",
    "upload_data",
]

import glob
from datetime import datetime, timezone

from arcsecond import ArcsecondConfig, AllSkyCameraImageUploadContext, AllSkyCameraImageFileUploader

config = ArcsecondConfig()  # it will read your config file.
context = AllSkyCameraImageUploadContext(
    config,
    input_camera_uuid="uuid of all-sky camera",
    org_subdomain="subdomain or portal / organisation"
)

context.validate()

for filepath in glob.glob('directory containing files'):
    uploader = AllSkyCameraImageFileUploader(context, filepath, display_progress=False)
    # You must provide timestamp for every file.
    status, substatus, error = uploader.upload_file(timestamp=datetime.now(timezone.utc).timestamp())
    print(status, substatus, error)

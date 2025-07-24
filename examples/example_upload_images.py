import glob
from datetime import datetime, timezone

from arcsecond import ArcsecondConfig, AllSkyCameraImageUploadContext, AllSkyCameraImageFileUploader

# You may type `arcsecond allskycameras` to get a list of your cameras (include -p <subdomain> for portals).
# Alternatively, you can use `ArcsecondAPI(config).allskycameras.list()` to list them all in Python.

config = ArcsecondConfig()  # it will read your config file.
context = AllSkyCameraImageUploadContext(
    config,
    input_camera_uuid="uuid of all-sky camera",
    org_subdomain="subdomain or portal / organisation"
)

context.validate()

# Make sure to include "/*" to encompass all directory files.
for filepath in glob.glob('directory containing files/*'):
    uploader = AllSkyCameraImageFileUploader(context, filepath, display_progress=False)
    # You must provide timestamp for every file. Below is just an example for tests.
    timestamp = datetime.now(timezone.utc).timestamp()  # random.randint(0, 1000)
    status, substatus, error = uploader.upload_file(utc_timestamp=timestamp)
    print(status, substatus, error)

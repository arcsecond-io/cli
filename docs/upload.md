---
sidebar: true
---

# Data Upload

Arcsecond CLI makes it easy to upload dataset files and all-sky camera images to
your account or to an observatory portal.

All non-hidden files are uploaded. Choose folders carefully so you only send the
data you actually want in Arcsecond Cloud Storage.

## Upload Dataset Files With The CLI

Use:

```bash
arcsecond upload <folder> --dataset <name-or-uuid> --telescope <telescope-uuid>
```

The main options are:

- `--dataset` or `-d` to choose the dataset by name or UUID
- `--telescope` or `-t` to choose the telescope attached to the dataset
- `--portal` or `-p` to upload to an observatory portal
- `--raw` to mark the uploaded files as raw or reduced
- `--tags` to attach the same custom tags to every uploaded file

The command summarizes its settings and asks for confirmation before the upload
starts.

Useful discovery commands:

- `arcsecond datasets`
- `arcsecond telescopes`
- `arcsecond allskycameras`

## Upload Dataset Files With Python

```python
from arcsecond import (
    ArcsecondConfig,
    DatasetFileUploader,
    DatasetUploadContext,
    walk_folder_and_upload_files,
)

config = ArcsecondConfig()
context = DatasetUploadContext(
    config,
    input_dataset_uuid_or_name="My dataset",
    input_telescope_uuid="telescope-uuid",
    org_subdomain="my-portal",
    is_raw_data=False,
    custom_tags=["calibrated"],
)

context.validate()

walk_folder_and_upload_files(DatasetFileUploader, context, "/folder/path")
```

You can also upload files one by one:

```python
from pathlib import Path

from arcsecond import ArcsecondConfig, DatasetFileUploader, DatasetUploadContext

config = ArcsecondConfig()
context = DatasetUploadContext(
    config,
    input_dataset_uuid_or_name="My dataset",
    input_telescope_uuid="telescope-uuid",
)

context.validate()

for file_path in Path("/folder/path").glob("**/*"):
    if not file_path.is_file():
        continue

    uploader = DatasetFileUploader(context, str(file_path), display_progress=False)
    status, substatus, error = uploader.upload_file(
        is_raw=False,
        tags=["science"],
    )

    if error:
        raise error
```

## Upload All-Sky Camera Images With Python

```python
from datetime import datetime, timezone
from pathlib import Path

from arcsecond import (
    AllSkyCameraImageFileUploader,
    AllSkyCameraImageUploadContext,
    ArcsecondConfig,
)

config = ArcsecondConfig()
context = AllSkyCameraImageUploadContext(
    config,
    input_camera_uuid="camera-uuid",
    org_subdomain="my-portal",
)

context.validate()

for file_path in Path("/folder/path").glob("*"):
    if not file_path.is_file():
        continue

    uploader = AllSkyCameraImageFileUploader(
        context,
        str(file_path),
        display_progress=False,
    )
    timestamp = datetime.now(timezone.utc).timestamp()
    status, substatus, error = uploader.upload_file(utc_timestamp=timestamp)

    if error:
        raise error
```

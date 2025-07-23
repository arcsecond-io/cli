import glob

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
    status, substatus, error = uploader.upload_file()
    print(status, substatus, error)

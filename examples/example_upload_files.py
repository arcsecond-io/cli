import glob

from arcsecond import ArcsecondConfig, DatasetUploadContext, DatasetFileUploader

config = ArcsecondConfig()  # it will read your config file.
context = DatasetUploadContext(
    config,
    input_dataset_uuid_or_name="uuid of dataset",
    input_telescope_uuid="uuid of telescope",
    is_raw_data=False,
    org_subdomain="ariel-survey"
)

context.validate()

for filepath in glob.glob('directory containing files'):
    uploader = DatasetFileUploader(context, filepath, display_progress=False)
    status, substatus, error = uploader.upload_file()
    print(status, substatus, error)

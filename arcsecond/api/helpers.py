import os


def make_file_upload_payload(filepath):
    return {'files': {'file': open(os.path.abspath(filepath), 'rb')}}

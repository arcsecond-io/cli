import os


def make_file_upload_payload(filepath):
    return {'files': {'file': open(os.path.abspath(filepath), 'rb')}}


def make_coords_dict(kwargs):
    coords_string = kwargs.pop('coordinates', None)
    elements = coords_string.split(',')
    if coords_string and len(elements) == 2:
        return {'right_ascension': float(elements[0]), 'declination': float(elements[1])}
    return {}

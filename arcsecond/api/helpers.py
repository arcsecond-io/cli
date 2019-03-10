import os

from .error import ArcsecondInputValueError


def make_file_upload_payload(filepath):
    return {'files': {'file': open(os.path.abspath(filepath), 'rb')}}


def make_coords_dict(kwargs):
    coords_string = kwargs.pop('coordinates', None)
    error_string = 'Invalid coordinates format. Expected decimal values, format=RA,Dec'
    if coords_string:
        if ',' not in coords_string:
            raise ArcsecondInputValueError(error_string)
        elements = coords_string.split(',')
        if len(elements) != 2:
            raise ArcsecondInputValueError(error_string)
        if not elements[0].replace('.', '').isdigit() or not elements[1].replace('.', '').isdigit():
            raise ArcsecondInputValueError(error_string)
        return {'right_ascension': float(elements[0]), 'declination': float(elements[1])}
    return coords_string

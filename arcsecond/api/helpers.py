import os

from .error import ArcsecondInputValueError


def make_file_upload_multipart_dict(filepath):
    return {'fields': {'file': (os.path.basename(filepath), open(os.path.abspath(filepath), 'rb'))}}


def extract_multipart_encoder_file_fields(payload):
    if isinstance(payload, str) and os.path.exists(payload) and os.path.isfile(payload):
        payload = make_file_upload_multipart_dict(payload)  # transform a str into a dict

    elif isinstance(payload, dict) and 'file' in payload.keys():
        file_value = payload.pop('file')  # .pop() not .get()
        if file_value and os.path.exists(file_value) and os.path.isfile(file_value):
            payload.update(**make_file_upload_multipart_dict(file_value))  # unpack the resulting dict of make_file...()
        else:
            payload.update(file=file_value)  # do nothing, it's not a file...

    fields = payload.pop('fields', None) if payload else None
    return payload, fields


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

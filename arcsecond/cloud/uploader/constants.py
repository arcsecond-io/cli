from copy import deepcopy
from enum import Enum

# As used in QLFits: https://github.com/onekiloparsec/QLFits
OORT_FITS_EXTENSIONS = [
    '.fits',
    '.fit',
    '.fts',
    '.ft',
    '.mt',
    '.imfits',
    '.imfit',
    '.uvfits',
    '.uvfit',
    '.pha',
    '.rmf',
    '.arf',
    '.rsp',
    '.pi'
]

DATA_EXTENSIONS = OORT_FITS_EXTENSIONS + ['.xisf', ]

ZIP_EXTENSIONS = ['.zip', '.gz', '.bz2']


def _extend_list(extensions):
    for zip in ZIP_EXTENSIONS:
        extensions += [e + zip for e in extensions]
    return extensions


def get_all_xisf_extensions():
    return _extend_list(deepcopy(['.xisf', ]))


def get_all_fits_extensions():
    return _extend_list(deepcopy(OORT_FITS_EXTENSIONS))


class Status(Enum):
    NEW = 'New'
    PREPARING = 'Preparing'
    UPLOADING = 'Uploading'
    FINISHING = 'Finishing'
    OK = 'OK'
    SKIPPED = 'Skipped'
    ERROR = 'Error'


class Substatus(Enum):
    PENDING = 'pending'
    CHECKING = 'checking remote file...'
    UPLOADING = 'uploading...'
    TAGGING = 'tagging...'

    DONE = 'done'
    ERROR = 'error'
    ALREADY_SYNCED = 'already synced'
    IGNORED = 'ignored'
    # --- SKIPPED: MUST BE STARTED WITH THE SAME 'skipped' LOWERCASE WORD. See Context.py ---
    SKIPPED_NO_DATE_OBS = 'skipped (no date obs found)'
    SKIPPED_HIDDEN_FILE = 'skipped (hidden file)'
    SKIPPED_EMPTY_FILE = 'skipped (empty file)'
    # ---

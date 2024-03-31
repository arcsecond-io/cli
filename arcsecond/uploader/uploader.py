import os
import socket
from datetime import datetime
from pathlib import Path

from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

from arcsecond import ArcsecondAPI
from arcsecond import __version__
from .constants import Status, Substatus
from .context import Context
from .errors import UploadRemoteDatasetCheckError, UploadRemoteFileCheckError
from .logger import get_oort_logger


class FileUploader(object):
    def __init__(self, context: Context, root_path: Path, file_path: Path, display_progress: bool = False):
        self._context = context
        self._root_path = root_path
        self._file_path = file_path
        self._display_progress = display_progress

        self._logger = get_oort_logger(debug=True)
        self._started = None
        self._progress = 0
        self._is_test_context = bool(os.environ.get('OORT_TESTS') == '1')
        self._status = [Status.NEW, Substatus.PENDING, None]

        self._api = ArcsecondAPI(self._context.config, self._context.organisation_subdomain)

    @property
    def log_prefix(self) -> str:
        return f'[FileUploader: {str(self._file_path.relative_to(self._root_path))}]'

    def _prepare_dataset(self):
        if self._context.dataset_uuid:
            response, error = self._api.datasets.read(self._context.dataset_uuid)
            if error:
                raise UploadRemoteDatasetCheckError(str(error))
            self._context.update_dataset(response)

        elif self._context.dataset_name:
            # Dataset UUID is empty, and CLI validators have already checked this dataset doesn't exist.
            # Simply create dataset.
            response, error = self._api.datasets.create({'name': self._context.dataset_name})
            if error:
                raise UploadRemoteDatasetCheckError(str(error))
            self._context.update_dataset(response)

        else:
            raise UploadRemoteDatasetCheckError('No dataset specified.')

    def _perform_upload(self):
        self._started = datetime.now()
        file_size = self._file_path.stat().st_size
        self._logger.info(f'{self.log_prefix} Starting upload to Arcsecond ({file_size} bytes)')

        e = MultipartEncoder(
            fields={'dataset': self._context.dataset_uuid,
                    'file': (self._file_path.name, open(self._file_path, 'rb'))}
        )

        def percent_printer(monitor):
            bar_length = 40
            self.__bytes_read = monitor.bytes_read
            fraction = min(float(monitor.bytes_read) / float(file_size), 1.0)
            hashes = '#' * int(round(fraction * bar_length))
            spaces = ' ' * (bar_length - len(hashes))
            print(f'[{hashes}{spaces}] {(fraction * 100):.1f}%', end='\r')

        m = MultipartEncoderMonitor(e, percent_printer)

        self._datafile, error = self._api.datafiles.create(data=m, headers={"Content-Type": m.content_type})
        if error:
            self._status = [Status.ERROR, Substatus.ERROR, None]
            raise UploadRemoteFileCheckError(str(error))

        ended = datetime.now()
        duration = (ended - self._started).total_seconds()
        self._logger.info(f'{self.log_prefix} Uploaded finished in {duration} seconds.')

    def _update_tags(self):
        tag_root = f'oort|root|{str(self._root_path)}'
        tag_origin = f'oort|origin|{socket.gethostname()}'
        tag_uploader = f'oort|uploader|{self._context.config.username}'
        tag_oort = f'oort|version|{__version__}'

        # Tags being a list, they cannot be part of the MultipartEncoder.fields because they will
        # be interpreted as a file field tuple/list.
        tags = [tag_root, tag_origin, tag_uploader, tag_oort]
        response, error = self._api.datafiles.update(self._datafile.get('pk'), json={'tags': tags})
        if error:
            self._status = [Status.ERROR, Substatus.ERROR, None]
            raise UploadRemoteFileCheckError(str(error))

    def upload_file(self):
        self._status = [Status.PREPARING, Substatus.CHECKING, None]
        self._logger.info(f'{self.log_prefix} Preparing Dataset...')
        self._prepare_dataset()
        self._logger.info(f'{self.log_prefix} Dataset preparation done.')

        self._status = [Status.UPLOADING, Substatus.UPLOADING, None]
        self._logger.info(f'{self.log_prefix} Opening upload sequence.')
        self._perform_upload()
        self._logger.info(f'{self.log_prefix} Closing upload sequence.')

        self._status = [Status.FINISHING, Substatus.TAGGING, None]
        self._logger.info(f'{self.log_prefix} Updating file tags....')
        self._update_tags()

        self._status = [Status.OK, Substatus.DONE, None]
        return self._status

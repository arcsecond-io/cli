from collections import Counter
from pathlib import Path

import click

from .constants import Status
from .context import UploadContext
from .logger import get_logger
from .uploader import FileUploader
from .utils import is_file_hidden


def __get_duplicates(values):
    dups = Counter(values) - Counter(set(values))
    return list(dups.keys())


def __walk_first_pass(context: UploadContext, root_path: Path):
    logger = get_logger()
    log_prefix = '[Walker - 1/2]'
    logger.info(f"{log_prefix} Making a first pass to collect info on files...")

    total_file_count = sum(1 for f in root_path.glob('**/*') if f.is_file() and not is_file_hidden(f))

    index = 0
    file_paths = []
    for file_path in root_path.glob('**/*'):
        # Skipping both hidden files and hidden directories.
        if is_file_hidden(file_path) or not file_path.is_file():
            continue

        index += 1
        msg = f"{log_prefix} File {index} / {total_file_count} ({index / total_file_count * 100:.2f}%) "
        msg += f"{file_path.name}"
        click.echo(msg)
        file_paths.append(file_path)

    logger.info(f"{log_prefix} Finished collecting file info inside folder {str(root_path)}.")
    return file_paths


def __walk_second_pass(context: UploadContext, root_path: Path, file_paths: list):
    logger = get_logger()
    log_prefix = '[Walker - 2/2]'
    logger.info(f"{log_prefix} Starting second pass to upload files...")

    uploads = {'succeeded': [], 'skipped': [], 'failed': []}
    total_file_count = len(file_paths)

    index = 0
    for file_path in file_paths:
        index += 1
        click.echo(f"{log_prefix} File {index} / {total_file_count} ({index / total_file_count * 100:.2f}%)")

        uploader = FileUploader(context, root_path, file_path, display_progress=True)
        status, substatus, error = uploader.upload_file()
        if status == Status.OK:
            uploads['succeeded'].append(str(file_path))
        elif status == Status.SKIPPED:
            uploads['skipped'].append((str(file_path), substatus, error))
        else:
            uploads['failed'].append((str(file_path), substatus, error))

    msg = f"{log_prefix}\n\nFinished upload walk inside folder {root_path} "
    logger.info(msg)

    return uploads


def walk_folder_and_upload(context: UploadContext, folder_string: str):
    logger = get_logger()
    log_prefix = '[Walker]'
    root_path = Path(folder_string).resolve()
    if root_path.is_file():  # Just in case we pass a file...
        root_path = root_path.parent

    logger.info(f"{log_prefix} Starting to walk through {root_path} and its subfolders...")

    file_paths = __walk_first_pass(context, root_path)
    if len(file_paths) == 0:
        msg = f"{log_prefix} No file paths to upload. Exiting.\n\n"
        logger.info(msg)
        return

    all_local_filenames = [path.name for path in file_paths]
    duplicates = __get_duplicates(all_local_filenames)
    if len(duplicates) > 0:
        msg = f"{log_prefix} The following files have duplicate names (not allowed in the same dataset): "
        msg += f"{', '.join(duplicates)}"
        logger.error(msg)
        logger.error(f"Exiting.")
        return

    uploads = __walk_second_pass(context, root_path, file_paths)
    msg = f"{log_prefix} uploads succeeded: {len(uploads['succeeded'])}, "
    msg += f"skipped: {len(uploads['skipped'])}, failed: {len(uploads['failed'])}\n"
    logger.info(msg)

    if len(uploads['skipped']) > 0:
        logger.error(f'{log_prefix} Here are the skipped uploads:')
        for path, substatus, error in uploads['skipped']:
            logger.warning(f'{path} ({substatus})')

    if len(uploads['failed']) > 0:
        logger.error(f'{log_prefix} Here are the failed uploads:')
        for path, substatus, error in uploads['failed']:
            logger.error(f'{path} ({substatus}) {error}')

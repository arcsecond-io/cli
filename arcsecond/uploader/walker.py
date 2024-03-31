import time
from pathlib import Path

import click

from .constants import Status
from .context import Context
from .logger import get_oort_logger
from .uploader import FileUploader
from .utils import is_file_hidden


def __walk_first_pass(context: Context, root_path: Path):
    logger = get_oort_logger()
    log_prefix = '[Walker - 1/2]'
    logger.info(f"{log_prefix} Making a first pass to collect info on files...")
    if context.config.api_name != 'dev':
        # For user experience, and let him/her read the above message.
        time.sleep(3)

    total_file_count = sum(1 for f in root_path.glob('**/*') if f.is_file() and not is_file_hidden(f))

    index = 0
    file_paths = []
    for file_path in root_path.glob('**/*'):
        # Skipping both hidden files and hidden directories.
        if is_file_hidden(file_path) or not file_path.is_file():
            continue

        index += 1
        click.echo(f"\n{log_prefix} File {index} / {total_file_count} ({index / total_file_count * 100:.2f}%)")
        file_paths.append(file_path)

    logger.info(f"{log_prefix} Finished collecting file info inside folder {str(root_path)}.")
    return file_paths


def __walk_second_pass(context: Context, root_path: Path, file_paths: list):
    logger = get_oort_logger()
    log_prefix = '[Walker - 2/2]'
    logger.info(f"{log_prefix} Starting second pass to upload files...")
    if context.config.api_name != 'dev':
        time.sleep(3)

    failed_uploads = []
    success_uploads = []
    total_file_count = len(file_paths)

    index = 0
    for file_path in file_paths:
        index += 1
        click.echo(f"\n{log_prefix} File {index} / {total_file_count} ({index / total_file_count * 100:.2f}%)\n")

        uploader = FileUploader(context, root_path, file_path, display_progress=True)
        status, substatus, error = uploader.upload_file()
        if status == Status.OK:
            success_uploads.append(str(file_path))
        else:
            failed_uploads.append((str(file_path), substatus, error))

    msg = f"{log_prefix}\n\nFinished upload walk inside folder {root_path} "
    logger.info(msg)

    return success_uploads, failed_uploads


def walk(context: Context, folder_string: str):
    logger = get_oort_logger()
    log_prefix = '[Walker]'
    root_path = Path(folder_string).resolve()
    if root_path.is_file():  # Just in case we pass a file...
        root_path = root_path.parent

    logger.info(f"{log_prefix} Starting upload walk through {root_path} and its subfolders...")

    file_paths = __walk_first_pass(context, root_path)
    if len(file_paths) > 0:
        success_uploads, failed_uploads = __walk_second_pass(context, root_path, file_paths)
        msg = f"{log_prefix} {len(success_uploads)} successful uploads and {len(failed_uploads)} failed.\n\n"
        logger.info(msg)

        if len(failed_uploads) > 0:
            logger.error(f'{log_prefix} Here are the failed uploads:')
            for path, substatus, error in failed_uploads:
                logger.error(f'{path} ({substatus}) {error}')
    else:
        msg = f"{log_prefix} No new file paths to upload.\n\n"
        logger.info(msg)

# if __name__ == '__main__':
#     root_path = sys.argv[1]
#     username, upload_key, subdomain, role, telescope, debug_str = sys.argv[2].split(",")
#     debug = (debug_str == 'True')
#     identity = Identity(username, upload_key, subdomain, role, telescope, debug)
#     walk(root_path, identity, debug)

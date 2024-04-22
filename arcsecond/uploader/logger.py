import os
from datetime import datetime
from logging import DEBUG, FileHandler, Formatter, INFO, Logger, StreamHandler, getLogger
from pathlib import Path


def get_logger(debug=False) -> Logger:
    suffix = ' (test)' if os.environ.get('OORT_TESTS') == '1' else ''
    logger = getLogger('arcsecond' + suffix)
    logger.setLevel(DEBUG if debug else INFO)

    if len(logger.handlers) == 0:
        formatter = Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        if os.environ.get('OORT_TESTS') != '1':
            log_file_path = Path(f'arcsecond_upload_{datetime.now().replace(microsecond=0).isoformat()}.log')
            file_handler = FileHandler(log_file_path)
            file_handler.setLevel(DEBUG if debug else INFO)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        console_handler = StreamHandler()
        console_handler.setLevel(DEBUG if debug else INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger

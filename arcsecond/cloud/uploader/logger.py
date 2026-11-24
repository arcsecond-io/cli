from logging import (
    DEBUG,
    INFO,
    Formatter,
    Logger,
    StreamHandler,
    getLogger,
)


def get_logger(debug=False) -> Logger:
    logger = getLogger("arcsecond")
    logger.setLevel(DEBUG if debug else INFO)

    if len(logger.handlers) == 0:
        formatter = Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        console_handler = StreamHandler()
        console_handler.setLevel(DEBUG if debug else INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger

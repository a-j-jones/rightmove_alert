import logging

LOG_LEVEL = logging.INFO


def logging_setup(logger: logging.Logger) -> logging.Logger:
    logger.setLevel(LOG_LEVEL)
    logger.propagate = False

    if logger.hasHandlers():
        logger.handlers.clear()

    sh = logging.StreamHandler()
    sh.setLevel(LOG_LEVEL)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    sh.setFormatter(formatter)
    logger.handlers = []
    logger.addHandler(sh)

    return logger

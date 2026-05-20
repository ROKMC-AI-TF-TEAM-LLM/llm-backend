import logging

from app.core.config import settings


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(settings.log_level.upper())

        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                fmt="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(handler)

    return logger

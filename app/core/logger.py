import logging


def get_logger(name: str) -> logging.Logger:
    """
    표준 logging 모듈 기반 로거 생성.

    예: get_logger(__name__)
        [14:32:01] INFO src.ingestion: ingestion 시작

    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)

        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                fmt="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(handler)

    return logger
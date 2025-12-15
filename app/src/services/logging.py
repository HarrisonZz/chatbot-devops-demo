import logging
from pythonjsonlogger import jsonlogger

def get_logger() -> logging.Logger:
    logger = logging.getLogger("app")
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger

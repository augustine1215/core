import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

def get_logger():
    logger = logging.getLogger('app')
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s.%(msecs)03d [%(levelname)s] : %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    file_log_handler = TimedRotatingFileHandler('logfile.log', when="midnight", interval=1)
    file_log_handler.suffix = "%Y%m%d"
    file_log_handler.setFormatter(formatter)
    logger.addHandler(file_log_handler)

    console_log_handler = logging.StreamHandler()
    console_log_handler.setFormatter(formatter)
    logger.addHandler(console_log_handler)

    logger.propagate = False

    return logger
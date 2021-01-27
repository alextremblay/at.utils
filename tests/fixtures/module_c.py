import logging


def func():
    logging.debug("test from stdlib root logger maybe")
    log = logging.getLogger(__name__)
    log.debug("test from stdlib __name__ logger")

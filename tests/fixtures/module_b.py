from loguru import logger

logger.disable(__name__)
logger.debug('module b loaded')


def func():
    logger.debug('hello from module b')

from si_utils.log import get_logger

logger = get_logger('app_b')
logger.debug('module b loaded')


def func():
    logger.debug('hello from module b')

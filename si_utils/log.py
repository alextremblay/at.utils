import sys
import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from getpass import getuser

if TYPE_CHECKING:
    from loguru import Logger

from ._vendor.appdirs import user_log_dir
from loguru import logger

STDERR_FORMAT = "<green>{time:MM-DD HH:mm}</> | <blue>{extra[app_name]}</> | \
    <level>{level.name: ^9}</> | <bold>{message}</>"

LOGFILE_FORMAT = "{time:MM-DD HH:mm} | {level.name: ^8} | {message} \n\
    Data: {extra}"

DEFAULT_LOG_DIR = '/var/log/si-utils'


def get_logger(app_name: str) -> 'Logger':
    "get a pre-configured logger instance"
    log = logger.opt(colors=True).bind(app_name=app_name)
    log.disable('')  # only cli apps should enable the logger
    log._si_app_name = app_name  # type: ignore
    return log


def _setup_sentry_sink(_logger: 'Logger', app_name: str):
    if os.environ.get('DISABLE_SENTRY_LOGGING'):
        _logger.debug(
            'Env var DISABLE_SENTRY_LOGGING is set. Sentry logging disabled')
        return

    # import here to avoid circular dependency
    from .main import get_config_key

    sentry_dsn = get_config_key('shared', 'sentry_dsn')
    if not sentry_dsn:
        sentry_dsn = get_config_key(app_name, 'sentry_dsn')
    if not sentry_dsn:
        _logger.debug(
            'Could not find valid configuration for Sentry. '
            'Sentry logging disabled')
        return

    try:
        import sentry_sdk
    except ImportError:
        _logger.debug(
            'the sentry_sdk package is not installed. Sentry logging disabled.'
            ' Please install si-utils with the "sentry" extra '
            '(ex. `pip install si-utils[sentry]`).')
        return
    # the way we set up sentry logging assumes you have one sentry
    # project for all your apps, and want to group all your alerts
    # into issues by app name

    def before_send(event, hint):
        # group all sentry events by app name
        if event.get('exception'):
            exc_type = event['exception']['values'][0]['type']
            event['exception']['values'][0]['type'] = \
                f'{app_name}: {exc_type}'
        if event.get('message'):
            event['message'] = f'{app_name}: {event["message"]}'
        return event

    sentry_sdk.init(
        sentry_dsn, with_locals=True,
        request_bodies='small', before_send=before_send
    )
    user = {'username': getuser()}
    email = os.environ.get('MY_EMAIL')
    if email:
        user['email'] = email
    sentry_sdk.set_user(user)

    def sentry_sink(msg):
        data = msg.record
        level = data['level'].name.lower()
        exception = data['exception']
        message = data['message']
        sentry_sdk.set_context('log_data', data)
        if exception:
            sentry_sdk.capture_exception()
        else:
            sentry_sdk.capture_message(message, level)
    _logger.add(sentry_sink, level='ERROR')


def _setup_logfile_sink(_logger: 'Logger', app_name: str, file_log_level: str):
    if not file_log_level:
        _logger.debug(
            f'file_log_level is {file_log_level}. File logging disabled.')
        return
    if os.environ.get('DISABLE_FILE_LOGGING'):
        _logger.debug(
            'Env var DISABLE_FILE_LOGGING is set. File logging disabled.')
        return

    def get_log_file(backup=False) -> Optional[Path]:
        log_dir = os.environ.get('DEFAULT_LOG_DIR', DEFAULT_LOG_DIR)
        if log_dir != DEFAULT_LOG_DIR:
            _logger.debug(
                'Env var DEFAULT_LOG_DIR is set. '
                'Will write to a log file in there')
        main_log_file = Path(f'{log_dir}/{app_name}.log')
        backup_log_file = Path(f'{user_log_dir(app_name)}/output.log')
        if not backup:
            log_file = main_log_file
        else:
            log_file = backup_log_file

        if log_file.is_file():
            _logger.debug(
                f'Found log file {log_file}. Will log messages to it')
            return log_file
        # attempt to create log_file
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.touch()
            _logger.debug(
                f'Created log file {log_file}. Will log messages to it')
            return log_file
        except OSError:
            if not backup:
                _logger.debug(
                    f"Unable to write logs to log file {log_file}. "
                    f"Will write to {backup_log_file} instead."
                )
                return get_log_file(backup=True)
            else:
                _logger.error(
                    f"Unable to write logs to log file {log_file} or "
                    f"to alternate log file {backup_log_file}. "
                    "Skipping file logging."
                )
                return None

    log_file = get_log_file()
    if log_file:
        _logger.add(sink=log_file, format=LOGFILE_FORMAT, level=file_log_level)


def enable_logging(
        _logger: 'Logger',
        stderr_level='INFO',
        file_log_level='DEBUG'
        ):
    """
    take a logger configured by the `get_logger` function above
    and set it up for logging to a file and to stderr
    if file_log_level is None or False, logging to file will be disabled
    """
    app_name = _logger._si_app_name  # type: ignore

    _logger.enable('')
    # Set up logging to stderr
    logger.remove()  # remove the default stderr handler
    logger.add(
        level=stderr_level, sink=sys.stderr, backtrace=False,
        colorize=True, format=STDERR_FORMAT
    )

    # Optionally set up sentry logging
    _setup_sentry_sink(_logger, app_name)

    # Set up logging to file
    _setup_logfile_sink(_logger, app_name, file_log_level)

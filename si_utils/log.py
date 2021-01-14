import sys
import os
from pathlib import Path
from typing import TYPE_CHECKING
from getpass import getuser

if TYPE_CHECKING:
    from loguru import Logger

from .main import get_config_key
from ._vendor.appdirs import user_log_dir

try:
    from loguru import logger
    import sentry_sdk
except ImportError:
    raise ImportError(
        "In order to use this module, the si-utils package must be "
        "installed with the 'log' extra (ex. `pip install si-utils[log]")

STDERR_FORMAT = "<green>{time:MM-DD HH:mm}</> | <blue>{extra[app_name]}</> | \
    <level>{level.name: ^9}</> | <bold>{message}</>"

LOGFILE_FORMAT = "{time:MM-DD HH:mm} | {level.name: ^8} | {message} \n\
    Data: {extra}"


def get_logger(app_name: str) -> 'Logger':
    "get a pre-configured logger instance"
    log = logger.opt(colors=True).bind(app_name=app_name)
    log.disable(None)  # only cli apps should enable the logger
    log._si_app_name = app_name  # type: ignore
    return log


def _setup_sentry_sink(_logger: 'Logger', app_name: str):
    try:
        sentry_dsn = get_config_key('shared', 'sentry_dsn')
    except Exception:
        # skip sentry sink setup if sentry not configured
        return
    
    if os.environ.get('DISABLE_SENTRY_LOGGING'):
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
    if not file_log_level:
        return
    log_dir = os.environ.get('SI_LOG_DIR', '/var/log/si-utils')
    log_path = Path(log_dir)
    log_file = log_path.joinpath(f'{app_name}.log')
    if not log_file.is_file():
        # attempt to create log_file
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.touch()
        except OSError:
            backup_log_path = Path(user_log_dir(app_name))
            backup_log_file = backup_log_path.joinpath('output.log')
            _logger.debug(
                f"unable to write logs to log file {log_file}. "
                f"Log folder {log_path} does not exist and cannot be "
                f"created. will write to {backup_log_file} instead"
            )

            if not backup_log_file.is_file():
                # attempt to create log_file
                try:
                    backup_log_file.parent.mkdir(parents=True, exist_ok=True)
                    backup_log_file.touch()
                except OSError:
                    _logger.error(
                        f"unable to write logs to log file {log_file} or "
                        f"to alternate log file {backup_log_file}. "
                        "skipping file logging."
                    )
    if log_path.is_dir():
        # at this point, either log_path was already a dir,
        # or it was successfully created
        log_file = log_path.joinpath(f'{app_name}.log')
        _logger.add(sink=log_file, format=LOGFILE_FORMAT)

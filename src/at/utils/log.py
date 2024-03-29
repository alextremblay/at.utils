import sys
import os
from pathlib import Path
from typing import Callable, List, Optional
from getpass import getuser
import logging
import logging.handlers
import platform

from loguru import logger as log

log.disable("at_utils")

STDERR_FORMAT = "<blue>{extra[app_name]}</> | <level>{level.name:8}</>| <bold>{message}</>"  # noqa

LOGFILE_FORMAT = "{time:MM-DD HH:mm} | {name}:{function}:{line} - {level.name: ^8} | {message} \nData: {extra}"

SYSLOG_FORMAT = "{extra[app_name]} | {name}:{function}:{line} - {level.name: ^8} | {message} | Data: {extra}"  # noqa

DEFAULT_LOG_DIR = "/var/log/at-utils"


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = log.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        log.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def get_sentry_sink(app_name: str) -> Optional[Callable]:
    if os.environ.get("DISABLE_SENTRY_LOGGING"):
        log.debug("Env var DISABLE_SENTRY_LOGGING is set. Sentry logging disabled")
        return None

    # import here to avoid circular dependency
    from .main import get_config_key_or_none  # noqa

    sentry_dsn = get_config_key_or_none("shared", "sentry_dsn")
    if not sentry_dsn:
        sentry_dsn = get_config_key_or_none(app_name, "sentry_dsn")
    if not sentry_dsn:
        log.debug(
            "Could not find valid configuration for Sentry. " "Sentry logging disabled"
        )
        return None

    try:
        import sentry_sdk # noqa
    except ImportError:
        log.debug(
            "the sentry_sdk package is not installed. Sentry logging disabled."
            ' Please install at-utils with the "sentry" extra '
            "(ex. `pip install at-utils[sentry]`)."
        )
        return None
    # the way we set up sentry logging assumes you have one sentry
    # project for all your apps, and want to group all your alerts
    # into issues by app name

    def before_send(event, hint): # noqa
        # group all sentry events by app name
        if event.get("exception"):
            exc_type = event["exception"]["values"][0]["type"]
            event["exception"]["values"][0]["type"] = f"{app_name}: {exc_type}"
        if event.get("message"):
            event["message"] = f'{app_name}: {event["message"]}'
        return event

    sentry_sdk.init(
        sentry_dsn, with_locals=True, request_bodies="small", before_send=before_send
    )
    user = {"username": getuser()}
    email = os.environ.get("MY_EMAIL")
    if email:
        user["email"] = email
    sentry_sdk.set_user(user)

    def sentry_sink(msg):
        data = msg.record
        level = data["level"].name.lower()
        exception = data["exception"]
        message = data["message"]
        sentry_sdk.set_context("log_data", data)
        if exception:
            sentry_sdk.capture_exception()
        else:
            sentry_sdk.capture_message(message, level)

    return sentry_sink


def get_logfile_sink(app_name: str) -> Optional[Path]:
    if os.environ.get("DISABLE_FILE_LOGGING"):
        log.debug("Env var DISABLE_FILE_LOGGING is set. File logging disabled.")
        return None

    def get_log_file(backup=False) -> Optional[Path]:
        log_dir = os.environ.get("DEFAULT_LOG_DIR", DEFAULT_LOG_DIR)
        if log_dir != DEFAULT_LOG_DIR:
            log.debug(
                "Env var DEFAULT_LOG_DIR is set. " "Will write to a log file in there"
            )
        main_log_file = Path(f"{log_dir}/{app_name}.log")
        backup_log_file = Path(f"{user_log_dir(app_name)}/output.log")
        if not backup:
            log_file = main_log_file
        else:
            log_file = backup_log_file

        if log_file.is_file():
            log.debug(f"Found log file {log_file}. Will log messages to it")
            return log_file
        # attempt to create log_file
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.touch()
            log.debug(f"Created log file {log_file}. Will log messages to it")
            return log_file
        except OSError:
            if not backup:
                log.debug(
                    f"Unable to write logs to log file {log_file}. "
                    f"Will write to {backup_log_file} instead."
                )
                return get_log_file(backup=True)
            #else:
            log.error(
                f"Unable to write logs to log file {log_file} or "
                f"to alternate log file {backup_log_file}. "
                "Skipping file logging."
            )
            return None

    log_file = get_log_file()
    if log_file:
        return log_file
    #else:
    return None


def configure_logging(  # noqa
    app_name: str,
    stderr_level: Optional[str] = "INFO",
    logfile_level: Optional[str] = "DEBUG",
    sentry_level: Optional[str] = "ERROR",
    stderr_opts: Optional[dict] = None,
    logfile_opts: Optional[dict] = None,
    sentry_opts: Optional[dict] = None,
    extra_handlers: Optional[List[dict]] = None,
    attach_stdlib_logger: bool = False,
    syslog_level: Optional[str] = None,
    syslog_opts: Optional[dict] = None,
):
    """
    Configures handlers and options for the Loguru logger.
    Sets up a stderr sink unless `stderr_level` is None
    Sets up a file log sink unless `file_log_level` is None
    Sets up a sentry sink if possible, unless `sentry_level` is None
    Any options defined in any of the *_opts dicts overlay / override
    default options for those handlers
    if attach_stdlib_logger is true, the logging module fro mthe stdlib will be
    configured to emit logs to loguru
    """

    handlers = []

    if stderr_level:
        stderr_handler = dict(
            sink=sys.stderr,
            backtrace=False,
            level=stderr_level,
            colorize=True,
            format=STDERR_FORMAT,
        )
        if stderr_opts:
            stderr_handler.update(**stderr_opts)
        handlers.append(stderr_handler)

    if logfile_level:
        logfile = get_logfile_sink(app_name)
        if logfile:
            logfile_handler = dict(
                sink=logfile, level=logfile_level, format=LOGFILE_FORMAT
            )
            if logfile_opts:
                logfile_handler.update(**logfile_opts)
            handlers.append(logfile_handler)
    
    if syslog_level:
        if platform.system() == 'Windows':
            # syslog configs like level and facility don't apply in windows, 
            # so we set up a basic event log handler instead
            syslog_sink = logging.handlers.NTEventLogHandler(appname=app_name)
        else:
            # should handle ~90% of unixes
            def_syslog_address = '/var/run/syslog' if platform.system() == 'Darwin' else '/dev/log'
            if syslog_opts:
                address = syslog_opts.get('syslog_address', def_syslog_address)
            else:
                address = def_syslog_address
            syslog_sink = logging.handlers.SysLogHandler(address=address)
            syslog_sink.ident = 'at-utils: '
        syslog_handler = dict(
                sink=syslog_sink, level=syslog_level, format=SYSLOG_FORMAT
            )
        if syslog_opts:
            syslog_handler.update(syslog_opts)
        handlers.append(syslog_handler)
        

    if sentry_level:
        sentry_sink = get_sentry_sink(app_name)
        if sentry_sink:
            sentry_handler = dict(sink=sentry_sink, level=sentry_level)
            if sentry_opts:
                sentry_handler.update(**sentry_opts)
            handlers.append(sentry_handler)

    if extra_handlers:
        handlers.extend(extra_handlers)

    if attach_stdlib_logger:
        logging.basicConfig(handlers=[InterceptHandler()], level=0)

    log.configure(
        handlers=handlers,
        extra={"app_name": app_name},
        activation=[("", True)],  # enable logging for all modules
    )

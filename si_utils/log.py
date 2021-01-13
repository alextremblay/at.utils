import sys
import os
from pathlib import Path
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from loguru import Logger

from loguru import logger

STDERR_FORMAT = "<green>{time:MM-DD HH:mm}</> | <blue>{extra[app_name]}</> | \
    <level>{level.name: ^9}</> | <bold>{message}</>"

LOGFILE_FORMAT = "{time:MM-DD HH:mm} | {level.name: ^8} | {message} \nData: \
    {extra}"


def get_logger(app_name) -> 'Logger':
    "get a pre-configured logger instance"
    log = logger.opt(colors=True).bind(app_name=app_name)
    log.disable(None)  # only cli apps should enable the logger
    log._si_app_name = app_name  # type: ignore
    return log


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
    _logger.enable('')
    # Set up logging to stderr
    logger.remove()  # remove the default stderr handler
    logger.add(
        level=stderr_level, sink=sys.stderr,
        colorize=True, format=STDERR_FORMAT
    )

    # Set up logging to file
    if not file_log_level:
        return
    app_name = _logger._si_app_name  # type: ignore
    log_dir = os.environ.get('SI_LOG_DIR', '/var/log/si-utils')
    log_path = Path(log_dir)
    log_file = log_path.joinpath(f'{app_name}.log')
    if not log_path.is_dir() and log_path.parent.exists():
        # attempt to create log_dir
        try:
            log_path.mkdir()
        except OSError:
            _logger.error(
                f"unable to write logs to log file {log_file}. "
                f"Log folder {log_path} does not exist and cannot be "
                "created")
    if log_path.is_dir():
        # at this point, either log_path was already a dir,
        # or it was successfully created
        log_file = log_path.joinpath(f'{app_name}.log')
        _logger.add(sink=log_file, format=LOGFILE_FORMAT)

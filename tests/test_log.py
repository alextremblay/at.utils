from pathlib import Path
from typing import TYPE_CHECKING
import logging

from si_utils import configure_logging

from .fixtures import module_a

import pytest
from loguru import logger

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch
    from _pytest.capture import CaptureFixture
    from _pytest.logging import LogCaptureFixture


@pytest.fixture
def caploguru(caplog):
    class PropogateHandler(logging.Handler):
        def emit(self, record):
            logging.getLogger(record.name).handle(record)

    handler_id = logger.add(PropogateHandler(), format="{message} {extra}")
    yield caplog
    logger.remove(handler_id)


def test_configure_logging(
        tmp_path: Path,
        monkeypatch: 'MonkeyPatch',
        capsys: 'CaptureFixture',
        caplog: 'LogCaptureFixture'
        ):

    # logger should start disabled
    module_a.doathing()
    assert caplog.text == ''

    # logging by default is a no-op, unless and until logging is enabled.
    # no log file should exist yet
    assert len(list(tmp_path.iterdir())) == 0
    configure_logging('test', 'DEBUG', None, None, {'colorize': False})
    # test basic configuration
    logger.info('When `logfile_level` is None, no file logging should occur')
    assert len(list(tmp_path.iterdir())) == 0

    # test sys.stderr sink
    assert 'When `logfile_level` is None, no file logging should occur' \
        in capsys.readouterr().err

    # test file logging
    # override the default log dir
    monkeypatch.setenv('DEFAULT_LOG_DIR', str(tmp_path))
    configure_logging('test', 'DEBUG', 'DEBUG', None, {'colorize': False})
    module_a.doathing()
    with logger.catch():
        1 / 0
    logfile = tmp_path.joinpath('test.log')

    # test logfile output
    assert logfile.exists()
    logfile_output = logfile.read_text()
    assert 'This is a TRACE message' not in logfile_output, \
        "default file log level should not capture TRACE messages"
    assert 'This is a DEBUG message' in logfile_output, \
        "default file log level should capture DEBUG messages"
    assert 'An error has been caught in function' in logfile_output, \
        "log file should collect exception messages"

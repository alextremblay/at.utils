from pathlib import Path
from typing import TYPE_CHECKING

from si_utils.log import get_logger, enable_logging

from .fixtures import module_a

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch
    from _pytest.capture import CaptureFixture


def test_log(
        tmp_path: Path,
        monkeypatch: 'MonkeyPatch',
        capsys: 'CaptureFixture'
        ):

    # override the default log dir
    monkeypatch.setenv('SI_LOG_DIR', str(tmp_path))

    # start loggers disabled
    logger = get_logger('test')
    logger.info('logging not yet enabled')
    module_a.doathing()

    # logging by default is a no-op, unless and until logging is enabled.
    # no log file should exist yet
    assert len(list(tmp_path.iterdir())) == 0
    enable_logging(logger)
    assert capsys.readouterr().err == ''
    logger.info('logging now enabled')
    module_a.doathing()
    with logger.catch():
        1 / 0
    logfile = tmp_path.joinpath('test.log')

    # test logfile output
    assert logfile.exists()
    logfile_output = logfile.read_text()
    assert 'logging not yet enabled' not in logfile_output, \
        "logger produced output before it was enabled"
    assert 'logging now enabled' in logfile_output, \
        "logger was enabled but did not produce output"
    assert 'This is a TRACE message' not in logfile_output, \
        "default file log level should not capture TRACE messages"
    assert 'This is a DEBUG message' in logfile_output, \
        "default file log level should capture DEBUG messages"
    assert 'An error has been caught in function' in logfile_output, \
        "log file should collect exception messages"

    # test stderr output
    cap = capsys.readouterr()
    stderr = cap.err
    assert 'logging now enabled' in stderr, \
        "logger stderr handler must handle INFO level messages by default"
    assert 'This is a DEBUG message' not in stderr, \
        "default stderr log level should not capture DEBUG messages"

    # TODO: figure out a way to test sentry. There seems to be some
    # wierd interaction with pytest which prevents it from working.
    # it doesn't fail, it just doesn't do anything.

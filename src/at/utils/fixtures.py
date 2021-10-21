
from typing import TYPE_CHECKING, Tuple
import logging
from pathlib import Path

import pytest
from _pytest.logging import caplog as _caplog
from loguru import logger

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
    from _pytest.logging import LogCaptureFixture
    from _pytest.fixtures import FixtureRequest
    from . import Util


class PropogateHandler(logging.Handler):
    def emit(self, record):
        logging.getLogger(record.name).handle(record)



@pytest.fixture
def caplog(caplog):
    """
    override and wrap the caplog fixture with one of our own
    """
    logger.remove() # remove default handler, if it exists
    logger.enable("") # enable all logs from all modules
    logging.addLevelName(5, "TRACE") # tell python logging how to interpret TRACE logs
    class PropogateHandler(logging.Handler):
        def emit(self, record):
            logging.getLogger(record.name).handle(record)
    logger.add(PropogateHandler(), format="{message} {extra}", level="TRACE") # shunt logs into the standard python logging machinery
    caplog.set_level(0) # Tell logging to handle all log levels
    yield caplog




class MockFolders:
    class ConfDir:
        def __init__(self, dir: Path, app_name: str) -> None:
            self.dir = dir
            self.ini_file = dir.joinpath(f'{app_name}.ini')
            self.json_file = dir.joinpath(f'{app_name}.json')
            self.yaml_file = dir.joinpath(f'{app_name}.yaml')
            self.toml_file = dir.joinpath(f'{app_name}.toml')

    def __init__(self, tmp_path: Path, app_name: str) -> None:
        self.root = tmp_path
        self.site_config = MockFolders.ConfDir(tmp_path / "etc/xdg/at-utils", app_name)
        # This would be:
        # - /Library/Application Support/at-utils on MacOS,
        # - /etc/xdg/at-utils on Linux,
        # - C:\ProgramData\at-utils on Win 7+

        # an alternative site config path, used to test the *_SITE_CONFIG env var logic
        self.site_config_env = MockFolders.ConfDir(tmp_path / "etc/alternate", app_name)

        self.user_config = MockFolders.ConfDir(tmp_path / "home/user/.config/at-utils", app_name)
        # This would be:
        # - ~/Library/Application Support/at-utils on MacOS,
        # - ~/.config/at-utils on Linux,
        # - C:\Users\<username>\AppData\Local\at-utils on Win 7+

        # an alternative user config path, used to test the *_USER_CONFIG env var logic
        self.user_config_env = MockFolders.ConfDir(tmp_path / "home/alternate", app_name)

        self.site_cache = tmp_path / f"usr/local/share/at-utils/{app_name}"
        self.user_cache = tmp_path / f"home/user/.local/share/at-utils/{app_name}"
        self.site_cache_env = tmp_path / f"usr/local/share/at-utils/alternate"
        self.user_cache_env = tmp_path / f"home/user/.local/share/at-utils/alternate"

        # create the folders
        self.site_config.dir.mkdir(parents=True)
        self.site_config_env.dir.mkdir(parents=True)
        self.user_config.dir.mkdir(parents=True)
        self.user_config_env.dir.mkdir(parents=True)
        self.site_cache.mkdir(parents=True)
        self.user_cache.mkdir(parents=True)


MockUtilFolders = Tuple['Util', MockFolders]


@pytest.fixture()
def mock_folders(tmp_path: Path, mocker: 'MockerFixture', request: 'FixtureRequest'):
    marker = request.node.get_closest_marker("app_name")
    if marker:
        app_name = marker.args[0]
    else:
        app_name = "example_app"
    
    import at.utils
    # To test the config file testing logic of the Util class, we need to mock out all the system calls
    # it makes to return repeatable, predictable paths we can control, regardless of which platform
    # the test is running on, or what config files / folcers may already exists
    # in the *real* locations returned by these calls
    folders = MockFolders(tmp_path, app_name)  # create the folders to use as mocks

    # mock out the real folders
    mocker.patch.object(at.utils.PlatformDirs, "site_config_path", folders.site_config.dir)
    mocker.patch.object(at.utils.PlatformDirs, "user_config_path", folders.user_config.dir)
    mocker.patch.object(at.utils.PlatformDirs, "site_data_path", folders.site_cache.parent)
    mocker.patch.object(at.utils.PlatformDirs, "user_cache_path", folders.user_cache.parent)

    util = at.utils.Util(app_name)  # create the Util instance to be tested

    mocker.patch.object(util, "common_user_config_dir", folders.user_config.dir)
    yield util, folders

    # clean up the file permissions so that the tmp_path directory can be cleaned up
    for f in folders.root.rglob('*'):
        f.chmod(0o777)
    
    # clean up the Util instance
    util._clear_caches()
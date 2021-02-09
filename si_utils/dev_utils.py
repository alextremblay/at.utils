from si_utils import main
from subprocess import run, PIPE
import sys
from pathlib import Path
from typing import Dict, List, TYPE_CHECKING
from types import ModuleType
import inspect

import loguru

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch

try:
    import tomlkit
    import semver
    import pytest
except ImportError:
    raise ImportError(
        "In order to use this module, the si-utils package must be installed "
        "with the 'dev-utils' extra (ex. `pip install si-utils[dev-utils]"
    )


def bump_version():
    """
    bump a project's version number.
    bumps the __version__ var in the project's __init__.py
    bumps the version in pyproject.toml
    tags the current git commit with that version number
    """
    if len(sys.argv) < 2:
        bump_type = "patch"
    else:
        bump_type = sys.argv[1]
    if bump_type not in ["major", "minor", "patch", "prerelease", "build"]:
        print(f"invalid bump_type {bump_type}")
        sys.exit()
    git_status = run(["git", "status"], stdout=PIPE, check=True).stdout.decode()
    if "nothing to commit, working tree clean" not in git_status:
        print(
            "git working tree not clean. aborting. run `git status` and commit"
            " or ignore all outstanding files, then try again."
        )
    pyproject = tomlkit.parse(Path("pyproject.toml").read_text())
    package_name = pyproject["tool"]["poetry"]["name"]  # type: ignore
    old_version = pyproject["tool"]["poetry"]["version"]  # type: ignore
    version = semver.VersionInfo.parse(old_version)
    # for every bump_type in the list above, there is a bump_{type} method
    # on the VersionInfo object. here we look up the method and call it
    # ex if bump_type is 'patch', this will call version.bump_patch()
    version = getattr(version, f"bump_{bump_type}")()
    new_version = str(version)
    pyproject["tool"]["poetry"]["version"] = new_version  # type: ignore
    init_file = Path(f"{package_name}/__init__.py")
    init_text = init_file.read_text()
    init_text.replace(
        f"__version__ = '{old_version}'", f"__version__ = '{new_version}'"
    )

    # no turning back now!
    Path("pyproject.toml").write_text(tomlkit.dumps(pyproject))
    init_file.write_text(init_text)
    run(["git", "add", "."], check=True)
    run(["git", "commit", "-m", f"bump version from {old_version} to {new_version}"], check=True)
    run(["git", "tag", "-s", "-a", new_version, "-m", f"version {new_version}"], check=True)
    print("done")


class CapLoguru:
    def __init__(self) -> None:
        self.logs: Dict[str, List['loguru.Message']] = {}
        self.handler_id = None

    def emit(self, msg: 'loguru.Message'):
        level = msg.record["level"].name
        if not self.logs.get(level):
            self.logs[level] = []
        self.logs[level].append(msg)

    def add_handler(self):
        self.handler_id = loguru.logger.add(self.emit, level="DEBUG")

    def remove_handler(self):
        if not self.handler_id:
            return  # noop
        loguru.logger.remove(self.handler_id)

    def all_logs(self):
        for log in self.logs.values():
            for line in log:
                yield line

    def string_in_log_level(self, level, string_partial):
        """
        Assert that a log line of the given log level contains the string
        """
        if not self.logs[level]:
            return False
        for line in self.logs[level]:
            if string_partial in line:
                return True
        # else:
        return False

    def line_in_log_level(self, level, match_line):
        """
        Assert that a log line of the given log level matches the given line
        """
        if not self.logs[level]:
            return False
        for log_line in self.logs[level]:
            if log_line == match_line:
                return True
        # else:
        return False

    def string_in_log(self, string_partial):
        """
        Assert that a log line of any log level contains the string
        """
        for line in self.all_logs():
            if string_partial in line:
                return True
        # else:
        return False

    def line_in_log(self, match_line):
        """
        Assert that a log line of any log level contains the string
        """
        for line in self.all_logs():
            if line == match_line:
                return True
        # else:
        return False

@pytest.fixture()
def caploguru():
    fixture = CapLoguru()
    yield fixture
    fixture.remove_handler()


def clear_caches(module: ModuleType):
    """
    clear all caches in a given module
    
    clear the caches of all cached functions and all cached classmethods 
    and staticmethods of all classes in a given module
    """

    def get_cachables():
        # functions
        for _, function_ in inspect.getmembers(module, inspect.isfunction):
            yield function_

        for _, class_ in inspect.getmembers(module, inspect.isclass):
            # static methods
            for _, static_method in inspect.getmembers(class_, inspect.isfunction):
                yield static_method
            
            # class methods
            for _, class_method in inspect.getmembers(class_, inspect.ismethod):
                yield class_method
    
    for cacheable in get_cachables():
        if hasattr(cacheable, 'cache'):
            cacheable.cache = {}


@pytest.fixture
def config_dirs(tmp_path: Path, monkeypatch: 'MonkeyPatch'):
    """
    sets up get_config_file to search a specific set of tmp folders
    
    Deprecated: use mock_si_utils_paths instead
    """
    site_conf = tmp_path.joinpath("site_config")
    site_conf.mkdir()
    user_conf = tmp_path.joinpath("user_config")
    user_conf.mkdir()
    site_cache = tmp_path.joinpath("site_cache")
    site_cache.mkdir()
    monkeypatch.setenv("SI_UTILS_SITE_CONFIG", str(site_conf))
    monkeypatch.setenv("SI_UTILS_USER_CONFIG", str(user_conf))
    monkeypatch.setenv("SI_UTILS_SITE_CACHE", str(site_cache))
    yield tmp_path
    clear_caches(main)

class SIUtilsPaths:
    site_conf: Path
    user_conf: Path
    site_cache: Path
    log_dir: Path

    def __init__(self, mock_path: Path) -> None:
        self.site_conf = mock_path.joinpath("site_config")
        self.site_conf.mkdir()
        self.user_conf = mock_path.joinpath("user_config")
        self.user_conf.mkdir()
        self.site_cache = mock_path.joinpath("site_cache")
        self.site_cache.mkdir()
        self.log_dir = mock_path.joinpath("log_dir")
        self.log_dir.mkdir()

    def set_config_toml(self, app_name: str, conf_str: str):
        self.site_conf.joinpath(f'{app_name}.toml').write_text(main.txt(conf_str))

    def set_config_yaml(self, app_name: str, conf_str: str):
        self.site_conf.joinpath(f'{app_name}.yaml').write_text(main.txt(conf_str))

    def set_config_json(self, app_name: str, conf_str: str):
        self.site_conf.joinpath(f'{app_name}.json').write_text(main.txt(conf_str))

    def set_config_ini(self, app_name: str, conf_str: str):
        self.site_conf.joinpath(f'{app_name}.ini').write_text(main.txt(conf_str))


@pytest.fixture
def mock_si_utils_paths(tmp_path: Path, monkeypatch: 'MonkeyPatch'):
    """
    mocks all paths returned by functions in si_utils to point to subfolders of a pytest tmp_path
    
    Deprecated: use mock_si_utils_paths instead
    """
    # set up
    paths = SIUtilsPaths(tmp_path)
    monkeypatch.setenv("SI_UTILS_SITE_CONFIG", str(paths.site_conf))
    monkeypatch.setenv("SI_UTILS_USER_CONFIG", str(paths.user_conf))
    monkeypatch.setenv("SI_UTILS_SITE_CACHE", str(paths.site_cache))
    monkeypatch.setenv("DEFAULT_LOG_DIR", str(paths.log_dir))

    # run tests
    yield paths

    # clean up
    clear_caches(main)
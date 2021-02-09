"""
The purpose of this module is to store all utilities, functions, and classes
which don't depend on any external packages.
This module can be used even if you don't install any of si-util's extras

"""

import os
from typing import List, Dict, Any, Optional
from pathlib import Path
import configparser
import json
from textwrap import dedent
import time

from ._vendor.appdirs import AppDirs
from ._vendor.decorator import decorate
from ._vendor import toml
from loguru import logger as log

log.disable("si_utils")


def _cache(func, *args, **kw):
    if kw:  # frozenset is used to ensure hashability
        key = args, frozenset(kw.items())
    else:
        key = args
    cache = func.cache  # attribute added by `cache` decorator
    if key not in cache:
        cache[key] = func(*args, **kw)
    return cache[key]


def cache(f):
    """
    A simple signature-preserving memoize implementation. It works by adding
    a .cache dictionary to the decorated function. The cache will grow
    indefinitely, so it is your responsibility to clear it, if needed.
    """
    f.cache = {}
    return decorate(f, _cache)


@cache
def get_config_file_or_fail(app_name: str) -> Path:
    """
    Find a valid config file for a given app name.
    File can be stored in a site-wide directory (ex. /etc/xdg/si-utils)
    or a user-local directory (ex. ~/.config/si-utils)
    file must have name matching `app_name` and one of the
    following extensions: ['.ini', '.yaml', '.json', '.toml']
    if an environment variable like {app_name}_CONFIG_FILE exists and points
    to a file that exists, that file will be returned
    if an environment variable SI_UTILS_CONFIG_PATH exists and points
    to a real directory, that directory will also be searched for a valid
    config file.

    `level` sets the severity level of log messages if a valid config file
    can't be found

    {app_name}_CONFIG_FILE is the preferred way to override the config file
    lookup procedure.
    SI_UTILS_CONFIG_PATH exists mainly for testing purposes

    Args:
        app_name: the name of the config file to search for, minus the extension

    Raises:
        Exception: if no valid config file found
    """
    # define common constants
    log.debug(f'Looking for a config file for app name "{app_name}"')
    valid_extensions = ["ini", "yaml", "json", "toml"]
    all_conf_files = []
    config_file_names = [f"{app_name}.{ext}" for ext in valid_extensions]

    # handle env vars
    env_var = f"{app_name.upper()}_CONFIG_FILE"
    site_conf_env_var = "SI_UTILS_SITE_CONFIG"
    user_conf_env_var = "SI_UTILS_USER_CONFIG"
    env_var_file = os.environ.get(env_var)
    if env_var_file:
        log.debug(f'Env var "{env_var}" is set to "{env_var_file}".')
        if Path(env_var_file).exists():
            log.debug(f'File "{env_var_file}" exists.')
            return Path(env_var_file)
        # else:
        log.debug(f'File "{env_var_file}" does not exist. Skipping it.')
    else:
        log.debug(
            f'Env var "{env_var}" not set. '
            f"Proceeding with normal config file lookup."
        )

    # handle site config
    site_conf: Path
    site_conf = os.environ.get(site_conf_env_var)  # type: ignore
    if site_conf:
        site_conf = Path(site_conf)
        log.debug(
            f"Env var {site_conf_env_var} is set. "
            "Adding it to the config file search path"
        )
    else:
        site_conf = Path(AppDirs("si-utils").site_config_dir)
    site_conf_files = [site_conf.joinpath(name) for name in config_file_names]
    all_conf_files.extend(site_conf_files)

    # handle user config
    user_conf: Path
    user_conf = os.environ.get(user_conf_env_var)  # type: ignore
    if user_conf:
        user_conf = Path(user_conf)
        log.debug(
            f"Env var {user_conf_env_var} is set. "
            "Adding it to the config file search path"
        )
    else:
        user_conf = Path(AppDirs("si-utils").user_config_dir)
    user_conf_files = [user_conf.joinpath(name) for name in config_file_names]
    all_conf_files.extend(user_conf_files)

    # find conf file
    log.trace(f"Searching for the following config files: {all_conf_files}")
    valid_conf_files = [file for file in all_conf_files if file.exists()]
    if len(valid_conf_files) > 0:
        log.debug(
            f"Found the following config files: {valid_conf_files}."
            f"Using config file: {valid_conf_files[0]}"
        )
        return valid_conf_files[0]
    # handle failure
    raise Exception(
        f"Could not find a valid config file for `app_name` {app_name}. "
        f"Searched for files {config_file_names} in folders {site_conf} "
        f"and {user_conf}, found nothing"
    )


@cache
def get_config_file_or_none(app_name, error_level="DEBUG") -> Optional[Path]:
    """
    Like `get_config_file_or_fail`, but logs an error and returns None if no
    config file found, rather than raising an exception.

    Args:
        app_name:
            the filename to search for within the config paths, minus the extension
        error_level:
            the name of the logging level to log a failure with
    """
    try:
        return get_config_file_or_fail(app_name)
    except Exception as e:
        log.log(error_level, e.args[0])
        return None


@cache
def get_config_obj_or_fail(app_name: str) -> Dict[str, Any]:
    """
    Finds a valid config file, loads it into memory, and converts it
    into a dictionary. Can be called multiple times without triggering
    multiple file load / parsing operations
    only .json, .ini, and .toml config files are currently supported
    for .ini files, keys in the DEFAULT section will be 'hoisted' so that they become
    keys of the top level dictionary returned

    Args:
        app_name:
            the filename to search for within the config paths, minus the extension
    """
    conf_file = get_config_file_or_fail(app_name)
    if not conf_file:
        raise Exception(f"Could not load config from file for app_name {app_name}")
    log.debug(f"Loading config object from {conf_file}")
    obj: Dict[str, Any]
    if conf_file.suffix == ".ini":
        cfp = configparser.ConfigParser()
        cfp.read(conf_file)
        obj = dict(cfp["DEFAULT"])
        for sect in cfp.sections():
            obj.update(dict(cfp[sect]))
    elif conf_file.suffix == ".json":
        obj = dict(json.loads(conf_file.read_text()))
    elif conf_file.suffix == ".toml":
        log.debug(f"Loading config object from {conf_file}")
        obj = dict(toml.loads(conf_file.read_text()))  # type: ignore
    else:
        raise Exception(
            f"Found config file {conf_file}. `get_config_key` "
            f"does not support config files of type {conf_file.suffix}. "
            "Only .toml, .ini and .json files are supported"
        )
    return obj


@cache
def get_config_obj_or_none(
    app_name: str,
    error_level="DEBUG",
) -> Optional[Dict[str, Any]]:
    """
    Like `get_config_obj_or_fail`, but logs an error and returns None if no
    config file found, rather than raising an exception.

    Args:
        app_name:
            the filename to search for within the config paths, minus the extension
        error_level:
            the name of the logging level to log a failure with
    """
    try:
        return get_config_obj_or_fail(app_name)
    except Exception as e:
        log.log(error_level, e.args[0])
        return None


def get_config_key_or_fail(app_name: str, key: str):
    """
    simple function to get a key value for a given app_name from
    either an environment variable or a config file
    only .json and .ini config files are currently supported
    keys in .ini files must be stored in the DEFAULT section
    only top-level keys in .json config files are supported

    Args:
        app_name:
            the filename to search for within the config paths, minus the extension

    Raises:
        KeyError: if the given key couldn't be found in the config file
        Exception: any exception raised by get_config_obj_or_fail
    """
    env_var_name = f"{app_name.upper()}_{key.upper()}"
    env_var = os.environ.get(env_var_name)
    if env_var:
        log.debug(
            f"Env var {env_var_name} is set, using as value instead of "
            "loading config file"
        )
        return env_var

    obj = get_config_obj_or_fail(app_name)

    val = obj.get(key)
    if not val:
        raise KeyError(f"Could not find key {key} in config object {obj}")

    return val


def get_config_key_or_none(app_name: str, key: str, error_level="DEBUG"):
    """
    Like `get_config_key_or_fail`, but logs an error and returns None if no
    config file found, rather than raising an exception.

    Args:
        app_name:
            the filename to search for within the config paths, minus the extension
        error_level:
            the name of the logging level to log a failure with
    """
    try:
        return get_config_key_or_fail(app_name, key)
    except Exception as e:
        log.log(error_level, e.args[0])
        return None


def get_cache_dir(app_name: str) -> Path:
    """
    create and return a cache dir for cache data.
    prefer system-wide data dir, fall back to user cache dir
    """
    env_var_path = os.environ.get(f"{app_name.upper()}_CACHE_PATH")
    site_cache_env_var = "SI_UTILS_SITE_CACHE"
    user_cache_env_var = "SI_UTILS_USER_CACHE"
    if env_var_path:
        try:
            path = Path(env_var_path)
            path.mkdir(parents=True, exist_ok=True)
            return path
        except OSError:
            pass

    system_cache_dir: Path
    system_cache_dir = os.environ.get(site_cache_env_var)  # type: ignore
    if system_cache_dir:
        system_cache_dir = Path(system_cache_dir)
        log.debug(
            f"Env var {site_cache_env_var} is set. "
            "Adding it to the config file search path"
        )
    else:
        system_cache_dir = Path(AppDirs("si-utils").site_data_dir)
    system_cache_dir = system_cache_dir.joinpath(app_name)
    try:
        system_cache_dir.mkdir(parents=True, exist_ok=True)
        return system_cache_dir
    except OSError:
        pass
    user_cache_dir: Path
    user_cache_dir = os.environ.get(user_cache_env_var)  # type: ignore
    if user_cache_dir:
        user_cache_dir = Path(user_cache_dir)
        log.debug(
            f"Env var {user_cache_env_var} is set. "
            "Adding it to the config file search path"
        )
    else:
        user_cache_dir = Path(AppDirs("si-utils").user_cache_dir)
    user_cache_dir = user_cache_dir.joinpath(app_name)
    try:
        user_cache_dir.mkdir(parents=True, exist_ok=True)
        return user_cache_dir
    except OSError:
        raise Exception(
            f"Unable to create or use {user_cache_dir}, "
            f"unable to create or use {system_cache_dir}, "
            f"and '{app_name.upper()}_CACHE_PATH' is either "
            "unspecified or invalid."
        )


def txt(s: str) -> str:
    """
    dedents a triple-quoted indented string, and strips the leading newline.
    Converts this:
    txt('''
        hello
        world
        ''')
    into this:
    "hello\nworld\n"
    """
    return dedent(
        s.lstrip(
            "\n",
        )
    )


def lst(s: str) -> List[str]:
    """
    convert a triple-quoted indented string into a list,
    stripping out '#' comments and empty lines
    Converts this:
    txt('''
        hello # comment in line

        # comment on its own
        world
        ''')
    into this:
    ['hello', 'world']
    """
    # dedent
    s = txt(s)
    # convert to list
    list_ = s.splitlines()
    # strip comments and surrounding whitespace
    list_ = [line.partition("#")[0].strip() for line in list_]
    # strip empty lines
    list_ = list(filter(bool, list_))
    return list_


class Timeit:
    """
    Wall-clock timer for performance profiling. makes it really easy to see
    elapsed real time between two points of execution.

    Example:
        from si_utils.main import Timeit

        # the clock starts as soon as the class is initialized
        timer = Timeit()
        time.sleep(1.1)
        timer.interval() # record an interval
        assert timer.float == 1.1
        assert timer.str == '1.1000s'
        time.sleep(2.5)
        timer.interval()

        # only the time elapsed since the start
        # of the last interval is recorded
        assert timer.float == 2.5
        assert timer.str == '2.5000s'

        # timer.interval() is the same as timer.stop() except it starts a new
        # clock immediately after recording runtime for the previous clock
        time.sleep(1.5)
        timer.stop()


    """

    def __init__(self) -> None:
        self.start = time.perf_counter()

    def stop(self):
        self.now = time.perf_counter()
        self.float = self.now - self.start
        self.str = f"{self.float:.4f}s"
        return self

    def interval(self):
        self.stop()
        self.start = self.now
        return self

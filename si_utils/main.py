"""
The purpose of this module is to store all utilities, functions, and classes
which don't depend on any external packages.
This module can be used even if you don't install any of si-util's extras

"""

import os
import sys
from typing import List, Dict, Any, Optional
from pathlib import Path
import configparser
import json
from textwrap import dedent
import time

from ._vendor.appdirs import AppDirs
from ._vendor.decorator import decorate
from loguru import logger as log
log.disable('si_utils')


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
def get_config_file(app_name: str, level='DEBUG') -> Optional[Path]:
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
    """
    # define common constants
    log.debug(f'Looking for a config file for app name "{app_name}"')
    valid_extensions = ['ini', 'yaml', 'json', 'toml']
    all_conf_files = []
    config_file_names = [f'{app_name}.{ext}' for ext in valid_extensions]

    # handle env vars
    env_var = f'{app_name.upper()}_CONFIG_FILE'
    env_var_file = os.environ.get(env_var)
    if env_var_file:
        log.debug(f'Env var "{env_var}" is set to "{env_var_file}".')
        if Path(env_var_file).exists():
            log.debug(
                f'File "{env_var_file}" exists.')
            return Path(env_var_file)
        else:
            log.debug(f'File "{env_var_file}" does not exist. Skipping it.')
    else:
        log.debug(
            f'Env var "{env_var}" not set. '
            f'Proceeding with normal config file lookup.')
    env_var_path = os.environ.get('SI_UTILS_CONFIG_PATH')
    if env_var_path:
        log.debug(f'Env var "SI_UTILS_CONFIG_PATH" is set to {env_var_path}')
        if Path(env_var_path).is_dir():
            log.debug(
                f'"{env_var_path}" exists. '
                'Adding it to config file search path')
            env_var_path_files = [
                Path(env_var_path).joinpath(name) for name in config_file_names
            ]
            all_conf_files.extend(env_var_path_files)
        else:
            log.debug(f'"{env_var_path}" does not exist. Skipping it.')
    else:
        log.debug(
            'Env var "SI_UTILS_CONFIG_PATH" not set. '
            'Proceeding with normal config file lookup.')

    # handle site config
    site_conf = Path(AppDirs('si-utils').site_config_dir)
    site_conf_files = [site_conf.joinpath(name) for name in config_file_names]
    all_conf_files.extend(site_conf_files)

    # handle user config
    user_conf = Path(AppDirs('si-utils').user_config_dir)
    user_conf_files = [user_conf.joinpath(name) for name in config_file_names]
    all_conf_files.extend(user_conf_files)

    # find conf file
    log.trace(f'Searching for the following config files: {all_conf_files}')
    valid_conf_files = [file for file in all_conf_files if file.exists()]
    if len(valid_conf_files) < 1:
        log.debug(
            f"Could not find a valid config file for app_name {app_name}. "
            f"Searched for files {config_file_names} in folders {site_conf} "
            f"and {user_conf}, found nothing")
        return None
    log.debug(
        f'Found the following config files: {valid_conf_files}.'
        f'Using config file: {valid_conf_files[0]}')
    return valid_conf_files[0]


@cache
def get_config_obj(app_name: str) -> Optional[Dict[str, Any]]:
    """
    Finds a valid config file, loads it into memory, and converts it
    into a dictionary. Can be called multiple times without triggering
    multiple file load / parsing operations
    only .json and .ini config files are currently supported
    keys in .ini files must be stored in the DEFAULT section
    only top-level keys in .json config files are supported
    """
    conf_file = get_config_file(app_name)
    if not conf_file:
        log.debug(f'Could not load config from file for app_name {app_name}')
        return None
    if conf_file.suffix == '.ini':
        log.debug(
            f'Loading configuration object from [DEFAULT] '
            f'section of {conf_file}')
        cfp = configparser.ConfigParser()
        cfp.read(conf_file)
        obj = dict(cfp['DEFAULT'])
    elif conf_file.suffix == '.json':
        log.debug(f'Loading config object from {conf_file}')
        obj = json.loads(conf_file.read_text())
    elif conf_file.suffix == '.toml':
        log.debug(f'Loading config object from {conf_file}')
        vendor_path = Path(__file__).parent.joinpath('_vendor')
        sys.path.append(str(vendor_path))
        import toml
        sys.path.remove(str(vendor_path))
        obj = toml.loads(conf_file.read_text())  # type: ignore
    else:
        log.debug(
            f"Found config file {conf_file}. get_config_key "
            f"does not support config files of type {conf_file.suffix}. "
            "Only .toml, .ini and .json files are supported")
        return None
    return obj  # type: ignore


def get_config_key(app_name: str, key: str):
    """
    simple function to get a key value for a given app_name from
    either an environment variable or a config file
    only .json and .ini config files are currently supported
    keys in .ini files must be stored in the DEFAULT section
    only top-level keys in .json config files are supported
    """
    env_var_name = f'{app_name.upper()}_{key.upper()}'
    env_var = os.environ.get(env_var_name)
    if env_var:
        log.debug(
            f'Env var {env_var_name} is set, using as value instead of '
            'loading config file')
        return env_var

    obj = get_config_obj(app_name)
    if not obj:
        log.debug('Failed to load configuration from file.')
        return None

    val = obj.get(key)
    if not val:
        log.debug(f'Could not find key {key} in config object {obj}')
        return None

    return val


def get_cache_dir(app_name: str) -> Path:
    """
    create and return a cache dir for cache data.
    prefer system-wide data dir, fall back to user cache dir
    """
    env_var_file = os.environ.get(f'{app_name.upper()}_CACHE_PATH')
    if env_var_file:
        try:
            path = Path(env_var_file)
            path.mkdir(parents=True, exist_ok=True)
            return path
        except OSError:
            pass
    system_cache_dir = Path(AppDirs('si-utils').site_data_dir)
    system_cache_dir = system_cache_dir.joinpath(app_name)
    try:
        system_cache_dir.mkdir(parents=True, exist_ok=True)
        return system_cache_dir
    except OSError:
        pass
    user_cache_dir = Path(AppDirs('si-utils').user_cache_dir)
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
    return dedent(s.lstrip('\n', ))


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
    list_ = [line.partition('#')[0].strip() for line in list_]
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
        self.str = f'{self.float:.4f}s'
        return self

    def interval(self):
        self.stop()
        self.start = self.now
        return self

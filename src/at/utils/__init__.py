# flake8: noqa

import os, sys, time, logging, logging.handlers, re, platform
from pathlib import Path
from functools import cached_property
from enum import Enum
from typing import Dict, Any, List, Iterable, Pattern, Tuple, Union
from textwrap import dedent
from getpass import getuser

from loguru import Message, logger
from rich.console import Console
from ._vendor.platformdirs import PlatformDirs
from ._vendor.decorator import decorate

__version__ = '0.4.3'

logger.disable(__name__)  
# loguru best practice is for libraries to disable themselves and 
# for cli apps to re-enable logging on the libraries they use

def memoize(f):
    """
    A simple memoize implementation. It works by adding a .cache dictionary
    to the decorated function. The cache will grow indefinitely, so it is
    your responsibility to clear it, if needed.
    to clear: `memoized_function.cache = {}`
    """
    def _memoize(func, *args, **kw):
        if kw:  # frozenset is used to ensure hashability
            key = args, frozenset(kw.items())
        else:
            key = args
        cache = func.cache  # attribute added by memoize
        if key not in cache:
            logger.trace(f"caching output of function `{func}` with arguments {args} and {kw}")
            cache[key] = func(*args, **kw)
        return cache[key]
    f.cache = {}
    return decorate(f, _memoize)

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
    return dedent(s.lstrip("\n"))

def chomptxt(s: str) -> str:
    """
    dedents a triple-quoted indented string, and replaces all single newlines with spaces.
    replaces as double newlines (\n\n) with single newlines
    Converts this:
    txt('''
        hello
        world

        here's another
        line
        ''')
    into this:
    "hello world\nhere's another line"
    """
    res = dedent(s)
    res = res.replace("\n\n", "[PRESERVEDNEWLINE]")
    res = res.replace("\n", " ")
    res = res.replace("[PRESERVEDNEWLINE]", "\n")
    return res.strip()


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
        from at_utils.main import Timeit

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


class AtUtilsError(Exception):
    pass


class InterceptHandler(logging.Handler):
    "This handler, when attached to the root logger of the python logging module, will forward all logs to Loguru's logger"
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


class StrEnum(str, Enum):
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"

    def __str__(self) -> str:
        return self.name
    
    @classmethod
    def from_str(cls, string):
        for member in cls:
            if str(member) == string:
                return member


class File(StrEnum):
    writable = object()
    readable = object()
    creatable = object()
    unusable = object()

    @classmethod
    def is_writable(cls, f: Path):
        return os.access(f, os.W_OK)

    @classmethod
    def is_readable(cls, f: Path):
        return os.access(f, os.R_OK)

    @classmethod
    def is_creatable(cls, f: Path):
        # a file is createable if it doesn't exist and its parent directory is writable / creatable
        try:
            return (not f.exists()) and (cls.is_writable(f.parent) or cls.is_creatable(f.parent))
        except PermissionError:
            # f.exists() will fail if we don't have execute permission on the file's parent folder.
            # when this happens, the file should be deemed uncreatable
            return False

    @classmethod
    def state(cls, f: Path):
        if cls.is_writable(f):
            return cls.writable
        elif cls.is_readable(f):
            return cls.readable
        elif cls.is_creatable(f):
            return cls.creatable
        else:
            return cls.unusable


class Util:
    """
    Core class for CLI apps to simplify access to config files, cache directories, and logging configuration
    """

    class Logging:

        def __init__(self, parent: 'Util') -> None:
            self.parent = parent

            self.stderr_format = f"<blue>{self.parent.app_name}</> | <level>{{level.name:8}}</>| <bold>{{message}}</>"
            self.syslog_format = f"{self.parent.app_name} | {{name}}:{{function}}:{{line}} - {{level.name: ^8}} | {{message}} | Data: {{extra}}"

        def add_stderr_sink(self, level="INFO", **kwargs): 
            options = dict(
                backtrace=False,
                level=level,
                colorize=True,
                format=self.stderr_format,
            )
            options.update(kwargs)
            logger.add(sys.stderr, **options)

        def add_stderr_rich_sink(self, level="INFO", **kwargs):

            options = dict(
                backtrace=False,
                level=level,
                format=self.stderr_format,
            )
            options.update(kwargs)
            logger.add(self.parent.console.print, **options)

        def add_json_logfile_sink(self, filename = None, level="DEBUG", **kwargs): 
            filename = filename or f"{self.parent.app_name}.log"
            options = dict(
                level=level,
                format="{message}",
                serialize=True, # Convert {message} to a json string of the Message object
                rotation="5MB", # How big should the log file get before it's rolled?
                retention=4, # How many compressed copies to keep?
                compression="zip"
            )
            options.update(kwargs)
            logger.add(filename, **options)

        def add_syslog_sink(self, level="DEBUG", syslog_address = None, **kwargs):
            if platform.system() == 'Windows':
                # syslog configs like level and facility don't apply in windows, 
                # so we set up a basic event log handler instead
                handler = logging.handlers.NTEventLogHandler(appname=self.parent.app_name)
            else:
                # should handle ~90% of unixes
                if syslog_address:
                    pass
                elif Path('/var/run/syslog').exists():
                    syslog_address = '/var/run/syslog' # MacOS syslog
                elif Path('/dev/log').exists():
                    syslog_address = '/dev/log' # Most Unixes?
                else:
                    syslog_address = ('localhost', 514) # Syslog daemon
                handler = logging.handlers.SysLogHandler(address=syslog_address)
                handler.ident = 'at-utils: '

            options = dict(
                level=level,
                format=self.syslog_format
            )
            options.update(kwargs)   
            logger.add(handler, **options)     

        def add_sentry_sink(self, level="ERROR", **kwargs):
            try:
                sentry_dsn = self.parent.get_config_key_or_fail("sentry_dsn")
            except KeyError:
                logger.debug(
                    "`sentry_dsn` option not found in any config file. Sentry logging disabled"
                )
                return None

            try:
                import sentry_sdk # noqa
            except ImportError:
                logger.debug(
                    "the sentry_sdk package is not installed. Sentry logging disabled."
                )
                return None
            # the way we set up sentry logging assumes you have one sentry
            # project for all your apps, and want to group all your alerts
            # into issues by app name

            def before_send(event, hint): # noqa
                # group all sentry events by app name
                if event.get("exception"):
                    exc_type = event["exception"]["values"][0]["type"]
                    event["exception"]["values"][0]["type"] = f"{self.parent.app_name}: {exc_type}"
                if event.get("message"):
                    event["message"] = f'{self.parent.app_name}: {event["message"]}'
                return event

            sentry_sdk.init(
                sentry_dsn, with_locals=True, request_bodies="small", before_send=before_send
            )
            user = {"username": getuser()}
            email = os.environ.get("MY_EMAIL")
            if email:
                user["email"] = email
            sentry_sdk.set_user(user)

            def sentry_sink(msg: Message):
                data = msg.record
                level = data["level"].name.lower()
                exception = data["exception"]
                message = data["message"]
                sentry_sdk.set_context("log_data", data)
                if exception:
                    sentry_sdk.capture_exception()
                else:
                    sentry_sdk.capture_message(message, level)

            logger.add(sentry_sink, level=level, **kwargs)

        def enable(self):
            logger.remove() # remove default handler, if it exists
            logger.enable("") # enable all logs from all modules

            # setup python logger to forward all logs to loguru
            logging.basicConfig(handlers=[InterceptHandler()], level=0)

    def __init__(self, app_name) -> None:
        self.app_name = app_name
        self.dirs = PlatformDirs("at-utils")
        self.common_user_config_dir = Path.home() / '.config/at-utils' 
        self.console = Console(stderr=True)
        self.logging = self.Logging(self)
        # there should be one config path which is common to all OS platforms, 
        # so that users who sync configs betweeen multiple computers can sync 
        # those configs to the same directory across machines and have it *just work*
        # By convention, this path is ~/.config/at-utils
        
    
    #region util
    def get_env_var(self, property):
        "fetches a namespaced environment variable"
        property = property.replace("-", "_")  # property names must have underscores, not dashes
        env_var_name = f"{self.app_name}_{property}".upper()
        res = os.environ.get(env_var_name)
        msg = f"Environment variable '{env_var_name}' for property '{property}'"
        if res:
            logger.trace(f"{msg} is set to '{res}'")
        else:
            logger.trace(f"{msg} is not set")
        return res

    def _clear_caches(self):
        try:
            del self.config_files
        except AttributeError:
            pass
        try:
            del self.merged_config_data
        except AttributeError:
            pass

    #endregion util
    #region config
    def config_dirs_generator(self):
        """generate a list of folders in which to look for config files

        Yields:
            Path: config file directories, yielded in order of priority from high to low

        Note:
            config files from high-priority directory should be selected first.
            priority list (low to high):
            - default os-specific site config folder (/etc/xdg/at-utils/ on Linux, /Library/Application Support/at-utils/ on OSX, etc)
            - directory pointed to by {self.app_name}_SITE_CONFIG environment variable if set
            - cross-platform user config folder (~/.config/at-utils/ on all operating systems)
            - default os-specific user config folder (~/.config/at_utils on Linux, ~/Library/Application Support/at-utils/ on OSX, etc)
            - directory pointed to by {self.app_name}_USER_CONFIG environment variable if set

        """
        # Site dirs
        if custom_site_config := self.get_env_var("site_config"):
            logger.trace(f"Using {custom_site_config} as site config directory")
            yield Path(custom_site_config)
        else:
            yield self.dirs.site_config_path
        
        # User dirs
        yield self.common_user_config_dir

        if custom_user_config := self.get_env_var("user_config"):
            logger.trace(f"Using {custom_user_config} as user config directory")
            yield Path(custom_user_config)
        elif (user_config := self.dirs.user_config_path) != self.common_user_config_dir:
            # yield user_config, but only if it's different than cross-platform user config
            # if you're on linux, these two will be the same. no sense yielding the same path twice
            yield user_config
        

    def config_files_generator(self):
        """
        Generates a set of config files that may or may not exist, 
        in descending order (from lowest to highest priority).

        Example:
            given self.app_name = example,
            and os = MacOS,
            and user = 'alex'
            this method would yield the following:

            - (PosixPath('/Library/Preferences/at-utils/shared.ini'), File.unusable)
            - (PosixPath('/Library/Preferences/at-utils/shared.yaml'), File.unusable)
            - (PosixPath('/Library/Preferences/at-utils/shared.json'), File.unusable)
            - (PosixPath('/Library/Preferences/at-utils/shared.toml'), File.unusable)
            - (PosixPath('/Library/Preferences/at-utils/example.ini'), File.unusable)
            - (PosixPath('/Library/Preferences/at-utils/example.yaml'), File.unusable)
            - (PosixPath('/Library/Preferences/at-utils/example.json'), File.unusable)
            - (PosixPath('/Library/Preferences/at-utils/example.toml'), File.unusable)
            - (PosixPath('/Users/alex/.config/at-utils/shared.ini'), File.creatable)
            - (PosixPath('/Users/alex/.config/at-utils/shared.yaml'), File.creatable)
            - (PosixPath('/Users/alex/.config/at-utils/shared.json'), File.creatable)
            - (PosixPath('/Users/alex/.config/at-utils/shared.toml'), File.creatable)
            - (PosixPath('/Users/alex/.config/at-utils/example.ini'), File.creatable)
            - (PosixPath('/Users/alex/.config/at-utils/example.yaml'), File.creatable)
            - (PosixPath('/Users/alex/.config/at-utils/example.json'), File.creatable)
            - (PosixPath('/Users/alex/.config/at-utils/example.toml'), File.creatable)
            - (PosixPath('/Users/alex/Library/Preferences/at-utils/shared.ini'), File.creatable)
            - (PosixPath('/Users/alex/Library/Preferences/at-utils/shared.yaml'), File.creatable)
            - (PosixPath('/Users/alex/Library/Preferences/at-utils/shared.json'), File.creatable)
            - (PosixPath('/Users/alex/Library/Preferences/at-utils/shared.toml'), File.creatable)
            - (PosixPath('/Users/alex/Library/Preferences/at-utils/example.ini'), File.creatable)
            - (PosixPath('/Users/alex/Library/Preferences/at-utils/example.yaml'), File.creatable)
            - (PosixPath('/Users/alex/Library/Preferences/at-utils/example.json'), File.creatable)
            - (PosixPath('/Users/alex/Library/Preferences/at-utils/example.toml'), File.creatable)

        """
        def file_names():
            for basename in ['shared', self.app_name]:
                for ext in ["ini", "yaml", "json", "toml"]:
                    yield f"{basename}.{ext}"
        
        for dir in self.config_dirs_generator():
            for name in file_names():
                file = dir / name
                yield file, File.state(file)


    @cached_property
    def config_files(self): 
        res = list(self.config_files_generator())
        logger.bind(list=res).trace(f"Caching list of config files: ")
        return res

    @property
    def readable_config_files(self):
        return [file for file, state in self.config_files if state in [File.readable, File.writable]]

    @property
    def writable_config_files(self):
        return [file for file, state in self.config_files if state == File.writable]

    def get_config_file_or_fail(self):
        """
        Find a valid config file.
        File can be stored in a site-wide directory (ex. /etc/xdg/at-utils)
        or a user-local directory (ex. ~/.config/at-utils)
        File must have basename matching either the `app_name` attribute of this class, or the word "shared"
        File must have one of the following extensions: ['.ini', '.yaml', '.json', '.toml']
        If an environment variable like {self.app_name}_CONFIG_FILE exists and points
        to a file that exists, that file will be returned instead of any file in any of the above directories.

        Raises:
            AtUtilsError: if no valid config file found
        """
        if custom_config_file := self.get_env_var("config_file"):
            logger.trace(f"Skipping normal config file lookup, using {custom_config_file} as configuration file")
            return Path(custom_config_file)
        # else:
        try:
            # self.readable_config_files lists files from lowest priority to highest.
            # Since we're only fetching one file (not merging),
            # we want to grab the highest-priority file only.
            files = self.readable_config_files
            last_file = files[-1]
            logger.trace(f"selecting config file {last_file} from available config files {files}")
            return last_file
        except IndexError:
            raise AtUtilsError(chomptxt(f"""
                Could not find a valid config file for application {self.app_name} 
                from any of: {[f for f, _ in self.config_files]}
                """))

    def parse_config_file(self, file: Path):
        obj: Dict[str, Any]
        if file.suffix == ".ini":
            import configparser # noqa
            cfp = configparser.ConfigParser()
            cfp.read(file)
            obj = dict(cfp["_common_"])
            for sect in cfp.sections():
                if sect != '_common_':
                    obj[sect] = dict(cfp[sect])
        elif file.suffix == ".json":
            import json # noqa
            obj = dict(json.loads(file.read_text()))
        elif file.suffix == ".toml":
            from ._vendor import toml
            obj = dict(toml.loads(file.read_text()))
        elif file.suffix == ".yaml":
            from ._vendor.yaml import YAML
            yaml = YAML(typ="safe")
            obj = dict(yaml.load(file))
        else:
            raise AtUtilsError(
                chomptxt(f"""Failed to parse {file}. 
                `{self.__class__.__name__}.parse_config_file()` 
                does not support config files of type {file.suffix}.
                Only .ini, .json, .toml, and .yaml files are supported""")
            )
        return obj

    def get_config_object_or_fail(self):
        """
        Finds a valid config file, loads it into memory, and converts it
        into a dictionary. 
        only .json, .ini, .toml, and .yaml config files are currently supported
        for .ini files, keys in the _common_ section will be 'hoisted' so that they become
        keys of the top level dictionary returned.

        raises:
            AtUtilsError: if, somehow, the config file handed to this method has an invalid format
        """
        conf_file = self.get_config_file_or_fail()
        logger.debug(f"Loading config object from {conf_file}")
        return self.parse_config_file(conf_file)

    def get_config_key_or_fail(self, key: str):
        """
        simple method to get a value from the config file for a given key

        Args:
            key: top-level key to retrieve from a parsed dictionary loaded from config file

        Raises:
            KeyError: if the given key couldn't be found in the config file
            AtUtilsError: any exception raised by self.get_config_obj_or_fail
        """
        if custom_key := self.get_env_var(key):
            logger.trace(f"Found environment variable override for config option {key}, using its value instead of pulling from config file")
            return custom_key
        # else:
        obj = self.get_config_object_or_fail()

        val = obj.get(key)
        if not val:
            raise KeyError(f"Could not find key {key} in config object {obj}")

        logger.debug(f"Found key {key} in config object")
        return val

    @cached_property
    def merged_config_data(self) -> Dict[str, Any]:
        data = {}
        for file in self.readable_config_files:
            logger.debug(f"Loading config data from {file}")
            data.update(self.parse_config_file(file))
        return data
    #endregion config
    #region cache

    @property
    def cache_dir(self):
        """
        Fetches the site-wide cache directory for {self.app_name} if available
        or the user-local cache directory for {self.app_name} as a fall-back.
        If a given directory does not exist but can be created, it will be created and returned.
        If an environment variable like {self.app_name}_SITE_CACHE exists and points
        to a directory that exists, that directory will be returned.
        If an environment variable like {self.app_name}_USER_CACHE exists and points
        to a directory that exists, and no valid site-wide cache directory was found, 
        that directory will be returned.
        """

        # Site dir
        site_cache = self.dirs.site_data_path.joinpath(self.app_name)
        if custom_site_cache := self.get_env_var("site_cache"):
            logger.trace(f"using {custom_site_cache} as site cache directory")
            return Path(custom_site_cache)
        # else:
        try:
            site_cache.mkdir(parents=True, exist_ok=True)
            return site_cache 
        except OSError:
            pass
        
        # User dir
        user_cache = self.dirs.user_cache_path.joinpath(self.app_name)
        if custom_user_cache := self.get_env_var("user_cache"):
            logger.trace(f"using {custom_user_cache} as user cache directory")
            return Path(custom_user_cache)
        # else:
        try:
            user_cache.mkdir(parents=True, exist_ok=True)
            return user_cache
        except OSError:
            raise AtUtilsError(chomptxt(f"""
                Neither site-wide cache directory ({site_cache}) nor 
                user-local cache directory ({user_cache}) exists, 
                and neither directory can be created.
                """))
    
    #endregion cache
#region logging





#endregion logging

        
class NestedData:
    """
    A collection of functions for working with nested data structures
    """

    UnStructuredData = Iterable[Tuple[str, Any]]
    RegexOrString = Union[str, Pattern[str]]

    @classmethod
    def unstructure(cls, data: Any) -> UnStructuredData:
        """
        Takes a data structure composed of arbitrarily nested dicts and lists, 
        and breaks it down into a list of 2-tuples where the second element is a value, 
        and the first element is a dotted string representing the datastructure path to that value.

        Args:
            data (Union[dict, list]): 
                The nested data structure to unstructure. 
                Can be a list or dict containing lists or dicts, to an almost infinite depth.

        Returns:
            List[Tuple[str, Any]]: 
                a list of 2-tuples representing "leaf node" elements 
                from the datastructure, and their keypaths.
        """
        if isinstance(data, list):
            for index, item in enumerate(data):
                keyname = f'[{index}]'
                for keypath, value in cls.unstructure(item):
                    if keypath:
                        keypath = f'{keyname}.{keypath}'
                    else:
                        keypath = keyname
                    yield keypath, value
        elif isinstance(data, dict):
            for key, item in data.items():
                if not isinstance(key, str):
                    raise Exception("This function only supports dictionaries whose keys are strings")
                if " " in key:
                    # key contains spaces, and must be escaped
                    keyname = f'"{key}"'
                else:
                    keyname = key
                for keypath, value in cls.unstructure(item):
                    if keypath:
                        keypath = f'{keyname}.{keypath}'
                    else:
                        keypath = keyname
                    yield keypath, value
        else:
            # We've reached a leaf node in the data structure. return a falsy value as keypath so that previous 
            # recursion uses its own keypath as the final keypath
            yield "", data

    @classmethod
    def restructure(cls, data: UnStructuredData) -> Any:
        """
        Takes a list of 2-tuples where the second element is a value, 
        and the first element is a dotted string representing the datastructure path to that value,
        and reconstructs a nested datastructure from that information

        Args:
            data (List[Tuple[str, Any]]): 
                a list of 2-tuples representing "leaf node" elements 
                from the datastructure, and their keypaths.

        Returns:
            Union[dict, list]: 
                The nested data structure, reconstructed. 
                Can be a list or dict containing lists or dicts, to an almost infinite depth.
        """
        

        # The first thing we want to do is group items from the list based on the first element of their keypath. 
        # All items sharing a common first element of a keypath belong to the same nested dict/list
        root_names: Dict[str, Any] = {}
        for keypath, value in data:
            key, _, keypath = keypath.partition('.')

            if key not in root_names:
                root_names[key] = []
            root_names[key].append((keypath, value))
        
        # Now, to reconstruct the object. The keys in root_names can either be all strings 
        # (meaning this object is a dict), or they can all strings of the pattern '[#]' 
        # representing list indices, or they can be blank, meaning we've reached "leaf nodes" in the data tree.
        # in order to figure out which object to reconstruct, 
        # we need to know what kind of keys we're dealing with
        if len(root_names) == 1 and list(root_names.keys())[0] == '':
            # We've reached a "leaf node"
            return root_names[''][0][1]

        def is_index_key(k: str) -> bool:
            return k.startswith('[') and k.endswith(']') and k[1:-1].isdecimal()

        if all([is_index_key(key) for key in root_names]):
            # All keys match the pattern for index keys (numbers wrapped in square brackets)
            result = []
            for value in root_names.values():
                r = cls.restructure(value)
                result.append(r)
        else:
            # This is a dict
            result = {}
            for key, value in root_names.items():
                r = cls.restructure(value)
                result[key] = r
        return result

    @classmethod
    def _compile_keys_if_needed(cls, from_key: str, to_key: str = '') -> Tuple[RegexOrString, str]:
        new_key1, new_key2 = from_key, to_key
        if '*' in new_key1:
            # This is a wildcard match and replace
            # in order to do a wildcard match, we need to convert the from_key string into a regex pattern, 
            # and replace the escaped shell-style '*' wildcards with regex-style '.*' wildcards
            # we need to escape this string first so that legitimate characters in it (like '[' and ']') aren't
            # interpreted as regex symbols
            new_key1 = re.escape(new_key1).replace('\\*', '(.*)')
            new_key1 = re.compile(new_key1)
            # we also need to convert to_key into a regex replace string (replace the '*' wildcard symbols 
            # with capture group backreferences '\#')
            # this part's a little bit trickier, since each such instance must be enumerated and assigned an index
            occurences = new_key2.count('*')
            for i in range(occurences):
                ref = i+1
                new_key2 = new_key2.replace('*', f'\\{ref}', 1)
        return new_key1, new_key2

    @classmethod
    def remap(cls, data: UnStructuredData, key_map: List[Tuple[str, str]]) -> UnStructuredData:
        result = list(data)
        for from_key, to_key in key_map:
            from_key, to_key = cls._compile_keys_if_needed(from_key, to_key)
            for index, tup in enumerate(result):
                key, value = tup
                if isinstance(from_key, Pattern): # noqa
                    #do a regex substitution
                    new_key = re.sub(from_key, to_key, key)
                else:
                    # do a regular substitution
                    new_key = key.replace(from_key, to_key)
                result[index] = new_key, value
        return result

    @classmethod
    def filter_(cls, data: UnStructuredData, key_list: List[str]) -> UnStructuredData:
        def test(pattern, tup):
            if isinstance(pattern, Pattern): # noqa
                return bool(re.match(pattern, tup[0]))
            # else:
            return bool(pattern in tup[0])
        
        filters_list = [cls._compile_keys_if_needed(key)[0] for key in key_list]

        for tup in data:
            # yield tup if it matches any of the filters
            if any([test(pat, tup) for pat in filters_list]):
                yield tup
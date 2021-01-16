__version__ = '0.1.1'

from .main import *  # noqa
from .log import configure_logging

# TODO: add logging to get_cache_dir

if __name__ == "__main__":
    import os
    if os.environ.get('PYDEBUG'):
        # we're in a debugger session
        from . import main
        configure_logging('test', 'DEBUG', None, None)
        main.get_config_key('test', 'key')
        main.get_cache_dir('test')
        exit()
    try:
        pass  # cli code goes here
    except KeyboardInterrupt:
        print("Aborted!")
        exit()

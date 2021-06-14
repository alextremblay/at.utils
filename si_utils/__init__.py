__version__ = '0.1.1'

from .main import *  # noqa
from .log import configure_logging # noqa

# TODO: add logging to get_cache_dir

if __name__ == "__main__":
    import os, sys # noqa
    if os.environ.get('PYDEBUG'):
        # we're in a debugger session
        from . import dev_utils # noqa
        #sys.argv = [__file__, 'minor']
        dev_utils.bump_version()
        sys.exit()
    try:
        pass  # cli code goes here
    except KeyboardInterrupt:
        print("Aborted!")
        sys.exit()

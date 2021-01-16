# About

This package contains a set of utilities useful for building python libraries, scripts, and command-line utilities

It's designed to be easy to include in other projects. all of its mainline dependencies are vendored and all modules which have external un-vendorable dependencies are available as optional extras

# Install

```
pip install si-utils
```

To make use of optional extras, like the yaml module or the log module:

```
pip install si-utils[yaml] # or si-utils[log], or si-utils[yaml,log]
```

# Usage

This toolkit makes it really easy to write small, simple, well designed CLI utilities
In fact, the aim of this project is to make well-engineered CLIs almost as easy to write and deploy as basic python scripts
it leverages a lot of really fantastic modern libraries and tools to do so, like *poetry*, *typer*, and *loguru*

let's assume you've created a new project with `poetry new`, and you want to add a CLI interface to it. here's one way to do that:
create a `__main__.py` file in your package like so:
```
import os

from .common import my_super_awesome_function

from si_utils.main import ...
from si_utils.log import configure_logging
import typer
from loguru import logger

app = typer.Typer()


@app.callback()
def callback(verbose: bool = False):
    """
    Here is my app's main help string
    """
    log_level = 'DEBUG' if verbose else 'INFO'
    configure_logging(
        'my_app_name', 
        stderr_level=log_level, 
        logfile_level='DEBUG', 
        sentry_level=None)


@app.command()
def my_command(option: bool):
    logger.debug("running my-command")  # this will only get printed if the --verbose flag is set
    my_super_awesome_function(option)


if __name__ == "__main__":
    if os.environ.get('PYDEBUG'):
        # we're in a debugger session
        #here we can put whatever debugging code we want
        # we can configure logging so all messages up to DEBUG are logged to stderr, and nothing gets logged to file:
        configure_logging('my_app_name', 'DEBUG', None, None)
        # do debugging stuff here
        logger.debug("I'm a debug message!")
        exit()
    try:
        pass  # cli code goes here
    except KeyboardInterrupt:
        print("Aborted!")
        exit()

```

the main api (all the stuff directly importable from `si_utils`) consists of:
- every function defined in the `main` module
- the `configure_logging` function from the `log` module

apart from that, there are other modules which can be imported separately:

`yaml` has a whole bunch of useful and sometimes esoteric utilities for working with yaml files, built on top of `ruamel.yaml`

`dev_utils` has commmand-line utilities for working with python projects, specifically made for projects that use `poetry`
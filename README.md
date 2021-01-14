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

```
from si_utils.main import ...

from si_utils.log import ...
```

`main` is the ... main ... module in this package. it's chock-full of handy-dandy functions

`log` contains some very useful functions for getting up and running with logging (especially thanks to `loguru`)

`yaml` has a whole bunch of useful and sometimes esoteric utilities for working with yaml files, built on top of `ruamel.yaml`

`dev_utils` has commmand-line utilities for working with python projects, specifically made for projects that use `poetry`
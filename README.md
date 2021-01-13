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


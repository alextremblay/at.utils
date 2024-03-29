# coding: utf-8

import warnings

from .util import configobj_walker as new_configobj_walker

from typing import TYPE_CHECKING
if TYPE_CHECKING:  # MYPY
    from typing import Any  # NOQA


def configobj_walker(cfg):
    # type: (Any) -> Any
    warnings.warn('configobj_walker has moved to ruamel.yaml.util, please update your code')
    return new_configobj_walker(cfg)

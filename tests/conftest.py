

import os
import pytest

pytest_plugins = ['at.utils.fixtures']

if os.getenv('_PYTEST_RAISE', "0") != "0":
    # set up hooks for VSCode debugger to break on exceptions
    @pytest.hookimpl(tryfirst=True)
    def pytest_exception_interact(call):
        raise call.excinfo.value

    @pytest.hookimpl(tryfirst=True)
    def pytest_internalerror(excinfo):
        raise excinfo.value
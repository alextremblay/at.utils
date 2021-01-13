try:
    import tomlkit
except ImportError:
    raise ImportError(
        "In order to use this module, the si-utils package must be installed "
        "with the 'dev-utils' extra (ex. `pip install si-utils[dev-utils]")


def bump_version():
    """
    bump a project's version number.
    bumps the __version__ var in the project's __init__.py
    bumps the version in pyproject.toml
    tags the current git commit with that version number
    """
    # Changes not staged for commit
    # Untracked files:
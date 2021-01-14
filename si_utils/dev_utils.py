from subprocess import run, PIPE
import sys
from pathlib import Path

try:
    import tomlkit
    import semver
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
    if len(sys.argv) < 2:
        bump_type = 'patch'
    else:
        bump_type = sys.argv[1]
    if bump_type not in ['major', 'minor', 'patch', 'prerelease', 'build']:
        print(f'invalid bump_type {bump_type}')
        exit()
    git_status = run(['git', 'status'], stdout=PIPE).stdout.decode()
    if 'nothing to commit, working tree clean' not in git_status:
        print(
            'git working tree not clean. aborting. run `git status` and commit'
            ' or ignore all outstanding files, then try again.')
    pyproject = tomlkit.parse(Path('pyproject.toml').read_text())
    package_name = pyproject['tool']['poetry']['name']  # type: ignore
    old_version = pyproject['tool']['poetry']['version']  # type: ignore
    version = semver.VersionInfo.parse(old_version)
    # for every bump_type in the list above, there is a bump_{type} method
    # on the VersionInfo object. here we look up the method and call it
    # ex if bump_type is 'patch', this will call version.bump_patch()
    version = getattr(version, f'bump_{bump_type}')()
    new_version = str(version)
    pyproject['tool']['poetry']['version'] = new_version  # type: ignore
    init_file = Path(f'{package_name}/__init__.py')
    init_text = init_file.read_text()
    init_text.replace(
        f"__version__ = '{old_version}'", f"__version__ = '{new_version}'")
    
    # no turning back now!
    Path('pyproject.toml').write_text(tomlkit.dumps(pyproject))
    init_file.write_text(init_text)
    run(['git', 'add', '.'])
    run([
        'git', 'commit', '-m',
        f'bump version from {old_version} to {new_version}'
    ])
    run([
        'git', 'tag', '-s', '-a', new_version, '-m', f'version {new_version}'
    ])
    print('done')

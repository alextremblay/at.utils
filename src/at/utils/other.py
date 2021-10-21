"""
This module stores a random assortment of functions and utilities which require 
additinal dependencies not included in 
"""

import re
import sys
from subprocess import run, PIPE
from pathlib import Path
from types import ModuleType
import inspect

from . import memoize

from typing import Iterator, List, Optional, Sequence, Tuple, Union, Pattern, cast, TYPE_CHECKING
if TYPE_CHECKING:
    from ._vendor.yaml import CommentedMap, CommentedSeq
    from pydantic import BaseModel

KeyPath = str
Val = str
Comment = Optional[str]
YamlValue = Tuple[KeyPath, Val, Comment]


def re_partition(regex: Pattern, s: str):
    match = regex.search(s)
    if match:
        return s[:match.start()], s[slice(*match.span())], s[match.end():]
    # else:
    return (s, '', '')


def re_rpartition(regex: Pattern, s: str):
    # find the last match, or None if not found
    match = None
    for match in regex.finditer(s):
        pass
    if match:
        return s[:match.start()], s[slice(*match.span())], s[match.end():]
    # else:
    return ('', '', s)


def get_comment(
        obj: Union['CommentedSeq', 'CommentedMap'], 
        key: Optional[Union[str, int]] = None
        ) -> Optional[str]: # noqa
    """
    Take a yaml object, and fetch comments from it. if a key is provided,
    fetch the comment associated with that key
    (str for mappings, int for sequences).
    if no key is provided, fetch the comment associated with the object itself
    if no comment can be found, return None
    """
    from ._vendor.yaml import CommentedMap, CommentedSeq, CommentToken
    if not isinstance(obj, (CommentedMap, CommentedSeq)):
        return None
    if key is None:
        comment_list = obj.ca.comment
        # here comment_list can either be None or a list
        comment_list = comment_list if comment_list else []
    else:
        comment_list = obj.ca.items.get(key, [None])
        # the values of the ca.items dict are always lists of 4 elements,
        # one of which is the comment token, the rest are None.
        # which of the 4 elements is the
        # CommentToken changes depending on... something?
        # so we'll jsut filter the list looking for the first comment token
    comment_list = [token for token in comment_list if token]
    comment_list = cast(Optional[List[CommentToken]], comment_list)
    if comment_list:
        return comment_list[0].value.partition('#')[2].strip()
    # else:
    return None


def flatten_yaml(s: Union['CommentedMap', str], sep) -> Iterator[YamlValue]:
    """
    generator, iterates over a yaml document, yielding 3-tuples for each value.
    each tuple consists of (keypath, val, comment or None)
    keys in the key path are separated by `sep`
    if `s` is a str, it will be parsed as a yaml document
    """
    # unfinished
    raise NotImplementedError


def unflatten_yaml(data: Sequence[YamlValue]):
    """
    Takes a sequence of 3-tuples representing a yaml document,
    and constructs a new yaml document from them
    """
    # unfinished
    raise NotImplementedError


def add_comments_to_yaml_doc(doc: str, model: 'BaseModel', indent=0):
    from pydantic.fields import ModelField
    for field in model.fields.values():  # type: ignore
        field: ModelField
        desc = field.field_info.description
        if desc:
            # we need to split the doc into 3 parts: the line containing the
            # alias this description belongs to, all preceeding lines, and all
            # following lines. To do this, we're going to regex partition the
            # document
            pattern = re.compile(
                fr'^ {{{indent}}}{field.alias}:.*$',
                re.MULTILINE
            )
            pre, match, rest = re_partition(pattern, doc)
            if len(desc) > 30:
                indent_spc = indent * ' '

                # comment before line, preceeded by blank line
                comment = f'\n{indent_spc}# {desc}\n'
                doc = ''.join([pre, comment, match, rest])
            else:
                comment = f'  # {desc}'  # comment at end of line
                doc = ''.join([pre, match, comment, rest])
        if issubclass(field.type_, BaseModel):
            submodel = model.__getattribute__(field.name)
            doc = add_comments_to_yaml_doc(doc, submodel, indent+2)
    return doc


def model_to_yaml(model: 'BaseModel'):
    from ._vendor.yaml import dumps
    doc = dumps(model.dict(by_alias=True))
    # Now to add in the comments.
    doc = add_comments_to_yaml_doc(doc, model)
    return doc


def bump_version():
    """
    bump a project's version number.
    bumps the __version__ var in the project's __init__.py
    bumps the version in pyproject.toml
    tags the current git commit with that version number
    """
    import argparse
    from ._vendor import tomlkit
    import semver  # type: ignore
    semver_bump_types = ["major", "minor", "patch", "prerelease", "build"]
    parser = argparse.ArgumentParser()
    parser.add_argument('bump_type', choices=semver_bump_types, default="patch", nargs='?')
    parser.add_argument('--no-sign', action='store_true', help="don't force signed commits")
    parser.add_argument(
        '--ignore-status', action='store_true', 
        help="ignore output of git status, proceed with unclean directory tree"
    )
    args = parser.parse_args()
    if not args.ignore_status:
        git_status = run(["git", "status"], stdout=PIPE, check=True).stdout.decode()
        if "nothing to commit, working tree clean" not in git_status:
            print(
                "git working tree not clean. aborting. run `git status` and commit"
                " or ignore all outstanding files, then try again."
            )
            sys.exit(1)
    pyproject = tomlkit.parse(Path("pyproject.toml").read_text())
    package_name = pyproject["tool"]["poetry"]["name"]  # type: ignore
    old_version = pyproject["tool"]["poetry"]["version"]  # type: ignore
    version = semver.VersionInfo.parse(old_version)
    # for every bump_type in the list above, there is a bump_{type} method
    # on the VersionInfo object. here we look up the method and call it
    # ex if bump_type is 'patch', this will call version.bump_patch()
    version = getattr(version, f"bump_{args.bump_type}")()
    new_version = str(version)
    pyproject["tool"]["poetry"]["version"] = new_version  # type: ignore
    init_file = Path(f"{package_name}/__init__.py")
    init_text = init_file.read_text()
    ver_strings_in_init_text = list(filter(lambda l: '__version__ =' in l, init_text.splitlines()))
    if len(ver_strings_in_init_text) > 0:
        old_ver_string = ver_strings_in_init_text[0]
        init_text = init_text.replace(
            old_ver_string, f"__version__ = '{new_version}'"
        )

    # no turning back now!
    Path("pyproject.toml").write_text(tomlkit.dumps(pyproject))
    init_file.write_text(init_text)
    run(["git", "add", "."], check=True)
    run(
        ["git", "commit", "-m", f"bump version from {old_version} to {new_version}"],
        check=True,
    )
    if args.no_sign:
        sign = ""
    else:
        sign = "-s"
    run(
        ["git", "tag", sign, "-a", new_version, "-m", f"version {new_version}"],
        check=True,
    )
    print("done")


def clear_caches(module: ModuleType):
    """
    clear all caches in a given module

    clear the caches of all cached functions and all cached classmethods
    and staticmethods of all classes in a given module
    """

    def get_cachables():
        # functions
        for _, function_ in inspect.getmembers(module, inspect.isfunction):
            yield function_

        for _, class_ in inspect.getmembers(module, inspect.isclass):
            # static methods
            for _, static_method in inspect.getmembers(class_, inspect.isfunction):
                yield static_method

            # class methods
            for _, class_method in inspect.getmembers(class_, inspect.ismethod):
                yield class_method

    for cacheable in get_cachables():
        if hasattr(cacheable, "cache"):
            cacheable.cache = {}

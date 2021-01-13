from io import StringIO
from typing import Iterator, Optional, Sequence, Tuple, Union, Pattern
from functools import lru_cache
import re

try:
    import ruamel.yaml
    from ruamel.yaml.comments import CommentedMap, CommentedBase
    # from ruamel.yaml.tokens import CommentToken
    from deepmerge import always_merger as merger
    # from boltons.iterutils import remap
    from pydantic import BaseModel
except ImportError:
    raise ImportError(
        "In order to use this module, the si-utils package must be "
        "installed with the 'log' extra (ex. `pip install si-utils[log]")


KeyPath = str
Val = str
Comment = Optional[str]
YamlValue = Tuple[KeyPath, Val, Comment]


def re_partition(regex: Pattern, s: str):
    match = regex.search(s)
    if match:
        return s[:match.start()], s[slice(*match.span())], s[match.end():]
    else:
        return (s, '', '')


def re_rpartition(regex: Pattern, s: str):
    # find the last match, or None if not found
    match = None
    for match in regex.finditer(s):
        pass
    if match:
        return s[:match.start()], s[slice(*match.span())], s[match.end():]
    else:
        return ('', '', s)


@lru_cache()
def yaml():
    y = ruamel.yaml.YAML()
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def to_yaml(data) -> str:
    stream = StringIO()
    yaml().dump(data, stream)
    return stream.getvalue()


def from_yaml(s: str) -> CommentedMap:
    return yaml().load(s)


def deep_merge_yaml(s: str, data):
    "Take a yaml document as a string, load it, merge updated data into it"
    # merger merges data from right object into left object.
    # In order to ensure this function can be used repeatedly,
    # it only accepts a yaml doc as string, parses it into a new object,
    # and then merges `data` into it
    doc: CommentedMap = from_yaml(s)
    merger.merge(doc, data)
    return doc


def get_comment(obj: CommentedBase, key: Optional[str] = None) -> Optional[str]: # noqa
    """
    Take a yaml object, and fetch comments from it. if a key is provided,
    fetch the comment associated with that key
    (str for mappings, int for sequences).
    if no key is provided, fetch the comment associated with the object itself
    if no comment can be found, return None
    """
    if not isinstance(obj, CommentedBase):
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
    if comment_list:
        return comment_list[0].value.partition('#')[2].strip()
    else:
        return None


def flatten_yaml(s: Union[CommentedMap, str], sep) -> Iterator[YamlValue]:
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


def add_comments_to_yaml_doc(doc: str, model: BaseModel, indent=0):
    for field in model.fields.values():
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


def model_to_yaml(model: BaseModel):
    doc = to_yaml(model.dict(by_alias=True))
    # Now to add in the comments.
    doc = add_comments_to_yaml_doc(doc, model)
    return doc

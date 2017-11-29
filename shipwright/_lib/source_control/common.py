from __future__ import absolute_import

import fnmatch
import os.path
import re
from collections import namedtuple


AUTO = 'AUTO'
GIT = 'GIT'
HG = 'HG'

SOURCE_CONTROL = [
    ('.git', GIT),
    ('.hg', HG)
]


class SourceControl(object):
    def __init__(self, path, namespace, name_map):
        self.path = path
        self._repo = None
        self._namespace = namespace
        self._name_map = name_map

    def _dirty_suffix(self, base_paths=['.']):
        raise NotImplementedError()

    def _hash_blob(self, blob):
        raise NotImplementedError()

    def _hash_blobs(self, blobs):
        raise NotImplementedError()

    def _in_paths(self, repo_wd, base_paths, path):
        wd = repo_wd
        p = _abspath(repo_wd, path)

        for base_path in base_paths:
            path_pattern = _abspath(wd, base_path)
            if not re.match('[*?]', path_pattern):
                if p == path_pattern:
                    return True
                extra = '*' if path_pattern.endswith(os.sep) else os.sep + '*'
                path_pattern += extra

            if fnmatch.fnmatch(p, path_pattern):
                return True
        return False


class SourceControlNotFound(Exception):
    def __init__(self):
        possible_values = ', '.join([x for x, _ in SOURCE_CONTROL])
        msg = 'Cannot find directory in {}'.format(possible_values)
        super(SourceControlNotFound, self).__init__(msg)


_Target = namedtuple('Target', ['image', 'ref', 'children'])


class Target(_Target):
    @property
    def name(self):
        return self.image.name

    @property
    def short_name(self):
        return self.image.short_name

    @property
    def parent(self):
        return self.image.parent

    @property
    def path(self):
        return self.image.path


del _Target


def _image_parents(index, image):
    while image:
        yield image
        image = index.get(image.parent)


def _abspath(repo_wd, path):
    return os.path.abspath(os.path.join(repo_wd, path))


def get_mode(path):
    for scm_dir, mode in SOURCE_CONTROL:
        if os.path.isdir(os.path.join(path, scm_dir)):
            return mode
    raise SourceControlNotFound()


def source_control(path, namespace, name_map, mode=None):
    if mode is None:
        mode = AUTO
    the_mode = mode if mode is not AUTO else get_mode(path)
    for cls in SourceControl.__subclasses__():
        if cls.mode is the_mode:
            return cls(path, namespace, name_map)

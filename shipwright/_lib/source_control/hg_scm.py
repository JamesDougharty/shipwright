import binascii
import hashlib

import hglib

from common import SourceControl
from common import HG, _image_parents, Target
from shipwright._lib import image


class HgBlob(object):

    def __init__(self, a_blob, b_blob):
        self.a_blob = a_blob
        self.b_blob = b_blob

    def __repr__(self):
        return 'HgBlob {} {}'.format(self.a_blob, self.b_blob)


class HgSourceControl(SourceControl):
    mode = HG

    def __init__(self, path, namespace, name_map):
        super(HgSourceControl, self).__init__(path, namespace, name_map)
        self._repo = hglib.open(path)

    def _hash_blob(self, blob):
        return 'hash({})'.format(blob)

    def _hash_blobs(self, blobs):
        return [('path', self._hash_blob(b)) for b in blobs if b]

    def last_commit(self):
        return self._repo.log()[0]

    def untracked_files(self):
        return [f for c, f in self._repo.status() if c in ['?']]

    def is_dirty(self):
        repo = self._repo
        dirty = False
        for c, f in repo.status():
            if c not in ['?']:
                print('{} {} has been modified'.format(c, f))
                dirty = True
        return dirty

    def diff_blobs(self):
        a_blob_lines = []
        b_blob_lines = []
        for d in self._repo.diff().splitlines():
            if d.startswith('diff'):
                if a_blob_lines or b_blob_lines:
                    yield HgBlob(a_blob_lines, b_blob_lines)
                    a_blob_lines = []
                    b_blob_lines = []
            elif d.startswith('@@'):
                a_blob_lines.append(d)
                b_blob_lines.append(d)
            elif d.startswith('-'):
                a_blob_lines.append(d)
            elif d.startswith('+'):
                b_blob_lines.append(d)
        if a_blob_lines or b_blob_lines:
            yield HgBlob(a_blob_lines, b_blob_lines)

    def _dirty_suffix(self, base_paths=['.']):
        repo_wd = self.path
        # diff = self._repo.diff()
        a_hashes = self._hash_blobs(d.a_blob for d in self.diff_blobs())
        b_hashes = self._hash_blobs(d.b_blob for d in self.diff_blobs())

        u_files = self.untracked_files()
        untracked_hashes = [(path, hashlib.md5(path).hexdigest()) for path in u_files]

        hashes = sorted(a_hashes) + sorted(b_hashes + untracked_hashes)
        filtered_hashes = [
            (path, h) for path, h in hashes if self._in_paths(repo_wd, base_paths, path)
        ]

        if not filtered_hashes:
            return ''

        digest = hashlib.sha256()
        for path, h in filtered_hashes:
            digest.update(path.encode('utf-8') + b'\0' + h.encode('utf-8'))
        return '-dirty-' + binascii.hexlify(digest.digest())[:12].decode('utf-8')

    def default_tags(self):
        repo = self._repo
        # if repo.head.is_detached:
        #     return []

        branch = repo.summary()['branch']
        return [branch]

    def this_ref_str(self):
        return self._hexsha(self.last_commit()) + self._dirty_suffix()

    @staticmethod
    def _hexsha(ref):
        if ref is not None:
            return ref[1][:12]
        else:
            return 'g' * 12

    def targets(self):
        repo = self._repo

        images = image.list_images(
            self._namespace,
            self._name_map,
            self.path,
        )
        c_index = {c.name: c for c in images}

        targets = []

        for c in images:
            paths = sorted(frozenset.union(
                *(p.copy_paths for p in _image_parents(c_index, c))
            ))
            ref = (self._hexsha(self.last_commit()) + self._dirty_suffix(paths))
            targets.append(Target(image=c, ref=ref, children=None))

        return targets

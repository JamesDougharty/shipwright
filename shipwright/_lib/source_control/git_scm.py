import binascii
import hashlib

import git

from common import SourceControl
from common import GIT, _image_parents, Target
from shipwright._lib import image


class GitSourceControl(SourceControl):
    mode = GIT

    def __init__(self, path, namespace, name_map):
        super(GitSourceControl, self).__init__(path, namespace, name_map)
        self._repo = git.Repo(path)

    def is_dirty(self):
        repo = self._repo
        for item in repo.index.diff(None):
            print('{} has been modified'.format(item.a_path))
        return repo.is_dirty()

    def _dirty_suffix(self, base_paths=['.']):
        repo_wd = self._repo.working_dir
        diff = self._repo.head.commit.diff(None)
        a_hashes = self._hash_blobs(d.a_blob for d in diff)
        b_hashes = self._hash_blobs(d.b_blob for d in diff)

        u_files = self._repo.untracked_files
        untracked_hashes = [(path, self._repo.git.hash_object(path)) for path in u_files]

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

    def _hash_blob(self, blob):
        if blob.hexsha != blob.NULL_HEX_SHA:
            return blob.hexsha
        else:
            return blob.repo.git.hash_object(blob.abspath)

    def _hash_blobs(self, blobs):
        return [(b.path, self._hash_blob(b)) for b in blobs if b]

    def default_tags(self):
        repo = self._repo
        if repo.head.is_detached:
            return []

        branch = repo.active_branch.name
        return [branch]

    def this_ref_str(self):
        return self._hexsha(self._repo.commit()) + self._dirty_suffix()

    def last_commit(self, paths):
        return self._repo.head.commit

    @staticmethod
    def _hexsha(ref):
        if ref is not None:
            return ref.hexsha[:12]
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
            ref = (self._hexsha(self.last_commit(paths)) + self._dirty_suffix(paths))
            targets.append(Target(image=c, ref=ref, children=None))

        return targets

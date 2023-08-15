import os
import re
import zlib
import hashlib

from lib.repo_functions import repo_dir, repo_file
from lib.tea_object import TeaCommit, TeaTree, TeaTag, TeaBlob

def object_read(repo, sha):
    """
    Read object object_id from Tea repository repo. Return a TeaObject whose exact
    type depends on the object.
    """

    path = repo_file(repo, "objects", sha[0:2], sha[2:])

    if (not os.path.isfile(path)):
        return None

    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())

        # Read object type
        x = raw.find(b' ')
        fmt = raw[0:x]

        # Read and validate object size
        y = raw.find(b'\x00', x)
        size = int(raw[x:y].decode("ascii"))
        
        LENGTH_NOT_MATCH = size != len(raw)-y-1
        if (LENGTH_NOT_MATCH):
            raise Exception(f"Malformed object {sha}: bad length")

        # Pick constructor
        match fmt:
            case b'commit' : c = TeaCommit
            case b'tree'   : c = TeaTree
            case b'tag'    : c = TeaTag
            case b'blob'   : c = TeaBlob
            case _:
                raise Exception("Unknown type {0} for object {1}".format(fmt.decode("ascii"), sha))

        # Call constructor and return object
        return c(raw[y+1:])

def object_write(obj, repo=None):
    # Serialize object data
    data = obj.serialize()

    # Add header
    result = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data

    # Compute hash
    sha = hashlib.sha1(result).hexdigest()

    if (repo):
        # Compute path
        path = repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)

        PATH_NOT_EXIST = not os.path.exists(path)
        if (PATH_NOT_EXIST):
            with open(path, 'wb') as f:
                f.write(zlib.compress(result))

    return sha

def object_find(repo, name, fmt=None, follow=True):
    sha = object_resolve(repo, name)

    if (not sha):
        raise Exception(f'No such reference {name}.')

    if (len(sha) > 1):
        raise Exception(f'Ambiguous reference {name}: Candidates are:\n - {"".join(sha)}')

    sha = sha[0]

    if (not fmt):
        return sha

    while True:
        obj = object_read(repo, sha)
    
        if (obj.fmt == fmt):
            return sha

        if (not follow):
            return None

        # Follow tags
        if (obj.fmt == b'tag'):
            sha = obj.kvlm[b'object'].decode('ascii')
        elif (obj.fmt == b'commit' and fmt == b'tree'):
            sha = obj.kvlm[b'tree'].decode('ascii')
        else:
            return None

def object_resolve(repo, name):
    """
    Resolve name to an object hash in a repo.

    This function is aware of:
    - the HEAD literal
    - short and long hashes
    - tags
    - branches
    - remote branches
    """

    candidates = list()
    hashRE = re.compile(r'^[0-9A-Fa-f]{4,40}$')

    # Empty string? abort.
    if (not name.strip()):
        return None

    # Head in nonambiguous
    if (name == 'HEAD'):
        return [ ref_resolve(repo, 'HEAD') ]

    # If it's a hex string, try for a hash
    if (hashRE.match(name)):
        # This may be a hash, either small or full. 4 seems to be the
        # minimal length for tea to consider something a short hash.
        # This limit is documented in man tea-rev-parse
        name = name.lower()
        prefix = name[0:2]
        path = repo_dir(repo, 'objects', prefix, mkdir=False)

        if (path):
            rem = name[2:]
            for f in os.listdir(path):
                if (f.startswith(rem)):
                    # Notice a string startswit() itself, so this
                    # works for full hashes
                    candidates.append(prefix + f)

    # Try for references.
    as_tag = ref_resolve(repo, 'refs/tags/' + name)
    if (as_tag): # Check if tag is found
        candidates.append(as_tag)

    as_branch = ref_resolve(repo, 'refs/heads/' + name)
    if (as_branch): # Check if branch is found
        candidates.append(as_branch)

    return candidates

def ref_resolve(repo, ref):
    path = repo_file(repo, ref)

    # Sometimes, an indirect reference may be broken. This is normal in one
    # specific case: we're looking for HEAD on a new repository with no
    # commits. In that case, .tea/HEAD points to 'ref: refs/heads/main'. But,
    # .tea/refs/heads/main doesn't exist yet (since there's no commit for it
    # to refer to).

    if (not os.path.isfile(path)):
        return None

    with open(path, 'r') as fp:
        data = fp.read()[:-1]
        # Drop final \n

    if (data.startswith('ref: ')):
        return ref_resolve(repo, data[5:])
    else:
        return data

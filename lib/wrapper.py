import os
import sys

from lib.repo_functions import repo_file
from lib.tea_object_function import object_find, object_read, object_write
from lib.tea_object import TeaBlob, TeaCommit, TeaTag, TeaTree

def cat_file(repo, obj, fmt=None):
    obj = object_read(repo, object_find(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialize())

def hash_object(fd, fmt, repo=None):
    """
    Hash object, writing it to repo if provided.
    """

    data = fd.read()

    # Choose constructor according to fmt argument
    match fmt:
        case b'commit'  : obj = TeaCommit(data) 
        case b'tree'    : obj = TeaTree(data)
        case b'tag'     : obj = TeaTag(data) 
        case b'blob'    : obj = TeaBlob(data)
        case _  : raise Exception(f"Unknown type {fmt}!")

    return object_write(obj, repo)

def log_graphviz(repo, sha, seen):
    if (sha in seen):
        return

    seen.add(sha) 
    
    commit = object_read(repo, sha) 
    short_hash = sha[0:8]
    message = commit.kvlm[None].decode("utf8").strip()
    message = message.replace("\\", "\\\\")
    message = message.replace("\"", "\\\"")

    if ("\n" in message): # Keep only the first line
        message = message[:message.index("\n")]

    print(f"  c_{sha} [label=\"{sha[0:7]}: {message}\"]")
    assert commit.fmt == b'commit'

    if (not (b'parent' in commit.kvlm.keys())):
        # Initial commit
        return
        
    parents = commit.kvlm[b'parent']

    if (type(parents) != list):
        parents = [ parents ]

    for p in parents:
        p = p.decode("ascii")
        print(f"  C_{sha} -> c_{p}")
        log_graphviz(repo, p, seen)

def ls_tree(repo, ref, recursive=None, prefix=""):
    sha = object_find(repo, ref, fmt=b"tree")
    obj = object_read(repo, sha)

    for item in obj.items:
        if (len(item.mode) == 5):
            type = item.mode[0:1]
        else:
            type = item.mode[0:2]

        match type:
            case b'04': type = "tree"
            case b'10': type = "blob"
            case b'12': type = "blob"
            case b'16': type = "commit"
            case _: raise Exception(f"Weird tree leaf mode {item.mode}")

        if (not (recursive and type == "tree")):
            print("{0} {1} {2}\t{3}".format(
                '0' * (6 - len(item.mode)) + item.mode.decode('ascii'),
                type,
                item.sha,
                os.path.join(prefix, item.path))
            )
        else:
            ls_tree(repo, item.sha, recursive, os.path.join(prefix, item.path))

def tree_checkout(repo, tree, path):
    for item in tree.items:
        obj = object_read(repo, item.sha)
        dest = os.path.join(path, item.path)

        if (obj.fmt == b'tree'):
            os.mkdir(dest)
            tree_checkout(repo, obj, dest)
        elif (obj.fmt == b'blob'):
            # @TODO Support symlinks (identified by mode 12****)
            with open(dest, 'wb') as f:
                f.write(obj.blobdata)

def show_ref(repo, refs, with_hash=True, prefix=''):
    for k, v in refs.items():
        if (type(v) == str):
            print("{0}{1}{2}".format(
                v + ' ' if with_hash else '',
                prefix + '/' if prefix else '',
                k
            ))
        else:
            show_ref(repo, v, with_hash=with_hash, prefix='{0}{1}{2}'.format(
                prefix,
                '/' if prefix else '',
                k
            ))

def branch_get_active(repo):
    with open(repo_file(repo, 'HEAD'), 'r') as f:
        head = f.read()

    if (head.startswith('ref: refs/heads/')):
        return head[16:-1]
    else:
        return False

def cmd_status_branch(repo):
    branch = branch_get_active(repo)

    if (branch):
        print(f"On branch {branch}")
    else:
        print("HEAD detached at {object_find(repo, 'HEAD')}")

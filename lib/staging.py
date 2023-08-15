import os

from fnmatch import fnmatch
from math import ceil

from lib.repo_functions import repo_file
from lib.tea_object_function import object_find, object_read
from lib.wrapper import hash_object

class TeaIndexEntry(object):
    def __init__(self, ctime=None, mtime=None, dev=None, ino=None,
                 mode_type=None, mode_perms=None, uid=None, gid=None,
                 fsize=None, sha=None, flag_assume_valid=None,
                 flag_stage=None, name=None):
        # The last time a file's metadata changed. This is a pair
        # (timestamp in seconds, nanoseconds)
        self.ctime = ctime
        
        # The last time a file's data changed. This is a pair
        # (timestamp in seconds, nanoseconds)
        self.mtime = mtime

        # The ID of device containing this file
        self.dev = dev

        # The file's inode number
        self.ino = ino

        # The object type, either b1000 (regular) ,b1010 (symlink),
        # b1110 (tealink).
        self.mode_type = mode_type

        # The object permissions, an integer
        self.mode_perms = mode_perms

        # User ID of owner
        self.uid = uid

        # Group ID of owner
        self.gid = gid

        # Size of this object, in bytes
        self.fsize = fsize

        # The object's SHA
        self.sha = sha
        self.flag_assume_valid = flag_assume_valid
        self.flag_stage = flag_stage

        # Name of the object (full path)
        self.name = name

class TeaIndex(object):
    version = None
    entries = []
    # ext = None 
    # sha = None 

    def __init__(self, version=2, entries=None):
        if (not entries):
            entries = list()

        self.version = version
        self.entries = entries

def index_read(repo):
    index_file = repo_file(repo, 'index')

    # New repositories have no index!
    if (not os.path.exists(index_file)):
        return TeaIndex()

    with open(index_file, 'rb') as f:
        raw = f.read()

    header = raw[:12]

    signature = header[:4]
    assert signature == b'DIRC' # DirCache

    version = int.from_bytes(header[4:8], 'big')
    assert version == 2

    count = int.from_bytes(header[8:12], 'big')

    entries = list()

    content = raw[12:]
    idx = 0
    for _ in range(0, count):
        # Read creation time as unix timestamp (seconds since
        # 1970-01-01 00:00:00, the 'epoch')
        ctime_s = int.from_bytes(content[idx : idx+4], 'big')

        # Read creation time as nanoseconds after that timestamps,
        # for extra precision
        ctime_ns = int.from_bytes(content[idx+4 : idx+8], 'big')

        # Same for modification time: first seconds from epoch
        mtime_s = int.from_bytes(content[idx+8 : idx+12], 'big')

        # Nanoseconds
        mtime_ns = int.from_bytes(content[idx+12 : idx+16], 'big')

        # Device ID
        dev = int.from_bytes(content[idx+16 : idx+20], 'big')

        # Inode
        ino = int.from_bytes(content[idx+20 : idx+24], 'big')

        # Ignored
        unused = int.from_bytes(content[idx+24 : idx+26], 'big')
        assert unused == 0

        mode = int.from_bytes(content[idx+26 : idx+28], 'big')
        mode_type = mode >> 12
        assert mode_type in [0b1000, 0b1010, 0b1110]
        mode_perms = mode & 0b0000000111111111

        # User ID
        uid = int.from_bytes(content[idx+28 : idx+32], 'big')

        # Group ID
        gid = int.from_bytes(content[idx+32 : idx+36], 'big')

        # Size
        fsize = int.from_bytes(content[idx+36 : idx+40], 'big')

        # SHA (object ID). We'll store it as a lowercase hex string
        # for consistency
        sha = format(int.from_bytes(content[idx+40 : idx+60], 'big'), '040x')

        # Flags we're going to ignore
        flags = int.from_bytes(content[idx+60 : idx+62], 'big')

        # Parse flags
        flag_assume_valid = (flags & 0b1000000000000000) != 0
        flag_extended = (flags & 0b0100000000000000) != 0
        assert not flag_extended
        flag_stage =  flags & 0b0011000000000000

        # Length of the name. This is stored on 12 bits, some max
        # value is 0xFFF, 4095. Since names can occasionally go
        # beyond that length, tea treats 0xFFF as meaning at least
        # 0xFFF and looks for the final 0x00 to find the end of the
        # name --- at a small, probably very rare, performance cost
        name_length = flags & 0b0000111111111111

        # We've read 62 bytes so far
        idx += 62

        if  (name_length < 0xFFF):
            assert content[idx + name_length] == 0x00
            raw_name = content[idx : idx+name_length]
            idx += name_length + 1
        else:
            print(f'Notice: Name is 0x{name_length:x} bytes long.')

            null_idx = content.find(b'\x00', idx+0xFFF)
            raw_name = content[idx:null_idx]
            idx = null_idx + 1

        # Just parse the name as utf-8
        name = raw_name.decode('utf8')

        # Data is padded on multiples of eight bytes for pointer
        # alignment, so we skip as many bytes as we need for the next
        # read to start at the right position

        idx = 8 * ceil(idx / 8)

        # And we add this entry to our list
        entries.append(
            TeaIndexEntry(
                ctime=(ctime_s, ctime_ns),
                mtime=(mtime_s, mtime_ns),
                dev=dev,
                ino=ino,
                mode_type=mode_type,
                mode_perms=mode_perms,
                uid=uid,
                gid=gid,
                fsize=fsize,
                sha=sha,
                flag_assume_valid=flag_assume_valid,
                flag_stage=flag_stage,
                name=name
            )
        )

    return TeaIndex(version=version, entries=entries)

def teaignore_parse_single(raw):
    raw = raw.strip()

    if (not raw or raw[0] == '#'):
        return None
    elif (raw[0] == '!'):
        return (raw[1:], False)
    elif (raw[0] == '\\'):
        return (raw[1:], True)
    else:
        return (raw, True)

def teaignore_parse(lines):
    ret = list()

    for line in lines:
        parsed = teaignore_parse_single(line)
        if (parsed):
            ret.append(parsed)

    return ret

class TeaIgnore(object):
    absolute = None
    scoped = None

    def __init__(self, absolute, scoped):
        self.absolute = absolute
        self.scoped = scoped

def teaignore_read(repo):
    ret = TeaIgnore(absolute = list(), scoped=dict())

    # Read local configuration in .tea/info/exclude
    repo_file = os.path.join(repo.teadir, 'info/exclude')
    if (os.path.exists(repo_file)):
        with open(repo_file, 'r') as f:
            ret.absolute.append(teaignore_parse(f.readlines()))

    # Global config
    if ("XDG_CONFIG_HOME" in os.environ):
        config_home = os.environ["XDG_CONFIG_HOME"]
    else:
        config_home = os.path.expanduser("~/.config")

    global_file = os.path.join(config_home, "git/ignore")

    if (os.path.exists(global_file)):
        with open(global_file, 'r') as f:
            ret.absolute.append(teaignore_parse(f.readlines()))

    # .teaignore files in the index
    index = index_read(repo)

    for entry in index.entries:
        print(entry.name)
        if (entry.name == '.teaignore' or entry.name.endswith('/.teaignore')):
            dir_name = os.path.dirname(entry.name)
            contents = object_read(repo, entry.sha)
            lines = contents.blobdata.decode('utf8').splitlines()
            ret.scoped[dir_name] = teaignore_parse(lines)

    return ret

def check_ignore_single(rules, path):
    result = None

    for (pattern, value) in rules:
        if (fnmatch(path, pattern)):
            result = value

    return result

def check_ignore_scoped(rules, path):
    parent = os.path.dirname(path)

    while (True):
        if (parent in rules):
            result = check_ignore_single(rules[parent], path)
            if (result != None):
                return result
        if (parent == ""):
            break
        parent = os.path.dirname(parent)

    return None

def check_ignore_absolute(rules, path):
    parent = os.path.dirname(path)

    for ruleset in rules:
        result = check_ignore_single(ruleset, path)

        if (result != None):
            return result

    return False

def check_ignore(rules, path):
    if (os.path.isabs(path)):
        raise Exception("This function requires path to be relative to the repository's root")

    result = check_ignore_scoped(rules.scoped, path)
    if (result != None):
        return result

    return check_ignore_absolute(rules.absolute, path)

def tree_to_dict(repo, ref, prefix=''):
    ret = dict()
    tree_sha = object_find(repo, ref, fmt=b'tree')
    tree = object_read(repo, tree_sha)

    for leaf in tree.items:
        full_path = os.path.join(prefix, leaf.path)

        # We read the object to extract its type (this is uselessly
        # expensive: we could just open it as a file and read the
        # first few bytes)
        is_subtree = leaf.mode.startswith(b'04')

        # Depending on the type, we either store the path (if it's a
        # blob, so a regular file), or recursive (if it's another tree,
        # so a subdir)
        if (is_subtree):
            ret.update(tree_to_dict(repo, leaf.sha, full_path))
        else:
            ret[full_path] = leaf.sha

    return ret

def cmd_status_head_index(repo, index):
    # print("Changes to be committed:")

    # head = tree_to_dict(repo, 'HEAD')
    # for entry in index.entries:
    #     if (entry.name in head):
    #         if (head[entry.name] != entry.sha):
    #             print("  modified:", entry.name)
    #         del head[entry.name]
    #     else:
    #         print("  added:   ", entry.name)

    # # Keys still in HEAD are files that we haven't met in the index,
    # # and are thus have been deleted
    # for entry in head.keys():
    #     print("  deleted: ", entry)

    try:
        head = tree_to_dict(repo, 'HEAD')
        for entry in index.entries:
            if (entry.name in head):
                if (head[entry.name] != entry.sha):
                    print("  modified:", entry.name)
                del head[entry.name]
            else:
                print("  added:   ", entry.name)

        # Keys still in HEAD are files that we haven't met in the index,
        # and are thus have been deleted
        for entry in head.keys():
            print("  deleted: ", entry)
    except TypeError as _:
        # git status when no files, do the same thing as ls-files
        for entry in index.entries:
            print("  added:   ", entry.name)

def cmd_status_index_worktree(repo, index):
    print("Changes not staged for commit:")

    ignore = teaignore_read(repo)

    teadir_prefix = repo.teadir + os.path.sep

    all_files = list()

    # We begin by walking the filesystem
    for (root, _, files) in os.walk(repo.worktree, True):
        if (root == repo.teadir or root.startswith(teadir_prefix)):
            continue

        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, repo.worktree)
            all_files.append(rel_path)

    # We now traverse the index and compare real files with the cached
    # versions.

    for entry in index.entries:
        full_path = os.path.join(repo.worktree, entry.name)

        # That file *name* is in the index
        if (not os.path.exists(full_path)):
            print("  deleted: ", entry.name)
        else:
            stat = os.stat(full_path)

            # Compare metadata
            ctime_ns = entry.ctime[0] * 10**9 + entry.ctime[1]
            mtime_ns = entry.mtime[0] * 10**9 + entry.mtime[1]

            if ((stat.st_ctime_ns != ctime_ns) or (stat.st_mtime_ns != mtime_ns)):
                # If different, deep compare
                # @FIXME This *will* crash on symlinks to dir
                with open(full_path, 'rb') as fd:
                    new_sha = hash_object(fd, b'blob', None)

                    # If the hashes are the same, the files are actually the same
                    same = entry.sha == new_sha

                    if (not same):
                        print("  modified:", entry.name)

        if (entry.name in all_files):
            all_files.remove(entry.name)

    print()
    print("Untracked files:")

    for f in all_files:
        # @TODO If a full directory is untracked, we should
        # display its name without its content
        if (not check_ignore(ignore, f)):
            print(" ", f)

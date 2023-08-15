import configparser
import os

from lib.repo_functions import repo_file
from lib.staging import TeaIndexEntry, index_read
from lib.tea_object import TeaCommit, TeaTree
from lib.tea_object_function import object_write
from lib.trees_checkout import TeaTreeLeaf
from lib.wrapper import hash_object

def index_write(repo, index):
    with open(repo_file(repo, "index"), "wb") as f:

        # HEADER

        # Write the magic bytes.
        f.write(b"DIRC")
        # Write version number.
        f.write(index.version.to_bytes(4, "big"))
        # Write the number of entries.
        f.write(len(index.entries).to_bytes(4, "big"))

        # ENTRIES

        idx = 0
        for e in index.entries:
            f.write(e.ctime[0].to_bytes(4, "big"))
            f.write(e.ctime[1].to_bytes(4, "big"))
            f.write(e.mtime[0].to_bytes(4, "big"))
            f.write(e.mtime[1].to_bytes(4, "big"))
            f.write(e.dev.to_bytes(4, "big"))
            f.write(e.ino.to_bytes(4, "big"))

            # Mode
            mode = (e.mode_type << 12) | e.mode_perms
            f.write(mode.to_bytes(4, "big"))

            f.write(e.uid.to_bytes(4, "big"))
            f.write(e.gid.to_bytes(4, "big"))

            f.write(e.fsize.to_bytes(4, "big"))
            # @FIXME Convert back to int
            f.write(int(e.sha, 16).to_bytes(20, "big"))

            flag_assume_valid = 0x1 << 15 if e.flag_assume_valid else 0

            name_bytes = e.name.encode("utf8")
            bytes_len = len(name_bytes)
            if (bytes_len >= 0xFFF):
                name_length = 0xFFF
            else:
                name_length = bytes_len

            # We merge back three pieces of data (two flags and the
            # lengthh of the name) on the same two bytes.
            f.write((flag_assume_valid | e.flag_stage | name_length).to_bytes(2, "big"))

            # Write back the name, and a final 0x00.
            f.write(name_bytes)
            f.write((0).to_bytes(1, "big"))

            idx += 62 + len(name_bytes) + 1

            # Add padding if necessary.
            if (idx % 8 != 0):
                pad = 8 - (idx % 8)
                f.write((0).to_bytes(pad, "big"))
                idx += pad

def rm(repo, paths, delete=True, skip_missing=False):
    # Find and read the index
    index = index_read(repo)

    worktree = repo.worktree + os.sep

    # Make paths absolute
    abspaths = list()
    for path in paths:
        abspath = os.path.abspath(path)

        if (abspath.startswith(worktree)):
            abspaths.append(abspath)
        else:
            raise Exception(f"Cannot remove paths outside of worktree: {paths}")

    keep_entries = list()
    remove = list()

    for e in index.entries:
        full_path = os.path.join(repo.worktree, e.name)

        if (full_path in abspaths):
            remove.append(full_path)
            abspaths.remove(full_path)
        else:
            keep_entries.append(e) # Preserve entry

    if (len(abspaths) > 0 and not skip_missing):
        raise Exception(f"Cannot remove pathhs not in the index: {abspaths}")

    if (delete):
        for path in remove:
            os.unlink(path)

    index.entries = keep_entries
    index_write(repo, index)

def add(repo, paths, delete=True, skip_missing=False):

    # First remove all paths from the index, if they exist.
    rm (repo, paths, delete=False, skip_missing=True)

    worktree = repo.worktree + os.sep

    # Convert the paths to pairs: (absolute, relative_to_worktree).
    # Also delete them from the index if they're present.
    clean_paths = list()
    for path in paths:
        abspath = os.path.abspath(path)
        
        if (not (abspath.startswith(worktree) and os.path.isfile(abspath))):
            raise Exception(f"Not a file, or outside the worktree: {paths}")

        relpath = os.path.relpath(abspath, repo.worktree)
        clean_paths.append((abspath, relpath))

    # Find and read the index. It was modified by rm. (This isn't
    # optimal, but good enough for tea)
    #
    # @FIXME though: we could just
    # move the index through commands instead of reading and writing
    # it over again.
    index = index_read(repo)

    for (abspath, relpath) in clean_paths:
        with open(abspath, "rb") as fd:
            sha = hash_object(fd, b"blob", repo)

        stat = os.stat(abspath)

        ctime_s = int(stat.st_ctime)
        ctime_ns = stat.st_ctime_ns % 10**9
        mtime_s = int(stat.st_mtime)
        mtime_ns = stat.st_mtime_ns % 10**9
        
        entry = TeaIndexEntry(
                    ctime = (ctime_s, ctime_ns),
                    mtime = (mtime_s, mtime_ns),
                    dev = stat.st_dev,
                    ino = stat.st_ino,
                    mode_type = 0b1000,
                    mode_perms = 0o644,
                    uid = stat.st_uid,
                    gid = stat.st_gid,
                    fsize = stat.st_size,
                    sha = sha,
                    flag_assume_valid = False,
                    flag_stage = False,
                    name = relpath
                )

        index.entries.append(entry)

    # Write the index back
    index_write(repo, index)

def teaconfig_read():
    xdg_config_home = os.environ["XDG_CONFIG_HOME"] if "XDG_CONFIG_HOME" in os.environ else "~/.config"

    configfiles = [
        os.path.expanduser(os.path.join(xdg_config_home, "git/config")),
        os.path.expanduser("~/.gitconfig")
    ]

    config = configparser.ConfigParser()
    config.read(configfiles)
    return config

def teaconfig_user_get(config):
    if ("user" in config):
        if ("name" in config["user"] and "email" in config["user"]):
            return f"{config['user']['name']} <{config['user']['email']}>"

    return None

def tree_from_index(repo, index):
    contents = dict()
    contents[""] = list()

    # Enumerate entries, and turn them into a dictionary where keys
    # are dictionaries, and values are list of directory contents.
    for entry in index.entries:
        dirname = os.path.dirname(entry.name)

        # We create all dictionary entries up to root (""). We need
        # them *all*, because even if a directory holds no files it
        # will contain at least a tree
        key = dirname
        
        while (key != ""):
            if (not key in contents):
                contents[key] = list()

            key = os.path.dirname(key)

        # For now, simply store the entry in the list.
        contents[dirname].append(entry)

    # Get keys (=directories) and sort them by length, descending.
    # This means that we'll always encounter a given path before its
    # parent, which is all we need, since for each directory D we'll
    # need to modify its parent P to add D's tree.
    sorted_paths = sorted(contents.keys(), key=len, reverse=True)

    # This variable will store the current tree's SHA-1. After we're
    # done iterating over our dict, it will contain the hash for the
    # root tree.
    sha = None

    # We get through the sorted list of paths (dict keys)
    for path in sorted_paths:
        # Prepare a new, empty tree object
        tree = TeaTree()

        # Add each entry to our new tree, in turn
        for entry in contents[path]:
            # An entry can be a normal TeaIndexEntry read from the
            # index, or a tree we've created.
            if (isinstance(entry, TeaIndexEntry)): # Regular entry (a file)

                # We transcode the mode: the entry stores it as integers,
                # we need an octal ASCII representation of the key
                leaf_mode = "{:02o}{:04o}".format(entry.mode_type, entry.mode_perms).encode("ascii")
                leaf = TeaTreeLeaf(mode = leaf_mode, path=os.path.basename(entry.name), sha=entry.sha)
            else: # Tree. We've stored it as a pair (basename, sha)
                leaf = TeaTreeLeaf(mode=b"040000", path=entry[0], sha=entry[1])

            tree.items.append(leaf)

        # Write the new tree object to the store.
        sha = object_write(tree, repo)

        # Add the new tree hash to the current dictionary's parent, as
        # a pair (basename, SHA)
        parent = os.path.dirname(path)
        base = os.path.basename(path) # The name without the path, eg main.go for src/main.go
        contents[parent].append((base, sha))

    return sha

def commit_create(repo, tree, parent, author, timestamp, message):
    commit = TeaCommit() # Create the new commit object.
    commit.kvlm[b"tree"] = tree.encode("ascii")

    if (parent):
        commit.kvlm[b"parent"] = parent.encode("ascii")

    # Format timezone
    offset = int(timestamp.astimezone().utcoffset().total_seconds())
    hours = offset // 3600
    minutes = (offset % 3600) // 60
    tz = "{}{:02}{:02}".format("+" if offset > 0 else "-", hours, minutes)

    author = author + timestamp.strftime(" %s ") + tz

    commit.kvlm[b"author"] = author.encode("utf8")
    commit.kvlm[b"committer"] = author.encode("utf8")
    commit.kvlm[None] = message.encode("utf8")

    return object_write(commit, repo)

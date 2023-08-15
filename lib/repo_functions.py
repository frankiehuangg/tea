import configparser
import os

class TeaRepository(object):
    """
    A tea repository
    """

    worktree = None
    teadir = None
    conf = None

    def __init__(self, path, force=False):
        self.worktree = path
        self.teadir = os.path.join(path, ".tea")

        NOT_TEA_REPO = (not force) and (not os.path.isdir(self.teadir))
        if (NOT_TEA_REPO):
            raise Exception(f"Not a Tea repository {path}")

        # Read configuration file in .tea/config
        self.conf = configparser.ConfigParser()
        cf = repo_file(self, "config")

        if (cf and os.path.exists(cf)):
            self.conf.read([cf])
        elif (not force):
            raise Exception("Configuration file missing")

        if (not force):
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if (vers != 0):
                raise Exception(f"Unsupported repositoryformatversion {vers}")

def repo_path(repo, *path):
    """
    Compute path under repo's teadir
    """

    return os.path.join(repo.teadir, *path)

def repo_file(repo, *path, mkdir=False):
    """
    Similar to repo_path, but create dirname(*path) if path is absent.
    """

    FILE_PARENT_DIR_EXIST = repo_dir(repo, *path[:-1], mkdir=mkdir)
    if (FILE_PARENT_DIR_EXIST):
        return repo_path(repo, *path)

def repo_dir(repo, *path, mkdir=False):
    """
    Same as repo_path, but mkdir *path if absent
    """

    path = repo_path(repo, *path)

    PATH_EXIST = os.path.exists(path)
    if (PATH_EXIST):
        PATH_IS_DIR = os.path.isdir(path)
        if (PATH_IS_DIR):
            return path
        else:
            raise Exception(f"Not a directory {path}")

    if (mkdir):
        os.makedirs(path)
        return path
    else:
        return None

def repo_default_config():
    ret = configparser.ConfigParser()

    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")

    return ret

def repo_create(path):
    """
    Create a new repository at path
    """

    repo = TeaRepository(path, True)

    WORKTREE_PATH_EXIST = os.path.exists(repo.worktree)
    if (WORKTREE_PATH_EXIST):
        WORKTREE_PATH_NOT_DIR = not os.path.isdir(repo.worktree)
        if (WORKTREE_PATH_NOT_DIR):
            raise Exception(f"{path} is not a directory!")
        
        WORKTREE_PATH_NOT_EMPTY = os.path.exists(repo.teadir) and os.listdir(repo.teadir)
        if (WORKTREE_PATH_NOT_EMPTY):
            raise Exception(f"{path} is not empty!")
    else:
        os.makedirs(repo.worktree)

    # Create .tea/branches .tea/objects .tea/refs/tags and .tea/refs/heads
    assert repo_dir(repo, "branches", mkdir=True)
    assert repo_dir(repo, "objects", mkdir=True)
    assert repo_dir(repo, "refs", "tags", mkdir=True)
    assert repo_dir(repo, "refs", "heads", mkdir=True)

    # Create .tea/description
    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unnamed repository: edit this file 'descrpition' to name this repository.\n")

    # .tea/HEAD
    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/main\n")

    # .tea/config
    with open(repo_file(repo, "config"), "w") as f:
        config = repo_default_config()
        config.write(f)

    return repo

def repo_find(path=".", required=True):
    path = os.path.realpath(path)

    TEA_FOLDER_EXIST = os.path.isdir(os.path.join(path, ".tea"))
    if (TEA_FOLDER_EXIST):
        return TeaRepository(path)

    parent = os.path.realpath(os.path.join(path, ".."))

    ROOT_DIR = (parent == path)
    if (ROOT_DIR):
        if (required):
            raise Exception("No tea directory.")
        else:
            return None

    return repo_find(parent, required)

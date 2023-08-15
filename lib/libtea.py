import os
import grp
import pwd
import sys
import argparse
from datetime import datetime

from lib.commit import add, commit_create, teaconfig_user_get, teaconfig_read, rm, tree_from_index
from lib.refs_tags_branch import ref_list, tag_create
from lib.repo_functions import repo_create, repo_file, repo_find
from lib.staging import check_ignore, cmd_status_head_index, cmd_status_index_worktree, teaignore_read, index_read
from lib.tea_object_function import object_read, object_find
from lib.wrapper import branch_get_active, cat_file, cmd_status_branch, hash_object, log_graphviz, show_ref, tree_checkout, ls_tree

# =================================================================
#                           ARGUMENT PARSER
# =================================================================

argparser = argparse.ArgumentParser(
    description = 'Version control system similar to git, but named \'tea\''
)

argsubparsers = argparser.add_subparsers(
    title = 'Commands',
    dest  = 'command'
)
argsubparsers.required = True

# ADD
argsp = argsubparsers.add_parser(
    'add',
    help = 'Add file contents to the index.'
)

argsp .add_argument(
    'path',
    nargs = '+',
    help  = 'Files to add.'
)

# CAT-FILE
argsp = argsubparsers.add_parser(
    'cat-file',
    help = 'Provide the content of a repository object.'
)

argsp.add_argument(
    'type',
    metavar = 'type',
    choices = ['blob', "commit", "tag", "tree"],
    help    = 'Specify the type.'
)

argsp.add_argument(
    'object',
    metavar = 'object',
    help    = 'The object to display.'
)

# CHECK-IGNORE
argsp = argsubparsers.add_parser(
    'check-ignore',
    help = 'Check path(s) against ignore rules.'
)

argsp.add_argument(
    'path',
    nargs = '+',
    help  = 'Paths to check.'
)

# CHECKOUT
argsp = argsubparsers.add_parser(
    'checkout',
    help = 'Checkout a commit inside of a directory.'
)

argsp.add_argument(
    'commit',
    help = 'The commit or tree to checkout to.'
)
argsp.add_argument(
    'path',
    help = 'The EMPTY directory to checkout on.'
)

# COMMIT
argsp = argsubparsers.add_parser(
    'commit',
    help = 'Record changes to the repository.'
)

argsp.add_argument(
    '-m',
    metavar = 'message',
    dest    = 'message',
    help    = 'Message to associate with this commit.'
)

# HASH-OBJECT
argsp = argsubparsers.add_parser(
    'hash-object',
    help = 'Compute object ID and optionally creates a blob from a file.'
)

argsp.add_argument(
    '-t',
    metavar = 'type',
    dest    = 'type',
    choices = ['blob', "commit", "tag", "tree"],
    default = 'blob',
    help    = 'Specify the type.'
)

argsp.add_argument(
    '-w',
    dest   = 'write',
    action = 'store_true',
    help   = 'Write the object into the database.'
)

argsp.add_argument(
    'path',
    help = 'Read object from <file>.'
)

# INIT
argsp = argsubparsers.add_parser(
    'init',
    help = 'Initialize a new, empty tea repository.'
)

argsp.add_argument(
    'path',
    metavar ='directory',
    nargs   ='?',
    default ='.',
    help    ='Where to create the repository.'
)

# LOG
argsp = argsubparsers.add_parser(
    'log',
    help = 'Display the history of a given commit.'
)

argsp.add_argument(
    'commit',
    default = 'HEAD',
    nargs   = '?',
    help    = 'Commit to start at.'
)

# LS-FILES
argsp = argsubparsers.add_parser(
    'ls-files',
    help = 'List all the stage files.'
)

argsp.add_argument(
    '--verbose',
    action = 'store_true',
    help   = 'Show everything.'
)

# LS-TREE
argsp = argsubparsers.add_parser(
    'ls-tree',
    help = 'Print a tree object.'
)

argsp.add_argument(
    '-r',
    dest = 'recursive',
    action = 'store_true',
    help = 'Recurse into sub-trees.'
)

argsp.add_argument(
    'tree',
    help = 'A tree-ish object.'
)

# REV-PARSE
argsp = argsubparsers.add_parser(
    'rev-parse',
    help = 'Parse a revision (or other object) identifiers'
)

argsp.add_argument(
    '--tea-type',
    metavar = 'type',
    dest    = 'type',
    choices = ['blob', 'commit', 'tag', 'tree'],
    default = None,
    help    = 'Specify the expected type.'
)

argsp.add_argument(
    'name',
    help = 'The name to parse.'
)

# RM
argsp = argsubparsers.add_parser(
    'rm',
    help = 'Remove files from the working tree and the index.'
)

argsp.add_argument(
    'path',
    nargs = '+',
    help  = 'Files to remove.'
)

# SHOW-REF
argsp = argsubparsers.add_parser(
    'show-ref',
    help = 'List references.'
)

# STATUS
argsp = argsubparsers.add_parser(
    'status',
    help = 'Show the working tree status.'
)

# TAG
argsp = argsubparsers.add_parser(
    'tag',
    help = 'List and create tags.'
)

argsp.add_argument(
    '-a',
    action = 'store_true',
    dest   = 'create_tag_object',
    help   = 'Whether to create a tag object.'
)

argsp.add_argument(
    'name',
    nargs = '?',
    help  = 'The new tag\'s name'
)

argsp.add_argument(
    'object',
    default = 'HEAD',
    nargs   = '?',
    help    = 'The object the new tag will point to.'
)

# =================================================================
#                              COMMANDS
# =================================================================

def cmd_add(args):
    repo = repo_find()
    add(repo, args.path)

def cmd_cat_file(args):
    repo = repo_find()
    cat_file(repo, args.object, fmt=args.type.encode())

def cmd_checkout(args):
    repo = repo_find()

    obj = object_read(repo, object_find(repo, args.commit))

    # If the object is a commit, we grab its tree
    if (obj.fmt == b'commit'):
        obj = object_read(repo, obj.kvlm[b'tree'].decode('ascii'))

    # Verify that path is an empty directory
    if (os.path.exists(args.path)):
        if (not os.path.isdir(args.path)):
            raise Exception(f"Not a directory {args.path}!")
        if (os.listdir(args.path)):
            raise Exception(f"Not empty {args.path}!")
    else:
        os.makedirs(args.path)

    tree_checkout(repo, obj, os.path.realpath(args.path))

def cmd_check_ignore(args):
    repo = repo_find()
    rules = teaignore_read(repo)

    for path in args.path:
        if (check_ignore(rules, path)):
            print(path)

def cmd_commit(args):
    repo = repo_find()
    index = index_read(repo)

    # Create trees, grab back SHA for the root tree.
    tree = tree_from_index(repo, index)

    # Create the commit object itself
    commit = commit_create(
                repo,
                tree,
                object_find(repo, "HEAD"),
                teaconfig_user_get(teaconfig_read()),
                datetime.now(),
                args.message
            )

    # Update HEAD so our commit is now thhe tip of the active branch.
    active_branch = branch_get_active(repo)

    if (active_branch): # If we're on a branch, we update refs/heads/BRANCH
        with open(repo_file(repo, os.path.join("refs/heads", active_branch)), "w") as fd:
            fd.write(commit + "\n")
    else: # Otherwise we update HEAD itself
        with open(repo_file(repo, "HEAD"), "w") as fd:
            fd.write("\n")

def cmd_hash_object(args):
    if (args.write):
        repo = repo_find()
    else:
        repo = None

    with open(args.path, 'rb') as fd:
        sha = hash_object(fd, args.type.encode(), repo)
        print(sha)

def cmd_init(args):
    repo_create(args.path)

def cmd_log(args):
    repo = repo_find()

    print("diagraph tealog{")
    print("  node[shape=rect]")
    log_graphviz(repo, object_find(repo, args.commit), set())
    print("}")

def cmd_ls_files(args):
    repo = repo_find()
    index = index_read(repo)

    if (args.verbose):
        print(f"Index file format v{index.version}, containing {len(index.entries)}")

    for e in index.entries:
        print(e.name)

        if (args.verbose):
            print("  {} with perms: {:o}".format(
                { 0b1000: "regular file",
                  0b1010: "symlink",
                  0b1110: "tea link"
                }[e.mode_type],
                e.mode_perms
            ))

            print(f"  on blob: {e.sha}")

            print("  created: {}.{}, modified: {}.{}".format(
                datetime.fromtimestamp(e.ctime[0]),
                e.ctime[1],
                datetime.fromtimestamp(e.mtime[0]),
                e.mtime[1]
            ))

            print(f"  device:{e.dev}, inode: {e.ino}")
            print("  user: {} ({}) group: {} ({})".format(
                pwd.getpwuid(e.uid).pw_name,
                e.uid,
                grp.getgrgid(e.gid).gr_name,
                e.gid
            ))

            print("  flags: stage={} assume_valid={}".format(
                e.flag_stage,
                e.flag_assume_valid
            ))

def cmd_ls_tree(args):
    repo = repo_find()
    ls_tree(repo, args.tree, args.recursive)

def cmd_rev_parse(args):
    if (args.type):
        fmt = args.type.encode()
    else:
        fmt = None

    repo = repo_find()

    print(object_find(repo, args.name, fmt, follow=True))

def cmd_rm(args):
    repo = repo_find()
    rm(repo, args.path)

def cmd_show_ref(args):
    repo = repo_find()
    refs = ref_list(repo)
    show_ref(repo, refs, prefix="refs")

def cmd_status(args):
    repo = repo_find()
    index = index_read(repo)

    cmd_status_branch(repo)
    cmd_status_head_index(repo, index)
    print()
    cmd_status_index_worktree(repo, index)

def cmd_tag(args):
    repo = repo_find()

    if (args.name):
        tag_create(
            repo,
            args.name,
            args.object,
            #args.create_tag_object
            'object' if args.create_tag_object else 'ref'
        )
    else:
        refs = ref_list(repo)
        show_ref(repo, refs['tags'], with_hash=False)

def main(argv = sys.argv[1:]):
    args = argparser.parse_args(argv)

    match args.command:
        case 'add'          : cmd_add(args)
        case 'cat-file'     : cmd_cat_file(args)
        case 'check-ignore' : cmd_check_ignore(args)
        case 'checkout'     : cmd_checkout(args)
        case 'commit'       : cmd_commit(args)
        case 'hash-object'  : cmd_hash_object(args)
        case 'init'         : cmd_init(args)
        case 'log'          : cmd_log(args)
        case 'ls-files'     : cmd_ls_files(args)
        case 'ls-tree'      : cmd_ls_tree(args)
        case 'rev-parse'    : cmd_rev_parse(args)
        case 'rm'           : cmd_rm(args)
        case 'show-ref'     : cmd_show_ref(args)
        case 'status'       : cmd_status(args)
        case 'tag'          : cmd_tag(args)
        case _              : print('Bad command')

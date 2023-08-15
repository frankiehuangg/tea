import configparser
import os

from lib.kvlm import kvlm_parse, kvlm_serialize
from lib.repo_functions import repo_file
from lib.trees_checkout import tree_parse, tree_serialize

class TeaObject(object):
    def __init__(self, data=None):
        if (data != None):
            self.deserialize(data)
        else:
            self.init()

    def serialize(self, repo):
        """
        This function must be implemented by subclasses
        """
        raise Exception("Unimplemented!")

    def deserialize(self, data):
        raise Exception("Unimplemented!")

    def init(self):
        pass

class TeaBlob(TeaObject):
    fmt = b'blob'

    def serialize(self):
        return self.blobdata

    def deserialize(self, data):
        self.blobdata = data

class TeaCommit(TeaObject):
    fmt = b'commit'

    def deserialize(self, data):
        self.kvlm = kvlm_parse(data) 

    def serialize(self):
        return kvlm_serialize(self.kvlm)

    def init(self):
        self.kvlm = dict()

class TeaTag(TeaCommit):
    fmt = b'tag'

class TeaTree(TeaObject):
    fmt = b'tree'

    def deserialize(self, data):
        self.items = tree_parse(data)

    def serialize(self):
        return tree_serialize(self)

    def init(self):
        self.items = list()

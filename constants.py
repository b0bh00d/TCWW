# pylint: disable=missing-docstring

# https://stackoverflow.com/questions/6343330/importing-a-long-list-of-constants-to-a-python-file
# https://code.activestate.com/recipes/65207-constants-in-python/

from copy import deepcopy

class __const(object):
    def __setattr__(self, name, value):
        if self.__dict__.has_key(name):
            raise NotImplementedError("Object is read-only.")
        self.__dict__[name] = value

    def __getattr__(self, name):
        if self.__dict__.has_key(name):
            return deepcopy(self.__dict__[name])

    def __delattr__(self, item):
        if self.__dict__.has_key(item):
            raise NotImplementedError("Object is read-only.")

FileModes = __const()
FileModes.CLOSED = 0
FileModes.READ_ONLY = 1
FileModes.WRITE_ONLY = 2

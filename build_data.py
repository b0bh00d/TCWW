# pylint: disable=missing-docstring
# pylint: disable=bad-whitespace

import sys
import cPickle

#-------------------------------------------------------------------------#
#     App: TeamCity9 Warning Watcher                                      #
#  Module: build_data.py                                                  #
#  Author: Bob Hood                                                       #
# License: LGPL-3.0                                                       #
#   PyVer: 2.7.x                                                          #
#  Detail: Data class that holds the information mined from the build     #
#          logs.                                                          #
#-------------------------------------------------------------------------#

class BuildData(object):
    DATAVERSION = 1
    def __init__(self):
        super(BuildData, self).__init__()

        self.id = None          # id of the build (full)
        self.prefix = None      # prefix of the build (without build numbers)
        self.number = 0
        self.warnings = []      # text lines from build output that are warnings

    # cPickle decided, rather arbitrarily, to stop working for me when I pickled
    # a class or builtin (like set()).  subsequent load()'s produced errors about
    # the modules not existing.  Google showed many other people with similar
    # problems, but no real solutions.
    #
    # so, this class saves and reconstructs itself piecemeal--which at least
    # works, and allows me to focus on more important technical issues...

    def store(self, pickle_file):
        cPickle.dump(BuildData.DATAVERSION, pickle_file)
        cPickle.dump(self.id, pickle_file)
        cPickle.dump(self.prefix, pickle_file)
        cPickle.dump(self.number, pickle_file)
        cPickle.dump(len(self.warnings), pickle_file)
        for warning in self.warnings:
            cPickle.dump(warning, pickle_file)

    def retrieve(self, pickle_file):
        version = cPickle.load(pickle_file)
        self.id = cPickle.load(pickle_file)
        self.prefix = cPickle.load(pickle_file)
        self.number = cPickle.load(pickle_file)
        warning_count = cPickle.load(pickle_file)
        self.warnings = []
        while warning_count:
            self.warnings.append(cPickle.load(pickle_file))
            warning_count -= 1

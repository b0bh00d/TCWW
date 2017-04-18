import os
import time
import glob
import hashlib

#-------------------------------------------------------------------------#
#     App: TeamCity9 Warning Watcher                                      #
#  Module: log_manager.py                                                 #
#  Author: Bob Hood                                                       #
# License: LGPL-3.0                                                       #
#   PyVer: 2.7.x                                                          #
#  Detail: This module gathers up all available TeamCity build logs and   #
#          stores them in descending chronological order for access by    #
#          other parts of the system.                                     #
#-------------------------------------------------------------------------#

class Log(object):
    def __init__(self, file_name):
        super(Log, self).__init__()

        self.file_name = file_name
        self.name = os.path.split(file_name)[-1]
        self.timestamp = os.stat(file_name).st_mtime

        self.key = None
        self._calculate_log_signature()

    def _calculate_log_signature(self):
        m = hashlib.md5()
        try:
            with open(self.file_name) as log:
                for i in range(3):
                    s = log.readline()
                    if len(s) == 0:
                        # not enough lines yet in the file to calculate a key
                        return
                    m.update(log.readline())

            self.key = m.digest()
        except:
            self.key = None

class LogManager(object):
    def __init__(self, config):
        self.config = config
        self._update_logs()

    def _update_logs(self):
        # establish our current environment
        self.logs = []
        for file_name in glob.glob(os.path.join(self.config.teamcity.build_agent_log_path, 'teamcity-build.log*')):
            self.logs.append(Log(file_name))

        if len(self.logs):
            # sort logs by their timestamps
            # logs at the start of the list are newer than those later in the list
            self.logs.sort(key=lambda x: x.timestamp, reverse=True)

            # creat a map for quick access by key
            self.log_map = {}
            for log in self.logs:
                self.log_map[log.key] = log

    def get_newer(self, key):
        newer_log = None

        newer_log_index = None
        for i in range(len(self.logs)):
            if self.logs[i].key == key:
                if i > 0:
                    newer_log = self.logs[i - 1]
                    break

        return newer_log

    def get_newest(self):
        newest_log = None

        if len(self.logs):
            newest_log = self.logs[0]

        return newest_log

    def get_older(self, key):
        older_log = None

        older_log_index = None
        for i in range(len(self.logs)):
            if self.logs[i].key == key:
                if i < len(self.logs):
                    older_log = self.logs[i + 1]
                    break

        return older_log

    def get_oldest(self):
        oldest_log = None

        if len(self.logs):
            oldest_log = self.logs[-1]

        return oldest_log

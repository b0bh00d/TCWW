# pylint: disable=missing-docstring
# pylint: disable=missing-docstring
# pylint: disable=bad-whitespace
# pylint: disable=too-many-instance-attributes
# Classes may contain as many instance attributes required to perform their function

import os
import re
import sys
import tempfile

from ftplib import FTP

from constants import FileModes
from dropbox import Dropbox

#-------------------------------------------------------------------------#
#     App: TeamCity9 Warning Watcher                                      #
#  Module: cache_file.py                                                  #
#  Author: Bob Hood                                                       #
# License: LGPL-3.0                                                       #
#   PyVer: 2.7.x                                                          #
#  Detail: This module houses a class that takes responsibility for       #
#          managing the cache file, abstracting away its true location.   #
#-------------------------------------------------------------------------#

class CacheFile(object):

    def __init__(self, config, path=tempfile.gettempdir()):
        super(CacheFile, self).__init__()
        self.config = config

        # we do not use the agent name in the file.  this
        # would prevent multiple different agents from
        # accessing/updating the same cache file.

        self.cache_file_name = '%s_%s_%s.pickle' % \
                                (config.teamcity.project_name,
                                 config.teamcity.config_name,
                                 config.teamcity.branch_name)

        self.local_file = None
        self.local_file_fp = None
        self.local_file_open_state = FileModes.CLOSED

        self.path = path

        self.ftp = None
        self.ftp_username = None
        self.ftp_password = None
        self.ftp_address = None
        self.ftp_path = None
        self.ftp_display = None

        self.dropbox = None

        temp_folder = tempfile.gettempdir()
        self.local_file = os.path.join(temp_folder, self.cache_file_name)

        if self.path.startswith('ftp://'):
            # open the FTP connection
            if not self._connect_to_ftp():
                print 'Warning: FTP cache folder could not be accessed: "%s"' % self.path
                print 'Warning: Defaulting to local file: "%s"' % self.local_file
            else:
                self.reset()

        elif self.path.startswith('dropbox:'):
            self.dropbox = Dropbox(self.path)
            if not self.dropbox.available():
                print 'Warning: Dropbox could not be accessed: "%s"' % self.path
                print 'Warning: Defaulting to local file: "%s"' % self.local_file
                self.dropbox = None

        else:
            if not os.path.exists(self.path):
                # make sure the full path to the cache folder exists
                try:
                    os.makedirs(self.path)
                except:
                    pass

            if not os.path.exists(self.path):
                print 'Error: Cache folder does not exist: "%s"' % self.path
                sys.exit(1)

            self.local_file = os.path.join(self.path, self.cache_file_name)

    def __del__(self):
        if self.ftp:
            self.ftp.close()
            if os.path.exists(self.local_file):
                os.remove(self.local_file)

    def reset(self):
        if os.path.exists(self.local_file):
            os.remove(self.local_file)

    def open(self, mode=FileModes.READ_ONLY):
        if mode not in [FileModes.READ_ONLY, FileModes.WRITE_ONLY]:
            return None

        self.local_file_open_state = mode
        self.local_file_fp = None

        if self.ftp:
            if not os.path.exists(self.local_file):
                if not self._retrieve_pickle_file():
                    return None

            try:
                self.local_file_fp = open(self.local_file,
                                          'rb' if mode == FileModes.READ_ONLY else 'wb')
            except:
                self.local_file_fp = None

        elif self.dropbox:
            self.local_file_fp = self.dropbox.open(self.cache_file_name, mode)

        else:
            try:
                self.local_file_fp = open(self.local_file,
                                          'rb' if mode == FileModes.READ_ONLY else 'wb')
            except:
                self.local_file_fp = None

        return self.local_file_fp

    def close(self):
        if self.ftp:
            if (not os.path.exists(self.local_file)) or (not self.local_file_fp):
                return

            try:
                self.local_file_fp.close()
            except:
                pass
            self.local_file_fp = None

            if self.local_file_open_state == FileModes.WRITE_ONLY:
                # upload the (presumably) updated cache file
                if not self._store_pickle_file():
                    print 'Error: Could not store cache file to FTP'
                    sys.exit(1)
                else:
                    self.reset()

        elif self.dropbox:
            self.dropbox.close()
            self.local_file_fp = None

        else:
            try:
                self.local_file_fp.close()
            except:
                pass
            self.local_file_fp = None

    def _retrieve_pickle_file(self):
        if self.ftp:
            files = []
            self.ftp.retrlines('NLST', files.append)
            if self.cache_file_name in files:
                try:
                    self.ftp.retrbinary('RETR %s' % self.cache_file_name,
                                        open(self.local_file, 'wb').write)
                except:
                    return False

        return True

    def _store_pickle_file(self):
        if self.ftp:
            with open(self.local_file, 'rb') as local_file_input:
                try:
                    self.ftp.storbinary('STOR %s' % self.cache_file_name, local_file_input)
                except:
                    return False

        return True

    def _connect_to_ftp(self):
        result = re.search(r'^ftp:\/\/([\da-z]+):([^\@]+)\@([^\/\s]+)\/(.+)$', self.path)
        if not result:
            return False

        self.ftp_username = result.group(1)
        self.ftp_password = result.group(2)
        self.ftp_address = result.group(3)
        self.ftp_path = result.group(4)

        # take the username/password info out of any displayed value
        self.ftp_display = 'ftp://%s/%s' % (self.ftp_address, self.ftp_path)

        try:
            self.ftp = FTP(self.ftp_address)
        except:
            self.ftp = None
            return False

        try:
            self.ftp.login(self.ftp_username, self.ftp_password)
        except:
            self.ftp.close()
            self.ftp = None
            return False

        #print self.ftp.getwelcome()

        try:
            self.ftp.cwd(self.ftp_path)
        except:
            self.ftp.close()
            self.ftp = None
            return False

        return True

    def __str__(self):
        if self.ftp:
            return '%s/%s' % (self.ftp_display, self.cache_file_name)
        if self.dropbox:
            return str(self.dropbox)
        return os.path.join(os.path.abspath(self.path), self.cache_file_name)

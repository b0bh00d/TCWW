# pylint: disable=missing-docstring
# pylint: disable=missing-docstring
# pylint: disable=bad-whitespace
# pylint: disable=too-many-instance-attributes
# Classes may contain as many instance attributes required to perform their function

import os
import sys
import md5
import uuid
import json
import time
import tempfile

DROPBOX_AVAILABLE = True
try:
    import dropbox
except ImportError:
    DROPBOX_AVAILABLE = False

from constants import FileModes

MAXSINGLEDBFILE = 150*1024*1024

#-------------------------------------------------------------------------#
#     App: TeamCity9 Warning Watcher                                      #
#  Module: dropbox.py                                                     #
#  Author: Bob Hood                                                       #
# License: LGPL-3.0                                                       #
#   PyVer: 2.7.x                                                          #
#  Detail: This module provides an interface to the Dropbox service.      #
#     URL: https://www.dropbox.com/developers-v1/core/docs                #
#-------------------------------------------------------------------------#

def _make_dropbox_chunks(datapath, maxsingle):
    """
    This function is used in cases where file uploads exceed
    the single-file limit of MAXSINGLEDBFILE
    """

    _basename = os.path.basename(datapath)
    _size = os.path.getsize(datapath)
    if (maxsingle == 0) or (_size <= maxsingle):
        yield (datapath, _size)
    else:
        _counter = 1
        _bufsize = 1024*1024
        with open(datapath, 'rb') as _input:
            _done = False
            while not _done:
                _chunk_name = '%04d_%s' % (_counter, _basename)
                _chunk_path = os.path.join(tempfile.gettempdir(), _chunk_name)

                _max_single = maxsingle
                _bytes_read = 0
                with open(_chunk_path, 'wb') as _output:
                    while _max_single > 0:
                        _data_amount = min(_bufsize, _max_single)
                        _data = _input.read(_data_amount)
                        if len(_data) == 0:
                            # end of file
                            _done = True
                            break
                        _output.write(_data)
                        _max_single -= _data_amount
                        _bytes_read += len(_data)

                yield (_chunk_path, _bytes_read)
                os.remove(_chunk_path)

                _counter += 1

class Dropbox(object):
    def __init__(self, dropbox_path, local_file=None):
        super(Dropbox, self).__init__()

        self.dropbox = None
        self.dropbox_token = ''
        self.dropbox_path = ''

        self.file_name = ''
        self.local_file_open_state = 0
        self.local_file_fp = None
        self.local_file_md5 = 0

        if local_file:
            self.local_file = local_file
        else:
            temp_folder = tempfile.gettempdir()
            self.local_file = os.path.join(temp_folder, str(uuid.uuid4()))

        if dropbox_path.startswith('dropbox:') and DROPBOX_AVAILABLE:
            items = dropbox_path.split(':')

            if len(items) < 3:
                print 'Error: Dropbox missing App access token: "%s"' % dropbox_path
                sys.exit(1)

            self.dropbox_token = items[1]
            assert len(self.dropbox_token), \
                'Error: Dropbox missing App access token: "%s"' % dropbox_path

            self.dropbox_path = items[2]
            if self.dropbox_path == '/':
                self.dropbox_path = ''

            try:
                self.dropbox = dropbox.client.DropboxClient(self.dropbox_token)
            except:
                self.dropbox = None
            else:
                self._reset()

    def available(self):
        return self.dropbox is not None

    def open(self, file_name, mode=FileModes.READ_ONLY):
        if not self.dropbox:
            return None

        self.file_name = file_name
        self.local_file_open_state = mode
        self.local_file_fp = None
        self.local_file_md5 = ''

        if mode not in [FileModes.READ_ONLY, FileModes.WRITE_ONLY]:
            return None

        if (mode == FileModes.READ_ONLY) and (not os.path.exists(self.local_file)):
            if not self._retrieve_file_locally():
                return None

        try:
            self.local_file_fp = open(self.local_file,
                                      'rb' if mode == FileModes.READ_ONLY else 'wb')
        except IOError:
            self.local_file_fp = None

        if os.path.exists(self.local_file):
            data = open(self.local_file).read()
            local_file_md5 = md5.new()
            local_file_md5.update(data)
            self.local_file_md5 = local_file_md5.digest()

        return self.local_file_fp

    def close(self):
        if (not self.dropbox) or \
           (not os.path.exists(self.local_file)) or \
           (not self.local_file_fp):
            return

        try:
            self.local_file_fp.close()
        except:
            pass
        self.local_file_fp = None

        if os.path.exists(self.local_file) and \
           (self.local_file_open_state == FileModes.WRITE_ONLY):

            data = open(self.local_file).read()
            local_file_md5 = md5.new()
            local_file_md5.update(data)
            current_md5 = local_file_md5.digest()

            if self.local_file_md5 != current_md5:
                # upload the modified file
                if not self._store_file_remotely():
                    print "Error: Could not store local file '%s' to Dropbox '%s/%s'" % \
                        (self.local_file, self.dropbox_path, self.file_name)
                    sys.exit(1)

        self._reset()

    def _reset(self):
        if os.path.exists(self.local_file):
            os.remove(self.local_file)

    def _retrieve_file_locally(self):
        full_dropbox_path = '%s/%s' % (self.dropbox_path, self.file_name)

        try:
            with open(self.local_file, 'w') as local_output:
                with self.dropbox.get_file(full_dropbox_path) as dropbox_input:
                    local_output.write(dropbox_input.read())
        except IOError:
            print "Error: Failed to retrieve remote Dropbox file '%s'" % full_dropbox_path
            return False
        except dropbox.rest.ErrorResponse, error_object:
            if error_object.status == 404:
                # it probably doesn't exist yet
                self._reset()
            else:
                print "Error %d: Failed to retrieve remote Dropbox file '%s': %s" % \
                   (error_object.status, full_dropbox_path, error_object.error_msg)
            return False

        return True

    def _store_file_remotely(self):
        full_dropbox_path = '%s/%s' % (self.dropbox_path, self.file_name)

        # we can use a chunked uploader for any size file,
        # but it's really intended for files larger than the
        # MAXSINGLEDBFILE limit.  for smaller files, though,
        # the Dropbox.put_file() method is probably lighter
        # and more efficient.

        file_size = os.stat(self.local_file).st_size
        if file_size > MAXSINGLEDBFILE:
            failed = False
            for chunk in _make_dropbox_chunks(self.local_file, MAXSINGLEDBFILE):
                with open(chunk[0], 'rb') as local_input:
                    uploader = self.dropbox.get_chunked_uploader(local_input, chunk[1])
                    try_counter = 0
                    while uploader.offset < chunk[1]:
                        try:
                            upload_json = uploader.upload_chunked()
                        except dropbox.rest.ErrorResponse, error_object:
                            try_counter += 1
                            print "Warning: Dropbox upload failed; retry count %d" % try_counter
                            if try_counter == 5:
                                failed = True
                                break
                            time.sleep(1.0)

                    if not failed:
                        try:
                            response_json = uploader.finish(full_dropbox_path, overwrite=True)
                        except dropbox.rest.ErrorResponse, error_object:
                            print "Dropbox Error %d: File '%s': '%s'" % \
                                (error_object.status, full_dropbox_path, error_object.message)
                            return False
                        except:
                            print "Error: Failed to add remote Dropbox file '%s'" % \
                                full_dropbox_path
                            return False
                        else:
                            #json_data = json.loads(response_json)
                            #print 'Dropbox: Uploaded "%s"' % json_data["path"]
                            pass
        else:
            # simple put_file() will do
            with open(self.local_file, 'rb') as local_file_input:
                try:
                    response_json = self.dropbox.put_file(
                        full_dropbox_path, local_file_input, overwrite=True)
                except dropbox.rest.ErrorResponse, error_object:
                    print "Dropbox Error %d: File '%s': '%s'" % \
                        (error_object.status, full_dropbox_path, error_object.message)
                    return False
                except:
                    print "Error: Failed to add remote Dropbox file '%s'" % \
                        full_dropbox_path
                    return False
                else:
                    #json_data = json.loads(response_json)
                    #print 'Dropbox: Uploaded "%s"' % json_data["path"]
                    pass

        return True

    def __str__(self):
        return 'dropbox:%s/%s' % (self.dropbox_path, self.file_name)

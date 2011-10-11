# -*- python -*-
# -*- coding: utf-8 -*-
# Started 26/05/2011 by Seblu <seblu@seblu.net>

'''
InstallSystems Generic Tools Library
'''

import os
import hashlib
import shutil
import urllib2

from progressbar import ProgressBar, Percentage, FileTransferSpeed
from progressbar import Bar, BouncingBar, ETA, UnknownLength
from installsystems.tarball import Tarball
from installsystems.printer import *


################################################################################
# Classes
################################################################################

class PipeFile(object):
    '''
    Pipe file object if a file object with extended capabilties
    like printing progress bar or compute file size, md5 on the fly
    '''

    def __init__(self, path=None, mode="r", fileobj=None, timeout=3,
                 progressbar=False):
        self.progressbar = progressbar
        self.open(path, mode, fileobj, timeout)

    def open(self, path=None, mode="r", fileobj=None, timeout=3):
        if path is None and fileobj is None:
            raise AttributeError("You must have a path or a fileobj to open")
        if mode not in ("r", "w"):
            raise AttributeError("Invalid open mode. Must be r or w")
        self.mode = mode
        self._md5 = hashlib.md5()
        self.size = None
        self.consumed_size = 0
        if fileobj is not None:
            self.fo = fileobj
            # seek to 0 and compute filesize if we have and fd
            if hasattr(self.fo, "fileno"):
                self.seek(0)
                self.size = os.fstat(self.fo.fileno()).st_size
        else:
            ftype = pathtype(path)
            if ftype == "file":
                self.fo = open(path, self.mode)
                self.size = os.fstat(self.fo.fileno()).st_size
            elif ftype == "http" or ftype == "ftp":
                try:
                    self.fo = urllib2.urlopen(path, timeout=timeout)
                except Exception as e:
                    # FIXME: unable to open file
                    raise IOError(e)
                if "Content-Length" in self.fo.headers:
                    self.size = int(self.fo.headers["Content-Length"])
            else:
                raise NotImplementedError
        # init progress bar
        if self.size is None:
            widget = [ BouncingBar(), " ", FileTransferSpeed() ]
            maxval = UnknownLength
        else:
            widget = [ Percentage(), " ", Bar(), " ", FileTransferSpeed(), " ", ETA() ]
            maxval = self.size
        self._progressbar = ProgressBar(widgets=widget, maxval=maxval)
        # start progressbar display if asked
        if self.progressbar:
            self._progressbar.start()

    def close(self):
        if self.progressbar:
            self._progressbar.finish()
        debug("MD5: %s" % self.md5)
        debug("Size: %s" % self.size)
        self.fo.close()

    def read(self, size=None):
        if self.mode == "w":
            raise IOError("Unable to read in w mode")
        buf = self.fo.read(size)
        length = len(buf)
        self._md5.update(buf)
        self.consumed_size += length
        if self.progressbar and length > 0:
            self._progressbar.update(self.consumed_size)
        return buf

    def flush(self):
        if hasattr(self.fo, "flush"):
            return self.fo.flush()

    def write(self, buf):
        if self.mode == "r":
            raise IOError("Unable to write in r mode")
        length = len(buf)
        self._md5.update(buf)
        self.consumed_size += length
        if self.progressbar and length > 0:
            self._progressbar.update(self.consumed_size)
        return None

    def consume(self):
        '''
        Read all data and doesn't save it
        Useful to obtain md5 and size
        '''
        if self.mode == "w":
            raise IOError("Unable to read in w mode")
        while True:
            buf = self.read(65536)
            if len(buf) == 0:
                break

    @property
    def md5(self):
        '''
        Return the md5 of read/write of the file
        '''
        return self._md5.hexdigest()

    @property
    def read_size(self):
        '''
        Return the current read size
        '''
        return self.consumed_size

    @property
    def write_size(self):
        '''
        Return the current wrote size
        '''
        return self.consumed_size

################################################################################
# Functions
################################################################################

def smd5sum(buf):
    '''
    Compute md5 of a string
    '''
    m = hashlib.md5()
    m.update(buf)
    return m.hexdigest()

def copy(source, destination, uid=None, gid=None, mode=None, timeout=None):
    '''
    Copy a source to destination. Take care of path type
    '''
    stype = pathtype(source)
    dtype = pathtype(destination)
    # ensure destination is not a directory
    if dtype == "file" and os.path.isdir(destination):
        destination = os.path.join(destination, os.path.basename(source))
    # trivial case
    if stype == dtype == "file":
        shutil.copy(source, destination)
    elif (stype == "http" or stype == "ftp") and dtype == "file":
        f_dest = open(destination, "w")
        f_source = urllib2.urlopen(source, timeout=timeout)
        copyfileobj(f_source, f_dest)
    elif stype == "file" and dtype == "":
        raise NotImplementedError
    else:
        raise NotImplementedError
    # setting destination file rights
    if dtype == "file":
        chrights(destination, uid, gid, mode)

def mkdir(path, uid=None, gid=None, mode=None):
    '''
    Create a directory and set rights
    '''
    os.makedirs(path)
    chrights(path, uid, gid, mode)

def chrights(path, uid=None, gid=None, mode=None, mtime=None):
    '''
    Set rights on a file
    '''
    if uid is not None:
        os.chown(path, uid, -1)
    if gid is not None:
        os.chown(path, -1, gid)
    if mode is not None:
        os.chmod(path, mode)
    if mtime is not None:
        os.utime(path, (mtime, mtime))

def pathtype(path):
    '''
    Return path type. This is usefull to know what kind of path is given
    '''
    if path.startswith("http://") or path.startswith("https://"):
        return "http"
    if path.startswith("ftp://") or path.startswith("ftps://"):
        return "ftp"
    elif path.startswith("ssh://"):
        return "ssh"
    else:
        return "file"

def isfile(path):
    '''
    Return True if path is of type file
    '''
    return pathtype(path) == "file"

def abspath(path):
    '''
    Format a path to be absolute
    '''
    ptype = pathtype(path)
    if ptype in ("http", "ftp", "ssh"):
        return path
    elif ptype == "file":
        if path.startswith("file://"):
            path = path[len("file://"):]
        return os.path.abspath(path)
    else:
        return None

def getsize(path):
    '''
    Get size of a path. Recurse if directory
    '''
    total_sz = os.path.getsize(path)
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            for filename in dirs + files:
                filepath = os.path.join(root, filename)
                filestat = os.lstat(filepath)
                if stat.S_ISDIR(filestat.st_mode) or stat.S_ISREG(filestat.st_mode):
                    total_sz += filestat.st_size
    return total_sz

def human_size(num):
    '''
    Return human readable size
    '''
    for x in ['Bytes', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']:
        if num < 1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0
    return "%3.1f%s" % (num, x)

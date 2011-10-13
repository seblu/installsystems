# -*- python -*-
# -*- coding: utf-8 -*-
# Started 26/05/2011 by Seblu <seblu@seblu.net>

'''
InstallSystems Generic Tools Library
'''

import os
import re
import hashlib
import shutil
import urllib2
import paramiko
import time

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
        self.open(path, mode, fileobj, timeout)
        # start progressbar display if asked
        self.progressbar = progressbar

    def open(self, path=None, mode="r", fileobj=None, timeout=3):
        if path is None and fileobj is None:
            raise AttributeError("You must have a path or a fileobj to open")
        if mode not in ("r", "w"):
            raise AttributeError("Invalid open mode. Must be r or w")
        self.mode = mode
        self.timeout = timeout
        self._md5 = hashlib.md5()
        self.size = None
        self.mtime = None
        self.consumed_size = 0
        # we already have and fo, nothing to open
        if fileobj is not None:
            self.fo = fileobj
            # seek to 0 and compute filesize if we have and fd
            if hasattr(self.fo, "fileno"):
                self.seek(0)
                self.size = os.fstat(self.fo.fileno()).st_size
        # we need to open the path
        else:
            ftype = pathtype(path)
            if ftype == "file":
                self._open_local(path)
            elif ftype == "http":
                self._open_http(path)
            elif ftype == "ftp":
                self._open_ftp(path)
            elif ftype == "ssh":
                self._open_ssh(path)
            else:
                raise IOError("URL type not supported")
        # init progress bar
        if self.size is None:
            widget = [ BouncingBar(), " ", FileTransferSpeed() ]
            maxval = UnknownLength
        else:
            widget = [ Percentage(), " ", Bar(), " ", FileTransferSpeed(), " ", ETA() ]
            maxval = self.size
        self._progressbar = ProgressBar(widgets=widget, maxval=maxval)

    def _open_local(self, path):
        '''
        Open file on the local filesystem
        '''
        self.fo = open(path, self.mode)
        sta = os.fstat(self.fo.fileno())
        self.size = sta.st_size
        self.mtime = sta.st_mtime

    def _open_http(self, path):
        '''
        Open a file accross an http server
        '''
        try:
            self.fo = urllib2.urlopen(path, timeout=self.timeout)
        except Exception as e:
            # FIXME: unable to open file
            raise IOError(e)
        # get file size
        if "Content-Length" in self.fo.headers:
            self.size = int(self.fo.headers["Content-Length"])
        else:
            self.size = None
        # get mtime
        try:
            self.mtime = int(time.mktime(time.strptime(self.fo.headers["Last-Modified"],
                                                       "%a, %d %b %Y %H:%M:%S %Z")))
        except:
            self.mtime = None

    def _open_ftp(self, path):
        '''
        Open file via ftp
        '''
        try:
            self.fo = urllib2.urlopen(path, timeout=self.timeout)
        except Exception as e:
            # FIXME: unable to open file
            raise IOError(e)
        # get file size
        try:
            self.size = int(self.fo.headers["content-length"])
        except:
            self.size = None

    def _open_ssh(self, path):
        '''
        Open current fo from an ssh connection
        '''
        # parse url
        (login, passwd, host, port, path) = re.match(
            "ssh://(([^:]+)(:([^@]+))?@)?([^/:]+)(:(\d+))?(/.*)?", path).group(2, 4, 5, 7, 8)
        if port is None: port = 22
        if path is None: path = "/"
        # open ssh connection
        # we need to keep it inside the object unless it was cutted
        self._ssh = paramiko.SSHClient()
        self._ssh.load_system_host_keys()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._ssh.connect(host, port=port, username=login, password=passwd,
                          look_for_keys=True,
                          timeout=int(self.timeout))
        # swith in sftp mode
        sftp = self._ssh.open_sftp()
        # get the file infos
        sta = sftp.stat(path)
        self.size = sta.st_size
        self.mtime = sta.st_mtime
        # open the file
        self.fo = sftp.open(path, self.mode)
        # this is needed to have correct file transfert speed
        self.fo.set_pipelined(True)

    def close(self):
        if self.progressbar:
            self._progressbar.finish()
        debug("MD5: %s" % self.md5)
        debug("Size: %s" % self.consumed_size)
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

    def consume(self, fo=None):
        '''
        Consume (read) all data and write it in fo
        if fo is None, data are discarded. This is useful to obtain md5 and size
        Useful to obtain md5 and size
        '''
        if self.mode == "w":
            raise IOError("Unable to read in w mode")
        while True:
            buf = self.read(1048576) # 1MiB
            if len(buf) == 0:
                break
            if fo is not None:
                fo.write(buf)

    @property
    def progressbar(self):
        '''
        Return is progressbar have been started
        '''
        return hasattr(self, "_progressbar_started")

    @progressbar.setter
    def progressbar(self, val):
        '''
        Set this property to true enable progress bar
        '''
        if val == True:
            self._progressbar_started = True
            self._progressbar.start()

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

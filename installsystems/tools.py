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
from installsystems.tarball import Tarball

def md5sum(path=None, fileobj=None):
    '''
    Compute md5 of a file
    '''
    if path is None and fileobj is None:
        raise ValueError("No path or fileobj specified")
    if fileobj is None:
        fileobj = uopen(path)
    m = hashlib.md5()
    while True:
        buf = fileobj.read(1024 * m.block_size)
        if len(buf) == 0:
            break
        m.update(buf)
    return m.hexdigest()

def copyfileobj(sfile, dfile):
    '''
    Copy data from sfile to dfile computing length and md5 on the fly
    '''
    f_sum = hashlib.md5()
    f_len = 0
    while True:
        buf = sfile.read(1024 * f_sum.block_size)
        buf_len = len(buf)
        if buf_len == 0:
            break
        f_len += buf_len
        f_sum.update(buf)
        if dfile is not None:
            dfile.write(buf)
    return (f_len , f_sum.hexdigest())

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
    elif stype == "http" and dtype == "file":
        f_dest = open(destination, "w")
        f_source = urllib2.urlopen(source, timeout=timeout)
        f_dest.write(f_source.read())
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
    os.mkdir(path)
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
    if ptype in ("http", "ssh"):
        return path
    elif ptype == "file":
        if path.startswith("file://"):
            path = path[len("file://"):]
        return os.path.abspath(path)
    else:
        return None

def uopen(path, mode="rb"):
    '''
    Universal Open
    Create a file-like object to a file which can be remote
    '''
    ftype = pathtype(path)
    if ftype == "file":
        return open(path, mode)
    elif ftype == "http" or ftype == "ftp":
        return urllib2.urlopen(path)
    else:
        raise NotImplementedError

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

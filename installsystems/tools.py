#!/usr/bin/env python
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

def md5sum(path):
    '''Compute md5 of a file'''
    m = hashlib.md5()
    m.update(open(path, "r").read())
    return m.hexdigest()

def copy(source, destination, uid=None, gid=None, mode=None, timeout=None):
    '''Copy a source to destination. Take care of path type'''
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
    '''Create a directory and set rights'''
    os.mkdir(path)
    chrights(path, uid, gid, mode)

def chrights(path, uid=None, gid=None, mode=None):
    '''Set rights on a file'''
    if uid is not None:
        os.chown(path, uid, -1)
    if gid is not None:
        os.chown(path, -1, gid)
    if mode is not None:
        os.chmod(path, mode)

def pathtype(path):
    '''Return path type. This is usefull to know what king of path is given'''
    from installsystems.image import Image
    if path.startswith("http://") or path.startswith("https://"):
        return "http"
    if path.startswith("ftp://") or path.startswith("ftps://"):
        return "ftp"
    elif path.startswith("ssh://"):
        return "ssh"
    elif path.startswith("file://") or path.startswith("/") or os.path.exists(path):
        return "file"
    elif Image.check_image_name(path):
        return "name"
    return None

def abspath(path):
    '''Format a path to be absolute'''
    ptype = pathtype(path)
    if ptype in ("http", "ssh"):
        return path
    elif ptype == "file":
        if path.startswith("file://"):
            path = path[len("file://")]
        return os.path.abspath(path)
    else:
        return None

def uopen(path):
    '''Universal Open
    Create a file-like object to a file which can be remote
    '''
    ftype = pathtype(path)
    if ftype == "file":
        return open(path, "r")
    elif ftype == "http" or ftype == "ftp":
        return urllib2.urlopen(path)
    else:
        raise NotImplementedError

def extractdata(image, name, target, filelist=None):
    '''Extract a databall name into target
    This will be done accross a forking to allow higher performance and
    on the fly checksumming
    '''
    filename = "%s-%s%s" % (image.id, name, image.extension_data)
    if filename not in image.datas.keys():
        raise Exception("No such data tarball in %s" % image.name)
    datainfo = image.datas[filename]
    fileobject = ropen(filename)
    tarball = Tarball.open(fileobj=fileobject, mode="r|gz")
    if filelist is None:
        tarball.extractall(target)
    else:
        for f in filelist:
            tarball.extract(f, target)
    tarball.close()
    fileobject.close()

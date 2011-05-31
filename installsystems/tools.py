#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Started 26/05/2011 by Seblu <seblu@seblu.net>

'''
InstallSystems Generic Tools Library
'''

import os
import hashlib
import shutil

def md5sum(path):
    '''Compute md5 of a file'''
    m = hashlib.md5()
    m.update(open(path, "r").read())
    return m.hexdigest()

def copy(source, destination, uid=None, gid=None, mode=None):
    '''Copy a source to destination. Take care of path type'''
    stype = pathtype(source)
    dtype = pathtype(destination)
    if stype == dtype == "file":
        shutil.copy(source, destination)
    elif stype == "file" and dtype == "":
        raise NotImplementedError
    else:
        raise NotImplementedError
    # setting destination file rights
    if dtype == "file":
        if os.path.isdir(destination):
            destination = os.path.join(destination, os.path.basename(source))
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

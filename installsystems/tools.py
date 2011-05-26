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

def cp(source, destination):
    '''Copy a source to destination. Take care of path type'''
    stype = get_path_type(source)
    dtype = get_path_type(destination)
    if stype == dtype == "file":
        shutil.copy(source, destination)
    elif stype == "file" and dtype == "":
        raise NotImplementedError
    else:
        raise NotImplementedError

def get_path_type(path):
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

def complete_path(path):
    '''Format a path to be complete'''
    ptype = get_path_type(path)
    if ptype in ("http", "ssh"):
        return path
    elif ptype == "file":
        if path.startswith("file://"):
            path = path[len("file://")]
        return os.path.abspath(path)
    else:
        return None

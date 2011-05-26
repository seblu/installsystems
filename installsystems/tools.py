#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Started 26/05/2011 by Seblu <seblu@seblu.net>

'''
InstallSystems Generic Tools Library
'''

import os
import hashlib

def md5sum(path):
    '''Compute md5 of a file'''
    m = hashlib.md5()
    m.update(open(path, "r").read())
    return m.hexdigest()

def cp(source, destination):
    '''Copy a source to destination. Take care of path type'''
    stype = path_type(source)
    dtype = path_type(destination)
    if stype == dtype == "file":
        shutil.copy(source, destination)
    elif stype == "file" and dtype == "":
        pass

def get_path_type(path):
    '''Return path type. This is usefull to know what king of path is given'''
    if path.startswith("http://") or path.startswith("https://"):
        return "http"
    elif path.startswith("ssh://"):
        return "ssh"
    elif path.startswith("file://") or os.path.exists(path):
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

def path_strip_file(path):
    '''Remove file:// header of a local file path'''
    if path.startswith("file://"):
        return path[len("file://")]
    return path

# -*- python -*-
# -*- coding: utf-8 -*-
# Started 17/05/2011 by Seblu <seblu@seblu.net>

'''
Tarball wrapper
'''

import os
import time
import tarfile
import StringIO
import re
import fnmatch

class Tarball(tarfile.TarFile):
    def add_str(self, name, content, ftype, mode):
        '''
        Add a string in memory as a file in tarball
        '''
        ti = tarfile.TarInfo(name)
        ti.type = ftype
        ti.mode = mode
        ti.mtime = int(time.time())
        ti.uid = ti.gid = 0
        ti.uname = ti.gname = "root"
        ti.size = len(content) if content is not None else 0
        self.addfile(ti, StringIO.StringIO(content))

    def get_str(self, name):
        '''
        Return a string from a filename in a tarball
        '''
        ti = self.getmember(name)
        fd = self.extractfile(ti)
        return fd.read() if fd is not None else ""

    def getnames(self, re_pattern=None, glob_pattern=None):
        lorig = super(Tarball, self).getnames()
        # regexp matching
        if re_pattern is not None:
            return [ tpname for tpname in lorig
                     if re.match(reg_pattern, tpname) ]
        # globbing matching
        if glob_pattern is not None:
            return fnmatch.filter(lorig, glob_pattern)
        return lorig

    def size(self):
        '''
        Return real (uncompressed) size of the tarball
        '''
        total_sz = 0
        for ti in self.getmembers():
            total_sz += ti.size
        return total_sz

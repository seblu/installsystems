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
# Use tarfile from python 2.7 which include filter parameter in add method.
# This is really needed to filter an modify tarball content on the fly.
# Should be removed when python 2.7 will be the minimum python version
from installsystems import tarfile

class Tarball(tarfile.TarFile):
    def add_str(self, name, content, ftype, mode):
        '''Add a string in memory as a file in tarball'''
        ti = tarfile.TarInfo(name)
        ti.type = ftype
        ti.mode = mode
        ti.mtime = int(time.time())
        ti.uid = ti.gid = 0
        ti.uname = ti.gname = "root"
        ti.size = len(content) if content is not None else 0
        self.addfile(ti, StringIO.StringIO(content))

    def get_str(self, name):
        '''Return a string from a filename in a tarball'''
        ti = self.getmember(name)
        return self.extractfile(ti).read()

    def getnames(self, reg_pattern=None):
        lorig = super(Tarball, self).getnames()
        if reg_pattern is None:
            return lorig
        else:
            return [ tpname for tpname in lorig
                     if re.match(reg_pattern, tpname) ]

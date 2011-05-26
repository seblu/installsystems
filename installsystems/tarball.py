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

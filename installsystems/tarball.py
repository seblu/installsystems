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

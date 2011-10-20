# -*- python -*-
# -*- coding: utf-8 -*-
# Started 17/05/2011 by Seblu <seblu@seblu.net>

'''
Tarball wrapper
'''

import os
import sys
import time
import installsystems.tarfile as tarfile # needed until python2.7
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
                     if re.match(re_pattern, tpname) ]
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

    def chown(self, tarinfo, targetpath):
        '''
        Override real chown method from tarfile which make crazy check about
        uid/gid before chowning. This leads to bug when a uid/gid doesn't
        exitsts on the running system

        This overide as a sexy side effect which allow badly create tarball
        (whithout --numeric-owner) to be extracted correctly

        This was reported upstream: http://bugs.python.org/issue12841
        '''
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            # We have to be root to do so.
            try:
                if tarinfo.issym() and hasattr(os, "lchown"):
                    os.lchown(targetpath, tarinfo.uid, tarinfo.gid)
                else:
                    if sys.platform != "os2emx":
                        os.chown(targetpath, tarinfo.uid, tarinfo.gid)
            except EnvironmentError, e:
                raise ExtractError("could not change owner")

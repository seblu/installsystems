# -*- python -*-
# -*- coding: utf-8 -*-

# This file is part of Installsystems.
#
# Installsystems is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Installsystems is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Installsystems.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import time
import tarfile
import StringIO
import re
import fnmatch
from installsystems.exception import *

class Tarball(tarfile.TarFile):
    '''
    Tarball wrapper
    '''

    def add_str(self, name, content, ftype, mode, mtime=None,
                uid=None, gid=None, uname=None, gname=None):
        '''
        Add a string in memory as a file in tarball
        '''
        if isinstance(name, unicode):
            name = name.encode("UTF-8")
        ti = tarfile.TarInfo(name)
        # set tarinfo attribute
        for v in ("name", "ftype", "mode", "mtime", "uid", "gid", "uname", "gname"):
            if vars()[v] is not None:
                vars(ti)[v] = vars()[v]
        # set mtime to current if not specified
        if mtime is None:
            ti.mtime = int(time.time())
        # unicode char is encoded in UTF-8, has changelog must be in UTF-8
        if isinstance(content, unicode):
            content = content.encode("UTF-8")
        ti.size = len(content) if content is not None else 0
        self.addfile(ti, StringIO.StringIO(content))

    def get_str(self, name):
        '''
        Return a string from a filename in a tarball
        '''
        if isinstance(name, unicode):
            name = name.encode("UTF-8")
        ti = self.getmember(name)
        fd = self.extractfile(ti)
        return fd.read() if fd is not None else ""

    def get_utf8(self, name):
        '''
        Return an unicode string from a file encoded in UTF-8 inside tarball
        '''
        if isinstance(name, unicode):
            name = name.encode("UTF-8")
        try:
            return unicode(self.get_str(name), "UTF-8")
        except UnicodeDecodeError:
            raise ISError(u"Invalid UTF-8 character in %s" % name)

    def getnames(self, re_pattern=None, glob_pattern=None, dir=True):
        names = super(Tarball, self).getnames()
        # regexp matching
        if re_pattern is not None:
            names = filter(lambda x: re.match(re_pattern, x), names)
        # globbing matching
        if glob_pattern is not None:
            names = fnmatch.filter(names, glob_pattern)
        # dir filering
        if not dir:
            names = filter(lambda x: not self.getmember(x).isdir(), names)
        # unicode encoding
        return map(lambda x: unicode(x, "UTF-8"), names)

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

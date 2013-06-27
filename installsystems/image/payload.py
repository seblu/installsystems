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

from installsystems.exception import ISError
from installsystems.image.image import Image
from installsystems.printer import debug
from installsystems.tools import PipeFile, mkdir
from installsystems.tools import chrights, get_compressor_path
from os import umask, listdir
from os.path import join, isdir, exists, dirname
from subprocess import Popen, PIPE
from time import time

'''
Image payload module
'''

class Payload(object):
    '''
    Payload class represents a payload object
    '''
    extension = ".isdata"
    legit_attr = ("isdir", "md5", "size", "uid", "gid", "mode", "mtime", "compressor")

    def __init__(self, name, filename, path, **kwargs):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "filename", filename)
        object.__setattr__(self, "path", path)
        # register legit param
        for attr in self.legit_attr:
            setattr(self, attr, None)
        # set all named param
        for kwarg in kwargs:
            # do not use hasattr which use getattr and so call md5 checksum...
            if kwarg in self.legit_attr:
                setattr(self, kwarg, kwargs[kwarg])

    def __getattr__(self, name):
        # get all value with an understance as if there is no underscore
        if hasattr(self, u"_%s" % name):
            return getattr(self, u"_%s" % name)
        raise AttributeError

    def __setattr__(self, name, value):
        # set all value which exists have no underscore, but where underscore exists
        if name in self.legit_attr:
            object.__setattr__(self, u"_%s" % name, value)
        else:
            object.__setattr__(self, name, value)

    def checksummize(self):
        '''
        Fill missing md5/size about payload
        '''
        fileobj = PipeFile(self.path, "r")
        fileobj.consume()
        fileobj.close()
        if self._size is None:
            self._size = fileobj.read_size
        if self._md5 is None:
            self._md5 = fileobj.md5

    @property
    def md5(self):
        '''
        Return md5 of payload
        '''
        if self._md5 is None:
            self.checksummize()
        return self._md5

    @property
    def size(self):
        '''
        Return size of payload
        '''
        if self._size is None:
            self.checksummize()
        return self._size

    @property
    def uid(self):
        '''
        Return uid of owner of orginal payload
        '''
        return self._uid if self._uid is not None else 0

    @property
    def gid(self):
        '''
        Return gid of owner of orginal payload
        '''
        return self._gid if self._gid is not None else 0

    @property
    def mode(self):
        '''
        Return mode of orginal payload
        '''
        if self._mode is not None:
            return self._mode
        else:
            oldmask = umask(0)
            umask(oldmask)
            return 0666 & ~oldmask

    @property
    def mtime(self):
        '''
        Return last modification time of orginal payload
        '''
        return self._mtime if self._mtime is not None else time()

    @property
    def compressor(self):
        '''
        Return payload compress format
        '''
        return self._compressor if self._compressor is not None else Image.default_compressor

    @property
    def info(self):
        '''
        Return a dict of info about current payload
        Auto calculated info like name and filename must not be here
        '''
        return {"md5": self.md5,
                "size": self.size,
                "isdir": self.isdir,
                "uid": self.uid,
                "gid": self.gid,
                "mode": self.mode,
                "mtime": self.mtime}

    def check(self):
        '''
        Check that path correspond to current md5 and size
        '''
        if self._size is None or self._md5 is None:
            debug("Check is called on payload with nothing to check")
            return True
        fileobj = PipeFile(self.path, "r")
        fileobj.consume()
        fileobj.close()
        if self._size != fileobj.read_size:
            raise ISError(u"Invalid size of payload %s" % self.name)
        if self._md5 != fileobj.md5:
            raise ISError(u"Invalid MD5 of payload %s" % self._md5)

    def download(self, dest, force=False):
        '''
        Download payload in directory
        '''
        # if dest is a directory try to create file inside
        if isdir(dest):
            dest = join(dest, self.filename)
        # try to create leading directories
        elif not exists(dirname(dest)):
            mkdir(dirname(dest))
        # check validity of dest
        if exists(dest):
            if isdir(dest):
                raise ISError(u"Destination %s is a directory" % dest)
            if not force:
                raise ISError(u"File %s already exists" % dest)
        # open remote file
        debug(u"Downloading payload %s from %s" % (self.filename, self.path))
        fs = PipeFile(self.path, progressbar=True)
        # check if announced file size is good
        if fs.size is not None and self.size != fs.size:
            raise ISError(u"Downloading payload %s failed: Invalid announced size" %
                            self.name)
        fd = open(dest, "wb")
        fs.consume(fd)
        # closing fo
        fs.close()
        fd.close()
        # checking download size
        if self.size != fs.read_size:
            raise ISError(u"Downloading payload %s failed: Invalid size" % self.name)
        if self.md5 != fs.md5:
            raise ISError(u"Downloading payload %s failed: Invalid MD5" % self.name)

    def extract(self, dest, force=False, filelist=None):
        '''
        Extract payload into dest
        filelist is a filter of file in tarball
        force will overwrite existing file if exists
        '''
        try:
            if self.isdir:
                self.extract_tar(dest, force=force, filelist=filelist)
            else:
                self.extract_file(dest, force=force)
        except Exception as e:
            raise ISError(u"Extracting payload %s failed" % self.name, e)

    def extract_tar(self, dest, force=False, filelist=None):
        '''
        Extract a payload which is a tarball.
        This is used mainly to extract payload from a directory
        '''
        # check validity of dest
        if exists(dest):
            if not isdir(dest):
                raise ISError(u"Destination %s is not a directory" % dest)
            if not force and len(listdir(dest)) > 0:
                raise ISError(u"Directory %s is not empty (need force)" % dest)
        else:
            mkdir(dest)
        # try to open payload file
        try:
            fo = PipeFile(self.path, progressbar=True)
        except Exception as e:
            raise ISError(u"Unable to open %s" % self.path)
        # check if announced file size is good
        if fo.size is not None and self.size != fo.size:
            raise ISError(u"Invalid announced size on %s" % self.path)
        # get compressor argv (first to escape file creation if not found)
        a_comp = get_compressor_path(self.compressor, compress=False)
        a_tar = ["tar", "--extract", "--numeric-owner", "--ignore-zeros",
                 "--preserve-permissions", "--directory", dest]
        # add optionnal selected filename for decompression
        if filelist is not None:
            a_tar += filelist
        p_tar = Popen(a_tar, shell=False, close_fds=True,
                      stdin=PIPE)
        p_comp = Popen(a_comp, shell=False, close_fds=True,
                       stdin=PIPE, stdout=p_tar.stdin)
        # close tar fd
        p_tar.stdin.close()
        # push data into compressor
        fo.consume(p_comp.stdin)
        # close source fd
        fo.close()
        # checking downloaded size
        if self.size != fo.read_size:
            raise ISError("Invalid size")
        # checking downloaded md5
        if self.md5 != fo.md5:
            raise ISError("Invalid MD5")
        # close compressor pipe
        p_comp.stdin.close()
        # check compressor return 0
        if p_comp.wait() != 0:
            raise ISError(u"Compressor %s return is not zero" % a_comp[0])
        # check tar return 0
        if p_tar.wait() != 0:
            raise ISError("Tar return is not zero")

    def extract_file(self, dest, force=False):
        '''
        Copy a payload directly to a file
        Check md5 on the fly
        '''
        # if dest is a directory try to create file inside
        if isdir(dest):
            dest = join(dest, self.name)
        # try to create leading directories
        elif not exists(dirname(dest)):
            mkdir(dirname(dest))
        # check validity of dest
        if exists(dest):
            if isdir(dest):
                raise ISError(u"Destination %s is a directory" % dest)
            if not force:
                raise ISError(u"File %s already exists" % dest)
        # get compressor argv (first to escape file creation if not found)
        a_comp = get_compressor_path(self.compressor, compress=False)
        # try to open payload file (source)
        try:
            f_src = PipeFile(self.path, "r", progressbar=True)
        except Exception as e:
            raise ISError(u"Unable to open payload file %s" % self.path, e)
        # check if announced file size is good
        if f_src.size is not None and self.size != f_src.size:
            raise ISError(u"Invalid announced size on %s" % self.path)
        # opening destination
        try:
            f_dst = open(dest, "wb")
        except Exception as e:
            raise ISError(u"Unable to open destination file %s" % dest, e)
        # run compressor process
        p_comp = Popen(a_comp, shell=False, close_fds=True,
                       stdin=PIPE, stdout=f_dst)
        # close destination file
        f_dst.close()
        # push data into compressor
        f_src.consume(p_comp.stdin)
        # closing source fo
        f_src.close()
        # checking download size
        if self.size != f_src.read_size:
            raise ISError("Invalid size")
        # checking downloaded md5
        if self.md5 != f_src.md5:
            raise ISError("Invalid MD5")
        # close compressor pipe
        p_comp.stdin.close()
        # check compressor return 0
        if p_comp.wait() != 0:
            raise ISError(u"Compressor %s return is not zero" % a_comp[0])
        # settings file orginal rights
        chrights(dest, self.uid, self.gid, self.mode, self.mtime)

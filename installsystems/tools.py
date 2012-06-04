# -*- python -*-
# -*- coding: utf-8 -*-

# Installsystems - Python installation framework
# Copyright © 2011-2012 Smartjog S.A
# Copyright © 2011-2012 Sébastien Luttringer
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

'''
InstallSystems Generic Tools Library
'''

import hashlib
import jinja2
import locale
import math
import os
import re
import shutil
import socket
import time
import urllib2

from subprocess import call, check_call, CalledProcessError

import installsystems
from progressbar import Widget, ProgressBar, Percentage
from progressbar import FileTransferSpeed
from progressbar import Bar, BouncingBar, ETA, UnknownLength
from installsystems.tarball import Tarball
from installsystems.printer import *


################################################################################
# Classes
################################################################################

class PipeFile(object):
    '''
    Pipe file object if a file object with extended capabilities
    like printing progress bar or compute file size, md5 on the fly
    '''

    class FileTransferSize(Widget):
        '''
        Custom progressbar widget
        Widget for showing the transfer size (useful for file transfers)
        '''

        format = '%6.2f %s%s'
        prefixes = ' kMGTPEZY'
        __slots__ = ('unit', 'format')

        def __init__(self, unit='B'):
            self.unit = unit

        def update(self, pbar):
            '''
            Updates the widget with the current SI prefixed speed
            '''
            if pbar.currval < 2e-6: # =~ 0
                scaled = power = 0
            else:
                power = int(math.log(pbar.currval, 1000))
                scaled = pbar.currval / 1000.**power
            return self.format % (scaled, self.prefixes[power], self.unit)


    def __init__(self, path=None, mode="r", fileobj=None, timeout=None,
                 progressbar=False):
        self.open(path, mode, fileobj, timeout, progressbar)

    def open(self, path=None, mode="r", fileobj=None, timeout=None, progressbar=False):
        if path is None and fileobj is None:
            raise AttributeError("You must have a path or a fileobj to open")
        if mode not in ("r", "w"):
            raise AttributeError("Invalid open mode. Must be r or w")
        self.timeout = timeout or socket.getdefaulttimeout()
        self.mode = mode
        self._md5 = hashlib.md5()
        self.size = 0
        self.mtime = None
        self.consumed_size = 0
        # we already have a fo, nothing to open
        if fileobj is not None:
            self.fo = fileobj
            # seek to 0 and compute filesize if we have and fd
            if hasattr(self.fo, "fileno"):
                self.seek(0)
                self.size = os.fstat(self.fo.fileno()).st_size
        # we need to open the path
        else:
            ftype = pathtype(path)
            if ftype == "file":
                self._open_local(path)
            elif ftype == "http":
                self._open_http(path)
            elif ftype == "ftp":
                self._open_ftp(path)
            elif ftype == "ssh":
                self._open_ssh(path)
            else:
                raise IOError("URL type not supported")
        # init progress bar
        # we use 0 because a null file is cannot show a progression during write
        if self.size == 0:
            widget = [ self.FileTransferSize(), " ",
                       BouncingBar(), " ", FileTransferSpeed() ]
            maxval = UnknownLength
        else:
            widget = [ Percentage(), " ", Bar(), " ", FileTransferSpeed(), " ", ETA() ]
            maxval = self.size
        self._progressbar = ProgressBar(widgets=widget, maxval=maxval)
        # enable displaying of progressbar
        self.progressbar = progressbar

    def _open_local(self, path):
        '''
        Open file on the local filesystem
        '''
        self.fo = open(path, self.mode)
        sta = os.fstat(self.fo.fileno())
        self.size = sta.st_size
        self.mtime = sta.st_mtime

    def _open_http(self, path):
        '''
        Open a file accross an http server
        '''
        try:
            self.fo = urllib2.urlopen(path, timeout=self.timeout)
        except Exception as e:
            # FIXME: unable to open file
            raise IOError(e)
        # get file size
        if "Content-Length" in self.fo.headers:
            self.size = int(self.fo.headers["Content-Length"])
        else:
            self.size = 0
        # get mtime
        try:
            self.mtime = int(time.mktime(time.strptime(self.fo.headers["Last-Modified"],
                                                       "%a, %d %b %Y %H:%M:%S %Z")))
        except:
            self.mtime = None

    def _open_ftp(self, path):
        '''
        Open file via ftp
        '''
        try:
            self.fo = urllib2.urlopen(path, timeout=self.timeout)
        except Exception as e:
            # FIXME: unable to open file
            raise IOError(e)
        # get file size
        try:
            self.size = int(self.fo.headers["content-length"])
        except:
            self.size = 0

    def _open_ssh(self, path):
        '''
        Open current fo from an ssh connection
        '''
        # try to load paramiko
        try:
            import paramiko
        except ImportError:
            raise IOError("URL type not supported")
        # parse url
        (login, passwd, host, port, path) = re.match(
            "ssh://(([^:]+)(:([^@]+))?@)?([^/:]+)(:(\d+))?(/.*)?", path).group(2, 4, 5, 7, 8)
        if port is None: port = 22
        if path is None: path = "/"
        # open ssh connection
        # we need to keep it inside the object unless it was cutted
        self._ssh = paramiko.SSHClient()
        self._ssh.load_system_host_keys()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._ssh.connect(host, port=port, username=login, password=passwd,
                          look_for_keys=True, timeout=self.timeout)
        # swith in sftp mode
        sftp = self._ssh.open_sftp()
        # get the file infos
        sta = sftp.stat(path)
        self.size = sta.st_size
        self.mtime = sta.st_mtime
        # open the file
        self.fo = sftp.open(path, self.mode)
        # this is needed to have correct file transfert speed
        self.fo.set_pipelined(True)

    def close(self):
        if self.progressbar:
            self._progressbar.finish()
        debug(u"MD5: %s" % self.md5)
        debug(u"Size: %s" % self.consumed_size)
        self.fo.close()

    def read(self, size=None):
        if self.mode == "w":
            raise IOError("Unable to read in w mode")
        buf = self.fo.read(size)
        length = len(buf)
        self._md5.update(buf)
        self.consumed_size += length
        if self.progressbar and length > 0:
            self._progressbar.update(self.consumed_size)
        return buf

    def flush(self):
        if hasattr(self.fo, "flush"):
            return self.fo.flush()

    def write(self, buf):
        if self.mode == "r":
            raise IOError("Unable to write in r mode")
        self.fo.write(buf)
        length = len(buf)
        self._md5.update(buf)
        self.consumed_size += length
        if self.progressbar and length > 0:
            self._progressbar.update(self.consumed_size)
        return None

    def consume(self, fo=None):
        '''
        if PipeFile is in read mode:
          Read all data from PipeFile and write it to fo
          if fo is None, data are discarded. This is useful to obtain md5 and size
        if PipeFile is in write mode:
          Read all data from fo and write it to PipeFile
        '''
        if self.mode == "w":
            if fo is None:
                raise TypeError("Unable to consume NoneType")
            while True:
                buf = fo.read(1048576) # 1MiB
                if len(buf) == 0:
                    break
                self.write(buf)
        else:
            while True:
                buf = self.read(1048576) # 1MiB
                if len(buf) == 0:
                    break
                if fo is not None:
                    fo.write(buf)

    @property
    def progressbar(self):
        '''
        Return is progressbar have been started
        '''
        return hasattr(self, "_progressbar_started")

    @progressbar.setter
    def progressbar(self, val):
        '''
        Set this property to true enable progress bar
        '''
        if installsystems.verbosity == 0:
            return
        if val == True and not hasattr(self, "_progressbar_started"):
            self._progressbar_started = True
            self._progressbar.start()

    @property
    def md5(self):
        '''
        Return the md5 of read/write of the file
        '''
        return self._md5.hexdigest()

    @property
    def read_size(self):
        '''
        Return the current read size
        '''
        return self.consumed_size

    @property
    def write_size(self):
        '''
        Return the current wrote size
        '''
        return self.consumed_size

################################################################################
# Functions
################################################################################

def smd5sum(buf):
    '''
    Compute md5 of a string
    '''
    if isinstance(buf, unicode):
        buf = buf.encode(locale.getpreferredencoding())
    m = hashlib.md5()
    m.update(buf)
    return m.hexdigest()

def mkdir(path, uid=None, gid=None, mode=None):
    '''
    Create a directory and set rights
    '''
    os.makedirs(path)
    chrights(path, uid, gid, mode)

def chrights(path, uid=None, gid=None, mode=None, mtime=None):
    '''
    Set rights on a file
    '''
    if uid is not None:
        os.chown(path, uid, -1)
    if gid is not None:
        os.chown(path, -1, gid)
    if mode is not None:
        os.chmod(path, mode)
    if mtime is not None:
        os.utime(path, (mtime, mtime))

def pathtype(path):
    '''
    Return path type. This is useful to know what kind of path is given
    '''
    if path.startswith("http://") or path.startswith("https://"):
        return "http"
    if path.startswith("ftp://") or path.startswith("ftps://"):
        return "ftp"
    elif path.startswith("ssh://"):
        return "ssh"
    else:
        return "file"

def pathsearch(name, path=None):
    '''
    Search PATH for a binary
    '''
    path = path or os.environ["PATH"]
    for d in path.split(os.pathsep):
        if os.path.exists(os.path.join(d, name)):
            return os.path.join(os.path.abspath(d), name)
    return None

def isfile(path):
    '''
    Return True if path is of type file
    '''
    return pathtype(path) == "file"

def abspath(path):
    '''
    Format a path to be absolute
    '''
    ptype = pathtype(path)
    if ptype in ("http", "ftp", "ssh"):
        return path
    elif ptype == "file":
        if path.startswith("file://"):
            path = path[len("file://"):]
        return os.path.abspath(path)
    else:
        return None

def getsize(path):
    '''
    Get size of a path. Recurse if directory
    '''
    total_sz = os.path.getsize(path)
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            for filename in dirs + files:
                filepath = os.path.join(root, filename)
                filestat = os.lstat(filepath)
                if stat.S_ISDIR(filestat.st_mode) or stat.S_ISREG(filestat.st_mode):
                    total_sz += filestat.st_size
    return total_sz

def human_size(num, unit='B'):
    '''
    Return human readable size
    '''
    prefixes = ('','Ki', 'Mi', 'Gi', 'Ti','Pi', 'Ei', 'Zi', 'Yi')
    power = int(math.log(num, 1024))
    # max is YiB
    if power >= len(prefixes):
        power = len(prefixes) - 1
    scaled = num / float(1024 ** power)
    return u"%3.1f%s%s" % (scaled, prefixes[power], unit)

def time_rfc2822(timestamp):
    '''
    Return a rfc2822 format time string from an unix timestamp
    '''
    return time.strftime("%a, %d %b %Y %H:%M:%S %z", time.gmtime(timestamp))

def guess_distro(path):
    '''
    Try to detect which distro is inside a directory
    '''
    if os.path.exists(os.path.join(path, "etc/debian_version")):
        return "debian"
    elif os.path.exists(os.path.join(path, "etc/arch-release")):
        return "archlinux"
    return None

def prepare_chroot(path, mount=True):
    '''
    Prepare a chroot environment by mounting /{proc,sys,dev,dev/pts}
    and try to guess dest os to avoid daemon launching
    '''
    # try to mount /proc /sys /dev /dev/pts /dev/shm
    if mount:
        mps = ("proc", "sys", "dev", "dev/pts", "dev/shm")
        arrow("Mounting filesystems")
        for mp in mps:
            origin =  u"/%s" % mp
            target = os.path.join(path, mp)
            if os.path.ismount(target):
                warn(u"%s is already a mountpoint, skipped" % target)
            elif os.path.ismount(origin) and os.path.isdir(target):
                arrow(u"%s -> %s" % (origin, target), 1)
                try:
                    check_call(["mount",  "--bind", origin, target], close_fds=True)
                except CalledProcessError as e:
                    warn(u"Mount failed: %s.\n" % e)
    arrow("Tricks")
    exists = os.path.exists
    join = os.path.join
    # check path is a kind of linux FHS
    if not exists(join(path, "etc")) or not exists(join(path, "usr")):
        return
    # trick resolv.conf
    try:
        resolv_path = join(path, "etc", "resolv.conf")
        resolv_backup_path = join(path, "etc", "resolv.conf.isbackup")
        resolv_trick_path = join(path, "etc", "resolv.conf.istrick")
        if (exists("/etc/resolv.conf")
            and not exists(resolv_backup_path)
            and not exists(resolv_trick_path)):
            arrow("resolv.conf", 1)
            if exists(resolv_path):
                os.rename(resolv_path, resolv_backup_path)
            else:
                open(resolv_trick_path, "wb")
            shutil.copy("/etc/resolv.conf", resolv_path)
    except Exception as e:
        warn(u"resolv.conf tricks fail: %s" % e)
    # trick mtab
    try:
        mtab_path = join(path, "etc", "mtab")
        mtab_backup_path = join(path, "etc", "mtab.isbackup")
        mtab_trick_path = join(path, "etc", "mtab.istrick")
        if not exists(mtab_backup_path) and not exists(mtab_trick_path):
            arrow("mtab", 1)
            if os.path.exists(mtab_path):
                os.rename(mtab_path, mtab_backup_path)
            os.symlink("/proc/self/mounts", mtab_path)
    except Exception as e:
        warn(u"mtab tricks fail: %s" % e)
    # try to guest distro
    distro = guess_distro(path)
    # in case of debian disable policy
    if distro == "debian":
        arrow("Debian specific", 1)
        # create a chroot header
        try: open(join(path, "etc", "debian_chroot"), "w").write("CHROOT")
        except: pass
        # fake policy-rc.d. It must exit 101, it's an expected exitcode.
        policy_path = join(path, "usr", "sbin", "policy-rc.d")
        try: open(policy_path, "w").write("#!/bin/bash\nexit 101\n")
        except: pass
        # policy-rc.d needs to be executable
        chrights(policy_path, mode=0755)

def unprepare_chroot(path, mount=True):
    '''
    Rollback preparation of a chroot environment inside a directory
    '''
    arrow("Untricks")
    exists = os.path.exists
    join = os.path.join
    # check path is a kind of linux FHS
    if exists(os.path.join(path, "etc")) and exists(os.path.join(path, "usr")):
        # untrick mtab
        mtab_path = join(path, "etc", "mtab")
        mtab_backup_path = join(path, "etc", "mtab.isbackup")
        mtab_trick_path = join(path, "etc", "mtab.istrick")
        if exists(mtab_backup_path) or exists(mtab_trick_path):
            arrow("mtab", 1)
            # order matter !
            if exists(mtab_trick_path):
                try: os.unlink(mtab_path)
                except OSError: pass
                try:
                    os.unlink(mtab_trick_path)
                except OSError:
                    warn(u"Unable to remove %s" % mtab_trick_path)
            if exists(mtab_backup_path):
                try: os.unlink(mtab_path)
                except OSError: pass
                try:
                    os.rename(mtab_backup_path, mtab_path)
                except OSError:
                    warn(u"Unable to restore %s" % mtab_backup_path)

        # untrick resolv.conf
        resolv_path = join(path, "etc", "resolv.conf")
        resolv_backup_path = join(path, "etc", "resolv.conf.isbackup")
        resolv_trick_path = join(path, "etc", "resolv.conf.istrick")
        if exists(resolv_backup_path) or exists(resolv_trick_path):
            arrow("resolv.conf", 1)
            # order matter !
            if exists(resolv_trick_path):
                try: os.unlink(resolv_path)
                except OSError: pass
                try:
                    os.unlink(resolv_trick_path)
                except OSError:
                    warn(u"Unable to remove %s" % resolv_trick_path)
            if exists(resolv_backup_path):
                try: os.unlink(resolv_path)
                except OSError: pass
                try:
                    os.rename(resolv_backup_path, resolv_path)
                except OSError:
                    warn(u"Unable to restore %s" % resolv_backup_path)
        # try to guest distro
        distro = guess_distro(path)
        # cleaning debian stuff
        if distro == "debian":
            arrow("Debian specific", 1)
            for f in ("etc/debian_chroot", "usr/sbin/policy-rc.d"):
                try: os.unlink(join(path, f))
                except: pass
    # unmounting
    if mount:
        mps = ("proc", "sys", "dev", "dev/pts", "dev/shm")
        arrow("Unmounting filesystems")
        for mp in reversed(mps):
            target = join(path, mp)
            if os.path.ismount(target):
                arrow(target, 1)
                call(["umount", target], close_fds=True)

def chroot(path, shell="/bin/bash", mount=True):
    '''
    Chroot inside a directory and call shell
    if mount is true, mount /{proc,dev,sys} inside the chroot
    '''
    # prepare to chroot
    prepare_chroot(path, mount)
    # chrooting
    arrow(u"Chrooting inside %s and running %s" % (path, shell))
    call(["chroot", path, shell], close_fds=True)
    # revert preparation of chroot
    unprepare_chroot(path, mount)

def is_version(version):
    '''
    Check if version is valid
    '''
    if re.match("^(\d+)(?:([-~+]).*)?$", version) is None:
        raise TypeError(u"Invalid version format %s" % buf)

def compare_versions(v1, v2):
    '''
    This function compare version :param v1: and version :param v2:
    Compare v1 and v2
    return > 0 if v1 > v2
    return < 0 if v2 > v1
    return = 0 if v1 == v2
    '''

    def get_ver(version):
        '''Return float version'''
        if type(version) is int or type(version) is float:
            return float(version)
        elif isinstance(version, basestring):
            iv = re.match("^(\d+)(?:([-~+]).*)?$", version)
            if iv is None:
                raise TypeError(u"Invalid version format: %s" % version)
            rv = float(iv.group(1))
            if iv.group(2) == "~":
                rv -= 0.1
            else:
                rv += 0.1
            return rv
        else:
            raise TypeError(u"Invalid version format: %s" % version)

    fv1 = get_ver(v1)
    fv2 = get_ver(v2)
    return fv1 - fv2

def get_compressor_path(name, compress=True, level=None):
    '''
    Return better compressor argv from its generic compressor name
    e.g: bzip2 can return pbzip2 if available or bzip2 if not
    '''
    compressors = {"gzip": [["gzip", "--no-name", "--stdout"]],
                   "bzip2": [["pbzip2", "--stdout"],
                             ["bzip2", "--compress", "--stdout"]],
                   "xz": [["xz", "--compress", "--stdout"]]}
    decompressors = {"gzip": [["gzip", "--decompress", "--stdout"]],
                     "bzip2": [["pbzip2","--decompress", "--stdout"],
                               ["bzip2", "--decompress", "--stdout"]],
                     "xz": [["xz", "--decompress", "--stdout"]]}
    # no compress level for decompression
    if not compress:
        level = None
    allcompressors = compressors if compress else decompressors
    # check compressor exists
    if name not in allcompressors.keys():
        raise Exception(u"Invalid compressor name: %s" % name)
    # get valid compressors
    for compressor in allcompressors[name]:
        path = pathsearch(compressor[0])
        if path is None:
            continue
        if level is not None:
            compressor.append("-%d" % level)
        return compressor
    raise Exception(u"No external decompressor for %s" % name)

def render_templates(target, context, tpl_ext=".istpl", force=False, keep=False):
    '''
    Render templates according to tpl_ext
    Apply template mode/uid/gid to the generated file
    '''
    for path in os.walk(target):
        for filename in path[2]:
            name, ext = os.path.splitext(filename)
            if ext == tpl_ext:
                tpl_path = os.path.join(path[0], filename)
                file_path = os.path.join(path[0], name)
                arrow(tpl_path)
                if os.path.exists(file_path) and not force:
                    raise Exception(u"%s will be overwritten, cancel template "
                                    "generation (set force=True if you know "
                                    "what you do)" % file_path)
                try:
                    with open(tpl_path) as tpl_file:
                        template = jinja2.Template(tpl_file.read())
                        with open(file_path, "w") as rendered_file:
                            rendered_file.write(template.render(context))
                except Exception as e:
                    raise Exception(u"Render template fail: %s" % e)
                st = os.stat(tpl_path)
                os.chown(file_path, st.st_uid, st.st_gid)
                os.chmod(file_path, st.st_mode)
                if not keep:
                    os.unlink(tpl_path)

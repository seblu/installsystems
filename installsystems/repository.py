# -*- python -*-
# -*- coding: utf-8 -*-
# Started 10/05/2011 by Seblu <seblu@seblu.net>

'''
Repository stuff
'''

import os
import time
import shutil
import pwd
import grp
import copy
import tempfile
import installsystems
import installsystems.tools as istools
from installsystems.printer import *
from installsystems.tarball import Tarball
from installsystems.image import Image, PackageImage
from installsystems.database import Database

class Repository(object):
    '''
    Repository class
    '''

    def __init__(self, config):
        self.config = config
        self.db = Database(config.dbpath)

    @classmethod
    def create(cls, config):
        '''Create an empty base repository'''
        # check local repository
        if istools.pathtype(config.path) != "file":
            raise NotImplementedError("Repository creation must be local")
        # create base directories
        arrow("Creating base directories")
        arrowlevel(1)
        # creating local directory
        try:
            if os.path.exists(config.path):
                arrow("%s already exists" % config.path)
            else:
                istools.mkdir(config.path, config.uid, config.gid, config.dmod)
                arrow("%s directory created" % config.path)
        except Exception as e:
            raise Exception("Unable to create directory %s: %s" % (config.path, e))
        arrowlevel(-1)
        # create database
        dbpath = os.path.join(config.path, config.dbname)
        d = Database.create(dbpath)
        istools.chrights(dbpath, uid=config.uid, gid=config.gid, mode=config.fmod)
        # create last file
        self = cls(config)
        self.update_last()
        return self

    def update_last(self):
        '''Update last file to current time'''
        # check local repository
        if istools.pathtype(self.config.path) != "file":
            raise NotImplementedError("Repository addition must be local")
        try:
            arrow("Updating last file")
            last_path = os.path.join(self.config.path, self.config.lastname)
            open(last_path, "w").write("%s\n" % int(time.time()))
            istools.chrights(last_path, self.config.uid, self.config.gid, self.config.fmod)
        except Exception as e:
            raise Exception("Update last file failed: %s" % e)

    def last(self):
        '''Return the last value'''
        try:
            last_path = os.path.join(config.path, config.lastname)
            return int(istools.uopen(last_path, "r").read().rstrip())
        except Exception as e:
            raise Exception("Read last file failed: %s" % e)
        return 0

    def add(self, image):
        '''Add a packaged image to repository'''
        # check local repository
        if istools.pathtype(self.config.path) != "file":
            raise NotImplementedError("Repository addition must be local")
        # checking data tarballs md5 before copy
        image.check("Check image and payload before copy")
        # adding file to repository
        arrow("Copying images and payload")
        arrowlevel(1)
        for obj in [ image ] + image.payload.values():
            dest = os.path.join(self.config.path, obj.md5)
            basesrc = os.path.basename(obj.path)
            if os.path.exists(dest):
                arrow("Skipping %s: already exists" % basesrc)
            else:
                arrow("Adding %s (%s)" % (basesrc, obj.md5))
                istools.copy(obj.path, dest,
                             self.config.uid, self.config.gid, self.config.fmod)
        arrowlevel(-1)
        # copy is done. create a image inside repo
        r_image = PackageImage(os.path.join(self.config.path, image.md5),
                                 md5name=True)
        # checking must be done with original md5
        r_image.md5 = image.md5
        # checking image and payload after copy
        r_image.check("Check image and payload after copy")
        # add description to db
        self.db.add(r_image)
        # update last file
        self.update_last()

    def delete(self, name, version):
        '''Delete an image from repository'''
        raise NotImplementedError()
        # check local repository
        if istools.pathtype(self.config.path) != "file":
            raise NotImplementedError("Repository deletion must be local")
        desc = self.db.find(name, version)
        if desc is None:
            error("Unable to find %s version %s in database" % (name, version))
        # removing script tarballs
        arrow("Removing script tarball")
        arrowlevel(1)
        tpath = os.path.join(self.config.path,
                             "%s-%s%s" % (name, version, Image.extension))
        if os.path.exists(tpath):
            os.unlink(tpath)
            arrow("%s removed" % os.path.basename(tpath))
        arrowlevel(1)
        # removing data tarballs
        arrow("Removing data tarballs")
        arrowlevel(1)
        for tb in self.db.databalls(name, version):
            tpath = os.path.join(self.config.data, tb)
            if os.path.exists(tpath):
                os.unlink(tpath)
                arrow("%s removed" % tb)
        arrowlevel(-1)
        # removing metadata
        self.db.delete(name, version)
        # update last file
        arrow("Updating last file")
        self.update_last()

    def has(self, name, version):
        return self.db.ask("select name,version from image where name = ? and version = ? limit 1", (name,version)).fetchone() is not None

    def get(self, name, version):
        '''return a image from a name and version of pakage'''
        # get file md5 from db
        r = self.db.ask("select md5 from image where name = ? and version = ? limit 1",
                        (name,version)).fetchone()
        if r is None:
            raise Exception("No such image %s version %s" % name, version)
        path = os.path.join(self.config.path, r[0])
        debug("Getting %s v%s from %s" % (name, version, path))
        return PackageImage(path, md5name=True)

    def last(self, name):
        '''Return last version of name in repo or -1 if not found'''
        r = self.db.ask("select version from image where name = ? order by version desc limit 1", (name,)).fetchone()
        # no row => no way
        if r is None:
            return -1
        # return last
        return r[0]


class RepositoryConfig(object):
    '''Repository configuration container'''

    def __init__(self, name, **kwargs):
        # set default value for arguments
        self.name = name
        self.path = ""
        self._dbpath = None
        self.dbname = "db"
        self._lastpath = None
        self.lastname = "last"
        self._uid = os.getuid()
        self._gid = os.getgid()
        umask = os.umask(0)
        os.umask(umask)
        self._fmod =  0666 & ~umask
        self._dmod =  0777 & ~umask
        self.update(**kwargs)

    def __str__(self):
        l = []
        for a in ("name", "path", "dbpath", "lastpath", "uid", "gid", "fmod", "dmod"):
            l.append("%s: %s" % (a, getattr(self, a)))
        return os.linesep.join(l)

    def __eq__(self, other):
        return vars(self) == vars(other)

    def __ne__(self, other):
        return not (self == other)

    def __contains__(self, key):
        return key in self.__dict__

    @property
    def lastpath(self):
        """return the last file complete path"""
        if self._lastpath is None:
            return os.path.join(self.path, self.lastname)
        return self._lastpath

    @lastpath.setter
    def lastpath(self, value):
        '''Set last path'''
        self._lastpath = value

    @property
    def dbpath(self):
        """return the db complete path"""
        if self._dbpath is None:
            return os.path.join(self.path, self.dbname)
        return self._dbpath

    @dbpath.setter
    def dbpath(self, value):
        '''Set db path'''
        # dbpath must be local, sqlite3 requirment
        if istools.pathtype(value) != "file":
            raise ValueError("Database path must be local")
        self._dbpath = os.path.abspath(value)

    @property
    def uid(self):
        '''Return owner of repository'''
        return self._uid

    @uid.setter
    def uid(self, value):
        '''Define user name owning repository'''
        if not value.isdigit():
            self._uid = pwd.getpwnam(value).pw_uid
        else:
            self._uid = int(value)

    @property
    def gid(self):
        '''Return group of the repository'''
        return self._gid

    @gid.setter
    def gid(self, value):
        '''Define group owning repository'''
        if not value.isdigit():
            self._gid = grp.getgrnam(value).gr_gid
        else:
            self._gid = int(value)

    @property
    def fmod(self):
        '''Return new file mode'''
        return self._fmod

    @fmod.setter
    def fmod(self, value):
        '''Define new file mode'''
        if value.isdigit():
            self._fmod = int(value, 8)
        else:
            raise ValueError("File mode must be an integer")

    @property
    def dmod(self):
        '''Return new directory mode'''
        return self._dmod

    @dmod.setter
    def dmod(self, value):
        '''Define new directory mode'''
        if value.isdigit():
            self._dmod = int(value, 8)
        else:
            raise ValueError("Directory mode must be an integer")

    def update(self, *args, **kwargs):
        '''Update attribute with checking value
        All attribute must already exists
        '''
        # autoset parameter in cmdline
        for k in kwargs:
            if hasattr(self, k):
                try:
                    setattr(self, k, kwargs[k])
                except Exception as e:
                    warn("Unable to set config parameter %s in repository %s: %s" % (k, self.name, e))
            else:
                debug("No such repository parameter: %s" % k)


class RepositoryManager(object):
    '''
    Manage multiple repostories

    This call implement a cache and a manager for multiple repositories
    '''

    def __init__(self, cache_path=None, timeout=None):
        self.timeout = 3 if timeout is None else timeout
        self.repos = []
        self.tempfiles = []
        if cache_path is None:
            self.cache_path = None
            debug("No repository cache")
        else:
            if istools.pathtype(cache_path) != "file":
                raise NotImplementedError("Repository cache must be local")
            self.cache_path =  os.path.abspath(cache_path)
            # must_path is a list of directory which must exists
            # create directory if not exists
            if not os.path.exists(self.cache_path):
                os.mkdir(self.cache_path)
            # ensure directories are avaiblable
            if not os.access(self.cache_path, os.W_OK | os.X_OK):
                raise Exception("%s is not writable or executable" % t_path)
            debug("Repository cache is in %s" % self.cache_path)

    def __del__(self):
        # delete temporary files (used by db)
        for f in self.tempfiles:
            try:
                debug("Removing %s" % f)
                os.unlink(f)
            except OSError:
                pass

    def register(self, config):
        '''Register a repository from its config'''
        debug("Registering repository %s (%s)" % (config.path, config.name))
        # find destination file and load last info
        if config.name is None or self.cache_path is None:
            # this is a forced temporary repository or without name repo
            tempfd, filedest = tempfile.mkstemp()
            os.close(tempfd)
            self.tempfiles.append(filedest)
        else:
            filedest = os.path.join(self.cache_path, config.name)
            # create file if not exists
            if not os.path.exists(filedest):
                open(filedest, "wb")
        # get remote last value
        rlast = int(istools.uopen(config.lastpath).read().strip())
        # get local last value
        llast = int(os.stat(filedest).st_mtime)
        # if repo is out of date, download it
        if rlast != llast:
            arrow("Getting %s" % config.dbpath)
            istools.copy(config.dbpath, filedest,
                         uid=config.uid,
                         gid=config.gid,
                         mode=config.fmod,
                         timeout=self.timeout)
            os.utime(filedest, (rlast, rlast))
        config.dbpath = filedest
        self.repos.append(Repository(config))

    def get(self, name, version=None):
        '''Crawl all repo to get the most recent image'''
        # search last version if needed
        if version is None:
            lv = -1
            for repo in self.repos:
                lv = max(lv, repo.last(name))
            if lv < 0:
                raise Exception("Unable to find last version of %s" % name)
            version = lv
        # search image in repos
        for repo in self.repos:
            if repo.has(name, version):
                return repo.get(name, version)
        raise Exception("Unable to find %s v%s" % (name, version))

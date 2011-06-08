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
import installsystems
import installsystems.tools as istools
from installsystems.printer import *
from installsystems.tarball import Tarball
from installsystems.image import Image, PackageImage
from installsystems.database import Database

class Repository(object):
    '''Repository class'''

    def __init__(self, config, verbose=True):
        self.verbose = verbose
        self.config = config
        self.db = Database(os.path.join(config.path, config.dbname), verbose=self.verbose)

    @classmethod
    def create(cls, config, verbose=True):
        '''Create an empty base repository'''
        # check local repository
        if istools.pathtype(config.path) != "file":
            raise NotImplementedError("Repository creation must be local")
        # create base directories
        arrow("Creating base directories", 1, verbose)
        # creating local directory
        try:
            if os.path.exists(config.path):
                arrow("%s already exists" % config.path, 2, verbose)
            else:
                istools.mkdir(config.path, config.chown, config.chgroup, config.dchmod)
                arrow("%s directory created" % config.path, 2, verbose)
        except Exception as e:
            raise Exception("Unable to create directory %s: %s" % (config.path, e))
        # create database
        dbpath = os.path.join(config.path, config.dbname)
        d = Database.create(dbpath, verbose=verbose)
        istools.chrights(dbpath, config.chown, config.chgroup, config.fchmod)
        # create last file
        arrow("Creating last file", 1, verbose)
        self = cls(config, verbose)
        self.update_last()
        return self

    def update_last(self):
        '''Update last file to current time'''
        # check local repository
        if istools.pathtype(self.config.path) != "file":
            raise NotImplementedError("Repository addition must be local")
        try:
            arrow("Updating last file", 1, self.verbose)
            last_path = os.path.join(self.config.path, self.config.lastname)
            open(last_path, "w").write("%s\n" % int(time.time()))
            os.chown(last_path, self.config.chown, self.config.chgroup)
            os.chmod(last_path, self.config.fchmod)
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

    def add(self, package):
        '''Add a packaged image to repository'''
        # check local repository
        if istools.pathtype(self.config.path) != "file":
            raise NotImplementedError("Repository addition must be local")
        # copy file to directory
        arrow("MD5summing tarballs", 1, self.verbose)
        # build dict of file to add
        filelist = dict()
        # script tarball
        arrow(package.filename, 2, self.verbose)
        filelist[package.md5] = package.path
        # data tarballs
        datas = package.datas
        for dt in datas:
            dt_path = datas[dt]["path"]
            old_md5 = datas[dt]["md5"]
            arrow(os.path.relpath(dt_path), 2, self.verbose)
            md5 = istools.md5sum(dt_path)
            if md5 != old_md5:
                raise Exception("MD5 mismatch on %s" % dt_path)
            filelist[md5] = dt_path
        # adding file to repository
        arrow("Adding files to directory", 1, self.verbose)
        for md5 in filelist:
            dest = os.path.join(self.config.path, md5)
            source = filelist[md5]
            if os.path.exists(dest):
                arrow("Skipping %s: already exists" % (os.path.basename(source)),
                      2, self.verbose)
            else:
                arrow("Adding %s (%s)" % (os.path.basename(source), md5), 2, self.verbose)
                istools.copy(source, dest,
                             self.config.chown, self.config.chgroup, self.config.fchmod)
        # add description to db
        self.db.add(package)
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
        arrow("Removing script tarball", 1, self.verbose)
        tpath = os.path.join(self.config.path,
                             "%s-%s%s" % (name, version, Image.extension))
        if os.path.exists(tpath):
            os.unlink(tpath)
            arrow("%s removed" % os.path.basename(tpath), 2, self.verbose)
        # removing data tarballs
        arrow("Removing data tarballs", 1, self.verbose)
        for tb in self.db.databalls(name, version):
            tpath = os.path.join(self.config.data, tb)
            if os.path.exists(tpath):
                os.unlink(tpath)
                arrow("%s removed" % tb, 2, self.verbose)
        # removing metadata
        self.db.delete(name, version)
        # update last file
        arrow("Updating last file", 1, self.verbose)
        self.update_last()

    def get(self, name, version):
        '''return a package from a name and version of pakage'''
        desc = self.db.get(name, version)
        p = PackageImage(os.path.join(self.config.path, desc["md5"]), verbose=self.verbose)
        if p.md5 != desc["md5"]:
            raise Exception("Invalid package MD5")
        return p

class RepositoryConfig(object):
    '''Repository configuration container'''

    def __init__(self, *args, **kwargs):
        # set default value for arguments
        self.name = args[0]
        self.dbname = "db"
        self.lastname = "last"
        self.path = ""
        self.chown = os.getuid()
        self.chgroup = os.getgid()
        umask = os.umask(0)
        os.umask(umask)
        self.fchmod =  0666 & ~umask
        self.dchmod =  0777 & ~umask
        self.update(**kwargs)

    def update(self, *args, **kwargs):
        '''Update attribute with checking value
        All attribute must already exists
        '''
        # autoset parameter in cmdline
        for k in kwargs:
            if hasattr(self, k):
                # attribute which are not in the following list cannot be loaded
                # from configuration
                try:
                    # convert userid
                    if k == "chown":
                        if not k.isdigit():
                            kwargs[k] = pwd.getpwnam(kwargs[k]).pw_uid
                        setattr(self, k, int(kwargs[k]))
                    # convert gid
                    elif k == "chgroup":
                        if not k.isdigit():
                            kwargs[k] = grp.getgrnam(kwargs[k]).gr_gid
                        setattr(self, k, int(kwargs[k]))
                    # convert file mode
                    elif k in ("fchmod", "dchmod"):
                        setattr(self, k, int(kwargs[k], 8))
                        # convert repo path
                    elif k in ("image", "data"):
                        setattr(self, k, istools.abspath(kwargs[k]))
                    # else is string
                    else:
                        setattr(self, k, kwargs[k])
                except Exception as e:
                    warn("Unable to set config parameter %s in repository %s: %s" % (k, self.name, e))

    def __eq__(self, other):
        return vars(self) == vars(other)

    def __ne__(self, other):
        return not (self == other)

    def __contains__(self, key):
        return key in self.__dict__

class RepositoryManager(object):
    '''Manage multiple repostories'''

    def __init__(self, timeout=None, verbose=True):
        self.verbose = verbose
        self.timeout = 3 if timeout is None else timeout
        self.repos = {}

    def register(self, configs):
        '''Register a list of repository from its config'''
        for conf in configs:
            self.repos[conf.name] = Repository(conf, self.verbose)

    def find_image(self, name, version):
        '''Find a repository containing image'''
        if version is None:
            arrow("Serching last version of %s" % name, 1, self.verbose)
        else:
            arrow("Serching %s version %s " % (name, version), 1, self.verbose)
        img = None
        # search in all repositories
        desc = None
        for repo in self.repos:
            desc = self.repos[repo].db.find(name, version)
            if desc is not None:
                # \o/
                break
        if desc is None:
            arrow("Not found", 2, self.verbose)
            if version is None:
                error("Unable to find a version of image %s" % name)
            else:
                error("Unable to find image %s version %s" % (name, version))
        arrow("Found %s version %s " % (desc["name"], desc["version"]), 2, self.verbose)
        return (desc, self.repos[repo])

    def get(self, name, version=None):
        '''Return a package object from local cache'''
        # find an image name/version in repository
        (desc, repo) = self.find_image(name, version)
        # get pkg object
        return repo.get(desc["name"], desc["version"])

class RepositoryCache(object):
    '''Local repository cache class'''

    def __init__(self, cache_path, timeout=3, verbose=True):
        self.verbose = verbose
        self.timeout = timeout
        self.repos = {}
        self.path = os.path.abspath(cache_path)
        # ensure cache directories are avaiblable
        if not os.path.exists(self.path):
            os.mkdir(self.path)
        if not os.access(self.path, os.W_OK | os.X_OK):
            raise Exception("%s is not writable or executable" % path)
        debug("Repository cache is in %s" % self.path)

    def register(self, configs):
        '''Register a list of repository from its config'''
        for conf in configs:
            self.repos[conf.name] = {}
            # keep original repository conf
            self.repos[conf.name]["orig"] = Repository(conf, self.verbose)
            # change configuration to make remote repository in cache
            cconf = copy.copy(conf)
            cconf.image = os.path.join(self.path, conf.name)
            cconf.data = "/dev/null"
            self.repos[conf.name]["cache"] = Repository(cconf, self.verbose)
            # create a local directory
            if not os.path.exists(cconf.image):
                os.mkdir(cconf.image)

    def update(self):
        '''Update cache info'''
        arrow("Updating repositories", 1, self.verbose)
        for r in self.repos:
            # last local
            local_last = self.last(r)
            # copy last file
            arrow("Checking %s repository last" % r, 2, self.verbose)
            istools.copy(self.repos[r]["orig"].last_path,
                         self.repos[r]["cache"].last_path, timeout=self.timeout)
            # last after update
            remote_last = self.last(r)
            debug("%s: last: local: %s, remote:%s" % (r, local_last, remote_last))
            # Updating db?
            remote_db = self.repos[r]["orig"].db.path
            local_db = self.repos[r]["cache"].db.path
            if remote_last > local_last or not os.path.exists(local_db):
                # copy db file
                arrow("Copying %s repository db" % r, 2, self.verbose)
                istools.copy(remote_db, local_db, timeout=self.timeout)

    def last(self, reponame):
        '''Return the last timestamp of a repo'''
        last_path = os.path.join(self.path, reponame, "last")
        try:
            return int(open(last_path, "r").read().rstrip())
        except Exception:
            return 0

    def get_image(self, reponame, imagename, imageversion):
        '''Obtain a local path in cache for a remote image in repo'''
        arrow("Getting image", 1, self.verbose)
        filename = "%s-%s%s" % (imagename, imageversion, Image.image_extension)
        cachepath = os.path.join(self.repos[reponame]["cache"].config.image, filename)
        # return db path if exists
        if os.path.exists(cachepath):
            arrow("Found in cache", 2, self.verbose)
        else:
            # get remote image
            remotepath = os.path.join(self.repos[reponame]["orig"].config.image, filename)
            arrow("Copying from repository", 2, self.verbose)
            istools.copy(remotepath, cachepath, timeout=self.timeout)
        return cachepath

    def find_image(self, name, version):
        '''Find an image in repositories'''
        if version is None:
            arrow("Serching last version of %s" % name, 1, self.verbose)
        else:
            arrow("Serching %s version %s " % (name, version), 1, self.verbose)
        img = None
        # search in all repositories
        for repo in self.repos:
            tempdb = Database(self.repos[repo]["cache"].db.path, False)
            img = tempdb.find(name, version)
            if img is not None:
                # \o/
                break
        if img is None:
            arrow("Not found", 2, self.verbose)
            if version is None:
                error("Unable to find a version of image %s" % name)
            else:
                error("Unable to find image %s version %s" % (name, version))
        arrow("Found %s version %s " % (img[0], img[1]), 2, self.verbose)
        return (repo, img[0], img[1])

    def get(self, name, version=None):
        '''Return a package object from local cache'''
        r, n, v = self.find_image(name, version)
        # download image if not in cache
        path = self.get_image(r, n, v)
        # create an object image
        return PackageImage(path, self.verbose)

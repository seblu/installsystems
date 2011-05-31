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
        self.db = Database(os.path.join(config.image, config.db), verbose=self.verbose)
        self.last_path = os.path.join(config.image, config.last)

    @classmethod
    def create(cls, config, verbose=True):
        '''Create an empty base repository'''
        # create base directories
        arrow("Creating base directories", 1, verbose)
        for d in (config.image, config.data):
            try:
                if os.path.exists(d):
                    arrow("%s already exists" % d, 2, verbose)
                else:
                    istools.mkdir(d, config.chown, config.chgroup, config.dchmod)
                    arrow("%s directory created" % d, 2, verbose)
            except Exception as e:
                raise
                raise Exception("Unable to create directory %s: %s" % (d, e))
        # create database
        dbpath = os.path.join(config.image, "db")
        d = Database.create(dbpath, verbose=verbose)
        istools.chrights(dbpath, config.chown, config.chgroup, config.fchmod)
        # create last file
        arrow("Creating last file", 1, verbose)
        self = cls(config, verbose)
        self.update_last()
        return self

    def update_last(self):
        '''Update last file to current time'''
        try:
            open(self.last_path, "w").write("%s\n" % int(time.time()))
            os.chown(self.last_path, self.config.chown, self.config.chgroup)
            os.chmod(self.last_path, self.config.fchmod)
        except Exception as e:
            raise Exception("Update last file failed: %s" % e)

    def last(self):
        '''Return the last value'''
        try:
            return int(open(self.last_path, "r").read().rstrip())
        except Exception as e:
            raise Exception("Read last file failed: %s" % e)
        return 0

    def add(self, package):
        '''Add a packaged image to repository'''
        # copy file to directory
        arrow("Adding file to directories", 1, self.verbose)
        arrow("Adding %s" % os.path.relpath(package.path), 2, self.verbose)
        istools.copy(package.path, self.config.image,
                     self.config.chown, self.config.chgroup, self.config.fchmod)
        for db in package.databalls:
            arrow("Adding %s" % os.path.basename(db), 2, self.verbose)
            istools.copy(db, self.config.data,
                         self.config.chown, self.config.chgroup, self.config.fchmod)
        # add file to db
        self.db.add(package)
        # update last file
        arrow("Updating last file", 1, self.verbose)
        self.update_last()

    def delete(self, name, version):
        '''Delete an image from repository'''
        if self.db.find(name, version) is None:
            error("Unable to find %s version %s in database" % (name, version))
        # removing script tarballs
        arrow("Removing script tarball", 1, self.verbose)
        tpath = os.path.join(self.config.image,
                             "%s-%s%s" % (name, version, Image.image_extension))
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


class RepositoryConfig(object):
    '''Repository configuration container'''

    def __init__(self, *args, **kwargs):
        # set default value for arguments
        self.name = args[0]
        self.db = "db"
        self.last = "last"
        self.image = ""
        self.data = ""
        self.chown = os.getuid()
        self.chgroup = os.getgid()
        umask = os.umask(0)
        os.umask(umask)
        self.fchmod =  0666 & ~umask
        self.dchmod =  0777 & ~umask
        self.update(**kwargs)

    def update(self, *args, **kwargs):
        '''
        Update attribute with checking value
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


class RepositoryCache(object):
    '''Local repository cache class'''

    def __init__(self, cache_path, verbose=True):
        self.verbose = verbose
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
            arrow("Copying %s repository last" % r, 2, self.verbose)
            istools.copy(self.repos[r]["orig"].last_path,
                         self.repos[r]["cache"].last_path,)
            # last after update
            remote_last = self.last(r)
            debug("%s: last: local: %s, remote:%s" % (r, local_last, remote_last))
            # Updating db?
            remote_db = self.repos[r]["orig"].db.path
            local_db = self.repos[r]["cache"].db.path
            if remote_last > local_last or not os.path.exists(local_db):
                # copy db file
                arrow("Copying %s repository db" % r, 2, self.verbose)
                istools.copy(remote_db, local_db)
                arrow("%s updated" % r, 2, self.verbose)

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
            istools.copy(remotepath, cachepath)
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

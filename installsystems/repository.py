# -*- python -*-
# -*- coding: utf-8 -*-
# Started 10/05/2011 by Seblu <seblu@seblu.net>

'''
Repository stuff
'''

import os
import time
import shutil
import json
import installsystems
import installsystems.tools as istools
from installsystems.printer import *
from installsystems.tarball import Tarball
from installsystems.image import Image, PackageImage
from installsystems.database import Database

class Repository(object):
    '''Repository class'''

    last_name = "last"

    def __init__(self, image_path, data_path, verbose=True):
        self.image_path = os.path.abspath(image_path)
        self.last_path = os.path.join(image_path, self.last_name)
        self.data_path = os.path.abspath(data_path)
        self.verbose = verbose
        self.db = Database(os.path.join(image_path, "db"), verbose=self.verbose)

    @classmethod
    def create(cls, image_path, data_path, verbose=True):
        '''Create an empty base repository'''
        # create base directories
        arrow("Creating base directories", 1, verbose)
        try:
            for d in (image_path, data_path):
                if os.path.exists(d):
                    arrow("%s already exists" % os.path.relpath(d), 2, verbose)
                else:
                    os.mkdir(d)
                    arrow("%s directory created" % os.path.relpath(d), 2, verbose)
        except Exception as e:
            raise Exception("Unable to create directory %s: %s" % (d, e))
        # create database
        d = Database.create(os.path.join(image_path, "db"), verbose=verbose)
        # create last file
        arrow("Creating last file", 1, verbose)
        self = cls(image_path, data_path, verbose)
        self.update_last()

    def update_last(self):
        '''Update last file to current time'''
        try:
            open(self.last_path, "w").write("%s\n" % int(time.time()))
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
        arrow("Adding %s" % os.path.basename(package.path), 2, self.verbose)
        shutil.copy(package.path, self.image_path)
        for db in package.databalls():
            arrow("Adding %s" % os.path.basename(db), 2, self.verbose)
            shutil.copy(db, self.data_path)
        # add file to db
        self.db.add(package)
        # update last file
        arrow("Updating last file", 1, self.verbose)
        self.update_last()

    def delete(self, name, version):
        '''Delete an image from repository'''
        name = "%s-%s" % (name, version)
        fname = "%s.json" % name
        # FIXME: check tarball exists before doing this
        tbs = self.tarballs(name)
        # removing metadata
        self.db.delete(name, version)
        # removing tarballs
        arrow("Removing tarballs", 1, self.verbose)
        for tb in tbs:
            arrow("Removing %s" % os.path.basename(tb), 2, self.verbose)
            os.unlink(tb)
        # update last file
        arrow("Updating last file", 1, self.verbose)
        self.update_last()

    def tarballs(self, name):
        '''List all tarballs (script + data)'''
        ts = list()
        # add script tarballs
        ts.append(os.path.abspath(os.path.join(self.image_path,
                                               "%s%s" % (name, Image.image_extension))))
        tempdb = Tarball.open(self.db_path, mode='r:bz2')
        jdesc = json.loads(tempdb.get_str("%s.json" % name))
        for dt in jdesc["data"]:
            ts.append(os.path.abspath(os.path.join(self.data_path, dt)))
        return ts


class RepositoryCache(object):
    '''Local repository cache class'''

    def __init__(self, cache_path, verbose=True):
        self.base_path = os.path.abspath(cache_path)
        self.image_path = os.path.join(self.base_path, "image")
        self.last_path = os.path.join(self.base_path, "last")
        self.db_path = os.path.join(self.base_path, "db")
        for path in (self.base_path, self.image_path, self.last_path, self.db_path):
            if not os.path.exists(path):
                os.mkdir(path)
            if not os.access(path, os.W_OK | os.X_OK):
                raise Exception("%s is not writable or executable" % path)
        self.verbose = verbose
        self.repos = dict()

    def register(self, name, image, data):
        '''Register a repository to track'''
        self.repos[name] = Repository(istools.complete_path(image),
                                      istools.complete_path(data),
                                      verbose=self.verbose)

    def update(self):
        '''Update cache info'''
        arrow("Updating repositories", 1, self.verbose)
        for r in self.repos:
            debug("%s: remote_last: %s, local_last:%s" % (r,
                                                           self.repos[r].last(),
                                                           self.last(r)))
            if self.repos[r].last() > self.last(r):
                # copy last file
                istools.cp(self.repos[r].last_path, os.path.join(self.last_path, r))
                # copy db file
                istools.cp(self.repos[r].db.path, os.path.join(self.db_path, r))
                arrow("%s updated" % r, 2, self.verbose)

    def last(self, reponame):
        '''Return the last timestamp of a repo'''
        last_path = os.path.join(self.last_path, reponame)
        if os.path.exists(last_path):
            return int(open(last_path, "r").read().rstrip())
        return 0

    def get_image(self, reponame, imagename, imageversion):
        '''Obtain a local path in cache for a remote image in repo'''
        arrow("Getting image", 1, self.verbose)
        filename = "%s-%s%s" % (imagename, imageversion, Image.image_extension)
        localpath = os.path.join(self.image_path, filename)
        # return db path if exists
        if os.path.exists(localpath):
            arrow("Found in cache", 2, self.verbose)
            return localpath
        # get remote image
        remotepath = os.path.join(self.repos[reponame].image_path, filename)
        arrow("Copying from repository", 2, self.verbose)
        istools.cp(remotepath, localpath)
        return localpath

    def find_image(self, name, version):
        '''Find an image in repositories'''
        if version is None:
            arrow("Serching last version of %s" % name, 1, self.verbose)
        else:
            arrow("Serching %s version %s " % (name, version), 1, self.verbose)
        img = None
        # search in all repositories
        for repo in self.repos:
            tempdb = Database(os.path.join(self.db_path, repo), False)
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

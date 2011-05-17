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
import installsystems.printer as p
import installsystems.tarball as tar
import installsystems.image as image

class Repository(object):
    '''Repository class'''

    db_name = "db.tar.bz2"
    last_name = "last"
    repo_format = "1"

    def __init__(self, image_path, data_path, verbose=True, create=False):
        '''Create an existant repository'''
        self.image_path = os.path.abspath(image_path)
        self.db_path = os.path.join(image_path, Repository.db_name)
        self.last_path = os.path.join(image_path, Repository.last_name)
        self.data_path = os.path.abspath(data_path)
        self.verbose = verbose
        if create:
            self.create()

    def create(self):
        '''Create an empty base repository'''
        # create base directories
        p.arrow("Creating base directories", 1, self.verbose)
        try:
            for d in (self.image_path, self.data_path):
                if os.path.exists(d):
                    p.arrow("%s already exists" % os.path.relpath(d), 2, self.verbose)
                else:
                    os.mkdir(d)
                    p.arrow("%s directory created" % os.path.relpath(d), 2, self.verbose)
        except Exception as e:
            raise Exception("Unable to create directory %s: %s" % (d, e))
        # create database
        p.arrow("Creating repository database", 1, self.verbose)
        if os.path.exists(self.db_path):
            raise Exception("db already exists")
        try:
            tarball = tar.Tarball.open(self.db_path, mode="w:bz2", dereference=True)
            tarball.add_str("format", Repository.repo_format, tar.tarfile.REGTYPE, 0444)
            tarball.close()
        except Exception as e:
            raise Exception("Create database failed: %s" % e)
        # create last file
        p.arrow("Creating last file", 1, self.verbose)
        self.update_last()

    def update_last(self):
        '''Update last file to current time'''
        try:
            open(self.last_path, "w").write("%s\n" % int(time.time()))
        except Exception as e:
            raise Exception("Update last file failed: %s" % e)

    def tarballs(self, name):
        '''List all tarballs (script + data)'''
        ts = list()
        # add script tarballs
        ts.append(os.path.abspath(os.path.join(self.image_path,
                                               "%s%s" % (name, image.image_extension))))
        db = tar.Tarball.open(self.db_path, mode='r:bz2')
        jdesc = json.loads(db.get_str("%s.json" % name))
        for dt in jdesc["data"]:
            ts.append(os.path.abspath(os.path.join(self.data_path, dt)))
        return ts

    def add(self, package):
        '''Add a packaged image to repository'''
        # copy file to directory
        p.arrow("Adding file to directories", 1, self.verbose)
        p.arrow("Adding %s" % os.path.basename(package.path), 2, self.verbose)
        shutil.copy(package.path, self.image_path)
        for db in package.databalls():
            p.arrow("Adding %s" % os.path.basename(db), 2, self.verbose)
            shutil.copy(db, self.data_path)
        # add file to db
        p.arrow("Adding metadata to db", 1, self.verbose)
        name = "%s.json" % package.name()
        newdb_path = "%s.new" % self.db_path
        try:
            db = tar.Tarball.open(self.db_path, mode='r:bz2')
            newdb = tar.Tarball.open(newdb_path, mode='w:bz2')
            for ti in db.getmembers():
                if ti.name != name:
                    newdb.addfile(ti, db.extractfile(ti))
            newdb.add_str(name, package.jdescription(), tar.tarfile.REGTYPE, 0444)
            db.close()
            newdb.close()
            shutil.move(newdb_path, self.db_path)
        except Exception as e:
            raise Exception("Adding metadata fail: %s" % e)
        # update last file
        p.arrow("Updating last file", 1, self.verbose)
        self.update_last()

    def delete(self, name, version):
        '''Delete an image from repository'''
        name = "%s-%s" % (name, version)
        fname = "%s.json" % name
        # FIXME: check tarball exists before doing this
        tbs = self.tarballs(name)
        # removing metadata
        p.arrow("Removing metadata from db", 1, self.verbose)
        newdb_path = "%s.new" % self.db_path
        try:
            db = tar.Tarball.open(self.db_path, mode='r:bz2')
            newdb = tar.Tarball.open(newdb_path, mode='w:bz2')
            for ti in db.getmembers():
                if ti.name != fname:
                    newdb.addfile(ti, db.extractfile(ti))
            db.close()
            newdb.close()
            shutil.move(newdb_path, self.db_path)
        except Exception as e:
            raise Exception("Removing metadata fail: %s" % e)
        # removing tarballs
        p.arrow("Removing tarballs", 1, self.verbose)
        for tb in tbs:
            p.arrow("Removing %s" % os.path.basename(tb), 2, self.verbose)
            os.unlink(tb)
        # update last file
        p.arrow("Updating last file", 1, self.verbose)
        self.update_last()

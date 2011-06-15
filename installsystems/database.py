# -*- python -*-
# -*- coding: utf-8 -*-
# Started 24/05/2011 by Seblu <seblu@seblu.net>

'''
Database stuff
'''

import json
import os
import shutil
import tarfile
import cStringIO
import installsystems.tools as istools
from installsystems.tarball import Tarball
from installsystems.printer import *

class Database(object):
    '''Abstract repo database stuff'''

    db_format = "1"

    @classmethod
    def create(cls, path, verbose=True):
        arrow("Creating repository database", 1, verbose)
        # check locality
        if istools.pathtype(path) != "file":
            raise NotImplementedError("Database creation must be local")
        dbpath = istools.abspath(path)
        if os.path.exists(dbpath):
            raise Exception("Database already exists. Remove it before")
        try:
            tarball = Tarball.open(dbpath, mode="w:gz", dereference=True)
            tarball.add_str("format", Database.db_format, tarfile.REGTYPE, 0444)
            tarball.close()
        except Exception as e:
            raise Exception("Create database failed: %s" % e)
        return cls(path, verbose)

    def __init__(self, path, verbose=True):
        self.path = istools.abspath(path)
        self.verbose = verbose
        # load db in memory
        self.file = cStringIO.StringIO()
        shutil.copyfileobj(istools.uopen(self.path), self.file)

    def get(self, name, version):
        '''Return a description dict from a package name'''
        # parse tarball
        try:
            self.file.seek(0)
            tarball = Tarball.open(fileobj=self.file, mode="r:gz")
            rdata = tarball.get_str("%s-%s" % (name, version))
            tarball.close()
        except KeyError:
            raise Exception("No package %s version %s in metadata" % (name, version))
        except Exception as e:
            raise Exception("Unable to read db %s version %s: e" % (name, version, e))
        # convert loaded data into dict (json parser)
        try:
            return json.loads(rdata)
        except Exception as e:
            raise Exception("Invalid metadata in package %s version %s: e" % (name, version, e))

    def add(self, package):
        '''Add a packaged image to a db'''
        arrow("Adding metadata to db", 1, self.verbose)
        # check locality
        if istools.pathtype(self.path) != "file":
            raise NotImplementedError("Database addition must be local")
        # naming
        newdb_path = "%s.new" % self.path
        # compute md5
        arrow("Formating metadata", 2, self.verbose)
        desc = package.description
        desc["md5"] = package.md5
        jdesc = json.dumps(desc)
        try:
            arrow("Adding metadata", 2, self.verbose)
            self.file.seek(0)
            newfile = cStringIO.StringIO()
            db = Tarball.open(fileobj=self.file, mode='r:gz')
            newdb = Tarball.open(fileobj=newfile, mode='w:gz')
            for ti in db.getmembers():
                if ti.name != package.id:
                    newdb.addfile(ti, db.extractfile(ti))
            newdb.add_str(package.id, jdesc, tarfile.REGTYPE, 0644)
            db.close()
            newdb.close()
            # writing to disk
            arrow("Writing to disk", 2, self.verbose)
            self.file.close()
            self.file = newfile
            self.write()
        except Exception as e:
            raise Exception("Adding metadata fail: %s" % e)

    def delete(self, name, version):
        '''Delete a packaged image'''
        arrow("Removing metadata from db", 1, self.verbose)
        # check locality
        if istools.pathtype(self.path) != "file":
            raise NotImplementedError("Database deletion must be local")
        newdb_path = "%s.new" % self.path
        fname = "%s-%s.json" % (name, version)
        try:
            db = Tarball.open(self.path, mode='r:gz')
            newdb = Tarball.open(newdb_path, mode='w:gz')
            for ti in db.getmembers():
                if ti.name != fname:
                    newdb.addfile(ti, db.extractfile(ti))
            db.close()
            newdb.close()
            # preserve permission and stats when moving
            shutil.copystat(self.path, newdb_path)
            os.rename(newdb_path, self.path)
        except Exception as e:
            raise Exception("Removing metadata fail: %s" % e)

    def databalls(self, name, version):
        '''List data tarballs filenames'''
        try:
            self.file.seek(0)
            db = Tarball.open(fileobj=self.file, mode='r:gz')
            jdesc = json.loads(db.get_str("%s-%s.json" % (name, version)))
            db.close()
            return jdesc["data"]
        except Exception as e:
            raise Exception("List data tarballs fail: %s" % e)

    def find(self, name, version=None):
        '''Find last version of an image'''
        try:
            self.file.seek(0)
            tarb = Tarball.open(fileobj=self.file, mode='r:gz')
            candidates = [ int((os.path.splitext(tpname)[0]).rsplit("-", 1)[1])
                           for tpname in tarb.getnames("%s-\d+" % name) ]
            tarb.close()
        except Exception as e:
            raise Exception("Find in db %s fail: %s" % (self.path, e))
        # no candidates => go west
        if len(candidates) == 0:
            return None
        # get last version
        if version is None:
            version = max(candidates)
        # check if version exists
        if int(version) not in candidates:
            return None
        return self.get(name, version)

    def write(self):
        '''Write current dabatase into its file'''
        if istools.pathtype(self.path) != "file":
            raise NotImplementedError("Database writing must be local")
        try:
            dest = open(self.path, "w")
            self.file.seek(0)
            shutil.copyfileobj(self.file, dest)
        except Exception as e:
            raise Exception("Unable to write database: %s" % e)

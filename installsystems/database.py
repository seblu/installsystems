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
import installsystems.tools as istools
from installsystems.tarball import Tarball
from installsystems.printer import *

class Database(object):
    '''Abstract repo database stuff'''

    db_format = "1"

    @classmethod
    def create(cls, path, verbose=True):
        arrow("Creating repository database", 1, verbose)
        dbpath = os.path.abspath(path)
        if os.path.exists(dbpath):
            raise Exception("db already exists")
        try:
            tarball = Tarball.open(dbpath, mode="w:bz2", dereference=True)
            tarball.add_str("format", Database.db_format, tarfile.REGTYPE, 0444)
            tarball.close()
        except Exception as e:
            raise Exception("Create database failed: %s" % e)
        return cls(path, verbose)

    def __init__(self, path, verbose=True):
        self.path = os.path.abspath(path)
        self.verbose = verbose

    def add(self, package):
        '''Add a packaged image to a db'''
        arrow("Adding metadata to db", 1, self.verbose)
        # naming
        name = "%s.json" % package.name
        newdb_path = "%s.new" % self.path
        # compute md5
        arrow("Compute MD5 of %s" % os.path.relpath(package.path), 2, self.verbose)
        md5 = package.md5
        arrow("Formating metadata", 2, self.verbose)
        desc = package.description
        desc["md5"] = md5
        jdesc = json.dumps(desc)
        try:
            arrow("Adding to tarball", 2, self.verbose)
            db = Tarball.open(self.path, mode='r:bz2')
            newdb = Tarball.open(newdb_path, mode='w:bz2')
            for ti in db.getmembers():
                if ti.name != name:
                    newdb.addfile(ti, db.extractfile(ti))
            newdb.add_str(name, jdesc, tarfile.REGTYPE, 0444)
            db.close()
            newdb.close()
            # preserve permission and stats when moving
            shutil.copystat(self.path, newdb_path)
            os.rename(newdb_path, self.path)
        except Exception as e:
            raise Exception("Adding metadata fail: %s" % e)

    def delete(self, name, version):
        '''Deltete a packaged image'''
        arrow("Removing metadata from db", 1, self.verbose)
        newdb_path = "%s.new" % self.path
        fname = "%s-%s.json" % (name, version)
        try:
            db = Tarball.open(self.path, mode='r:bz2')
            newdb = Tarball.open(newdb_path, mode='w:bz2')
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
            db = Tarball.open(self.path, mode='r:bz2')
            jdesc = json.loads(db.get_str("%s-%s.json" % (name, version)))
            db.close()
            return jdesc["data"]
        except Exception as e:
            raise Exception("Listing data tarballs fail: %s" % e)

    def find(self, name, version=None):
        '''Find last version of an image'''
        try:
            tarb = Tarball.open(self.path, mode='r:bz2')
            candidates = [ int((os.path.splitext(tpname)[0]).rsplit("-", 1)[1])
                           for tpname in tarb.getnames("%s-\d+.json" % name) ]
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
        return (name, version)

# -*- python -*-
# -*- coding: utf-8 -*-
# Started 24/05/2011 by Seblu <seblu@seblu.net>

'''
Database stuff
'''

import json
import os
import shutil
import cStringIO
import sqlite3
import installsystems.tools as istools
import installsystems.template as istemplate
from installsystems.tarball import Tarball
from installsystems.printer import *

class Database(object):
    '''  Abstract repo database stuff
    It needs to be local cause of sqlite3 which need to open a file
    '''

    db_format = "1"

    @classmethod
    def create(cls, path, verbose=True):
        arrow("Creating repository database", 1, verbose)
        # check locality
        if istools.pathtype(path) != "file":
            raise NotImplementedError("Database creation must be local")
        path = os.path.abspath(path)
        if os.path.exists(path):
            raise Exception("Database already exists. Remove it before")
        try:
            conn = sqlite3.connect(path, isolation_level=None)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(istemplate.createdb)
            conn.commit()
            conn.close()
        except Exception as e:
            raise Exception("Create database failed: %s" % e)
        return cls(path, verbose)

    def __init__(self, path, verbose=True):
        # check locality
        if istools.pathtype(path) != "file":
            raise NotImplementedError("Database creation must be local")
        self.path = os.path.abspath(path)
        self.verbose = verbose
        self.conn = sqlite3.connect(self.path, isolation_level=None)
        self.conn.execute("PRAGMA foreign_keys = ON")

    def get(self, name, version):
        '''Return a description dict from a image name'''
        # parse tarball
        try:
            self.file.seek(0)
            tarball = Tarball.open(fileobj=self.file, mode="r:gz")
            rdata = tarball.get_str("%s-%s" % (name, version))
            tarball.close()
        except KeyError:
            raise Exception("No image %s version %s in metadata" % (name, version))
        except Exception as e:
            raise Exception("Unable to read db %s version %s: %s" % (name, version, e))
        # convert loaded data into dict (json parser)
        try:
            return json.loads(rdata)
        except Exception as e:
            raise Exception("Invalid metadata in image %s version %s: e" % (name, version, e))

    def ask(self, sql, args=()):
        '''Ask question to db'''
        return self.conn.execute(sql, args)

    def add(self, image):
        '''Add a packaged image to a db'''
        try:
            # let's go
            arrow("Begin transaction to db", 1, self.verbose)
            self.conn.execute("BEGIN TRANSACTION")
            # insert image information
            arrow("Add image metadata", 2, self.verbose)
            self.conn.execute("INSERT OR REPLACE INTO image values (?,?,?,?,?,?,?)",
                              (image.md5,
                               image.name,
                               image.version,
                               image.date,
                               image.author,
                               image.description,
                               image.size,
                               ))
            # insert data informations
            arrow("Add payload metadata", 2, self.verbose)
            for name, obj in image.payload.items():
                self.conn.execute("INSERT OR REPLACE INTO payload values (?,?,?,?,?)",
                                  (obj.md5,
                                   image.md5,
                                   name,
                                   obj.isdir,
                                   obj.size,
                                   ))
            # on commit
            arrow("Commit transaction to db", 1, self.verbose)
            self.conn.execute("COMMIT TRANSACTION")
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
